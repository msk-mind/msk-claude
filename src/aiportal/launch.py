"""aiportal-opencode, aiportal-claude and aiportal-omp: launch a client against the proxy."""
import argparse
import json
import os
import shutil
import sys

from .models import DEFAULT_MODEL, model_names, opencode_models
from .omp import update_providers
from .paths import host_state_dir, private_dir
from .proxy import ensure_proxy


def parse_args(prog, client, resume_help, examples, names=None, default=DEFAULT_MODEL,
               source="the models on MSK's AI Portal", add_args=None):
    """Parse a launcher's arguments; names and default are the model list (default: the AI Portal's)."""
    names = names or model_names()
    epilog = "Available models:\n" + "\n".join(
        f"  {n}{' (default)' if n == default else ''}" for n in names)
    epilog += "\n\nExamples:\n" + "\n".join(f"  {prog} {e}" for e in examples)
    epilog += "\n\nUpdate aiportal (and its model list) with: uv tool upgrade aiportal"
    p = argparse.ArgumentParser(prog=prog, description=f"Launch {client} with {source}.",
                                epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("directory", nargs="?", default=None, help="directory to work in (default: current)")
    p.add_argument("-m", "--model", default=default, metavar="MODEL", help=f"model to use (default: {default})")
    p.add_argument("-c", "--continue", dest="cont", action="store_true",
                   help="continue the most recent session in the directory")
    if client == "opencode":
        p.add_argument("-r", "--resume", "-s", "--session", dest="resume", metavar="ID", help=resume_help)
    else:
        p.add_argument("-r", "--resume", dest="resume", nargs="?", const="", metavar="ID", help=resume_help)
    if client != "omp":  # omp has no way to fork a session from the command line
        p.add_argument("--fork", action="store_true", help="with -c or -r, continue in a copy and leave the original as is")
    if add_args:
        add_args(p)
    args = p.parse_intermixed_args()
    args.fork = getattr(args, "fork", False)

    # aiportal-claude -r DIR: a directory after -r is the directory, not a session ID
    if args.resume and args.directory is None and os.path.isdir(args.resume):
        args.directory, args.resume = args.resume, ""
    if client == "opencode" and args.resume == "":
        p.error("-r needs a session ID (inside opencode, /sessions lists them; -c continues the latest)")
    if args.model not in names:
        p.error(f"unknown model '{args.model}'; choose one of: {', '.join(names)}")
    if args.fork and not (args.cont or args.resume is not None):
        p.error("--fork needs -c or -r")
    args.directory = os.path.abspath(args.directory or ".")
    if not os.path.isdir(args.directory):
        p.error(f"directory does not exist: {args.directory}")
    if not shutil.which(client):
        sys.exit(f"Error: {client} is not installed or not on your PATH")
    return args


def opencode_main():
    args = parse_args(
        "aiportal-opencode", "opencode",
        "resume a specific session (inside opencode, /sessions lists them)",
        ["", "~/project", "-m gpt-5.6-terra", "-c   # pick up where you left off",
         "-r ses_abc123 --fork   # branch off an earlier session"])
    resume = (["--continue"] if args.cont else []) + (["--session", args.resume] if args.resume else [])
    if args.fork:
        resume.append("--fork")

    host, port, key = ensure_proxy()
    # An MSK-only config layered over the user's global opencode config via
    # OPENCODE_CONFIG; the key comes from the environment, so it isn't in the file
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"msk/{args.model}",
        "provider": {
            "msk": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "MSK AI Copilot",
                "options": {"baseURL": f"http://{host}:{port}/v1", "apiKey": "{env:MSK_PROXY_KEY}"},
                "models": opencode_models(),
            }
        },
    }
    config_path = os.path.join(private_dir(host_state_dir()), "opencode.json")
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)

    env = dict(os.environ, OPENCODE_CONFIG=config_path, MSK_PROXY_KEY=key)
    print(f"Launching opencode with msk/{args.model} in {args.directory}")
    sys.stdout.flush()  # exec replaces this process, dropping anything still buffered
    os.execvpe("opencode", ["opencode", *resume, args.directory], env)


def omp_provider(host, port):
    """The "msk" provider for omp's models.yml; the key comes from MSK_PROXY_KEY."""
    models = []
    for name, entry in opencode_models().items():
        model = {"id": name, "name": entry["name"], "input": ["text", "image"] if entry["attachment"] else ["text"]}
        if "limit" in entry:
            model.update(contextWindow=entry["limit"]["context"], maxTokens=entry["limit"]["output"])
        models.append(model)
    return {"baseUrl": f"http://{host}:{port}/v1", "api": "openai-completions",
            "apiKey": "MSK_PROXY_KEY", "models": models}


def omp_main():
    args = parse_args(
        "aiportal-omp", "omp",
        "resume a session by ID; without an ID, pick one from a list",
        ["", "~/project", "-m gpt-5.6-terra", "-c   # pick up where you left off",
         "-r   # choose a session to resume"])
    resume = (["--continue"] if args.cont else []) + (
        ["--resume"] + ([args.resume] if args.resume else []) if args.resume is not None else [])

    host, port, key = ensure_proxy()
    # omp only reads providers from its models.yml, which machines sharing a home
    # directory share too: the "msk" provider points at the last-launched machine's proxy
    update_providers({"msk": omp_provider(host, port)})
    env = dict(os.environ, MSK_PROXY_KEY=key)
    print(f"Launching omp with msk/{args.model} in {args.directory}")
    sys.stdout.flush()
    os.execvpe("omp", ["omp", "--model", f"msk/{args.model}", "--cwd", args.directory, *resume], env)


# Keep Claude Code from contacting Anthropic directly
CLAUDE_PRIVACY_ENV = {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}


def claude_env(host, port, key):
    return {"ANTHROPIC_BASE_URL": f"http://{host}:{port}", "ANTHROPIC_AUTH_TOKEN": key, **CLAUDE_PRIVACY_ENV}


def claude_main():
    args = parse_args(
        "aiportal-claude", "claude",
        "resume a conversation; without an ID, pick one from a list",
        ["", "~/project", "-m claude-opus-5.5", "-c   # pick up where you left off",
         "-r   # choose a conversation to resume"])
    resume = (["--continue"] if args.cont else []) + (
        ["--resume"] + ([args.resume] if args.resume else []) if args.resume is not None else [])
    if args.fork:
        resume.append("--fork-session")

    host, port, key = ensure_proxy()
    env = dict(os.environ, **claude_env(host, port, key))
    os.chdir(args.directory)
    print(f"Launching Claude Code with {args.model} in {args.directory}")
    sys.stdout.flush()  # exec replaces this process, dropping anything still buffered
    os.execvpe("claude", ["claude", "--model", args.model, *resume], env)
