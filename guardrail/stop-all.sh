#!/bin/bash

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BASE_DIR/.guard_pids"

echo "Stopping guardrail services ..."

if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
            echo "  Stopped pid $pid"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Fallback: match by script basename so it works regardless of absolute/relative path or cwd.
SCRIPTS="qwen3-guard.py meta-prompt-guard.py"
for script in $SCRIPTS; do
    pkill -f "$script" 2>/dev/null
done
sleep 2
for script in $SCRIPTS; do
    pkill -9 -f "$script" 2>/dev/null
done

echo "Done."
