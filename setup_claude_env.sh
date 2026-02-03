#!/bin/bash
# Configure environment for Claude CLI to connect to LiteLLM proxy
# Source this file or use connect_claude.sh wrapper

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_INFO_FILE="$SCRIPT_DIR/.litellm_server_info"
PORT_FILE="$SCRIPT_DIR/.litellm_port"

# Read server info from file if it exists
if [ -f "$SERVER_INFO_FILE" ]; then
    source "$SERVER_INFO_FILE"
    LITELLM_HOST="${hostname:-localhost}"
    LITELLM_PORT="${port:-22660}"
    echo "Read LiteLLM server info from file:"
    echo "  Hostname: $LITELLM_HOST"
    echo "  Port: $LITELLM_PORT"
elif [ -f "$PORT_FILE" ]; then
    LITELLM_HOST="localhost"
    LITELLM_PORT=$(cat "$PORT_FILE")
    echo "Read LiteLLM port from file: $LITELLM_PORT"
    echo "Using localhost as hostname"
else
    LITELLM_HOST="localhost"
    LITELLM_PORT=22660
    echo "Warning: Server info files not found, using defaults"
    echo "  Hostname: $LITELLM_HOST"
    echo "  Port: $LITELLM_PORT"
    echo "Make sure LiteLLM proxy is running"
fi

# Configure Claude CLI to use LiteLLM proxy
export ANTHROPIC_AUTH_TOKEN="sk-1234"
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ANTHROPIC_BASE_URL="http://${LITELLM_HOST}:${LITELLM_PORT}"

echo "Claude CLI configured to connect to LiteLLM proxy"
echo "Base URL: $ANTHROPIC_BASE_URL"
echo ""
echo "Make sure LiteLLM proxy is running: ./start_litellm_proxy.sh"
echo "You can now run: claude"
