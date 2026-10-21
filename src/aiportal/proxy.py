"""The background LiteLLM proxy: finding, starting, restarting, stopping it.

Each machine keeps its proxy state in its own directory (see paths.host_state_dir):
  server_info   where the proxy listens, and a fingerprint of what it was started with
  proxy.pid     "<hostname> <pid>" of a background proxy started by aiportal
  proxy.log     its output
  proxy.lock    serializes launches on this machine
"""
import fcntl
import hashlib
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

from . import __version__
from .auth import check_token, load_token
from .paths import LITELLM_CONFIG, PACKAGE_DIR, PROXY_KEY_PATH, STATE_DIR, host_state_dir, private_dir

STARTUP_TIMEOUT = 120


# --- key ----------------------------------------------------------------------

def _new_key_file():
    """Write a fresh key to a private temp file next to the key file and return its path."""
    fd, tmp = tempfile.mkstemp(prefix="master_key.", suffix=".tmp", dir=STATE_DIR)  # created 0600
    with os.fdopen(fd, "w") as f:
        f.write(f"sk-{secrets.token_urlsafe(32)}\n")
    return tmp


def _read_key():
    try:
        return open(PROXY_KEY_PATH).read().strip()
    except FileNotFoundError:
        return ""


def ensure_proxy_key():
    """The secret clients use to authenticate to the proxy, created on first use.

    The key file only ever appears fully written: it is created by hard-linking a
    complete temp file into place, which also fails safely if another process
    created it first. An empty or truncated key is replaced, never returned.
    """
    private_dir(STATE_DIR)
    if not os.path.exists(PROXY_KEY_PATH):
        tmp = _new_key_file()
        try:
            os.link(tmp, PROXY_KEY_PATH)
        except FileExistsError:
            pass
        finally:
            os.unlink(tmp)
    key = _read_key()
    if len(key) < 20:
        os.replace(_new_key_file(), PROXY_KEY_PATH)
        key = _read_key()
    os.chmod(PROXY_KEY_PATH, 0o600)
    return key


# --- state --------------------------------------------------------------------

def fingerprint():
    """Changes whenever the proxy should be restarted: new config, code, token or key."""
    h = hashlib.sha256()
    for path in (LITELLM_CONFIG, os.path.join(PACKAGE_DIR, "callbacks.py"), os.path.join(PACKAGE_DIR, "server.py")):
        h.update(open(path, "rb").read())
    h.update((load_token() or "").encode())
    h.update(_read_key().encode())
    h.update(__version__.encode())
    return h.hexdigest()[:16]


def read_server_info(path):
    info = {}
    try:
        for line in open(path):
            key, _, value = line.strip().partition("=")
            info[key] = value
    except (FileNotFoundError, NotADirectoryError):
        return None
    return info


def connect_address(info):
    """Where to reach a proxy, or None if it only listens on another machine's localhost."""
    if info.get("bind") == "127.0.0.1":
        return "127.0.0.1" if info.get("hostname") == socket.gethostname() else None
    return info.get("hostname")


def probe(host, port, key=None):
    """'ok' if the proxy accepts our key, 'rejected' if it doesn't, 'down' if unreachable."""
    if not host or not port:
        return "down"
    import requests
    try:
        r = requests.get(f"http://{host}:{port}/v1/models", timeout=5,
                         headers={"Authorization": f"Bearer {key or ensure_proxy_key()}"},
                         proxies={"http": None, "https": None})
    except requests.RequestException:
        return "down"
    # LiteLLM answers 400 rather than 401 for some keys it doesn't recognize
    return "ok" if r.status_code == 200 else "rejected" if r.status_code in (400, 401, 403) else "down"


def process_args(pid):
    """A process's command line as a list of strings, or None if it isn't running."""
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace").split("\0")
    except FileNotFoundError:
        return None
    except OSError:  # no /proc (e.g. macOS)
        out = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True)
        return out.stdout.split() if out.returncode == 0 and out.stdout.strip() else None


def is_aiportal_proxy(pid):
    """True only if pid is an aiportal proxy, so a stale pid file (e.g. after a reboot,
    once the pid has been reused) never leads to killing an unrelated process."""
    return "aiportal.server" in (process_args(pid) or [])


