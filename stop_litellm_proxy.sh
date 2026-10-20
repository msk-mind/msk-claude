#!/bin/bash
# Stop the LiteLLM proxy that ensure_proxy.sh started in the background on this machine

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
STATE_DIR="$SCRIPT_DIR/.proxy/$(hostname)"
PID_FILE="$STATE_DIR/proxy.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No background proxy recorded on $(hostname)"
    exit 0
fi

read -r HOST PID < "$PID_FILE"
if kill -0 "$PID" 2>/dev/null; then
    # The proxy runs in its own session, so its pid is also its process group id
    kill -- -"$PID" 2>/dev/null || kill "$PID"
    echo "Stopped LiteLLM proxy (pid $PID)"
else
    echo "LiteLLM proxy (pid $PID) was not running"
fi

rm -f "$PID_FILE" "$STATE_DIR/server_info"
