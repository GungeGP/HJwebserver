"""Command-line access to the audit log.

    python -m WebServer [--app main:app] <command> [...]

The CLI imports your application module to reuse its setDatabase()/settings()
configuration, so keep `app.start()` behind `if __name__ == "__main__":`.

Users and their groups live in Authentik, so there are no user, role,
session or lockout commands.

Commands:
    audit [--user NAME] [--limit N]
"""

import argparse
import importlib
import os
import sys
import time


def _load_app(spec):
    module_name, _, attr = spec.partition(":")
    attr = attr or "app"
    sys.path.insert(0, os.getcwd())
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        sys.exit(f"Could not import '{module_name}': {e}. Run from your project folder or pass --app module:app")
    app = getattr(module, attr, None)
    if app is None:
        sys.exit(f"'{module_name}' has no attribute '{attr}'. Pass --app module:variable")
    return app


def _ts(epoch):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch)) if epoch else "-"


def _table(rows, columns):
    if not rows:
        print("(none)")
        return
    widths = [max(len(c), *(len(str(r[i])) for r in rows)) for i, c in enumerate(columns)]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m WebServer", description="HJwebserver audit log")
    parser.add_argument("--app", default="main:app", help="module:variable of your WebServer instance (default main:app)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("audit", help="show the audit log"); p.add_argument("--user"); p.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)
    app = _load_app(args.app)

    try:
        if args.command == "audit":
            _table([(_ts(e.At), e.Username or "", e.Event, e.Detail or "", e.Ip or "") for e in app.getAuditLog(args.limit, args.user)],
                   ["time", "user", "event", "detail", "ip"])
            return 0
    except ValueError as e:
        sys.exit(f"Error: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
