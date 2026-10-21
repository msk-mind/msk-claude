"""aiportal: manage the MSK AI Portal setup, proxy, models and token."""
import argparse
import sys

from . import __version__


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="aiportal",
        description="Manage the MSK AI Portal proxy for opencode (aiportal-opencode) and Claude Code (aiportal-claude).")
    p.add_argument("--version", action="version", version=f"aiportal {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    s = sub.add_parser("setup", help="first-time setup: token, moving over from the clone-based setup, checks")
    s.add_argument("--import", dest="imports", action="append", default=[], metavar="CLONE",
                   help="an old clone of the repository to move your token from (found automatically if "
                        "it's the current directory or its proxy is running)")
    sub.add_parser("doctor", help="check the whole setup and say what to fix")

    t = sub.add_parser("token", help="show when your session token expires")
    tsub = t.add_subparsers(dest="action", metavar="ACTION")
    tsub.add_parser("set", help="save a new session token (checked with the portal first)")

    pr = sub.add_parser("proxy", help="manage this machine's proxy")
    psub = pr.add_subparsers(dest="action", metavar="ACTION", required=True)
    psub.add_parser("status", help="where the proxy is running and whether it answers")
    psub.add_parser("logs", help="follow this machine's proxy log")
    psub.add_parser("stop", help="stop this machine's background proxy")
    psub.add_parser("start", help="run the proxy in the foreground, to watch its output")

    m = sub.add_parser("models", help="list the configured models")
    msub = m.add_subparsers(dest="action", metavar="ACTION")
    sy = msub.add_parser("sync", help="compare the model list with what the portal offers")
    sy.add_argument("--apply", action="store_true",
                    help="update the model list and README to match (in a clone of the repository)")
    sy.add_argument("--test", action="store_true", help="send a one-line prompt to every configured model")

    e = sub.add_parser("env", help="print shell exports for running `claude` yourself: eval \"$(aiportal env)\"")
    e.set_defaults(action=None)

    args = p.parse_args(argv)

    if args.command == "setup":
        from .migrate import cmd_setup
        return cmd_setup(args.imports)
    if args.command == "doctor":
        from .doctor import cmd_doctor
        return cmd_doctor()
    if args.command == "token":
        from .auth import cmd_token_set, cmd_token_show
        return cmd_token_set() if args.action == "set" else cmd_token_show()
    if args.command == "proxy":
        from . import proxy
        return {"status": proxy.cmd_status, "logs": proxy.cmd_logs,
                "stop": proxy.cmd_stop, "start": proxy.cmd_start_foreground}[args.action]()
    if args.command == "models":
        from .models import cmd_sync, model_names
        if args.action == "sync":
            return cmd_sync(apply=args.apply, test=args.test)
        print("\n".join(model_names()))
        return 0
    if args.command == "env":
        import contextlib
        import shlex
        from .launch import claude_env
        from .proxy import ensure_proxy
        with contextlib.redirect_stdout(sys.stderr):  # keep stdout to the exports only
            host, port, key = ensure_proxy()
        for name, value in claude_env(host, port, key).items():
            print(f"export {name}={shlex.quote(value)}")
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
