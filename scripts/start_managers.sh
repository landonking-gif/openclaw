#!/bin/zsh
# Start the 3 manager agents with PROFILE ISOLATION to prevent session lock conflicts
set -uo pipefail

ARMY_HOME=/Users/landonking/openclaw-army
LOG_DIR=$ARMY_HOME/data/logs
PID_DIR=$ARMY_HOME/data/pids

# Load env safely (avoid set -e due to potential subshell failures in .env)
set -a
source $ARMY_HOME/.env 2>/dev/null || true
set +a

mkdir -p $LOG_DIR $PID_DIR

# Kill any existing openclaw processes
echo "Killing existing openclaw processes..."
pkill -f openclaw-gateway 2>/dev/null || true
pkill -f "openclaw gateway" 2>/dev/null || true
sleep 2

# Clear ALL stale session locks
echo "Clearing stale lock files..."
find $HOME/.openclaw -name "*.lock" -type f -delete 2>/dev/null || true
find $HOME/.openclaw-alpha -name "*.lock" -type f -delete 2>/dev/null || true
find $HOME/.openclaw-beta -name "*.lock" -type f -delete 2>/dev/null || true
find $HOME/.openclaw-gamma -name "*.lock" -type f -delete 2>/dev/null || true

# Executable path
OPENCLAW_CLI="node $HOME/openclaw-core/openclaw.mjs"

echo ""
echo "=== Starting Manager Agents (with profile isolation) ==="

# Alpha Manager — uses --profile alpha-manager (state in ~/.openclaw-alpha-manager/)
echo "Starting alpha-manager on port 18800 (profile: alpha-manager)..."
OPENCLAW_SERVICE_LABEL=alpha-manager \
OPENCLAW_CONFIG_PATH=$ARMY_HOME/agents/alpha-manager/openclaw.json \
NVIDIA_API_KEY=$NVAPI_KIMI_KEY_1 \
eval "nohup $OPENCLAW_CLI gateway --port 18800 --force --profile alpha-manager > $LOG_DIR/agent-alpha-manager.log 2>&1 &"
echo $! > $PID_DIR/agent-alpha-manager.pid
echo "  PID: $!"
sleep 2

# Beta Manager — uses --profile beta-manager (state in ~/.openclaw-beta-manager/)
echo "Starting beta-manager on port 18801 (profile: beta-manager)..."
OPENCLAW_SERVICE_LABEL=beta-manager \
OPENCLAW_CONFIG_PATH=$ARMY_HOME/agents/beta-manager/openclaw.json \
NVIDIA_API_KEY=$NVAPI_DEEPSEEK_KEY_1 \
eval "nohup $OPENCLAW_CLI gateway --port 18801 --force --profile beta-manager > $LOG_DIR/agent-beta-manager.log 2>&1 &"
echo $! > $PID_DIR/agent-beta-manager.pid
echo "  PID: $!"
sleep 2

# Gamma Manager — uses --profile gamma-manager (state in ~/.openclaw-gamma-manager/)
echo "Starting gamma-manager on port 18802 (profile: gamma-manager)..."
OPENCLAW_SERVICE_LABEL=gamma-manager \
OPENCLAW_CONFIG_PATH=$ARMY_HOME/agents/gamma-manager/openclaw.json \
NVIDIA_API_KEY=$NVAPI_KIMI_KEY_2 \
eval "nohup $OPENCLAW_CLI gateway --port 18802 --force --profile gamma-manager > $LOG_DIR/agent-gamma-manager.log 2>&1 &"
echo $! > $PID_DIR/agent-gamma-manager.pid
echo "  PID: $!"

echo ""
echo "Waiting 20s for agents to boot..."
sleep 20

echo ""
echo "=== Checking Ports ==="
for port in 18800 18801 18802; do
    if lsof -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
        echo "  Port $port: LISTENING"
    else
        echo "  Port $port: NOT LISTENING"
    fi
done

echo ""
echo "=== Agent Logs (last 3 lines each) ==="
for name in alpha-manager beta-manager gamma-manager; do
    echo "--- $name ---"
    tail -3 $LOG_DIR/agent-${name}.log 2>/dev/null || echo "  (no log)"
done
