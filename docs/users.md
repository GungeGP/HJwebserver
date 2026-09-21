# Managing users

Users are managed by an administrator, either from the command line or from
Python. There is no self-registration.

## Command line

```bash
python -m WebServer <command> [options]
```

Run it from your project folder. The CLI imports your `main.py` to pick up the
`setDatabase(...)` and `settings(...)` configuration, so keep `app.start()`
behind `if __name__ == "__main__":`. If your app object lives elsewhere, pass
`--app module:variable`.

| Command | What it does |
|---------|--------------|
| `createuser <name> [--role R] [--temporary] [--password P]` | Create a user. Prompts for the password if `--password` is omitted. `--temporary` forces a password change at first login. |
| `setpassword <name> [--temporary] [--password P]` | Reset a password. Logs the user out everywhere. |
| `setrole <name> <role>` | Change the role (takes effect on the user's next request). |
| `disable <name>` / `enable <name>` | Block or re-allow logins. Disabling also ends all sessions. The account and its history are kept. |
| `deleteuser <name>` | Remove the user and their sessions. |
| `listusers` / `user <name>` | Show users, roles and flags. |
| `sessions <name>` | Active sessions with created / last-seen / expiry times. |
| `revoke <name>` | Log the user out everywhere. |
| `lockouts` / `unlock [<name>] [--ip IP]` | Show or lift login lockouts. `unlock` with no arguments clears all. |
| `audit [--user NAME] [--limit N]` | Show the audit log, newest first. |

Typical first setup:

```bash
python -m WebServer createuser admin --role admin
python -m WebServer createuser alice --temporary      # alice picks her own password at first login
```

Exit code is `0` on success, `1` when the user was not found / already exists,
and the message says which.

## From Python

Every CLI command is a method on `app`, useful for seed scripts:

```python
app.createUser("alice", "s3cret-pass", role="user", mustChangePassword=True)   # False if exists
app.setPassword("alice", "temporary-pass", mustChangePassword=True)           # False if no such user
app.setRole("alice", "admin")
app.disableUser("alice"); app.enableUser("alice")
app.deleteUser("alice")
app.getUser("alice")     # {"username", "role", "disabled", "mustChangePassword"} or None
app.listUsers()          # list of the same dicts
app.getSessions("alice"); app.revokeSessions("alice")
app.getLockouts(); app.unlock("alice")
app.getAuditLog(limit=50, username="alice")
```

Usernames are case-insensitive and stored lower-case; `"Alice"` and `"alice"`
are the same account on every backend.

## Roles

A role is a free-form string on the user (`"user"` by default). Routes and
pages can require one:

```python
@app.route('GET', '/api/users', roles=["admin"])
def users(request): ...

app.addPath('/admin', 'public/admin.html', roles=["admin", "manager"])
```

A logged-in user without a matching role gets `403`. Inside any handler,
`request.user["role"]` tells you the caller's role. Role changes are read from
the database on every request, so `setrole` applies immediately.

The framework only ships the concept; which roles exist and what they mean is
up to your app.

## Temporary passwords

`createuser --temporary` / `setpassword --temporary` (or `mustChangePassword=True`
in Python) mark the account. On the next login the user sees a change-password
form and cannot reach any page or API route until they set a new password. The
`Users` row keeps `MustChangePassword = 1` until they do.

## Disabling vs. deleting

| | `disable` | `deleteuser` |
|-|-----------|--------------|
| Can log in | no (`403 This account is disabled`) | no (`401`, same as unknown user) |
| Existing sessions | ended immediately | ended immediately |
| Row in `Users` | kept | removed |
| Audit history | kept, still attributed | kept, but the user no longer exists |
| Reversible | `enable` | no |

Prefer `disable` for people who leave; delete only test accounts.
