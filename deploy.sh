#!/bin/zsh
# ═══════════════════════════════════════════════════════════════════════════════
# OpenClaw Army — Unified Deployment Script
# Usage: ./deploy.sh [install|start|stop|status|health|restart|logs]
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

ARMY_HOME="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ARMY_HOME/.env"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# ── Constants ─────────────────────────────────────────────────────────────────
AGENTS_DIR="$ARMY_HOME/agents"
SERVICES_DIR="$ARMY_HOME/services"
EXTENSIONS_DIR="$ARMY_HOME/extensions"
DATA_DIR="$ARMY_HOME/data"
LOG_DIR="$DATA_DIR/logs"
PID_DIR="$DATA_DIR"
NODE_BIN="/opt/homebrew/opt/node@22/bin/node"
if [[ ! -x "$NODE_BIN" ]]; then
    NODE_BIN="node"
fi
OPENCLAW_NODE_MAX_OLD_SPACE="${OPENCLAW_NODE_MAX_OLD_SPACE:-2048}"
OPENCLAW_CLI_ENTRY="${OPENCLAW_CLI_ENTRY:-$ARMY_HOME/openclaw.mjs}"
if [[ ! -f "$OPENCLAW_CLI_ENTRY" ]]; then
    OPENCLAW_CLI_ENTRY="$HOME/openclaw-core/openclaw.mjs"
fi
OPENCLAW_CLI="$NODE_BIN --max-old-space-size=$OPENCLAW_NODE_MAX_OLD_SPACE --expose-gc $OPENCLAW_CLI_ENTRY"

# Ensure required dependencies are in PATH (PostgreSQL, Redis, OpenClaw Node modules)
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql@17/bin:$HOME/.npm-global/bin:$PATH"
if [[ -x "$HOME/Library/pnpm/pnpm" ]]; then
    export PATH="$HOME/Library/pnpm:$PATH"
fi

