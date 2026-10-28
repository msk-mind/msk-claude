"""databricks-opencode, databricks-claude and databricks-omp: launch a client against a
Databricks workspace's Foundation Model API endpoints.

No proxy is needed: Databricks serves Anthropic-format requests at
<host>/serving-endpoints/anthropic and OpenAI Responses requests at
<host>/serving-endpoints/responses. The workspace and token come from a profile in
~/.databrickscfg. The token is passed to the client in an environment variable, so it
is never written to a config file.
"""
import configparser
import json
import os
import shutil
import subprocess
import sys

from .launch import CLAUDE_PRIVACY_ENV, parse_args
from .omp import update_providers
from .paths import host_state_dir, private_dir

# Models tested with tool calls in opencode. Names are the serving endpoint names
# without their "databricks-" prefix. Limits: the Claude endpoints report a
# 1,000,000-token maximum; the GPT ones follow OpenAI's published limits.
CLAUDE_MODELS = {
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-haiku-5-5": "Claude Haiku 5.5",
}
GPT_MODELS = {
    "gpt-6-sol": "GPT-6 Sol",
    "gpt-5-6-terra": "GPT-5.6 Terra",
}
CLAUDE_LIMIT = {"context": 1_000_000, "output": 128_000}
GPT_LIMIT = {"context": 1_050_000, "input": 922_000, "output": 128_000}
DEFAULT_MODEL = "claude-sonnet-5-5"

# Not DATABRICKS_TOKEN: that would also change what the databricks CLI does inside the session
TOKEN_ENV = "DATABRICKS_FMAPI_TOKEN"
CLAUDE_PROVIDER = "databricks-claude"
OPENAI_PROVIDER = "databricks-openai"


def endpoint(model):
    return f"databricks-{model}"


def _provider(model):
    return CLAUDE_PROVIDER if model in CLAUDE_MODELS else OPENAI_PROVIDER


def _add_profile_arg(p):
    default = os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT")
    p.add_argument("-p", "--profile", default=default,
                   help=f"profile in ~/.databrickscfg to use (default: {default})")


