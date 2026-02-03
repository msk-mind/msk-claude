#!/usr/bin/env python3
import ssl
import os
import sys
import socket

# Add script directory to Python path for custom callbacks
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Disable SSL verification globally
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''

# Patch aiohttp to disable SSL verification
import aiohttp
from aiohttp import TCPConnector

original_init = TCPConnector.__init__

def patched_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    return original_init(self, *args, **kwargs)

TCPConnector.__init__ = patched_init

def find_available_port(start_port=22660, max_attempts=100):
    """Find the next available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts}")

# Run litellm
from litellm.proxy.proxy_cli import run_server
import litellm

# Register custom callback to strip unsupported params
from custom_callbacks import strip_params_callback
litellm.callbacks = [strip_params_callback]
print("Registered custom callback: StripUnsupportedParams")

if __name__ == "__main__":
    port = find_available_port()
    hostname = socket.gethostname()

    # Write port to file for connect_claude.sh to read
    port_file = os.path.join(os.path.dirname(__file__), '.litellm_port')
    with open(port_file, 'w') as f:
        f.write(str(port))

    # Write server info to file for remote connections
    info_file = os.path.join(os.path.dirname(__file__), '.litellm_server_info')
    with open(info_file, 'w') as f:
        f.write(f"hostname={hostname}\n")
        f.write(f"port={port}\n")
        f.write(f"url=http://{hostname}:{port}\n")

    print(f"Server hostname: {hostname}")
    print(f"Using port: {port}")
    print(f"Server URL: http://{hostname}:{port}")
    print(f"Port written to: {port_file}")
    print(f"Server info written to: {info_file}")

    sys.argv = [
        "litellm",
        "--config", "litellm_config.yaml",
        "--port", str(port),
        "--host", "0.0.0.0"
    ]
    run_server()