def owned_pid(state_dir=None):
    """The pid of this machine's background proxy, if one is recorded and still running."""
    try:
        host, pid = open(os.path.join(state_dir or host_state_dir(), "proxy.pid")).read().split()
        pid = int(pid)
    except (FileNotFoundError, ValueError):
        return None
    if host != socket.gethostname() or not is_aiportal_proxy(pid):
        return None
    return pid


def kill_process_group(pid):
    """Stop a proxy that runs in its own process group, waiting until it has exited."""
    for sig, wait in ((signal.SIGTERM, 15), (signal.SIGKILL, 5)):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            return
        for _ in range(wait * 10):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)


@contextmanager
def _locked(state_dir):
    """Serialize launches on this machine so two at once don't both start a proxy."""
    fd = os.open(os.path.join(state_dir, "proxy.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


# --- starting -----------------------------------------------------------------

def _spawn_detached(argv, env, cwd, log_path):
    """Start argv in a new session, fully detached from this process; returns its pid.

    A double fork hands the proxy to init, so whatever this process becomes next
    (opencode or Claude Code, via exec) never has to reap it.
    """
    sys.stdout.flush()  # otherwise the forked children inherit, and may repeat, buffered output
    sys.stderr.flush()
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        try:
            os.close(read_fd)
            os.setsid()
            grandchild = os.fork()
            if grandchild == 0:
                os.setpgid(0, 0)  # own process group, so kill_process_group(pid) reaches it
                log = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                devnull = os.open(os.devnull, os.O_RDONLY)
                os.dup2(devnull, 0)
                os.dup2(log, 1)
                os.dup2(log, 2)
                os.chdir(cwd)
                os.execve(argv[0], argv, env)
            os.write(write_fd, str(grandchild).encode())
        finally:
            os._exit(0)
    os.close(write_fd)
    os.waitpid(child, 0)
    pid = int(os.read(read_fd, 32) or b"0")
    os.close(read_fd)
    return pid


def _tail(path, lines=20):
    try:
        return "".join(open(path, errors="replace").readlines()[-lines:])
    except FileNotFoundError:
        return ""


def _start_background(state_dir, previous_port=None):
    """Start a proxy on this machine and wait until it answers. Returns (host, port)."""
    pid = owned_pid(state_dir)
    if pid:
        kill_process_group(pid)
    info_path = os.path.join(state_dir, "server_info")
    log_path = os.path.join(state_dir, "proxy.log")
    for name in ("server_info", "proxy.pid"):
        try:
            os.unlink(os.path.join(state_dir, name))
        except FileNotFoundError:
            pass

    print(f"Starting a new proxy on {socket.gethostname()} (log: {log_path})...")
    env = dict(os.environ)
    # Come back on the same port, so sessions already running keep working
    env["MSK_PROXY_PORT"] = str(previous_port or "")
    pid = _spawn_detached([sys.executable, "-m", "aiportal.server"], env, state_dir, log_path)
    fd = os.open(os.path.join(state_dir, "proxy.pid"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"{socket.gethostname()} {pid}\n")

    key = ensure_proxy_key()
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            sys.exit(f"Error: the proxy exited during startup. Last log lines:\n{_tail(log_path)}")
        info = read_server_info(info_path)
        if info and probe(connect_address(info), info.get("port"), key) == "ok":
            host, port = connect_address(info), info["port"]
            print(f"Proxy started at http://{host}:{port} (pid {pid})")
            print("It keeps running after you exit; stop it with 'aiportal proxy stop'.")
            return host, port
        time.sleep(1)
    sys.exit(f"Error: the proxy did not become ready within {STARTUP_TIMEOUT}s. Last log lines:\n{_tail(log_path)}")


def _find_shared_proxy(key):
    """A key-accepting proxy that another machine started with MSK_PROXY_BIND=0.0.0.0."""
    here = host_state_dir()
    if not os.path.isdir(STATE_DIR):
        return None
    for host in sorted(os.listdir(STATE_DIR)):
        state_dir = os.path.join(STATE_DIR, host)
        info = read_server_info(os.path.join(state_dir, "server_info"))
        if state_dir == here or not info or info.get("bind") == "127.0.0.1":
            continue
        if probe(connect_address(info), info.get("port"), key) == "ok":
            print(f"Using the shared proxy on {host} at http://{info['hostname']}:{info['port']}")
            if info.get("fingerprint") != fingerprint():
                print(f"Warning: your token, key or aiportal version changed after that proxy started; "
                      f"restart it on {host} to pick up the change.")
            return info["hostname"], info["port"]
    return None


def requested_bind():
    """The address a new proxy listens on: localhost unless MSK_PROXY_BIND opts in to other machines."""
    return os.environ.get("MSK_PROXY_BIND", "127.0.0.1")


def ensure_proxy():
    """Make sure a proxy is reachable, starting or restarting one if needed.

    Returns (host, port, key). Exits with an explanation if the token is missing
    or expired, or the proxy can't be started.
    """
    if not check_token():
        sys.exit(1)
    key = ensure_proxy_key()
    state_dir = private_dir(host_state_dir())
    with _locked(state_dir):
        info = read_server_info(os.path.join(state_dir, "server_info"))
        host, port = (connect_address(info), info.get("port")) if info else (None, None)
        status = probe(host, port, key) if info else "down"

        if status == "ok":
            reason = None
            if info.get("fingerprint") != fingerprint():
                reason = "your token, key or aiportal version changed since the proxy started"
            elif "MSK_PROXY_BIND" in os.environ and info.get("bind") != requested_bind():
                reason = f"the proxy listens on {info.get('bind')}, but MSK_PROXY_BIND={requested_bind()}"
            if not reason:
                print(f"Proxy is running at http://{host}:{port}")
                return host, port, key
            if not owned_pid(state_dir):
                print(f"Warning: {reason}, but the proxy at http://{host}:{port} was not started by "
                      "aiportal, so it was left running. Restart it yourself to pick up the change.")
                return host, port, key
            print(f"{reason[0].upper()}{reason[1:]}; restarting it...")
        elif status == "rejected":
            print(f"The proxy at http://{host}:{port} rejected this key; replacing it...")
        else:
            # No working proxy here: use a shared one from another machine if there is one
            shared = _find_shared_proxy(key)
            if shared:
                return (*shared, key)
            if info:
                print(f"Proxy not reachable at http://{host}:{port}")
        return (*_start_background(state_dir, previous_port=port), key)


# --- commands -----------------------------------------------------------------

def cmd_stop():
    state_dir = host_state_dir()
    pid = owned_pid(state_dir)
    if pid is None:
        print(f"No background proxy running on {socket.gethostname()}")
    else:
        kill_process_group(pid)
        print(f"Stopped the proxy (pid {pid})")
    for name in ("proxy.pid", "server_info"):
        try:
            os.unlink(os.path.join(state_dir, name))
        except FileNotFoundError:
            pass
    return 0


def cmd_status():
    here = socket.gethostname()
    found = False
    for host in sorted(os.listdir(STATE_DIR)) if os.path.isdir(STATE_DIR) else []:
        state_dir = os.path.join(STATE_DIR, host)
        info = read_server_info(os.path.join(state_dir, "server_info"))
        if not info:
            continue
        found = True
        addr = connect_address(info)
        if host == here:
            pid = owned_pid(state_dir)
            started = f"background, pid {pid}" if pid else "foreground or not started by aiportal"
            print(f"{host} (this machine): {probe(addr, info.get('port'))} at http://{addr}:{info.get('port')} ({started})")
            current = "current" if info.get("fingerprint") == fingerprint() else "restarts on the next launch"
            print(f"  listening on {info.get('bind', '?')}; config {current}; log: {os.path.join(state_dir, 'proxy.log')}")
        elif addr is None:
            print(f"{host}: localhost-only proxy on port {info.get('port')} (not reachable from {here})")
        else:
            print(f"{host}: shared proxy, {probe(addr, info.get('port'))} at http://{addr}:{info.get('port')}")
    if not found:
        print("No proxy recorded. aiportal-opencode / aiportal-claude start one automatically.")
    return 0


def cmd_logs():
    log = os.path.join(host_state_dir(), "proxy.log")
    if not os.path.exists(log):
        print(f"No proxy log on {socket.gethostname()} ({log})")
        return 1
    os.execvp("tail", ["tail", "-n", "50", "-f", log])


def cmd_start_foreground():
    """Run the proxy in the foreground on this machine (to watch its output)."""
    if not check_token():
        return 1
    state_dir = private_dir(host_state_dir())
    if owned_pid(state_dir):
        print("A background proxy is already running on this machine; stop it first with 'aiportal proxy stop'.")
        return 1
    ensure_proxy_key()
    os.chdir(state_dir)
    os.execv(sys.executable, [sys.executable, "-m", "aiportal.server"])
