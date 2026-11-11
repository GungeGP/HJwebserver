# `WebServer` reference

```python
from WebServer import WebServer
app = WebServer(port=8080)
```

Everything you do goes through this one object. Methods are listed in the order
you typically call them.

---

## `WebServer(host="127.0.0.1", port=8000, static_dir=None, threaded=True)`

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `host` | `"127.0.0.1"` | Interface to listen on. Use `"0.0.0.0"` to accept connections from other machines, e.g. from the proxy in front of the app. |
| `port` | `8000` | TCP port. |
| `static_dir` | `None` | Folder to serve static files from. When omitted the framework looks for a `public/` folder next to your script, then in the current directory. |
| `threaded` | `True` | Handle requests at the same time, each in its own thread. `False` handles one request at a time, as before. See [Threads](#threads). |

On startup it prints which folder (if any) is used for static files.

It also reads `.env`, so `os.environ` holds your keys from the next line on —
before `settings()`:

```python
import os
app = WebServer(host="0.0.0.0", port=8080)   # reads .env
group = os.environ["GROUP_ADMIN"]
```

### Threads

With `threaded=True` (the default) a slow request, such as a big table
export or a call to another service, no longer makes everyone else wait.
At most `app.max_threads` requests (default 32) run at once; more wait in line.

The framework's own code is safe with threads: every query opens its own
database connection, TableViewer edits run one at a time, and the TLS handshake (with `useHttps`) happens in each request's own thread.

**Your own handlers** may now run at the same time as each other. That only
matters if they share something in Python memory:

```python
counter = 0

@app.route('POST', '/api/next-number')
def next_number(request):
    global counter
    counter += 1          # two requests at once can both read the same value
    send_json(request, 200, {"n": counter})
```

Guard such state with a lock, or keep it in the database:

```python
import threading
counter_lock = threading.Lock()

@app.route('POST', '/api/next-number')
def next_number(request):
    global counter
    with counter_lock:
        counter += 1
        n = counter
    send_json(request, 200, {"n": n})
```

Handlers that only read the request, query the database and send a response
(almost all of them) need nothing. If an app can't be made safe, pass
`WebServer(port=8080, threaded=False)`.

A client that goes quiet for 30 seconds in the middle of a request is
disconnected, in both modes, so it can't hold the server.

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
| `createTables` | `True` | Create the framework tables (`Users`, `Sessions`, `LoginAttempts`, `AuditLog`, `tableviewLedger`) if they don't exist. Pass `False` if the schema is managed elsewhere. |

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

Put the app behind Authentik and tune security. See [Authentication](auth.md).

```python
app.settings(auth=True)                                   # needs PROXY_SECRET and JWT_SECRET in .env
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_DEV"]: "dev", os.environ["GROUP_ADMIN"]: "admin"})
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `auth` | `None` | `True` puts the app behind Authentik. **Every request must carry `PROXY_SECRET` in `X-Proxy-Secret`** (else a bare `403`), and every route and page needs a user from Authentik unless registered with `public=True`. Refuses to start without `PROXY_SECRET`, or with a `JWT_SECRET` shorter than 32 bytes. |
| `roleHierarchy` | `None` | Ranked roles, highest first, e.g. `["dev", "admin", "user"]`. `roles=[...]` then means "this role or higher". `None` = exact match. |
| `authentikRoles` | `None` | `{Authentik group name: role}`. The user gets the highest matching role (with `roleHierarchy`) or the first match; in none of the groups, the lowest role. See [Roles from Authentik groups](auth.md#roles-from-authentik-groups). |
| `devUser` | `None` | `{"username": ..., "groups": [...]}` (optionally `"name"`, `"email"`): every request is this user, and no secret or header is checked. Only allowed when `host` is `127.0.0.1`, `localhost` or `::1`. See [Local development](auth.md#local-development-without-authentik). |
| `auditLog` | `True` | Write logouts, refused access and refused form tokens to the `AuditLog` table. |
| `auditRetentionDays` | `None` | Delete audit log rows older than this, at start. `None` = keep forever. |
| `trustProxy` | `False` | Take the client IP from `X-Forwarded-For`. Set it behind the proxy. |
| `csp` | a default policy | `Content-Security-Policy` header value. `None` sends none. See [Authentication → Security headers](auth.md#security-headers). |
| `securityHeaders` | `True` | Send `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP (and HSTS on HTTPS). |

Calling `settings()` without `auth=True` (or not at all) leaves the server fully open.

---

## `app.useHttps(certfile, keyfile)`

Serve over TLS. Takes paths to a PEM certificate and private key. Also turns
on the HSTS header. Behind the proxy you don't need it: TLS ends at the proxy.

```python
app.useHttps("cert.pem", "key.pem")
```

`useHttps` only *serves* TLS; it does not obtain a certificate. You need to
bring one:

| Where from | Cost | Browsers trust it? |
|------------|------|--------------------|
| Self-signed (command below) | free | No — every user sees a warning and has to click through or import the cert. Fine for development. |
| Your company's internal CA | free | Yes, on company-managed PCs. The normal choice for an internal tool — ask IT. |
| Public CA (Let's Encrypt or paid) | free / paid | Yes, everywhere — but only possible if the server has a public DNS name the CA can reach. Not for `10.x.x.x` or `.local` names. |

Self-signed pair for development:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

Certificates expire (Let's Encrypt: 90 days) and `useHttps` does not renew
them. If you want automatic renewal, run a reverse proxy such as Caddy or nginx
in front of the app instead, and pass `settings(trustProxy=True)`.

Raises `FileNotFoundError` if either file is missing.

---

## `app.addPath(url_path, file_path, public=False, roles=None)`

Serve one file at a fixed URL.

| Parameter | Meaning |
|-----------|---------|
| `url_path` | URL to respond on, e.g. `'/'` or `'/report'`. |
| `file_path` | File to send, relative to the project root, e.g. `'public/index.html'`. |
| `public` | When auth is on: `True` makes this page viewable without a user from Authentik. |
| `roles` | List of roles allowed to view it, e.g. `["admin"]`. Others get `403`. |

```python
app.addPath('/', 'public/index.html')
app.addPath('/about', 'public/about.html', public=True)
app.addPath('/admin', 'public/admin.html', roles=["admin"])
```

HTML files get the framework scripts injected. Other files are sent as-is with a
content type guessed from the extension.

---

## `@app.route(method, path, public=False, roles=None)`

Register a handler function for a URL. See [Routes & requests](routes.md).

| Parameter | Meaning |
|-----------|---------|
| `method` | `'GET'`, `'POST'`, `'PUT'` or `'DELETE'`. |
| `path` | Exact URL path, e.g. `'/api/data'`. Query strings are ignored for matching. |
| `public` | When auth is on: `True` lets anyone call this route (the proxy's secret is still required). |
| `roles` | List of roles allowed to call it, e.g. `["admin"]`. Others get `403`. |

```python
@app.route('POST', '/api/data')
def save(request):
    ...

@app.route('DELETE', '/api/users', roles=["admin"])
def remove(request):
    ...
```

The decorated function receives one argument, the request. It must write a
response itself (see [Routes & requests](routes.md#sending-a-response)).

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

Most recent audit entries, newest first (also `python -m WebServer audit`).
Rows have `Id`, `At` (epoch seconds), `Username`, `Event`, `Detail`, `Ip`. See [Authentication → Audit log](auth.md#audit-log)
for the built-in event names.

---

## `app.start()`

Start listening. Blocks until Ctrl+C. Always the last call. The startup line
says whether the server is threaded (`(32 threads)`) or `(single-threaded)`.

---

## Less common

### `app.checkAuth(request)`

Returns the user Authentik sent with the request (the same dict as
`request.user`), else `None`. Inside a protected route you don't need this —
`request.user` is already set. It is for `public=True` routes that want to
behave differently for logged-in users. Always `None` without `auth=True`.

### `app.getDatabaseConnection()`

Returns a raw DB-API connection for the configured backend, for queries the
helpers don't cover. You must `close()` it. See [Database](database.md#your-own-queries)
for the higher-level helpers, which are usually easier.
