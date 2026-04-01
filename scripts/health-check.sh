#!/bin/zsh
# ═══════════════════════════════════════════════════════════════════════════════
# OpenClaw Army — Health Check & Watchdog
# Usage: ./health-check.sh [--watch] [--auto-restart]
#
# --watch         Continuous monitoring (every 30s)
# --auto-restart  Automatically restart failed components
# ═══════════════════════════════════════════════════════════════════════════════
set -uo pipefail

ARMY_HOME="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ARMY_HOME/.env"
PID_DIR="$ARMY_HOME/data/pids"
LOG_DIR="$ARMY_HOME/data/logs"

if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ── Component Definitions ─────────────────────────────────────────────────────
# Infrastructure
INFRA_CHECKS=(
    "PostgreSQL:5432:pg_isready -q"
    "Redis:6379:redis-cli ping 2>/dev/null | grep -q PONG"
)

# Services: name:port
SERVICE_CHECKS=(
    "memory-service:${MEMORY_SERVICE_PORT:-18820}"
    "orchestrator-api:${ORCHESTRATOR_API_PORT:-18830}"
    "ralph:${RALPH_PORT:-18840}"
    "knowledge-bridge:${KNOWLEDGE_BRIDGE_PORT:-18850}"
)

# Agents: name:port
AGENT_CHECKS=(
    "main:${KING_PORT:-18789}"
    "alpha-manager:${ALPHA_PORT:-18800}"
    "beta-manager:${BETA_PORT:-18801}"
    "gamma-manager:${GAMMA_PORT:-18802}"
    "coding-1:${CODING_1_PORT:-18803}"
    "coding-2:${CODING_2_PORT:-18804}"
    "coding-3:${CODING_3_PORT:-18805}"
    "coding-4:${CODING_4_PORT:-18806}"
    "agentic-1:${AGENTIC_1_PORT:-18807}"
    "agentic-2:${AGENTIC_2_PORT:-18808}"
    "agentic-3:${AGENTIC_3_PORT:-18809}"
    "agentic-4:${AGENTIC_4_PORT:-18810}"
    "general-1:${GENERAL_1_PORT:-18811}"
    "general-2:${GENERAL_2_PORT:-18812}"
    "general-3:${GENERAL_3_PORT:-18813}"
    "general-4:${GENERAL_4_PORT:-18814}"
)

# ── Counters ──────────────────────────────────────────────────────────────────
TOTAL=0
HEALTHY=0
UNHEALTHY=0
RESTARTED=0
FAILURES=()

AUTO_RESTART=false
WATCH_MODE=false

# Parse args
for arg in "$@"; do
    case "$arg" in
        --auto-restart) AUTO_RESTART=true ;;
        --watch) WATCH_MODE=true ;;
    esac
done

# ── Check Functions ───────────────────────────────────────────────────────────

check_infra() {
    echo "${BOLD}${CYAN}Infrastructure${NC}"
    for check in "${INFRA_CHECKS[@]}"; do
        local name="${check%%:*}"
        local rest="${check#*:}"
        local port="${rest%%:*}"
        local cmd="${rest#*:}"
        TOTAL=$((TOTAL + 1))

        printf "  %-25s " "$name ($port)"
        if eval "$cmd" 2>/dev/null; then
            echo "${GREEN}● HEALTHY${NC}"
            HEALTHY=$((HEALTHY + 1))
        else
            echo "${RED}○ DOWN${NC}"
            UNHEALTHY=$((UNHEALTHY + 1))
            FAILURES+=("infra:$name")
        fi
    done
    echo ""
}

check_services() {
    echo "${BOLD}${CYAN}Services${NC}"
    for svc in "${SERVICE_CHECKS[@]}"; do
        local name="${svc%%:*}"
        local port="${svc#*:}"
        TOTAL=$((TOTAL + 1))

        printf "  %-25s " "$name ($port)"
        if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
            echo "${GREEN}● HEALTHY${NC}"
            HEALTHY=$((HEALTHY + 1))
        elif [[ -f "$PID_DIR/${name}.pid" ]] && kill -0 "$(cat "$PID_DIR/${name}.pid" 2>/dev/null)" 2>/dev/null; then
            echo "${YELLOW}◐ RUNNING (no /health)${NC}"
            HEALTHY=$((HEALTHY + 1))
        else
            echo "${RED}○ DOWN${NC}"
            UNHEALTHY=$((UNHEALTHY + 1))
            FAILURES+=("service:$name:$port")

            if $AUTO_RESTART; then
                _restart_service "$name" "$port"
            fi
        fi
    done
    echo ""
}

check_agents() {
    echo "${BOLD}${CYAN}Agents${NC}"

    # Group display
    echo "  ${BLUE}Orchestrator${NC}"
    _check_agent "main" "${KING_PORT:-18789}" "    "

    echo "  ${BLUE}Managers (3)${NC}"
    _check_agent "alpha-manager" "${ALPHA_PORT:-18800}" "    "
    _check_agent "beta-manager" "${BETA_PORT:-18801}" "    "
    _check_agent "gamma-manager" "${GAMMA_PORT:-18802}" "    "

    echo "  ${BLUE}Coding Workers (4)${NC}"
    for i in 1 2 3 4; do
        local port_var="CODING_${i}_PORT"
        _check_agent "coding-$i" "${(P)port_var:-$((18802 + i))}" "    "
    done

    echo "  ${BLUE}Agentic Workers (4)${NC}"
    for i in 1 2 3 4; do
        local port_var="AGENTIC_${i}_PORT"
        _check_agent "agentic-$i" "${(P)port_var:-$((18806 + i))}" "    "
    done

    echo "  ${BLUE}General Workers (4)${NC}"
    for i in 1 2 3 4; do
        local port_var="GENERAL_${i}_PORT"
        _check_agent "general-$i" "${(P)port_var:-$((18810 + i))}" "    "
    done
    echo ""
}

