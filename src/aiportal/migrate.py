"""aiportal setup: first-time setup, and moving over from the clone-based setup.

Earlier versions ran from a clone of the repository and kept their state in it:
.auth.env (the token), .proxy/ or .litellm_* files (proxy key and state), and
symlinks in ~/.local/bin pointing into the clone.
"""
import json
import os
import shutil
import socket
import sys
import time

from .auth import check_token, cmd_token_set, load_token, parse_pasted_token, token_expiry, write_auth_file
from .paths import AUTH_PATH, PROXY_KEY_PATH, STATE_DIR, private_dir
from .proxy import kill_process_group, process_args

LEGACY_STATE = (".auth.env", ".proxy", ".litellm_proxy.pid", ".litellm_master_key", ".litellm_server_info")


REPO_MARKERS = ("proxy/litellm_config.yaml", "litellm_config.yaml", "src/aiportal/litellm_config.yaml")


def _has_legacy_state(path):
    """A clone of this repository that still holds state from the clone-based setup."""
    return (any(os.path.exists(os.path.join(path, m)) for m in REPO_MARKERS)
            and any(os.path.exists(os.path.join(path, name)) for name in LEGACY_STATE))


def legacy_proxies():
    """(pid, clone) for proxies of yours still running from a clone-based setup."""
    found = []
    for pid in filter(str.isdigit, os.listdir("/proc")) if os.path.isdir("/proc") else []:
        try:
            if os.stat(f"/proc/{pid}").st_uid != os.getuid():
                continue
            argv = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            continue
        if not any(os.path.basename(a) in (b"server.py", b"start_litellm.py") for a in argv):
            continue
        for clone in (cwd, os.path.dirname(cwd)):  # old layouts ran from the clone or its proxy/
            if _has_legacy_state(clone):
                found.append((int(pid), clone))
                break
    return found


def _stop_legacy_proxies(clone, running):
    host = socket.gethostname()
    pids = {pid for pid, c in running if c == clone}
    for pid_file in (os.path.join(clone, ".proxy", host, "proxy.pid"), os.path.join(clone, ".litellm_proxy.pid")):
        try:
            recorded_host, pid = open(pid_file).read().split()
            if recorded_host == host:
                pids.add(int(pid))
        except (OSError, ValueError):
            pass
    for pid in pids:
        # Only ever stop an old proxy: a recorded pid may since have been reused
        if not _is_legacy_proxy(pid):
            continue
        kill_process_group(pid)
        if _alive(pid):
            os.kill(pid, 9)
        print(f"  Stopped the old proxy (pid {pid})")


def _is_legacy_proxy(pid):
    args = process_args(pid) or []
    return any(os.path.basename(a) in ("server.py", "start_litellm.py") for a in args)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _import_token(clone):
    if load_token():
        return
    try:
        token = parse_pasted_token(open(os.path.join(clone, ".auth.env")).read().split("WEBUI_SESSION_TOKEN=", 1)[1])
    except (OSError, IndexError):
        return
    exp = token_expiry(token)
    if exp is not None and exp <= time.time():
        print("  The token in the old setup has expired; you'll be asked for a new one.")
        return
    write_auth_file(token)
    print(f"  Moved your token to {AUTH_PATH}")


def _import_key(clone):
    """Keep the old proxy key, so sessions started with the old setup keep working."""
    if os.path.exists(PROXY_KEY_PATH):
        return
    for name in (".proxy/master_key", ".litellm_master_key"):
        try:
            key = open(os.path.join(clone, name)).read().strip()
        except OSError:
            continue
        if len(key) >= 20:
            private_dir(STATE_DIR)
            fd = os.open(PROXY_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(key + "\n")
            print("  Kept your proxy key, so sessions you already have open keep working")
            return


def _remove_old_links(clone):
    bin_dir = os.path.expanduser("~/.local/bin")
    if not os.path.isdir(bin_dir):
        return
    clone = os.path.realpath(clone)
    for name in os.listdir(bin_dir):
        link = os.path.join(bin_dir, name)
        if os.path.islink(link) and os.path.realpath(link).startswith(clone + os.sep):
            os.unlink(link)
            print(f"  Removed the old command link {link}")


def migrate_clone(clone, running):
    print(f"Moving over from the clone-based setup in {clone}")
    _stop_legacy_proxies(clone, running)
    _import_token(clone)
    _import_key(clone)
    _remove_old_links(clone)
    leftovers = [name for name in (*LEGACY_STATE, ".venv", ".opencode_msk.json")
                 if os.path.exists(os.path.join(clone, name))]
    if leftovers:
        print(f"  No longer used, safe to delete: cd {clone} && rm -rf {' '.join(leftovers)}")


def _clean_global_opencode_config():
    """Earlier launchers wrote an msk provider into the global opencode config and never removed it."""
    path = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "opencode", "opencode.json")
    try:
        config = json.load(open(path))
    except (OSError, ValueError):
        return
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


def cmd_setup(import_paths):
    from .doctor import cmd_doctor

    running = legacy_proxies()
    candidates = [*import_paths, os.getcwd(), *(clone for _, clone in running)]
    seen = set()
    for path in candidates:
        path = os.path.realpath(os.path.expanduser(path))
        if path in seen or not _has_legacy_state(path):
            continue
        seen.add(path)
        migrate_clone(path, running)
    _clean_global_opencode_config()

    if not check_token(quiet=True):
        if sys.stdin.isatty():
            print()
            cmd_token_set()
        else:
            print("\nNo valid token saved yet. Run 'aiportal token set' to add one.")

    print("\nChecking the setup")
    return cmd_doctor()
