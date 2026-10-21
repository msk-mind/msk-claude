"""The MSK AI Portal session token: reading, checking and saving it."""
import base64
import getpass
import json
import os
import re
import stat
import sys
import tempfile
import time

from .paths import API_BASE, AUTH_PATH, CONFIG_DIR, WEBUI_URL, private_dir

TOKEN_WARN_DAYS = 2

TOKEN_HELP = f"""To get a new token:
  1. Visit {WEBUI_URL} and log in
  2. Open Developer Tools (F12; Cmd+Option+I on a Mac)
  3. Go to the cookies for that site:
       Chrome/Edge: Application tab -> Cookies;  Firefox/Safari: Storage tab -> Cookies
  4. Copy the value of the 'token' cookie
  5. Run: aiportal token set"""

ENV_TOKEN_HINT = (f"WEBUI_SESSION_TOKEN is set in your shell, but aiportal only reads {AUTH_PATH}.\n"
                  "Save it there with: printenv WEBUI_SESSION_TOKEN | aiportal token set")


def load_token():
    """The saved token, or None. The environment is deliberately ignored: the proxy reads the file."""
    try:
        text = open(AUTH_PATH).read()
    except FileNotFoundError:
        return None
    m = re.search(r"WEBUI_SESSION_TOKEN=['\"]?([^'\"\n]+)", text)
    return m.group(1) if m else None


def token_expiry(token):
    """The token's expiry as a Unix time, or None if it isn't a JWT with an exp claim."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("exp")
    except Exception:
        return None


def format_time(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def restrict_to_owner(path):
    """Make a secret file readable only by its owner; returns True if it had to be tightened."""
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return True
    return False


def check_token(quiet=False):
    """True if a usable token is saved. Explains the problem (and near-expiry) unless quiet."""
    say = (lambda *a: None) if quiet else print
    if os.path.exists(AUTH_PATH) and restrict_to_owner(AUTH_PATH):
        say(f"Note: {AUTH_PATH} was readable by other users; restricted it to you.")
    token = load_token()
    if not token:
        if os.environ.get("WEBUI_SESSION_TOKEN"):
            say(f"Error: no token saved.\n{ENV_TOKEN_HINT}")
        else:
            say(f"Error: no MSK session token saved yet.\n\n{TOKEN_HELP}")
        return False
    exp = token_expiry(token)
    if exp is None:
        return True
    remaining = exp - time.time()
    if remaining <= 0:
        say(f"Error: your MSK session token expired on {format_time(exp)}.\n\n{TOKEN_HELP}")
        return False
    if remaining < TOKEN_WARN_DAYS * 86400:
        say(f"Warning: your MSK session token expires in {round(remaining / 3600)}h "
            f"({format_time(exp)}).\n\n{TOKEN_HELP}\n")
    return True


def verify_token(token):
    """True if the portal accepts the token, False if it rejects it, None if it can't be reached."""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        r = requests.get(f"{API_BASE}/auths/", headers={"Authorization": f"Bearer {token}"},
                         verify=False, timeout=20)
    except requests.RequestException:
        return None
    if r.status_code in (401, 403):
        return False
    return r.ok or None


def write_auth_file(token):
    """Replace the token file in one step, readable only by its owner."""
    private_dir(CONFIG_DIR)
    fd, tmp = tempfile.mkstemp(prefix="auth.env.", dir=CONFIG_DIR)  # created 0600
    with os.fdopen(fd, "w") as f:
        f.write(f"export WEBUI_SESSION_TOKEN='{token}'\n")
    os.replace(tmp, AUTH_PATH)


def parse_pasted_token(raw):
    """Accept a bare token or a pasted line like: export WEBUI_SESSION_TOKEN='...'"""
    return re.sub(r"^\s*(export\s+)?(WEBUI_SESSION_TOKEN=)?", "", raw.strip()).strip("'\" ")


def save_token(token):
    """Check a token with the portal and save it. Returns True on success."""
    if not token:
        print("No token entered; nothing changed.")
        return False
    exp = token_expiry(token)
    if exp is not None and exp <= time.time():
        print("Error: that token has already expired; log in again and copy a fresh one.")
        return False
    ok = verify_token(token)
    if ok is False:
        print("Error: the portal rejected that token; nothing changed. "
              "Make sure you copied the whole 'token' cookie.")
        return False
    write_auth_file(token)
    print(f"Saved the token to {AUTH_PATH} (readable only by you).")
    if ok is None:
        print(f"Warning: couldn't reach {WEBUI_URL} to check it.")
    if exp is not None:
        print(f"It is valid until {format_time(exp)}.")
    return True


def cmd_token_set():
    if sys.stdin.isatty():
        print(f"Paste your session token from {WEBUI_URL} (the 'token' cookie).")
        raw = getpass.getpass("Token (input hidden): ")
    else:
        raw = sys.stdin.read()
    if not save_token(parse_pasted_token(raw)):
        return 1
    print("The proxy picks it up on your next aiportal-opencode / aiportal-claude launch.")
    return 0


def cmd_token_show():
    if not check_token():
        return 1
    exp = token_expiry(load_token())
    if exp:
        print(f"Token is valid until {format_time(exp)}.")
    return 0