_check_agent() {
    local name="$1" port="$2" indent="${3:-  }"
    TOTAL=$((TOTAL + 1))

    printf "${indent}%-22s " "$name ($port)"

    local pidfile="$PID_DIR/agent-${name}.pid"
    local pid_alive=false

    if [[ -f "$pidfile" ]]; then
        local pid=$(cat "$pidfile" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            pid_alive=true
        fi
    fi

    if $pid_alive; then
        echo "${GREEN}● UP${NC} ${DIM}(PID $pid)${NC}"
        HEALTHY=$((HEALTHY + 1))
    else
        # Also check if port is responding
        if curl -sf --max-time 2 "http://localhost:$port" >/dev/null 2>&1; then
            echo "${YELLOW}◐ RESPONDING (no PID)${NC}"
            HEALTHY=$((HEALTHY + 1))
        else
            echo "${RED}○ DOWN${NC}"
            UNHEALTHY=$((UNHEALTHY + 1))
            FAILURES+=("agent:$name:$port")

            if $AUTO_RESTART; then
                _restart_agent "$name" "$port"
            fi
        fi
    fi
}

_restart_service() {
    local name="$1" port="$2"
    local svc_dir="$ARMY_HOME/services/$name"
    local logfile="$LOG_DIR/${name}.log"
    local pidfile="$PID_DIR/${name}.pid"
    local python="python3.14"

    if [[ -f "$ARMY_HOME/.venv/bin/activate" ]]; then
        source "$ARMY_HOME/.venv/bin/activate"
        python="$ARMY_HOME/.venv/bin/python"
    fi

    if [[ ! -d "$svc_dir" ]]; then
        echo "      ${RED}Cannot restart: $svc_dir not found${NC}"
        return
    fi

    echo "      ${YELLOW}↻ Restarting $name...${NC}"
    cd "$svc_dir"
    ARMY_HOME="$ARMY_HOME" \
    nohup $python -m uvicorn main:app --host 127.0.0.1 --port "$port" > "$logfile" 2>&1 &
    echo "$!" > "$pidfile"
    cd "$ARMY_HOME"
    sleep 1

    if kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "      ${GREEN}✓ Restarted (PID $(cat "$pidfile"))${NC}"
        RESTARTED=$((RESTARTED + 1))
    else
        echo "      ${RED}✗ Restart failed${NC}"
    fi
}

_restart_agent() {
    local name="$1" port="$2"
    local agent_dir="$ARMY_HOME/agents/$name"
    local logfile="$LOG_DIR/agent-${name}.log"
    local pidfile="$PID_DIR/agent-${name}.pid"

    if [[ ! -d "$agent_dir" ]]; then
        echo "      ${RED}Cannot restart: $agent_dir not found${NC}"
        return
    fi

    echo "      ${YELLOW}↻ Restarting $name...${NC}"

    OPENCLAW_SERVICE_LABEL="$name" \
    OPENCLAW_CONFIG_PATH="$agent_dir/openclaw.json" \
    nohup openclaw > "$logfile" 2>&1 &

    echo "$!" > "$pidfile"
    sleep 1

    if kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "      ${GREEN}✓ Restarted (PID $(cat "$pidfile"))${NC}"
        RESTARTED=$((RESTARTED + 1))
    else
        echo "      ${RED}✗ Restart failed${NC}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

run_check() {
    TOTAL=0; HEALTHY=0; UNHEALTHY=0; RESTARTED=0; FAILURES=()

    echo ""
    echo "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo "${BOLD}${CYAN}  OpenClaw Army Health Check — $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo "${BOLD}${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""

    check_infra
    check_services
    check_agents

    # Summary
    echo "${BOLD}═══════════════════════════════════════════════════════${NC}"
    local pct=0
    (( TOTAL > 0 )) && pct=$((HEALTHY * 100 / TOTAL))

    if (( UNHEALTHY == 0 )); then
        echo "  ${GREEN}${BOLD}ALL SYSTEMS NOMINAL${NC}  ${DIM}($HEALTHY/$TOTAL healthy — ${pct}%)${NC}"
    else
        echo "  ${RED}${BOLD}$UNHEALTHY FAILURES${NC}  ${DIM}($HEALTHY/$TOTAL healthy — ${pct}%)${NC}"
        if (( RESTARTED > 0 )); then
            echo "  ${YELLOW}↻ Auto-restarted: $RESTARTED${NC}"
        fi
        echo ""
        echo "  ${RED}Failed:${NC}"
        for f in "${FAILURES[@]}"; do
            echo "    ${RED}•${NC} $f"
        done
    fi
    echo "${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

if $WATCH_MODE; then
    echo "${BOLD}Entering watch mode (Ctrl-C to stop)${NC}"
    while true; do
        clear
        run_check
        sleep 30
    done
else
    run_check
    exit $UNHEALTHY
fi
