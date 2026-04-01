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
PYTHON="python3.14"
OPENCLAW_CLI="node --max-old-space-size=512 --expose-gc $HOME/openclaw-core/openclaw.mjs"

# Ensure required dependencies are in PATH (PostgreSQL, Redis, OpenClaw Node modules)
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql@17/bin:$HOME/.npm-global/bin:$PATH"

# Use virtual environment if available
if [[ -f "$ARMY_HOME/.venv/bin/activate" ]]; then
    source "$ARMY_HOME/.venv/bin/activate"
    PYTHON="$ARMY_HOME/.venv/bin/python"
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

    # 2. Start Python services
    _start_services

    # 3. Start all agents
    _start_agents

    # 4. Build and install Mac app
    _build_mac_app

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

_start_services() {
    for sdef in "${SERVICE_DEFS[@]}"; do
        local name="${sdef%%:*}"
        local rest="${sdef#*:}"
        local port="${rest%%:*}"
        local cmd="${rest#*:}"
        local pidfile="$PID_DIR/pids/${name}.pid"
        local logfile="$LOG_DIR/${name}.log"

        # Check if already running
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            log_ok "$name already running (PID $(cat "$pidfile"))"
            continue
        fi

        log_info "Starting $name on port $port..."
        cd "$SERVICES_DIR/$name"

        # Source .env in the service context
        eval "env ARMY_HOME=\"$ARMY_HOME\" \
        POSTGRES_URL=\"${POSTGRES_URL:-postgresql://openclaw:openclaw@localhost:5432/openclaw_army}\" \
        REDIS_URL=\"${REDIS_URL:-redis://localhost:6379/0}\" \
        CHROMA_PATH=\"$DATA_DIR/chroma\" \
        VAULT_PATH=\"$ARMY_HOME/data/obsidian database\" \
        NVIDIA_API_KEY=\"${NVIDIA_API_KEY:-}\" \
        nohup $cmd > \"$logfile\" 2>&1 &"

        local pid=$!
        echo "$pid" > "$pidfile"
        sleep 1

        if kill -0 "$pid" 2>/dev/null; then
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
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            log_ok "Agent $name already running (PID $(cat "$pidfile"))"
            continue
        fi

        if [[ ! -d "$agent_dir" ]]; then
            log_warn "Agent dir missing: $agent_dir — skipping"
            continue
        fi

        # Resolve the NVAPI key safely even with set -u
        local api_key=""
        if [[ -v "$key_name" ]]; then
            api_key="${(P)key_name}"
        else
            api_key="${NVIDIA_API_KEY:-}"
        fi

        # Kill anything on port first
        pids=$(lsof -ti :$port 2>/dev/null || true)
        if [ ! -z "$pids" ]; then
            echo "Stopping previous agent on port $port (PIDs: $pids)"
            echo "$pids" | xargs kill -9 >/dev/null 2>&1
            sleep 1
        fi

        # Start the agent via gateway subcommand
        eval "env OPENCLAW_SERVICE_LABEL=\"$name\" \
        OPENCLAW_CONFIG_PATH=\"$agent_dir/openclaw.json\" \
        OPENCLAW_DISABLE_BONJOUR=1 \
        NVIDIA_API_KEY=\"$api_key\" \
        nohup $OPENCLAW_CLI gateway --port \"$port\" --force --profile \"$name\" > \"$logfile\" 2>&1 &"

        local pid=$!
        echo "$pid" > "$pidfile"
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
            local pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
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
            local pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
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
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            echo "${GREEN}RUNNING${NC} (PID $(cat "$pidfile"))"
        else
            echo "${RED}DOWN${NC}"
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
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            agent_status="${GREEN}UP${NC}"
            pid_display="$(cat "$pidfile")"
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
        if curl -sf "http://localhost:$port" >/dev/null 2>&1; then
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
            kill -TERM "$(cat "$pidfile")" 2>/dev/null || true
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

                OPENCLAW_SERVICE_LABEL="$name" \
                OPENCLAW_CONFIG_PATH="$agent_dir/openclaw.json" \
                OPENCLAW_DISABLE_BONJOUR=1 \
                NVIDIA_API_KEY="$api_key" \
                eval nohup $OPENCLAW_CLI gateway --port "$port" --force > "$logfile" 2>&1 &

                echo "$!" > "$PID_DIR/pids/agent-${name}.pid"
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
