#!/usr/bin/env python3
import ssl
import os
import sys

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

# Run litellm
from litellm.proxy.proxy_cli import run_server

if __name__ == "__main__":
    sys.argv = [
        "litellm",
        "--config", "litellm_config.yaml",
        "--port", "22660",
        "--host", "127.0.0.1"
    ]
    run_server()
