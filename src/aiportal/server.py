"""Runs the LiteLLM proxy: python -m aiportal.server

Started in the background by aiportal-opencode / aiportal-claude, or in the
foreground by `aiportal proxy start`.
"""
import os
import socket
import ssl
import sys

from .auth import load_token
from .paths import LITELLM_CONFIG, WEBUI_URL, host_state_dir, private_dir
from .proxy import ensure_proxy_key, fingerprint, requested_bind

# Listen on localhost only unless MSK_PROXY_BIND=0.0.0.0 opts in to clients on other machines
BIND_HOST = requested_bind()

# The portal uses an internal certificate: disable SSL verification for this process
ssl._create_default_https_context = ssl._create_unverified_context
for var, value in (("PYTHONHTTPSVERIFY", "0"), ("REQUESTS_CA_BUNDLE", ""), ("SSL_CERT_FILE", ""),
                   ("CURL_CA_BUNDLE", ""), ("NODE_TLS_REJECT_UNAUTHORIZED", "0")):
    os.environ[var] = value


def _disable_aiohttp_ssl():
    from aiohttp import TCPConnector
    original_init = TCPConnector.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["ssl"] = False
        return original_init(self, *args, **kwargs)

    TCPConnector.__init__ = patched_init


def find_available_port(start_port=22660, max_attempts=100):
    """Find a free port, preferring the one a previous proxy used (MSK_PROXY_PORT).

    Reusing the previous port lets running opencode / Claude Code sessions keep
    working across a restart. SO_REUSEADDR matches how uvicorn binds, so a port
    whose old connections are still in TIME_WAIT counts as free.
    """
    preferred = os.environ.get("MSK_PROXY_PORT", "")
    candidates = ([int(preferred)] if preferred.isdigit() else []) + list(range(start_port, start_port + max_attempts))
    for port in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((BIND_HOST, port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts}")


def main():
    token = load_token()
    if not token:
        sys.exit("Error: no MSK session token saved; run: aiportal token set")
    os.environ["WEBUI_SESSION_TOKEN"] = token

    # Clients must present this secret
    os.environ["LITELLM_MASTER_KEY"] = ensure_proxy_key()
    if not os.environ["LITELLM_MASTER_KEY"]:
        sys.exit("Error: empty proxy key; refusing to start an unauthenticated proxy")

    _disable_aiohttp_ssl()
    import litellm
    from litellm.proxy.proxy_cli import run_server

    # Request fixes and error hints (also patches litellm.completion / acompletion)
    from .callbacks import strip_params_callback
    litellm.callbacks = [strip_params_callback]

    port = find_available_port()
    hostname = socket.gethostname()
    state_dir = private_dir(host_state_dir(hostname))

    # Written last, in one step: its appearance tells the launchers where to connect
    info_path = os.path.join(state_dir, "server_info")
    tmp = f"{info_path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"hostname={hostname}\nport={port}\nbind={BIND_HOST}\n"
                f"url=http://{hostname}:{port}\nfingerprint={fingerprint()}\n")
    os.replace(tmp, info_path)

    print(f"MSK AI Portal proxy for {WEBUI_URL}")
    print(f"Listening on http://{BIND_HOST}:{port} ({hostname}); press Ctrl+C to stop")
    sys.stdout.flush()

    sys.argv = ["litellm", "--config", LITELLM_CONFIG, "--port", str(port), "--host", BIND_HOST]
    run_server()


if __name__ == "__main__":
    main()
