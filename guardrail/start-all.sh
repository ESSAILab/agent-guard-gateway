#!/bin/bash
set -euo pipefail

CONDA_ENV="LlmGuardEnv"
HOST="127.0.0.1"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            CONDA_ENV="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--host HOST] [--env CONDA_ENV]"
            exit 1
            ;;
    esac
done

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BASE_DIR/.guard_pids"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

# name:script:port
SERVICES=(
    "qwen3-guard:qwen3-guard.py:18001"
    "meta-prompt-guard:meta-prompt-guard.py:18004"
)

echo "Starting guardrail services with env=$CONDA_ENV host=$HOST ..."

# Activate the shared conda env directly so $! is the real python process
# (conda run would leave us tracking a wrapper instead of the server).
CONDA_BASE="$(conda info --base 2>/dev/null)"
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

# Stop any existing instances first to avoid 'Address already in use' port conflicts.
"$BASE_DIR/stop-all.sh"

cd "$BASE_DIR"
: > "$PID_FILE"

for service in "${SERVICES[@]}"; do
    IFS=':' read -r name script port <<< "$service"
    log_file="$LOG_DIR/${name}.nohup.log"
    nohup python "$BASE_DIR/$script" --host "$HOST" --port "$port" > "$log_file" 2>&1 &
    pid=$!
    echo "$pid" >> "$PID_FILE"
    echo "  $name started (pid: $pid, port: $port, log: $log_file)"
done

echo "Done. PIDs saved to $PID_FILE"
