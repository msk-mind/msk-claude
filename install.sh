#!/bin/bash
# Install the aiportal-opencode and aiportal-claude commands into ~/.local/bin

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="${MSK_BIN_DIR:-$HOME/.local/bin}"

mkdir -p "$BIN_DIR"
for pair in "aiportal-opencode:connect_opencode.sh" "aiportal-claude:connect_claude.sh"; do
    name="${pair%%:*}"
    target="$SCRIPT_DIR/${pair#*:}"
    link="$BIN_DIR/$name"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
        echo "Skipping $link: a file that is not a symlink already exists there"
        continue
    fi
    ln -sfn "$target" "$link"
    echo "Installed $link -> $target"
done

# Remove links installed under earlier command names
for old in msk msk-claude; do
    link="$BIN_DIR/$old"
    if [ -L "$link" ] && [[ "$(readlink "$link")" == "$SCRIPT_DIR/"* ]]; then
        rm "$link"
        echo "Removed old command $link"
    fi
done

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not on your PATH; add it to use aiportal-opencode / aiportal-claude" ;;
esac

# Earlier versions of connect_opencode.sh wrote the msk provider into the global
# opencode config and never removed it. The config now comes from OPENCODE_CONFIG,
# so remove those leftovers (with a backup) to keep retired models from lingering.
OPENCODE_CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/opencode.json"
if [ -f "$OPENCODE_CONFIG_FILE" ]; then
    python3 - "$OPENCODE_CONFIG_FILE" <<'PYEOF'
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

echo ""
echo "Done. Run 'aiportal-opencode' to start opencode or 'aiportal-claude' to start Claude Code."
