#!/bin/bash
# Wrapper script to connect Claude CLI to Open WebUI

# Get script directory before any directory changes
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default model
DEFAULT_MODEL="claude-sonnet-4.5"
AVAILABLE_MODELS=("claude-sonnet-4.5" "claude-sonnet-4" "claude-3.7-sonnet" "claude-3.5-sonnet")

# Parse arguments
MODEL="$DEFAULT_MODEL"
WORK_DIR="."

show_usage() {
    echo "Usage: $0 [OPTIONS] [working_directory]"
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
    echo "  $0                              # Use default model in current directory"
    echo "  $0 /path/to/project             # Use default model in specified directory"
    echo "  $0 -m claude-sonnet-4           # Use specific model in current directory"
    echo "  $0 -m claude-3.5-sonnet /path   # Use specific model in specified directory"
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

# Validate and change to working directory
if [ ! -d "$WORK_DIR" ]; then
    echo "Error: Working directory does not exist: $WORK_DIR"
    exit 1
fi

cd "$WORK_DIR"
echo "Working directory: $(pwd)"
echo "Model: $MODEL"
echo ""

# Set up Claude environment
source "${SCRIPT_DIR}/setup_claude_env.sh"

# Launch Claude CLI with selected model
echo "Launching Claude CLI..."
echo "Server: https://chat.aicopilot.aws.mskcc.org"
echo "This may take 10-30 seconds to initialize..."
echo "Press Ctrl+D or type 'exit' to quit"
echo ""

exec claude --model "$MODEL"
