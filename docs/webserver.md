# `WebServer` reference

```python
from WebServer import WebServer
app = WebServer(port=8080)
```

Everything you do goes through this one object. Methods are listed in the order
you typically call them.

---

## `WebServer(host="127.0.0.1", port=8000, static_dir=None)`

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `host` | `"127.0.0.1"` | Interface to listen on. Use `"0.0.0.0"` to accept connections from other machines. |
| `port` | `8000` | TCP port. |
| `static_dir` | `None` | Folder to serve static files from. When omitted the framework looks for a `public/` folder next to your script, then in the current directory. |

On startup it prints which folder (if any) is used for static files.

---

## `app.setDatabase(type="mssql", server="localhost", dbName="test", user=None, password=None, port=None, createTables=True)`

Configure the database. See [Database](database.md) for backend details.

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `type` | `"mssql"` | `"sqlite"`, `"mssql"` or `"mysql"`. Anything else raises `ValueError`. |
| `server` | `"localhost"` | Hostname of the database server. Ignored for sqlite. |
| `dbName` | `"test"` | Database name. For sqlite: path to the `.db` file (created if missing). |
| `user` | `None` | Username. Required for mysql. For mssql, leave empty to use Windows authentication. |
| `password` | `None` | Password for `user`. |
| `port` | `None` | Port override. Defaults: mssql 1433, mysql 3306. |
| `createTables` | `True` | Create the framework tables (`Users`, `Sessions`, `AuditLog`, `WorkTimeEntries`) if they don't exist. Pass `False` if the schema is managed elsewhere. |

```python
app.setDatabase(type="sqlite", dbName="workTime.db")
app.setDatabase(type="mssql", server="db01", dbName="workTime")                    # Windows auth
app.setDatabase(type="mssql", server="db01", dbName="workTime", user="sa", password="…")
app.setDatabase(type="mysql", server="db01", dbName="workTime", user="root", password="…")
```

Note: with `createTables=True` (the default) a connection is opened immediately,
so wrong credentials fail here rather than on the first request.

---

## `app.settings(auth=None, ...)`

Turn on authentication and tune security. See [Authentication](auth.md).

```python
app.settings(auth=True)                                   # sensible defaults
app.settings(auth=True, tokenLifetimeHours=8, maxLoginAttempts=3)
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `auth` | `None` | `True` enables login. **Every route and page then requires login** unless registered with `public=True`. |
| `jwtSecret` | `None` | Secret used to sign sessions, at least 32 bytes. Defaults to `JWT_SECRET` from `.env`. Missing or too short → `RuntimeError` at startup. |
| `tokenLifetimeHours` | `24` | How long a login stays valid before the user has to sign in again. |
| `secureCookie` | `False` | Add the `Secure` flag to the session cookie. Turned on automatically by `useHttps()`. |
| `bearerTokens` | `True` | Also accept `Authorization: Bearer <token>` (for scripts). `False` = cookie only. |
| `maxLoginAttempts` | `5` | Failed logins (per username *and* per IP) before a lockout. |
| `lockoutMinutes` | `15` | How long a lockout lasts. |
| `minPasswordLength` | `5` | Enforced by `createUser` / `setPassword`. |
| `auditLog` | `True` | Write logins, logouts, lockouts and user changes to the `AuditLog` table. |
| `trustProxy` | `False` | Take the client IP from `X-Forwarded-For`. Only set behind a reverse proxy you control. |
| `csp` | a default policy | `Content-Security-Policy` header value. `None` sends none. See [Authentication → Security headers](auth.md#security-headers). |
| `securityHeaders` | `True` | Send `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP (and HSTS on HTTPS). |

Calling `settings()` without `auth=True` (or not at all) leaves the server fully open.

---

## `app.useHttps(certfile, keyfile)`

Serve over TLS. Takes paths to a PEM certificate and private key. Also turns
on the `Secure` cookie flag and the HSTS header.

```python
app.useHttps("cert.pem", "key.pem")
```

For a local self-signed pair (browsers will warn once):

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

Raises `FileNotFoundError` if either file is missing.

---

## `app.addPath(url_path, file_path, public=False)`

Serve one file at a fixed URL.

| Parameter | Meaning |
|-----------|---------|
| `url_path` | URL to respond on, e.g. `'/'` or `'/report'`. |
| `file_path` | File to send, relative to the project root, e.g. `'public/index.html'`. |
| `public` | When auth is on: `True` makes this page viewable without login. |

```python
app.addPath('/', 'public/index.html')
app.addPath('/about', 'public/about.html', public=True)
```

HTML files get the framework scripts injected. Other files are sent as-is with a
content type guessed from the extension.

---

## `@app.route(method, path, public=False)`

Register a handler function for a URL. See [Routes & requests](routes.md).

| Parameter | Meaning |
|-----------|---------|
| `method` | `'GET'`, `'POST'`, `'PUT'` or `'DELETE'`. |
| `path` | Exact URL path, e.g. `'/api/data'`. Query strings are ignored for matching. |
| `public` | When auth is on: `True` lets anyone call this route. |

```python
@app.route('POST', '/api/data')
def save(request):
    ...
```

The decorated function receives one argument, the request. It must write a
response itself (see [Routes & requests](routes.md#sending-a-response)).

---

## `app.createUser(username, password)`

Create a login. The password is hashed before it is stored.

| Returns | Meaning |
|---------|---------|
| `True` | User created. |
| `False` | Username already exists; nothing changed. |

Raises `ValueError` if the username is empty or the password is shorter than
`minPasswordLength` (default 5). Requires `setDatabase` first.

```python
app.createUser("alice", "correct-horse-battery")
```

Safe to leave in `main.py`: on later runs it just returns `False`.

---

## `app.setPassword(username, password)`

Replace a user's password (hashed) and log them out everywhere.

| Returns | Meaning |
|---------|---------|
| `True` | Password updated, all sessions revoked. |
| `False` | No such user. |

Raises `ValueError` if the password is shorter than `minPasswordLength`.

---

## `app.deleteUser(username)`

Remove the user and all their sessions. Returns `True`, or `False` if no such user.

---

## `app.revokeSessions(username)`

Log a user out of every browser and device immediately. Their next request gets `401`.

---

## `app.getSessions(username)`

List of active sessions for a user. Each row has `Jti`, `Username`, `CreatedAt`,
`ExpiresAt` (epoch seconds).

---

## `app.audit(request, event, detail=None)`

Write your own entry to the audit log, attributed to the request's user and IP.

```python
@app.route('DELETE', '/api/entries')
def wipe(request):
    app.audit(request, "entries_wiped", f"count={n}")
```

---

## `app.getAuditLog(limit=100, username=None)`

Most recent audit entries, newest first. Rows have `Id`, `At` (epoch seconds),
`Username`, `Event`, `Detail`, `Ip`. See [Authentication → Audit log](auth.md#audit-log)
for the built-in event names.

---

## `app.start()`

Start listening. Blocks until Ctrl+C. Always the last call.

---

## Less common

### `app.checkAuth(request)`

Returns `{"username": ...}` if the request carries a valid session, else `None`.
Inside a protected route you don't need this — `request.user` is already set.
It is for `public=True` routes that want to behave differently for logged-in users.

### `app.getDatabaseConnection()`

Returns a raw DB-API connection for the configured backend, for queries the
helpers don't cover. You must `close()` it. See [Database](database.md#your-own-queries)
for the higher-level helpers, which are usually easier.

### `app.createAuth(username)`

Returns a signed session token for `username` without checking a password.
Useful for scripts or tests that call the API with `Authorization: Bearer <token>`.
Requires `settings(auth=True)`.