# Resolve newest usable Python when no venv is active.
_resolve_python() {
    local candidates=(
        "python3.13"
        "python3.12"
        "python3.11"
        "python3.10"
        "python3"
    )
    local candidate
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

_resolve_agent_config_path() {
    local agent_dir="$1"
    local config_path="$agent_dir/openclaw.json"
    if [[ -f "$config_path" ]]; then
        echo "$config_path"
        return 0
    fi
    config_path="$agent_dir/.openclaw/openclaw.json"
    if [[ -f "$config_path" ]]; then
        echo "$config_path"
        return 0
    fi
    return 1
}

_pid_on_port() {
    local port="$1"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

_read_pidfile() {
    local pidfile="$1"
    [[ -f "$pidfile" ]] || return 1
    local pid
    pid="$(<"$pidfile" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    echo "$pid"
}

_is_port_listening() {
    local port="$1"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

_pid_listens_on_port() {
    local pid="$1"
    local port="$2"
    lsof -nP -a -p "$pid" -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

_wait_for_port_listener() {
    local port="$1"
    local attempts="${2:-25}"
    local sleep_s="${3:-0.2}"
    local i
    for ((i = 0; i < attempts; i++)); do
        local pid="$(_pid_on_port "$port" || true)"
        if [[ -n "$pid" ]]; then
            echo "$pid"
            return 0
        fi
        sleep "$sleep_s"
    done
    return 1
}

_wait_for_port_free() {
    local port="$1"
    local attempts="${2:-25}"
    local sleep_s="${3:-0.2}"
    local i
    for ((i = 0; i < attempts; i++)); do
        if ! _is_port_listening "$port"; then
            return 0
        fi
        sleep "$sleep_s"
    done
    return 1
}

_ensure_agent_config() {
    local name="$1"
    local port="$2"
    local agent_dir="$3"
    local config_path=""
    if config_path="$(_resolve_agent_config_path "$agent_dir")"; then
        "$PYTHON" - "$config_path" "$name" "$agent_dir" "$port" <<'PY'
import json, pathlib, sys
cfg_path = pathlib.Path(sys.argv[1])
name = sys.argv[2]
workspace = sys.argv[3]
port = int(sys.argv[4])
cfg = json.loads(cfg_path.read_text())
assistant = cfg.setdefault("ui", {}).setdefault("assistant", {})
assistant["name"] = name
assistant["avatar"] = name
cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = workspace
gateway = cfg.setdefault("gateway", {})
gateway["port"] = port
gateway["mode"] = "local"
gateway.setdefault("bind", "loopback")
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
PY
        echo "$config_path"
        return 0
    fi

    local template=""
    local candidate
    for candidate in \
        "$AGENTS_DIR/$name/.openclaw/openclaw.json" \
        "$AGENTS_DIR/$name/openclaw.json" \
        "$AGENTS_DIR/alpha-manager/.openclaw/openclaw.json" \
        "$AGENTS_DIR/alpha-manager/openclaw.json" \
        "$AGENTS_DIR/beta-manager/.openclaw/openclaw.json" \
        "$AGENTS_DIR/beta-manager/openclaw.json" \
        "$AGENTS_DIR/main/.openclaw/openclaw.json" \
        "$AGENTS_DIR/main/openclaw.json"; do
        if [[ -f "$candidate" ]]; then
            template="$candidate"
            break
        fi
    done
    if [[ -z "$template" ]]; then
        local agent_root
        for agent_root in "$AGENTS_DIR"/*(N/); do
            for candidate in "$agent_root/openclaw.json" "$agent_root/.openclaw/openclaw.json"; do
                if [[ -f "$candidate" ]]; then
                    template="$candidate"
                    break 2
                fi
            done
        done
    fi
    if [[ -z "$template" ]]; then
        return 1
    fi

    mkdir -p "$agent_dir"
    config_path="$agent_dir/openclaw.json"
    cp "$template" "$config_path"
    "$PYTHON" - "$config_path" "$name" "$agent_dir" "$port" <<'PY'
import json, pathlib, sys
cfg_path = pathlib.Path(sys.argv[1])
name = sys.argv[2]
workspace = sys.argv[3]
port = int(sys.argv[4])
cfg = json.loads(cfg_path.read_text())
assistant = cfg.setdefault("ui", {}).setdefault("assistant", {})
assistant["name"] = name
assistant["avatar"] = name
cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = workspace
gateway = cfg.setdefault("gateway", {})
gateway["port"] = port
gateway["mode"] = "local"
gateway.setdefault("bind", "loopback")
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
PY
    echo "$config_path"
    return 0
}

PYTHON="$(_resolve_python || true)"
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: No supported Python found (tried python3.13, python3.12, python3.11, python3.10, python3)" >&2
    exit 1
fi

# Use virtual environment if available
if [[ -f "$ARMY_HOME/.venv/bin/activate" ]]; then
    source "$ARMY_HOME/.venv/bin/activate"
    PYTHON="$ARMY_HOME/.venv/bin/python"
fi

if ! "$PYTHON" -c 'import uvicorn' >/dev/null 2>&1; then
    log_err "Python interpreter '$PYTHON' is missing uvicorn. Run: $PYTHON -m pip install -r services/orchestrator-api/requirements.txt"
    exit 1
fi

# Agent definitions: name:port:model_env_key
AGENT_DEFS=(
 # King AI (supreme orchestrator)
 "main:${KING_PORT:-18789}:NVAPI_KIMI_KEY_1"
 
 # Alpha Dept: Writing, General
 "alpha-manager:${ALPHA_PORT:-18800}:NVAPI_KIMI_KEY_2"
 "general-worker:${GENERAL_1_PORT:-18810}:NVAPI_DEEPSEEK_KEY_5"
 
 # Beta Dept: Software Engineering
 "beta-manager:${BETA_PORT:-18801}:NVAPI_DEEPSEEK_KEY_1"
 "coding-worker:${CODING_1_PORT:-18811}:NVAPI_DEEPSEEK_KEY_3"
 
 # Gamma Dept: Research & Analysis
 "gamma-manager:${GAMMA_PORT:-18802}:NVAPI_KIMI_KEY_2"
 "research-worker:${AGENTIC_1_PORT:-18812}:NVAPI_GLM5_KEY_1"

 # Delta Dept: Marketing & Growth
 "delta-manager:${DELTA_PORT:-18803}:NVAPI_KIMI_KEY_1"
 "marketing-worker:${MARKETING_1_PORT:-18813}:NVAPI_DEEPSEEK_KEY_2"

 # Epsilon Dept: Product & UX
 "epsilon-manager:${EPSILON_PORT:-18804}:NVAPI_KIMI_KEY_2"
 "product-worker:${PRODUCT_1_PORT:-18814}:NVAPI_DEEPSEEK_KEY_1"

 # Zeta Dept: Infrastructure & DevOps
 "zeta-manager:${ZETA_PORT:-18805}:NVAPI_KIMI_KEY_1"
 "infra-worker:${INFRA_1_PORT:-18815}:NVAPI_DEEPSEEK_KEY_5"

 # Eta Dept: Legal & Compliance
 "eta-manager:${ETA_PORT:-18806}:NVAPI_KIMI_KEY_2"
 "legal-worker:${LEGAL_1_PORT:-18816}:NVAPI_DEEPSEEK_KEY_7"
)
# Service definitions: name:port:command
SERVICE_DEFS=(
    "memory-service:${MEMORY_SERVICE_PORT:-18820}:$PYTHON -m uvicorn main:app --host 127.0.0.1 --port ${MEMORY_SERVICE_PORT:-18820}"
    "orchestrator-api:${ORCHESTRATOR_API_PORT:-18830}:$PYTHON run_dualstack.py ${ORCHESTRATOR_API_PORT:-18830}"
    "ralph:${RALPH_PORT:-18840}:$PYTHON -m uvicorn ralph:app --host 127.0.0.1 --port ${RALPH_PORT:-18840}"
    "knowledge-bridge:${KNOWLEDGE_BRIDGE_PORT:-18850}:$PYTHON -m uvicorn main:app --host 127.0.0.1 --port ${KNOWLEDGE_BRIDGE_PORT:-18850}"
    "agent-registry:${AGENT_REGISTRY_PORT:-18860}:$PYTHON -m uvicorn main:app --host 127.0.0.1 --port ${AGENT_REGISTRY_PORT:-18860}"
    "notification:${NOTIFICATION_PORT:-18870}:$PYTHON -m uvicorn main:app --host 127.0.0.1 --port ${NOTIFICATION_PORT:-18870}"
)

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log_info()  { echo "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo "${YELLOW}[WARN]${NC}  $1"; }
log_err()   { echo "${RED}[ERROR]${NC} $1"; }
log_head()  { echo "\n${BOLD}${CYAN}══ $1 ══${NC}\n"; }

# ═══════════════════════════════════════════════════════════════════════════════
# INSTALL
# ═══════════════════════════════════════════════════════════════════════════════
cmd_install() {
    log_head "Installing OpenClaw Army Dependencies"

    # Homebrew check
    if ! command -v brew &>/dev/null; then
        log_err "Homebrew not found. Install from https://brew.sh"
        exit 1
    fi

    # PostgreSQL
    if ! brew list postgresql@17 &>/dev/null 2>&1; then
        log_info "Installing PostgreSQL 17..."
        brew install postgresql@17
    else
        log_ok "PostgreSQL 17 already installed"
    fi

    # Redis
    if ! brew list redis &>/dev/null 2>&1; then
        log_info "Installing Redis..."
        brew install redis
    else
        log_ok "Redis already installed"
    fi

    # Start services
    log_info "Starting PostgreSQL and Redis..."
    brew services start postgresql@17 2>/dev/null || true
    brew services start redis 2>/dev/null || true
    sleep 2

    # Create database and user
    log_info "Setting up database..."
    if psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "${POSTGRES_DB:-openclaw_army}"; then
        log_ok "Database '${POSTGRES_DB:-openclaw_army}' already exists"
    else
        createuser "${POSTGRES_USER:-openclaw}" 2>/dev/null || true
        createdb "${POSTGRES_DB:-openclaw_army}" -O "${POSTGRES_USER:-openclaw}" 2>/dev/null || true
        psql -d "${POSTGRES_DB:-openclaw_army}" -c "ALTER USER ${POSTGRES_USER:-openclaw} WITH PASSWORD '${POSTGRES_PASSWORD:-openclaw}';" 2>/dev/null || true
        log_ok "Database created: ${POSTGRES_DB:-openclaw_army}"
    fi

    # Run migrations
    log_info "Running database migrations..."
    psql -d "${POSTGRES_DB:-openclaw_army}" -f "$ARMY_HOME/scripts/setup-database.sql" 2>/dev/null
    log_ok "Database schema applied"

    # Python packages
    log_info "Installing Python packages..."
    $PYTHON -m pip install --quiet --upgrade \
        fastapi uvicorn asyncpg redis chromadb \
        pydantic pydantic-settings httpx websockets \
        sentence-transformers aiofiles aiohttp 2>/dev/null || {
        log_warn "Some Python packages may need manual install"
    }
    log_ok "Python packages installed"

    # Verify OpenClaw
    if command -v openclaw &>/dev/null; then
        log_ok "OpenClaw binary found: $(which openclaw)"
    else
        log_err "OpenClaw binary not found in PATH"
    fi

    # Create data directories
    mkdir -p "$DATA_DIR"/{chroma,ralph,logs}
    mkdir -p "$PID_DIR"/pids

    log_head "Installation Complete"
    echo "  Next: ./deploy.sh start"
}

# ═══════════════════════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════════════════════
cmd_start() {
    log_head "Starting OpenClaw Army"
    mkdir -p "$LOG_DIR" "$PID_DIR/pids"

    # 1. Check infrastructure
    _check_infra_or_start
    _ensure_orchestrator_desktop

    # 2. Start Python services
    _start_services

    # 3. Start all agents
    _start_agents

    # 4. Build and install Mac app (optional on server-only restart loops)
    if [[ "${SKIP_APP_BUILD:-0}" == "1" ]]; then
        log_info "Skipping Mac App build (SKIP_APP_BUILD=1)"
    else
        _build_mac_app
    fi

    log_head "All Systems Online"
    cmd_status
}

_check_infra_or_start() {
    log_info "Checking infrastructure..."

    # PostgreSQL
    if pg_isready -q 2>/dev/null; then
        log_ok "PostgreSQL running"
    else
        log_info "Starting PostgreSQL..."
        brew services start postgresql@17 2>/dev/null || true
        sleep 2
        if pg_isready -q 2>/dev/null; then
            log_ok "PostgreSQL started"
        else
            log_err "PostgreSQL failed to start"
            exit 1
        fi
    fi

    # Redis
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        log_ok "Redis running"
    else
        log_info "Starting Redis..."
        brew services start redis 2>/dev/null || true
        sleep 1
        if redis-cli ping 2>/dev/null | grep -q PONG; then
            log_ok "Redis started"
        else
            log_err "Redis failed to start"
            exit 1
        fi
    fi
}

_ensure_orchestrator_desktop() {
    local container="${ORCH_DESKTOP_CONTAINER:-orchestrator-desktop}"
    if ! command -v docker >/dev/null 2>&1; then
        log_warn "Docker CLI not found; isolated virtual desktop unavailable"
        return 0
    fi
    if ! docker info >/dev/null 2>&1; then
        log_warn "Docker daemon is not running; isolated virtual desktop unavailable"
        return 0
    fi
    local running
    running="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)"
    if [[ "$running" == "true" ]]; then
        local current_vnc_pw
        current_vnc_pw="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$container" 2>/dev/null | awk -F= '$1=="VNC_PW"{print $2; exit}')"
        local expected_vnc_pw="${ORCH_DESKTOP_VNC_PW:-openclaw}"
        if [[ -n "$current_vnc_pw" && "$current_vnc_pw" != "$expected_vnc_pw" ]]; then
            log_warn "Virtual desktop password drift detected; recreating $container"
            docker rm -f "$container" >/dev/null 2>&1 || true
            running="false"
        fi
    fi
    if [[ "$running" == "true" ]]; then
        log_ok "Virtual desktop container ready ($container)"
        return 0
    fi
    if docker inspect "$container" >/dev/null 2>&1; then
        if docker start "$container" >/dev/null 2>&1; then
            log_ok "Virtual desktop container started ($container)"
            return 0
        fi
    fi
    log_info "Starting isolated virtual desktop container ($container)..."
    if docker run -d --name "$container" \
        -p 5901:5901 -p 6901:6901 \
        -e VNC_PW="${ORCH_DESKTOP_VNC_PW:-openclaw}" \
        --shm-size=2g \
        consol/ubuntu-xfce-vnc:latest >/dev/null 2>&1; then
        log_ok "Virtual desktop container created ($container)"
    else
        log_warn "Could not create $container; Gemini desktop automation may fail until Docker image is available"
    fi
}

_start_services() {
    for sdef in "${SERVICE_DEFS[@]}"; do
        local name="${sdef%%:*}"
        local rest="${sdef#*:}"
        local port="${rest%%:*}"
        local cmd="${rest#*:}"
        local pidfile="$PID_DIR/pids/${name}.pid"
        local logfile="$LOG_DIR/${name}.log"

        # Check if already running
        local tracked_pid=""
        tracked_pid="$(_read_pidfile "$pidfile" || true)"
        if [[ -n "$tracked_pid" ]] && kill -0 "$tracked_pid" 2>/dev/null; then
            local pid="$tracked_pid"
            if curl -sf --max-time 2 "http://localhost:$port/health" >/dev/null 2>&1; then
                log_ok "$name already running (PID $pid)"
                continue
            fi
            log_warn "$name PID $pid is stale/unhealthy; restarting"
            kill -TERM "$pid" 2>/dev/null || true
            rm -f "$pidfile"
            sleep 1
        fi
        local existing_pid="$(_pid_on_port "$port" || true)"
        if [[ -n "$existing_pid" ]]; then
            if curl -sf --max-time 2 "http://localhost:$port/health" >/dev/null 2>&1; then
                echo "$existing_pid" > "$pidfile"
                log_ok "$name already running (PID $existing_pid)"
                continue
            fi
            log_warn "$name port $port occupied by PID $existing_pid; reclaiming port"
            kill -TERM "$existing_pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$existing_pid" 2>/dev/null; then
                kill -9 "$existing_pid" 2>/dev/null || true
            fi
        fi

        log_info "Starting $name on port $port..."
        cd "$SERVICES_DIR/$name"

        # Source .env in the service context
        eval "env ARMY_HOME=\"$ARMY_HOME\" \
        POSTGRES_URL=\"${POSTGRES_URL:-postgresql://openclaw:openclaw@localhost:5432/openclaw_army}\" \
        REDIS_URL=\"${REDIS_URL:-redis://localhost:6379/0}\" \
        CHROMA_PATH=\"$DATA_DIR/chroma\" \
        VAULT_PATH=\"$ARMY_HOME/data/obsidian database\" \
        GEMINI_API_KEY=\"${GEMINI_API_KEY:-}\" \
        NVIDIA_API_KEY=\"${NVIDIA_API_KEY:-}\" \
        ORCH_TASK_REQUIRE_ISOLATED_DESKTOP=\"${ORCH_TASK_REQUIRE_ISOLATED_DESKTOP:-1}\" \
        ORCH_DESKTOP_CONTROL_DISABLED=\"${ORCH_DESKTOP_CONTROL_DISABLED:-1}\" \
        ORCH_BROWSER_HEADLESS=\"${ORCH_BROWSER_HEADLESS:-1}\" \
        ORCH_CHAT_TIMEOUT_SECONDS=\"${ORCH_CHAT_TIMEOUT_SECONDS:-600}\" \
        ORCH_CHAT_LONG_TIMEOUT_SECONDS=\"${ORCH_CHAT_LONG_TIMEOUT_SECONDS:-1800}\" \
        ORCH_CHAT_IDLE_TIMEOUT_SECONDS=\"${ORCH_CHAT_IDLE_TIMEOUT_SECONDS:-180}\" \
        ORCH_CHAT_LONG_IDLE_TIMEOUT_SECONDS=\"${ORCH_CHAT_LONG_IDLE_TIMEOUT_SECONDS:-600}\" \
        nohup $cmd > \"$logfile\" 2>&1 &"

        local pid="$(_wait_for_port_listener "$port" 25 0.2 || true)"
        if [[ -z "$pid" ]]; then
            pid=$!
        fi
        [[ -n "$pid" ]] && echo "$pid" > "$pidfile"
        sleep 1

        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log_ok "$name started (PID $pid, port $port)"
        else
            log_err "$name failed to start — check $logfile"
        fi

        cd "$ARMY_HOME"
    done
}

_build_mac_app() {
    log_info "Building Mac App..."
    if [[ -d "$ARMY_HOME/app" ]]; then
        cd "$ARMY_HOME/app" && ./build.sh >/dev/null
        if [[ -d "build/King AI.app" ]]; then
            log_ok "App built. Installing to /Applications/"
            killall "KingAI" 2>/dev/null || true
            rm -rf "/Applications/King AI.app"
            cp -R "build/King AI.app" "/Applications/"
            log_ok "App installed to /Applications/King AI.app"
        else
            log_warn "App build failed."
        fi
        cd "$ARMY_HOME"
    fi
}


_start_agents() {
    local started=0
    for adef in "${AGENT_DEFS[@]}"; do
        local name="${adef%%:*}"
        local rest="${adef#*:}"
        local port="${rest%%:*}"
        local key_name="${rest#*:}"
        local agent_dir="$AGENTS_DIR/$name"
        local pidfile="$PID_DIR/pids/agent-${name}.pid"
        local logfile="$LOG_DIR/agent-${name}.log"

        # Check if already running
        local tracked_pid=""
        tracked_pid="$(_read_pidfile "$pidfile" || true)"
        if [[ -n "$tracked_pid" ]] && kill -0 "$tracked_pid" 2>/dev/null; then
            local existing_pid="$tracked_pid"
            if _pid_listens_on_port "$existing_pid" "$port"; then
                log_ok "Agent $name already running (PID $existing_pid)"
                continue
            fi
            log_warn "Agent $name PID $existing_pid is not listening on $port; restarting"
            kill -TERM "$existing_pid" 2>/dev/null || true
            rm -f "$pidfile"
            sleep 1
        fi

        if [[ ! -d "$agent_dir" ]]; then
            log_warn "Agent dir missing: $agent_dir — skipping"
            continue
        fi

        local port_pid="$(_pid_on_port "$port" || true)"
        if [[ -n "$port_pid" ]]; then
            log_warn "Agent $name port $port occupied by PID $port_pid; reclaiming port"
            kill -TERM "$port_pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$port_pid" 2>/dev/null; then
                kill -9 "$port_pid" 2>/dev/null || true
            fi
            _wait_for_port_free "$port" 20 0.2 || true
        fi

        # Resolve the NVAPI key safely even with set -u
        local api_key=""
        if [[ -v "$key_name" ]]; then
            api_key="${(P)key_name}"
        else
            api_key="${NVIDIA_API_KEY:-}"
        fi

        # Start the agent via gateway subcommand
        local config_path=""
        if ! config_path="$(_ensure_agent_config "$name" "$port" "$agent_dir")"; then
            log_warn "No config for $name (expected $agent_dir/openclaw.json or $agent_dir/.openclaw/openclaw.json) — skipping"
            continue
        fi

        eval "env OPENCLAW_SERVICE_LABEL=\"$name\" \
        OPENCLAW_CONFIG_PATH=\"$config_path\" \
        OPENCLAW_DISABLE_BONJOUR=1 \
        NVIDIA_API_KEY=\"$api_key\" \
        nohup $OPENCLAW_CLI --profile \"$name\" gateway run --port \"$port\" --force --allow-unconfigured > \"$logfile\" 2>&1 &"

        local pid="$(_wait_for_port_listener "$port" 40 0.2 || true)"
        if [[ -z "$pid" ]]; then
            pid=$!
        elif ! _pid_listens_on_port "$pid" "$port"; then
            pid="$(_pid_on_port "$port" || echo "$pid")"
        fi
        [[ -n "$pid" ]] && echo "$pid" > "$pidfile"
        started=$((started + 1))

        # Don't wait between agents — they start fast
        if (( started % 4 == 0 )); then
            sleep 0.5
        fi
    done

    # Wait for all to start
    sleep 2
    log_ok "$started agents launched"
}

# ═══════════════════════════════════════════════════════════════════════════════
# STOP
# ═══════════════════════════════════════════════════════════════════════════════
cmd_stop() {
    log_head "Stopping OpenClaw Army"
    local flag="${1:-}"

    # 1. Stop agents
    log_info "Stopping agents..."
    local stopped=0
    for adef in "${AGENT_DEFS[@]}"; do
        local name="${adef%%:*}"
        local pidfile="$PID_DIR/pids/agent-${name}.pid"
        if [[ -f "$pidfile" ]]; then
            local pid="$(_read_pidfile "$pidfile" || true)"
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                kill -TERM "$pid" 2>/dev/null
                stopped=$((stopped + 1))
            fi
            rm -f "$pidfile"
        fi
    done
    log_ok "$stopped agents stopped"

    # 2. Stop services
    log_info "Stopping services..."
    for sdef in "${SERVICE_DEFS[@]}"; do
        local name="${sdef%%:*}"
        local pidfile="$PID_DIR/pids/${name}.pid"
        if [[ -f "$pidfile" ]]; then
            local pid="$(_read_pidfile "$pidfile" || true)"
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                kill -TERM "$pid" 2>/dev/null
                log_ok "Stopped $name (PID $pid)"
            fi
            rm -f "$pidfile"
        fi
    done

    # 3. Kill any orphans on our ports
    for adef in "${AGENT_DEFS[@]}"; do
        local rest="${adef#*:}"
        local port="${rest%%:*}"
        lsof -ti :"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    done
    for sdef in "${SERVICE_DEFS[@]}"; do
        local rest="${sdef#*:}"
        local port="${rest%%:*}"
        lsof -ti :"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    done

    # 4. Optionally stop infrastructure
    if [[ "$flag" == "--full" ]]; then
        log_info "Stopping infrastructure (--full)..."
        brew services stop postgresql@17 2>/dev/null || true
        brew services stop redis 2>/dev/null || true
        log_ok "PostgreSQL and Redis stopped"
    fi

    log_head "All Systems Offline"
}

# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════
cmd_status() {
    log_head "OpenClaw Army Status Dashboard"

    # Infrastructure
    echo "${BOLD}Infrastructure${NC}"
    printf "  %-20s " "PostgreSQL (5432):"
    if pg_isready -q 2>/dev/null; then echo "${GREEN}RUNNING${NC}"; else echo "${RED}DOWN${NC}"; fi
    printf "  %-20s " "Redis (6379):"
    if redis-cli ping 2>/dev/null | grep -q PONG; then echo "${GREEN}RUNNING${NC}"; else echo "${RED}DOWN${NC}"; fi
    echo ""

    # Services
    echo "${BOLD}Services${NC}"
    for sdef in "${SERVICE_DEFS[@]}"; do
        local name="${sdef%%:*}"
        local rest="${sdef#*:}"
        local port="${rest%%:*}"
        local pidfile="$PID_DIR/pids/${name}.pid"
        printf "  %-25s " "$name ($port):"
        local pid="$(_read_pidfile "$pidfile" || true)"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && curl -sf --max-time 2 "http://localhost:$port/health" >/dev/null 2>&1; then
            echo "${GREEN}RUNNING${NC} (PID $pid)"
        else
            local port_pid="$(_pid_on_port "$port" || true)"
            if [[ -n "$port_pid" ]] && curl -sf --max-time 2 "http://localhost:$port/health" >/dev/null 2>&1; then
                echo "$port_pid" > "$pidfile"
                echo "${GREEN}RUNNING${NC} (PID $port_pid)"
            else
                echo "${RED}DOWN${NC}"
            fi
        fi
    done
    echo ""

    # Agents
    echo "${BOLD}Agents${NC}"
    printf "  ${BOLD}%-18s %-7s %-8s %-10s${NC}\n" "Name" "Port" "Status" "PID"
    for adef in "${AGENT_DEFS[@]}"; do
        local name="${adef%%:*}"
        local rest="${adef#*:}"
        local port="${rest%%:*}"
        local pidfile="$PID_DIR/pids/agent-${name}.pid"
        local agent_status="${RED}DOWN${NC}"
        local pid_display="-"
        local pid="$(_read_pidfile "$pidfile" || true)"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && _pid_listens_on_port "$pid" "$port"; then
            agent_status="${GREEN}UP${NC}"
            pid_display="$pid"
        else
            local port_pid="$(_pid_on_port "$port" || true)"
            if [[ -n "$port_pid" ]]; then
                echo "$port_pid" > "$pidfile"
                agent_status="${GREEN}UP${NC}"
                pid_display="$port_pid"
            fi
        fi
        printf "  %-18s %-7s %-18b %-10s\n" "$name" "$port" "$agent_status" "$pid_display"
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
cmd_health() {
    log_head "OpenClaw Army Health Check"
    local total=0 healthy=0

    # Infrastructure
    total=$((total + 2))
    printf "  %-30s " "PostgreSQL..."
    if pg_isready -q 2>/dev/null; then echo "${GREEN}HEALTHY${NC}"; healthy=$((healthy+1)); else echo "${RED}UNHEALTHY${NC}"; fi
    printf "  %-30s " "Redis..."
    if redis-cli ping 2>/dev/null | grep -q PONG; then echo "${GREEN}HEALTHY${NC}"; healthy=$((healthy+1)); else echo "${RED}UNHEALTHY${NC}"; fi

    # Services
    for sdef in "${SERVICE_DEFS[@]}"; do
        local name="${sdef%%:*}"
        local rest="${sdef#*:}"
        local port="${rest%%:*}"
        total=$((total + 1))
        printf "  %-30s " "$name ($port)..."
        if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
            echo "${GREEN}HEALTHY${NC}"
            healthy=$((healthy+1))
        else
            echo "${RED}UNHEALTHY${NC}"
        fi
    done

    # Agents
    for adef in "${AGENT_DEFS[@]}"; do
        local name="${adef%%:*}"
        local rest="${adef#*:}"
        local port="${rest%%:*}"
        total=$((total + 1))
        printf "  %-30s " "$name ($port)..."
        if _is_port_listening "$port"; then
            echo "${GREEN}HEALTHY${NC}"
            healthy=$((healthy+1))
        else
            echo "${RED}UNHEALTHY${NC}"
        fi
    done

    echo ""
    echo "${BOLD}Result: $healthy/$total healthy${NC}"
    if (( healthy == total )); then
        log_ok "All systems nominal"
    else
        log_warn "$((total - healthy)) components need attention"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# RESTART
# ═══════════════════════════════════════════════════════════════════════════════
cmd_restart() {
    local target="${1:-all}"
    if [[ "$target" == "all" ]]; then
        cmd_stop
        sleep 1
        cmd_start
    else
        # Restart a specific agent
        local pidfile="$PID_DIR/pids/agent-${target}.pid"
        if [[ -f "$pidfile" ]]; then
            local existing_pid="$(_read_pidfile "$pidfile" || true)"
            [[ -n "$existing_pid" ]] && kill -TERM "$existing_pid" 2>/dev/null || true
            rm -f "$pidfile"
        fi
        sleep 1
        # Find agent def
        for adef in "${AGENT_DEFS[@]}"; do
            local name="${adef%%:*}"
            if [[ "$name" == "$target" ]]; then
                local rest="${adef#*:}"
                local port="${rest%%:*}"
                local key_name="${rest#*:}"
                local agent_dir="$AGENTS_DIR/$name"
                local logfile="$LOG_DIR/agent-${name}.log"
                local api_key=""
                if [[ -v "$key_name" ]]; then
                    api_key="${(P)key_name}"
                else
                    api_key="${NVIDIA_API_KEY:-}"
                fi

                local config_path=""
                if ! config_path="$(_ensure_agent_config "$name" "$port" "$agent_dir")"; then
                    log_err "No config for $name (expected $agent_dir/openclaw.json or $agent_dir/.openclaw/openclaw.json)"
                    return
                fi

                OPENCLAW_SERVICE_LABEL="$name" \
                OPENCLAW_CONFIG_PATH="$config_path" \
                OPENCLAW_DISABLE_BONJOUR=1 \
                NVIDIA_API_KEY="$api_key" \
                eval nohup $OPENCLAW_CLI --profile "$name" gateway run --port "$port" --force --allow-unconfigured > "$logfile" 2>&1 &

                local pid="$(_wait_for_port_listener "$port" 40 0.2 || true)"
                if [[ -z "$pid" ]]; then
                    pid=$!
                elif ! _pid_listens_on_port "$pid" "$port"; then
                    pid="$(_pid_on_port "$port" || echo "$pid")"
                fi
                [[ -n "$pid" ]] && echo "$pid" > "$PID_DIR/pids/agent-${name}.pid"
                log_ok "Restarted $name on port $port"
                return
            fi
        done
        log_err "Agent '$target' not found"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOGS
# ═══════════════════════════════════════════════════════════════════════════════
cmd_logs() {
    local target="${1:-all}"
    if [[ "$target" == "all" ]]; then
        tail -f "$LOG_DIR"/*.log
    else
        local logfile="$LOG_DIR/agent-${target}.log"
        [[ -f "$logfile" ]] || logfile="$LOG_DIR/${target}.log"
        if [[ -f "$logfile" ]]; then
            tail -f "$logfile"
        else
            log_err "No log file found for '$target'"
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
case "${1:-help}" in
    install)  cmd_install ;;
    start)    cmd_start ;;
    stop)     cmd_stop "${2:-}" ;;
    status)   cmd_status ;;
    health)   cmd_health ;;
    restart)  cmd_restart "${2:-all}" ;;
    logs)     cmd_logs "${2:-all}" ;;
    *)
        echo "${BOLD}OpenClaw Army — Unified Deployment${NC}"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  install           Install PostgreSQL, Redis, Python packages, create DB"
        echo "  start             Start infrastructure, services, and all 16 agents"
        echo "  stop [--full]     Stop agents & services (--full also stops Postgres/Redis)"
        echo "  status            Show status dashboard"
        echo "  health            Deep health check on all components"
        echo "  restart [name]    Restart all or a specific agent"
        echo "  logs [name]       Tail logs for all or a specific agent/service"
        ;;
esac
