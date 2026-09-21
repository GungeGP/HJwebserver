# Authentication

## Setup

1. Put a signing secret in `.env` next to `main.py` (at least 32 bytes):

   ```bash
   python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))" > .env
   ```

   The server refuses to start with `auth=True` if it is missing or too short.
   Never commit `.env`; commit `.env.example` instead.

2. Enable auth and create users:

   ```python
   app.setDatabase(type="sqlite", dbName="app.db")
   app.settings(auth=True)
   app.createUser("alice", "correct-horse-battery")   # returns False if alice already exists
   ```

   Passwords must be at least 5 characters (`minPasswordLength`).

All options: [`settings(...)`](webserver.md#appsettingsauthnone-).

## What "auth on" means

**Everything requires login by default.** Every `@app.route`, every `addPath`
page and every static file. To open something up, mark it public:

```python
@app.route('GET', '/api/health', public=True)
def health(request): ...

app.addPath('/welcome', 'public/welcome.html', public=True)
```

Static files in `public/` cannot be marked public individually; use `addPath(..., public=True)`
for the specific ones you need.

What an unauthenticated visitor gets:

| Request | Response |
|---------|----------|
| Browser opens a protected page | A bare login page (the real HTML is **not** sent) |
| `fetch()` / API call to a protected route | `401` with `{"error": "Authentication required."}` |
| Anything marked `public=True` | Served normally |

Once logged in, a protected handler can rely on `request.user`:

```python
@app.route('GET', '/api/my-entries')
def my_entries(request):
    username = request.user["username"]
    ...
```

`request.user` is `None` on public routes even if the visitor is logged in; use
`app.checkAuth(request)` there if you need to know.

## Brute-force protection

After `maxLoginAttempts` (default 5) failed logins for a username **or** from
one IP address, further attempts get `429 Too Many Requests` with a
`Retry-After` header for `lockoutMinutes` (default 15) — even with the correct
password. The counter resets on a successful login. Lockouts are kept in
memory and cleared when the server restarts.

Login also takes the same amount of time whether or not the username exists,
so an attacker cannot discover valid usernames by timing.

## How a session works

1. The browser posts `{"username", "password"}` to `POST /api/login`.
2. The server checks the password against the stored hash and, if it matches,
   sets a cookie `hj_session=<signed token>` with `HttpOnly; SameSite=Strict`
   and a lifetime of `tokenLifetimeHours`.
3. Every later request from the browser carries the cookie automatically, so your
   own `fetch('/api/...')` calls need no special headers.
4. `POST /api/logout` clears the cookie.

Because the cookie is `HttpOnly`, JavaScript on the page can never read the
token, which is what protects it from being stolen by injected scripts.

The token is a signed JWT **and** a row in the `Sessions` table. Every request
checks that the row still exists, which is what makes sessions revocable:

| Action | Effect |
|--------|--------|
| `POST /api/logout` | that one session is deleted |
| `app.revokeSessions(username)` | all of that user's sessions are deleted |
| `app.setPassword(username, ...)` | all sessions revoked (the user must log in again) |
| `app.deleteUser(username)` | user and sessions gone |
| changing `JWT_SECRET` | every token becomes invalid |

`app.getSessions(username)` lists a user's active sessions. Expired rows are
cleaned up on each login.

### Non-browser clients (scripts, tests, other services)

Send the token as a bearer header instead of a cookie:

```
Authorization: Bearer <token>
```

Get a token from the JSON body of `POST /api/login` (`"token"`) or from
`app.createAuth(username)` in Python. Set `settings(bearerTokens=False)` to
refuse the header entirely if only browsers will ever call the server.

## Passwords

- Stored as salted scrypt hashes (`scrypt$<salt>$<hash>`) in `Users.PasswordHash`.
  The plaintext is never written.
- `app.createUser(username, password)` and `app.setPassword(username, password)`
  do the hashing. Don't insert into `Users` directly.
- Rows that still contain a plaintext password (from before hashing existed) are
  accepted on the next login and upgraded to a hash at that moment.
- There is no self-registration endpoint and no "forgot password" flow; both are
  handled from Python code by an admin.

## Framework routes

| Route | Public | Body / response |
|-------|--------|-----------------|
| `POST /api/login` | yes | body `{"username", "password"}` → `200 {"valid": true, "token": ...}` + cookie, or `401` |
| `POST /api/logout` | yes | clears the cookie → `200` |
| `GET /api/verify` | no | `200 {"valid": true, "user": {...}}` or `401` |

## HTTPS

Without TLS, passwords and session cookies cross the network in the clear. On a
trusted LAN that may be acceptable; anywhere else, turn it on:

```python
app.useHttps("cert.pem", "key.pem")
```

This also adds the `Secure` flag to the cookie and a `Strict-Transport-Security`
header. See [`useHttps`](webserver.md#appusehttpscertfile-keyfile) for generating a
self-signed certificate. If you instead terminate TLS on a reverse proxy, pass
`settings(secureCookie=True, trustProxy=True)`.

## Security headers

Every response carries:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | stops browsers guessing content types |
| `X-Frame-Options` | `DENY` | page cannot be embedded in another site (clickjacking) |
| `Referrer-Policy` | `same-origin` | URLs are not leaked to other sites |
| `Content-Security-Policy` | see below | limits where scripts, styles, images may load from |
| `Strict-Transport-Security` | `max-age=31536000` | HTTPS only; sent when `useHttps` is on |
| `Cache-Control` | `no-store` | only on authenticated responses, so protected data is never cached |

The default CSP allows same-origin and `https:` sources plus inline scripts and
styles (teammates' pages commonly use both), and forbids framing. Loading
anything over plain `http://` from another host is blocked. To change it:

```python
app.settings(auth=True, csp="default-src 'self'; frame-ancestors 'none'")   # stricter
app.settings(auth=True, csp=None)                                           # no CSP header
```

A handler that sets one of these headers itself wins over the default.

## Audit log

With `auditLog=True` (the default) these events are written to the `AuditLog`
table and printed to the console:

| Event | When |
|-------|------|
| `login_ok`, `login_failed`, `login_locked` | `/api/login` |
| `logout` | `/api/logout` |
| `user_created`, `user_deleted`, `password_changed`, `password_rehashed` | user management |
| `sessions_revoked` | `app.revokeSessions` |
| anything you like | `app.audit(request, event, detail)` |

Read it back with `app.getAuditLog(limit=100, username=None)`. Each row has
`At` (epoch seconds), `Username`, `Event`, `Detail`, `Ip`. The IP is the direct
peer unless `trustProxy=True`, in which case `X-Forwarded-For` is used.

## Turning auth off

Omit `settings(auth=True)`. Then no login page is shown, no routes are
protected, and `request.user` is always `None`. `public=` flags are ignored.
