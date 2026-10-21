"""Where aiportal keeps things.

Your token lives in the config directory and runtime state (the proxy key and
one directory per machine) in the state directory, following the XDG
conventions. AIPORTAL_CONFIG_DIR / AIPORTAL_STATE_DIR override them.
"""
import os
import socket

WEBUI_URL = "https://chat.aicopilot.aws.mskcc.org"
API_BASE = f"{WEBUI_URL}/api/v1"

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
LITELLM_CONFIG = os.path.join(PACKAGE_DIR, "litellm_config.yaml")


def _xdg(var, default):
    return os.environ.get(var) or os.path.expanduser(default)


CONFIG_DIR = os.environ.get("AIPORTAL_CONFIG_DIR") or os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "aiportal")
STATE_DIR = os.environ.get("AIPORTAL_STATE_DIR") or os.path.join(_xdg("XDG_STATE_HOME", "~/.local/state"), "aiportal")

AUTH_PATH = os.path.join(CONFIG_DIR, "auth.env")
PROXY_KEY_PATH = os.path.join(STATE_DIR, "master_key")


def host_state_dir(host=None):
    """Per-machine state, so machines sharing a home directory don't overwrite each other."""
    return os.path.join(STATE_DIR, host or socket.gethostname())


def private_dir(path):
    """Create a directory readable only by its owner (tightening it if it exists)."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def source_checkout():
    """The repository root when running from a git clone (src layout), else None."""
    root = os.path.dirname(os.path.dirname(PACKAGE_DIR))
    if os.path.exists(os.path.join(root, "pyproject.toml")) and os.path.isdir(os.path.join(root, ".git")):
        return root
    return None
