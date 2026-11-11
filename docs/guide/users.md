# Users and roles

Users live in **Authentik**, not in the app. There is no user to create, no
password to set and no session to end here: who may log in, and which groups
they are in, is managed in Authentik (by IT). The app reads the user from
Authentik's headers on every request — see [Authentication](auth.md).

## Roles

A role is a string on `request.user["role"]`. The app decides it from the
user's Authentik groups with `authentikRoles`:

```python
import os
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_DEV"]: "dev",
                             os.environ["GROUP_ADMIN"]: "admin"})
```

The group names are your organisation's own, so they go in the app's `.env`
(`GROUP_DEV=...`, `GROUP_ADMIN=...`), not in code.

Routes and pages can require one:

```python
@app.route('GET', '/api/users', roles=["admin"])
def users(request): ...

app.addPath('/admin', 'public/admin.html', roles=["admin", "manager"])
```

A user without a matching role gets `403`, and the refusal is written to the
audit log as `access_denied`.

| | With `roleHierarchy` | Without |
|---|---|---|
| The user's role | the highest role among their groups | the role of the first group in `authentikRoles` they are in |
| `roles=["admin"]` lets in | admin, and every role ranked above it | admin only |
| In none of the groups | the last role in `roleHierarchy` | `"user"` |

The framework only ships the concept; which roles exist and what they mean is
up to your app.

### Giving someone a role

Add them to the Authentik group that maps to it. Removing them from the group
takes the role away. Both apply on the next request Authentik sends with the
new groups — there is nothing to change in the app.

### Trying roles locally

`devUser={"username": "test", "groups": [...]}` on `settings()` makes every
request that user, without Authentik. See
[Authentication → Local development](auth.md#local-development-without-authentik).

## Command line

```bash
python -m WebServer audit [--user NAME] [--limit N]
```

Shows the audit log, newest first. Run it from your project folder: it imports
your `main.py` to use its `setDatabase(...)` configuration, so keep
`app.start()` behind `if __name__ == "__main__":`. If your app object lives
elsewhere, pass `--app module:variable`. Because it imports `main.py`, the
keys `main.py` reads (`PROXY_SECRET`, `JWT_SECRET`, group names) must be in `.env`.

There are no user, role, session or lockout commands any more.

## The old tables

`Users`, `Sessions` and `LoginAttempts` are still created and left as they
are, with whatever rows they had from before the app moved behind Authentik.
Nothing reads or writes them.
