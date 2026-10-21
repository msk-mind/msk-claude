"""aiportal doctor: check the whole setup and say what to fix."""
import importlib.metadata as md
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time

from . import __version__
from .auth import ENV_TOKEN_HINT, TOKEN_WARN_DAYS, format_time, load_token, token_expiry, verify_token
from .models import model_names
from .paths import AUTH_PATH, LITELLM_CONFIG, WEBUI_URL, host_state_dir
from .proxy import connect_address, fingerprint, probe, read_server_info


def _pinned_requirements():
    pins = {}
    for req in md.requires("aiportal") or []:
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)(\[[^\]]*\])?\s*==\s*([^\s;]+)", req)
        if m:
            pins[m.group(1)] = m.group(3)
    return pins


def _version_of(cmd):
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=20,
                             stdin=subprocess.DEVNULL).stdout.strip().splitlines()
        return out[0] if out else "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def cmd_doctor():
    from .migrate import legacy_proxies

    problems = 0

    def report(ok, label, detail, fix=None):
        nonlocal problems
        mark = {True: "ok  ", False: "FAIL", None: "warn"}[ok]
        print(f"  [{mark}] {label}: {detail}")
        if fix and ok is not True:
            print(f"         -> {fix}")
        problems += ok is False

    print("Installation")
    report(True, "aiportal", f"{__version__} (Python {sys.version.split()[0]}, {sys.prefix})")
    try:
        pins = _pinned_requirements()
    except md.PackageNotFoundError:
        pins = {}
        report(None, "package metadata", "aiportal isn't installed as a package",
               "install it with: uv tool install git+https://github.com/msk-mind/msk-claude")
    for name, pinned in pins.items():
        try:
            have = md.version(name)
        except md.PackageNotFoundError:
            report(False, name, "not installed", "reinstall: uv tool install --reinstall aiportal")
            continue
        report(True if have == pinned else None, name,
               have if have == pinned else f"{have} (tested with {pinned})",
               "reinstall: uv tool install --reinstall aiportal")

    print("Session token")
    token = load_token()
    if not token:
        report(False, "token", "none saved",
               ENV_TOKEN_HINT.replace("\n", "\n            ") if os.environ.get("WEBUI_SESSION_TOKEN")
               else "run: aiportal token set")
    else:
        exp = token_expiry(token)
        if exp is not None:
            days = (exp - time.time()) / 86400
            report(False if days <= 0 else None if days < TOKEN_WARN_DAYS else True, "expiry",
                   f"expired {format_time(exp)}" if days <= 0 else f"valid until {format_time(exp)} ({days:.1f} days)",
                   "run: aiportal token set")
        accepted = verify_token(token)
        report(accepted, "portal accepts it",
               {True: "yes", False: "rejected", None: f"couldn't reach {WEBUI_URL}"}[accepted],
               "run: aiportal token set" if accepted is False else "check your network / VPN")
        mode = stat.S_IMODE(os.stat(AUTH_PATH).st_mode)
        report(not mode & 0o077 or None, "permissions", f"{AUTH_PATH} {oct(mode)}",
               "the next launch restricts it automatically")

    print("Models")
    try:
        report(True, "config", f"{len(model_names())} models ({LITELLM_CONFIG})")
    except Exception as e:  # noqa: BLE001 - report any config problem
        report(False, "config", f"can't read {LITELLM_CONFIG}: {e}", "reinstall: uv tool install --reinstall aiportal")

    print("Proxy")
    here = socket.gethostname()
    info = read_server_info(os.path.join(host_state_dir(), "server_info"))
    state = probe(connect_address(info), info.get("port")) if info else "down"
    if state == "ok":
        current = info.get("fingerprint") == fingerprint()
        report(True, here, f"running at http://{connect_address(info)}:{info['port']}"
               + ("" if current else " (restarts with your current setup on the next launch)"))
    elif state == "rejected":
        report(False, here, f"a proxy at http://{connect_address(info)}:{info['port']} rejects the key",
               "run: aiportal proxy stop, then relaunch")
    else:
        report(True, here, "not running (starts on the next launch)")
    for pid, clone in legacy_proxies():
        report(None, "old proxy", f"pid {pid} from the clone-based setup in {clone} is still running",
               "run: aiportal setup  (stops it and moves your token over)")

    print("Commands")
    for name in ("aiportal-opencode", "aiportal-claude", "aiportal"):
        found = shutil.which(name)
        expected = os.path.join(sys.prefix, "bin", name)
        if not found:
            report(False, name, "not on your PATH", "run: uv tool update-shell, then open a new terminal")
        elif os.path.realpath(found) != os.path.realpath(expected):
            report(None, name, f"{found} belongs to another installation",
                   "reinstall: uv tool install --force git+https://github.com/msk-mind/msk-claude")
        else:
            report(True, name, found)
    clients = [c for c in ("opencode", "claude") if shutil.which(c)]
    for c in ("opencode", "claude"):
        if shutil.which(c):
            report(True, c, _version_of(c))
        else:
            report(None if clients else False, c, "not installed",
                   "install it to use " + ("aiportal-opencode" if c == "opencode" else "aiportal-claude"))

    print()
    print("Everything looks good." if not problems else f"{problems} problem(s) found; see the -> lines above.")
    return 1 if problems else 0