def workspace(profile):
    """The (host, token) of a ~/.databrickscfg profile."""
    path = os.environ.get("DATABRICKS_CONFIG_FILE") or os.path.expanduser("~/.databrickscfg")
    # [DEFAULT] is an ordinary profile in .databrickscfg, not configparser's defaults section
    cfg = configparser.ConfigParser(default_section="\0", interpolation=None)
    cfg.read(path)
    if not cfg.has_section(profile):
        profiles = ", ".join(cfg.sections()) or "none"
        sys.exit(f"Error: no profile '{profile}' in {path} (profiles: {profiles}).\n"
                 f"Add one with: databricks auth login --profile {profile}")
    section = cfg[profile]
    host = section.get("host", "").rstrip("/")
    if not host:
        sys.exit(f"Error: profile '{profile}' in {path} has no host")
    if not host.startswith("http"):
        host = f"https://{host}"
    token = section.get("token")
    if token:
        return host, token
    # OAuth profile: ask the CLI for an access token
    if not shutil.which("databricks"):
        sys.exit(f"Error: profile '{profile}' has no token, and the databricks CLI isn't installed to get one")
    result = subprocess.run(["databricks", "auth", "token", "--profile", profile, "-o", "json"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"Error: couldn't get a token for profile '{profile}':\n{result.stderr.strip()}\n"
                 f"Log in again with: databricks auth login --profile {profile}")
    print(f"Note: profile '{profile}' uses OAuth, whose tokens last about an hour; when requests "
          "start failing, quit and continue the session (-c). A profile with a personal access "
          "token avoids this.", file=sys.stderr)
    return host, json.loads(result.stdout)["access_token"]


def _resume_args(args, fork_flag):
    resume = ["--continue"] if args.cont else []
    if args.resume is not None:
        resume += ["--resume"] + ([args.resume] if args.resume else [])
    if args.fork:
        resume.append(fork_flag)
    return resume


# --- opencode -----------------------------------------------------------------

def opencode_config(host, model):
    def models(names, limit):
        return {endpoint(m): {"name": label, "limit": limit} for m, label in names.items()}

    return {
        "$schema": "https://opencode.ai/config.json",
        "model": f"{_provider(model)}/{endpoint(model)}",
        "provider": {
            CLAUDE_PROVIDER: {
                "npm": "@ai-sdk/anthropic",
                "name": "Databricks (Claude)",
                # Databricks only accepts the token as a bearer token, not as x-api-key
                "options": {"baseURL": f"{host}/serving-endpoints/anthropic/v1", "apiKey": "unused",
                            "headers": {"Authorization": f"Bearer {{env:{TOKEN_ENV}}}"}},
                "models": models(CLAUDE_MODELS, CLAUDE_LIMIT),
            },
            OPENAI_PROVIDER: {
                # The Responses API: GPT models refuse tools with reasoning on chat completions
                "npm": "@ai-sdk/openai",
                "name": "Databricks (OpenAI)",
                "options": {"baseURL": f"{host}/serving-endpoints", "apiKey": f"{{env:{TOKEN_ENV}}}"},
                "models": models(GPT_MODELS, GPT_LIMIT),
            },
        },
    }


def opencode_main():
    args = parse_args(
        "databricks-opencode", "opencode",
        "resume a specific session (inside opencode, /sessions lists them)",
        ["", "~/project", "-m gpt-6-sol", "-p dev   # another workspace",
         "-c   # pick up where you left off"],
        names=[*CLAUDE_MODELS, *GPT_MODELS], default=DEFAULT_MODEL,
        source="the models on a Databricks workspace", add_args=_add_profile_arg)
    resume = (["--continue"] if args.cont else []) + (["--session", args.resume] if args.resume else [])
    if args.fork:
        resume.append("--fork")

    host, token = workspace(args.profile)
    config_path = os.path.join(private_dir(host_state_dir()), "databricks-opencode.json")
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(opencode_config(host, args.model), f, indent=2)

    env = dict(os.environ, OPENCODE_CONFIG=config_path, **{TOKEN_ENV: token})
    print(f"Launching opencode with {endpoint(args.model)} on {host} (profile {args.profile}) in {args.directory}")
    sys.stdout.flush()  # exec replaces this process, dropping anything still buffered
    os.execvpe("opencode", ["opencode", *resume, args.directory], env)


# --- Claude Code --------------------------------------------------------------

def claude_main():
    args = parse_args(
        "databricks-claude", "claude",
        "resume a conversation; without an ID, pick one from a list",
        ["", "~/project", "-m claude-opus-5-5", "-p dev   # another workspace",
         "-c   # pick up where you left off"],
        names=list(CLAUDE_MODELS), default=DEFAULT_MODEL,
        source="the Claude models on a Databricks workspace", add_args=_add_profile_arg)
    resume = _resume_args(args, "--fork-session")

    host, token = workspace(args.profile)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # it would take precedence
    env.update(CLAUDE_PRIVACY_ENV,
               ANTHROPIC_BASE_URL=f"{host}/serving-endpoints/anthropic",
               ANTHROPIC_AUTH_TOKEN=token,
               # Claude Code's opus/sonnet/haiku aliases and background tasks use these
               ANTHROPIC_DEFAULT_OPUS_MODEL=endpoint("claude-opus-5-5"),
               ANTHROPIC_DEFAULT_SONNET_MODEL=endpoint("claude-sonnet-5-5"),
               ANTHROPIC_DEFAULT_HAIKU_MODEL=endpoint("claude-haiku-5-5"),
               CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="1")
    os.chdir(args.directory)
    print(f"Launching Claude Code with {endpoint(args.model)} on {host} (profile {args.profile}) in {args.directory}")
    sys.stdout.flush()
    os.execvpe("claude", ["claude", "--model", endpoint(args.model), *resume], env)


# --- omp ----------------------------------------------------------------------

def omp_providers(host):
    def models(names, limit, **extra):
        return [{"id": endpoint(m), "name": label, "contextWindow": limit.get("input", limit["context"]),
                 "maxTokens": limit["output"], "reasoning": True, "input": ["text", "image"], **extra}
                for m, label in names.items()]

    return {
        CLAUDE_PROVIDER: {
            "baseUrl": f"{host}/serving-endpoints/anthropic",
            "api": "anthropic-messages",
            "apiKey": TOKEN_ENV,  # omp reads the named environment variable
            "authHeader": True,  # Databricks only accepts a bearer token
            # omp sends Claude Code's beta flags, which Databricks rejects; replace them
            "headers": {"anthropic-beta": "interleaved-thinking-2025-05-14"},
            "models": models(
                CLAUDE_MODELS, CLAUDE_LIMIT,
                compat={"allowAnthropicHeaderOverrides": True},
                # omp doesn't recognize these ids as Claude 5.5, which only takes adaptive thinking
                thinking={"mode": "anthropic-adaptive", "efforts": ["low", "medium", "high", "xhigh", "max"]}),
        },
        OPENAI_PROVIDER: {
            "baseUrl": f"{host}/serving-endpoints",
            "api": "openai-responses",
            "apiKey": TOKEN_ENV,
            "models": models(GPT_MODELS, GPT_LIMIT),
        },
    }


def omp_main():
    args = parse_args(
        "databricks-omp", "omp",
        "resume a session by ID; without an ID, pick one from a list",
        ["", "~/project", "-m gpt-6-sol", "-p dev   # another workspace",
         "-c   # pick up where you left off"],
        names=[*CLAUDE_MODELS, *GPT_MODELS], default=DEFAULT_MODEL,
        source="the models on a Databricks workspace", add_args=_add_profile_arg)
    resume = _resume_args(args, None)

    host, token = workspace(args.profile)
    update_providers(omp_providers(host))
    env = dict(os.environ, **{TOKEN_ENV: token})
    model = f"{_provider(args.model)}/{endpoint(args.model)}"
    print(f"Launching omp with {endpoint(args.model)} on {host} (profile {args.profile}) in {args.directory}")
    sys.stdout.flush()
    os.execvpe("omp", ["omp", "--model", model, "--cwd", args.directory, *resume], env)
