#!/bin/bash
# Stop a LiteLLM proxy that was started in the background by ensure_proxy.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.litellm_proxy.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No background proxy recorded ($PID_FILE not found)"
    exit 0
fi

read -r HOST PID < "$PID_FILE"
if [ "$HOST" != "$(hostname)" ]; then
    echo "The proxy was started on $HOST; run this script there to stop it"
    exit 1
fi

if kill -0 "$PID" 2>/dev/null; then
    # The proxy was started with setsid, so its pid is also its process group id
    kill -- -"$PID" 2>/dev/null || kill "$PID"
    echo "Stopped LiteLLM proxy (pid $PID)"
else
    echo "LiteLLM proxy (pid $PID) was not running"
fi

rm -f "$PID_FILE" "$SCRIPT_DIR/.litellm_server_info" "$SCRIPT_DIR/.litellm_port"
