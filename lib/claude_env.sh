#!/bin/bash
# Configure the environment for Claude Code to use the LiteLLM proxy.
# Sourced by bin/aiportal-claude; you can also source it yourself and run `claude`.

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find a running proxy, or start one
source "$SCRIPT_DIR/ensure_proxy.sh" || return 1 2>/dev/null || exit 1

# Configure Claude CLI to use LiteLLM proxy
export ANTHROPIC_AUTH_TOKEN="$MSK_PROXY_KEY"
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ANTHROPIC_BASE_URL="http://${LITELLM_HOST}:${LITELLM_PORT}"

echo "Claude CLI configured to connect to LiteLLM proxy"
echo "Base URL: $ANTHROPIC_BASE_URL"
echo ""
echo "You can now run: claude"
