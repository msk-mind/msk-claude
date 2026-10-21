#!/bin/bash
# Set up the MSK AI Portal commands: check prerequisites, create the private
# Python environment, install aiportal-opencode / aiportal-claude / aiportal
# into ~/.local/bin, save your session token, and check the result.
#
# Safe to re-run: it only reinstalls dependencies when requirements.txt changes.
#
# Usage: ./install.sh [--reinstall]

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="${MSK_BIN_DIR:-$HOME/.local/bin}"
VENV="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
REQUIREMENTS_STAMP="$VENV/.requirements.sha256"
MIN_PYTHON="3.10"

REINSTALL=0
case "$1" in
    "") ;;
    --reinstall) REINSTALL=1 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
esac

step() { echo ""; echo "==> $*"; }
fail() { echo "Error: $*"; exit 1; }

# --- 1. Prerequisites ---------------------------------------------------------
step "Checking prerequisites"
for tool in curl flock setsid; do
    command -v "$tool" > /dev/null || fail "'$tool' is required but not installed"
done
if command -v uv > /dev/null; then
    echo "Using uv to manage the Python environment"
else
    command -v python3 > /dev/null || fail "Python $MIN_PYTHON or newer is required (or install uv: https://docs.astral.sh/uv/)"
    python3 -c "import sys; sys.exit(sys.version_info < tuple(map(int, '$MIN_PYTHON'.split('.'))))" \
        || fail "Python $MIN_PYTHON or newer is required; found $(python3 --version 2>&1)"
fi
CLIENTS=()
for client in opencode claude; do
    command -v "$client" > /dev/null && CLIENTS+=("$client")
done
if [ ${#CLIENTS[@]} -eq 0 ]; then
    echo "Warning: neither opencode nor Claude Code is installed; install one to use these commands"
    echo "  opencode: https://opencode.ai    Claude Code: https://claude.com/claude-code"
else
    echo "Found: ${CLIENTS[*]}"
fi

# --- 2. Private Python environment --------------------------------------------
step "Setting up the Python environment in .venv"
if [ ! -x "$VENV/bin/python" ]; then
    if command -v uv > /dev/null; then
        uv venv --quiet --python ">=$MIN_PYTHON" "$VENV" || fail "couldn't create $VENV"
    else
        python3 -m venv "$VENV" || fail "couldn't create $VENV"
    fi
fi
wanted="$(sha256sum "$REQUIREMENTS" | cut -d' ' -f1)"
if [ "$REINSTALL" = 1 ] || [ "$(cat "$REQUIREMENTS_STAMP" 2> /dev/null)" != "$wanted" ]; then
    echo "Installing dependencies (this can take a minute)..."
    if command -v uv > /dev/null; then
        uv pip install --quiet --python "$VENV/bin/python" -r "$REQUIREMENTS"
    else
        "$VENV/bin/python" -m pip install --quiet --upgrade pip &&
            "$VENV/bin/python" -m pip install --quiet -r "$REQUIREMENTS"
    fi || fail "dependency installation failed; re-run with --reinstall after fixing the error above"
    echo "$wanted" > "$REQUIREMENTS_STAMP"
else
    echo "Dependencies are up to date"
fi

# --- 3. Commands ----------------------------------------------------------------
step "Installing commands into $BIN_DIR"
mkdir -p "$BIN_DIR"
for name in aiportal-opencode aiportal-claude aiportal; do
    target="$SCRIPT_DIR/bin/$name"
    link="$BIN_DIR/$name"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
        echo "Skipping $link: a file that is not a symlink already exists there"
        continue
    fi
    ln -sfn "$target" "$link"
    echo "Installed $name"
done

# Remove links from earlier versions (e.g. msk, msk-claude) that point into this
# repo at files that no longer exist
for link in "$BIN_DIR"/*; do
    if [ -L "$link" ] && [ ! -e "$link" ] && [[ "$(readlink "$link")" == "$SCRIPT_DIR/"* ]]; then
        rm "$link"
        echo "Removed old command $link"
    fi
done

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not on your PATH. Add this to your ~/.bashrc:"
       echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# Earlier versions of the opencode launcher wrote the msk provider into the global
# opencode config and never removed it. The config now comes from OPENCODE_CONFIG,
# so remove those leftovers (with a backup) to keep retired models from lingering.
OPENCODE_CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/opencode.json"
if [ -f "$OPENCODE_CONFIG_FILE" ]; then
    "$VENV/bin/python" - "$OPENCODE_CONFIG_FILE" <<'PYEOF'
import json, shutil, sys, time

path = sys.argv[1]
with open(path) as f:
    config = json.load(f)

changed = False
if "msk" in config.get("provider", {}):
    del config["provider"]["msk"]
    if not config["provider"]:
        del config["provider"]
    changed = True
if str(config.get("model", "")).startswith("msk/"):
    del config["model"]
    changed = True

if changed:
    backup = f"{path}.pre-msk-cleanup.{time.strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(path, backup)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Removed leftover msk settings from {path} (backup: {backup})")
PYEOF
fi

AIPORTAL="$SCRIPT_DIR/bin/aiportal"

# --- 4. Session token -----------------------------------------------------------
step "Checking your session token"
if "$AIPORTAL" _token-check > /dev/null 2>&1; then
    "$AIPORTAL" token
elif [ -t 0 ]; then
    "$AIPORTAL" token set || echo "Run 'aiportal token set' when you have a token."
else
    echo "No valid token yet. Run 'aiportal token set' to add one."
fi

# --- 5. Check -------------------------------------------------------------------
step "Checking the setup"
"$AIPORTAL" doctor
status=$?

echo ""
if [ $status -eq 0 ]; then
    echo "Done. Run 'aiportal-opencode' to start opencode or 'aiportal-claude' to start Claude Code."
else
    echo "Installed, but fix the problems above before launching ('aiportal doctor' re-checks)."
fi
exit $status
