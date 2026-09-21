"""Command-line user management.

    python -m WebServer [--app main:app] <command> [...]

The CLI imports your application module to reuse its setDatabase()/settings()
configuration, so keep `app.start()` behind `if __name__ == "__main__":`.

Commands:
    createuser <name> [--role R] [--password P] [--temporary]
    setpassword <name> [--password P] [--temporary]
    setrole <name> <role>
    disable <name> | enable <name> | deleteuser <name>
    listusers | user <name>
    sessions <name> | revoke <name>
    lockouts | unlock [<name>] [--ip IP]
    audit [--user NAME] [--limit N]
"""

import argparse
import getpass
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


def _password(args):
    if args.password:
        return args.password
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        sys.exit("Passwords do not match.")
    return first


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
    parser = argparse.ArgumentParser(prog="python -m WebServer", description="HJwebserver user management")
    parser.add_argument("--app", default="main:app", help="module:variable of your WebServer instance (default main:app)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("createuser", help="create a user"); p.add_argument("name")
    p.add_argument("--role", default="user"); p.add_argument("--password")
    p.add_argument("--temporary", action="store_true", help="user must change the password at first login")

    p = sub.add_parser("setpassword", help="set a user's password (logs them out everywhere)"); p.add_argument("name")
    p.add_argument("--password"); p.add_argument("--temporary", action="store_true")

    p = sub.add_parser("setrole", help="change a user's role"); p.add_argument("name"); p.add_argument("role")
    p = sub.add_parser("disable", help="block logins, keep the account"); p.add_argument("name")
    p = sub.add_parser("enable", help="re-enable a disabled account"); p.add_argument("name")
    p = sub.add_parser("deleteuser", help="delete a user"); p.add_argument("name")
    sub.add_parser("listusers", help="list all users")
    p = sub.add_parser("user", help="show one user"); p.add_argument("name")
    p = sub.add_parser("sessions", help="list a user's active sessions"); p.add_argument("name")
    p = sub.add_parser("revoke", help="log a user out everywhere"); p.add_argument("name")
    sub.add_parser("lockouts", help="show current login lockouts")
    p = sub.add_parser("unlock", help="lift lockouts"); p.add_argument("name", nargs="?"); p.add_argument("--ip")
    p = sub.add_parser("audit", help="show the audit log"); p.add_argument("--user"); p.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)
    app = _load_app(args.app)

    def done(ok, yes, no):
        print(yes if ok else no)
        return 0 if ok else 1

    try:
        if args.command == "createuser":
            ok = app.createUser(args.name, _password(args), role=args.role, mustChangePassword=args.temporary)
            return done(ok, f"Created {args.name} ({args.role}).", f"{args.name} already exists.")
        if args.command == "setpassword":
            ok = app.setPassword(args.name, _password(args), mustChangePassword=args.temporary)
            return done(ok, f"Password set for {args.name}.", f"No such user: {args.name}")
        if args.command == "setrole":
            return done(app.setRole(args.name, args.role), f"{args.name} is now {args.role}.", f"No such user: {args.name}")
        if args.command == "disable":
            return done(app.disableUser(args.name), f"{args.name} disabled.", f"No such user: {args.name}")
        if args.command == "enable":
            return done(app.enableUser(args.name), f"{args.name} enabled.", f"No such user: {args.name}")
        if args.command == "deleteuser":
            return done(app.deleteUser(args.name), f"{args.name} deleted.", f"No such user: {args.name}")
        if args.command == "listusers":
            _table([(u["username"], u["role"], "yes" if u["disabled"] else "", "yes" if u["mustChangePassword"] else "")
                    for u in app.listUsers()], ["username", "role", "disabled", "must change pw"])
            return 0
        if args.command == "user":
            u = app.getUser(args.name)
            if not u:
                return done(False, "", f"No such user: {args.name}")
            for k, v in u.items():
                print(f"{k}: {v}")
            return 0
        if args.command == "sessions":
            _table([(s.Jti[:8] + "…", _ts(s.CreatedAt), _ts(s.LastSeen), _ts(s.ExpiresAt)) for s in app.getSessions(args.name)],
                   ["session", "created", "last seen", "expires"])
            return 0
        if args.command == "revoke":
            app.revokeSessions(args.name); print(f"All sessions for {args.name} revoked."); return 0
        if args.command == "lockouts":
            _table([(l["type"], l["value"], l["failures"], f'{l["remaining"]}s') for l in app.getLockouts()],
                   ["type", "value", "failures", "remaining"])
            return 0
        if args.command == "unlock":
            n = app.unlock(args.name, args.ip); print(f"Removed {n} lockout entr{'y' if n == 1 else 'ies'}."); return 0
        if args.command == "audit":
            _table([(_ts(e.At), e.Username or "", e.Event, e.Detail or "", e.Ip or "") for e in app.getAuditLog(args.limit, args.user)],
                   ["time", "user", "event", "detail", "ip"])
            return 0
    except ValueError as e:
        sys.exit(f"Error: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
