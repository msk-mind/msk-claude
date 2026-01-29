#!/bin/bash
# Configure environment for Claude CLI to connect to LiteLLM proxy
# Source this file or use connect_claude.sh wrapper

# Configure Claude CLI to use LiteLLM proxy
export ANTHROPIC_AUTH_TOKEN="sk-1234"
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export ANTHROPIC_BASE_URL="http://localhost:22660"

echo "Claude CLI configured to connect to LiteLLM proxy"
echo "Base URL: $ANTHROPIC_BASE_URL"
echo ""
echo "Make sure LiteLLM proxy is running: ./start_litellm_proxy.sh"
echo "You can now run: claude"
