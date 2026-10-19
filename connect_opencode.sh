#!/bin/bash
# Wrapper script to connect opencode to Open WebUI via LiteLLM proxy

# Get script directory before any directory changes (resolving the aiportal-opencode symlink)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# Default model
DEFAULT_MODEL="claude-sonnet-5.5"
# Model names come from litellm_config.yaml
mapfile -t AVAILABLE_MODELS < <(python3 "$SCRIPT_DIR/aiportal.py" names)

MODEL="$DEFAULT_MODEL"
WORK_DIR="."

show_usage() {
    local cmd
    cmd="$(basename "$0")"
    echo "Usage: $cmd [OPTIONS] [working_directory]"
    echo ""
    echo "Options:"
    echo "  -m, --model MODEL    Model to use (default: $DEFAULT_MODEL)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Available models:"
    for m in "${AVAILABLE_MODELS[@]}"; do
        if [ "$m" = "$DEFAULT_MODEL" ]; then
            echo "  - $m (default)"
        else
            echo "  - $m"
        fi
    done
    echo ""
    echo "Examples:"
    echo "  $cmd                          # Use default model in current directory"
    echo "  $cmd /path/to/project         # Use default model in specified directory"
    echo "  $cmd -m gpt-5.5               # Use specific model in current directory"
    echo "  $cmd -m claude-opus-5.5 /path # Use specific model in specified directory"
    echo ""
    echo "Update the model list from the MSK endpoint with: $SCRIPT_DIR/aiportal.py sync --apply"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
        *)
            WORK_DIR="$1"
            shift
            break
            ;;
    esac
done

# Validate model selection
if [[ ! " ${AVAILABLE_MODELS[@]} " =~ " ${MODEL} " ]]; then
    echo "Error: Invalid model '$MODEL'"
    echo "Available models: ${AVAILABLE_MODELS[*]}"
    exit 1
fi

# Validate and resolve working directory
if [ ! -d "$WORK_DIR" ]; then
    echo "Error: Working directory does not exist: $WORK_DIR"
    exit 1
fi
WORK_DIR="$(cd "$WORK_DIR" && pwd)"

# Find a running proxy, or start one
source "$SCRIPT_DIR/ensure_proxy.sh" || exit 1

LITELLM_BASE_URL="http://${LITELLM_HOST}:${LITELLM_PORT}/v1"

echo "Working directory: $WORK_DIR"
echo "Model: msk/$MODEL"
echo "LiteLLM proxy: $LITELLM_BASE_URL"
echo ""

# Generate an MSK-only config and layer it over the user's global opencode config
# via OPENCODE_CONFIG, so the global ~/.config/opencode/opencode.json is never modified
export OPENCODE_CONFIG="$SCRIPT_DIR/.opencode_msk.json"

MSK_MODELS_JSON="$(python3 "$SCRIPT_DIR/aiportal.py" opencode-models)" || {
    echo "Error: Failed to read models from litellm_config.yaml"
    exit 1
}

python3 - "$OPENCODE_CONFIG" "$LITELLM_BASE_URL" "$MODEL" "$MSK_MODELS_JSON" <<'PYEOF' || { echo "Error: Failed to write opencode config"; exit 1; }
import json, sys

config_path, base_url, model, models_json = sys.argv[1:5]
config = {
    "$schema": "https://opencode.ai/config.json",
    "model": f"msk/{model}",
    "provider": {
        "msk": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "MSK AI Copilot",
            # opencode reads the key from the environment, so it never lands in this file
            "options": {"baseURL": base_url, "apiKey": "{env:MSK_PROXY_KEY}"},
            "models": json.loads(models_json),
        }
    },
}
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
PYEOF

echo "Launching opencode..."
echo "Press 'q' or Ctrl+C to quit"
echo ""

exec opencode "$WORK_DIR"
