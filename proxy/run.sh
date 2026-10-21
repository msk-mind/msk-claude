#!/bin/bash
# Start LiteLLM proxy to translate between Claude CLI and Open WebUI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Check if .auth.env exists
if [ ! -f "$REPO_DIR/.auth.env" ]; then
    echo "Error: .auth.env file not found"
    echo "Please create .auth.env with your session token:"
    echo "  export WEBUI_SESSION_TOKEN='your-token-here'"
    exit 1
fi

# Always load the token from .auth.env, so a refreshed token there wins over a
# stale WEBUI_SESSION_TOKEN exported in the calling shell
echo "Loading session token from .auth.env..."
unset WEBUI_SESSION_TOKEN
source "$REPO_DIR/.auth.env"

# Check if session token is set
if [ -z "$WEBUI_SESSION_TOKEN" ]; then
    echo "Error: WEBUI_SESSION_TOKEN is not set"
    echo "Make sure .auth.env contains:"
    echo "  export WEBUI_SESSION_TOKEN='your-token-here'"
    exit 1
fi

# Export token for LiteLLM config
export WEBUI_SESSION_TOKEN

# Disable SSL verification for internal MSK server
export NODE_TLS_REJECT_UNAUTHORIZED=0
export REQUESTS_CA_BUNDLE=""
export SSL_CERT_FILE=""
export PYTHONHTTPSVERIFY=0
export CURL_CA_BUNDLE=""

echo "Starting LiteLLM proxy..."
echo "Finding next available port (starting from 22660)..."
echo "WebUI backend: https://chat.aicopilot.aws.mskcc.org"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
exec python3 server.py
