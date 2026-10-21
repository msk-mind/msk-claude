#!/bin/bash
# Install aiportal from this clone and move over from the clone-based setup.
#
# Most people don't need a clone at all:
#   uv tool install git+https://github.com/msk-mind/msk-claude && aiportal setup
#
# This script is for existing users of the clone-based setup: run it after
# `git pull` to install the package and move your token over.

set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

if command -v uv > /dev/null; then
    # --force replaces the old command links in ~/.local/bin
    uv tool install --force --reinstall "$SCRIPT_DIR"
    BIN_DIR="$(uv tool dir --bin)"
elif command -v pipx > /dev/null; then
    pipx install --force "$SCRIPT_DIR"
    BIN_DIR="${PIPX_BIN_DIR:-$HOME/.local/bin}"
else
    echo "Error: aiportal installs with uv (or pipx). Install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not on your PATH; run 'uv tool update-shell' and open a new terminal." ;;
esac

exec "$BIN_DIR/aiportal" setup --import "$SCRIPT_DIR"
