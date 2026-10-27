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

   Passwords must be at least 5 characters (`minPasswordLength`). Usernames are
   case-insensitive. See [Managing users](users.md) for the CLI, roles,
   temporary passwords and disabling accounts.

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
    username = request.user["username"]     # also: ["role"], ["mustChangePassword"]
    ...
```

Routes and pages can additionally require a role — `@app.route(..., roles=["admin"])`
— in which case other users get `403`. See [Managing users → Roles](users.md#roles).

`request.user` is `None` on public routes even if the visitor is logged in; use
`app.checkAuth(request)` there if you need to know.

## Brute-force protection

After `maxLoginAttempts` (default 5) failed logins for a username **or** from
one IP address, further attempts get `429 Too Many Requests` with a
`Retry-After` header for `lockoutMinutes` (default 15) — even with the correct
password. The counter resets on a successful login. Lockouts are stored in
the `LoginAttempts` table, so they survive restarts and can be lifted from the
CLI while the server is running.

### Getting a locked-out user back in

| Way | How |
|-----|-----|
| Wait | The `429` response says how long (`"Try again in 847 seconds"`, plus a `Retry-After` header). |
| Unlock from Python | `app.unlock("alice")` — lifts her lockout and any IP lockout her attempts caused. `app.unlock(ip="10.0.0.5")` for an address, `app.unlock()` for everything. |
| See who is locked | `app.getLockouts()` → `[{"type": "username", "value": "alice", "failures": 5, "remaining": 612}, ...]` |
| From the command line | `python -m WebServer unlock alice` (see [Managing users](users.md)). |

Unlocking is recorded in the audit log as `lockout_cleared`.

Login also takes the same amount of time whether or not the username exists,
so an attacker cannot discover valid usernames by timing.

## How a session works

1. The browser posts `{"username", "password", "rememberMe"}` to `POST /api/login`.
2. The server checks the password against the stored hash and, if it matches,
   sets a cookie `hj_session=<signed token>` with `HttpOnly; SameSite=Strict`
   and a lifetime of `tokenLifetimeHours` — or `rememberMeDays` when the
   "Remember me" box was ticked.
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
| `POST /api/logout-all` | all of the user's sessions are deleted ("log out everywhere") |
| user changes their password | every *other* session is deleted; the current one stays |
| `app.revokeSessions(username)` | all of that user's sessions are deleted |
| `app.setPassword(username, ...)` / `disableUser` / `deleteUser` | all sessions revoked |
| idle for `idleTimeoutMinutes` (if set) | that session is deleted on its next request |
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
- `app.createUser` / `app.setPassword` (and the CLI) do the hashing. Don't insert
  into `Users` directly.
- **Users change their own password** with the "Change password" form
  (`POST /api/change-password` with `currentPassword` + `newPassword`). The
  current password is required; other sessions are logged out.
- **Temporary passwords:** an admin can mark a password as must-change
  (`--temporary` / `mustChangePassword=True`). The user is forced through the
  change-password form before anything else works.
- Rows that still contain a plaintext password (from before hashing existed) are
  accepted on the next login and upgraded to a hash at that moment.
- There is no self-registration endpoint and no "forgot password" e-mail flow;
  an admin resets passwords with `python -m WebServer setpassword <name> --temporary`.

## Framework routes

| Route | Public | Body / response |
|-------|--------|-----------------|
| `GET /api/login-config` | yes | `{"title", "message", "logo", "rememberMe", "minPasswordLength"}` for the login form |
| `POST /api/login` | yes | body `{"username", "password", "rememberMe"?}` → `200 {"valid": true, "token", "user"}` + cookie; `401` wrong; `403` disabled; `429` locked |
| `POST /api/logout` | yes | clears the cookie → `200` |
| `POST /api/logout-all` | no | revokes every session of the user → `200` |
| `GET /api/verify` | no | `200 {"valid": true, "user": {"username", "role", "mustChangePassword"}}` or `401` |
| `POST /api/change-password` | no | body `{"currentPassword", "newPassword"}` → `200`; `401` wrong current; `400` policy |

While a password change is pending, every other protected route answers
`403 {"error": "password_change_required"}`.

## Changing how the login looks

| What | How |
|---|---|
| Title, message, logo | `settings(auth=True, loginTitle="...", loginMessage="...", loginLogo="/img/logo.png")` |
| All of the styling | Put your own `public/css/auth.css` in the project. It replaces the framework's copy completely, so start from a copy of `WebServer/public/css/auth.css` |
| A few rules, on a public page | Ordinary CSS in your page, e.g. `html #login-overlay { background-color: rgba(255,255,255,.35); }` |

On a protected page, a visitor who isn't logged in never receives your HTML.
They get a bare login page from the framework, so only `auth.css` styles it,
not your page's own CSS. Making the page public (`addPath(..., public=True)`)
sends your page with the login form on top. That's how to show a
[TableViewer ghost table behind the login](tableviewer.md#showing-the-table-behind-the-login).

### Your own `auth.css`

When the browser asks for `/css/auth.css`, the framework serves
`public/css/auth.css` from your project if it exists, and its own copy only
otherwise. The same goes for every framework file: `public/js/auth.js`,
`public/css/TableViewer.css`, and so on. These files are sent uncached, so
a change shows on the next reload.

Your file **replaces** the framework's, it doesn't add to it. Copy
`WebServer/public/css/auth.css` into `public/css/` and edit from there,
otherwise everything you don't restyle loses its styling.

What the login form is made of (drawn by `auth.js`):

| Selector | What it is |
|---|---|
| `#login-overlay` | The full-screen layer behind the form (dark and blurred by default) |
| `.login-box` | The card holding the form |
| `.login-box .headerLine` | The colored bar at the top of the card |
| `.login-box img.logo` | The logo, when `loginLogo=` is set |
| `#login-form h2`, `#login-form p` | Title and message (`loginTitle=`, `loginMessage=`) |
| `#username`, `#password` | The input fields |
| `.login-box label.remember` | "Remember me" (hidden with `rememberMeDays=0`) |
| `#login-btn` | Sign in; disabled until both fields are filled |
| `#change-form` | The change-password form: `#current-password`, `#new-password`, `#confirm-password`, `#change-btn` |
| `#change-cancel`, `.login-box button.secondary` | Cancel on the change-password form |

**Keep `display: none` on `#login-overlay`.** `auth.js` switches it to
`display: flex` to show the form and back to `none` after login. Without
`display: none` in your CSS, the login box stays on screen once you're logged in.

Example: a see-through background and a card in your own colors.

```css
#login-overlay {
    position: fixed; inset: 0; z-index: 9999;
    display: none; justify-content: center; align-items: center;
    background: rgba(255, 255, 255, 0.35);
}
.login-box {
    background: #fff; border-radius: 12px; width: clamp(300px, 30vw, 400px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15); overflow: hidden; text-align: center;
}
.login-box .headerLine { height: 6px; background: #00563B; }
.login-box form { display: flex; flex-direction: column; padding: 24px; }
.login-box input[type="text"], .login-box input[type="password"] {
    margin-bottom: 12px; padding: 10px; border: 1px solid #d0d7de; border-radius: 8px;
}
.login-box button { padding: 10px; border: none; border-radius: 8px; background: #00563B; color: #fff; cursor: pointer; }
.login-box button:disabled { background: #e3edf3; color: #2c3531; cursor: not-allowed; }
.login-box button.secondary { background: none; color: #00563B; }
```

### What CSS can't change

CSS changes how the form looks, not what's in it. Which fields and buttons
exist, and in what order, comes from `auth.js`. The text and logo come from
`settings()`.

A different form, such as other fields or the email-first layout in
[SignInForm.md](SignInForm.md), means overriding `public/js/auth.js` the same
way. That works, but your copy then *is* the login: a mistake in it can lock
everyone out, and later fixes to the framework's `auth.js` won't reach you.
Keep the parts the server relies on: posting `{"username", "password",
"rememberMe"}` to `/api/login`, reloading after a successful login, and
showing the form again when a request answers `401`.

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

| Event | When | Detail |
|-------|------|--------|
| `user_created` | `app.createUser` / `createuser` | `role=admin, by terminal (d1misgu)` |
| `role_changed` | `app.setRole` / `setrole` | old and new role: `user -> admin, by python (d1misgu)` |
| `user_deleted` | `app.deleteUser` / `deleteuser` | the role the user had: `role=user, by terminal (d1misgu)` |
| `user_disabled`, `user_enabled` | `app.disableUser` / `app.enableUser` | `by terminal (d1misgu)` |
| `access_denied` | a logged-in user calls a route their role doesn't allow (403) | `PUT /api/x needs admin, has user` (no query string) |
| `password_changed` | by the user themselves, or set with `app.setPassword` / `setpassword` | `by user`, or `temporary, by terminal (d1misgu)` |
| `password_change_failed` | wrong current password when changing it | |
| `password_rehashed` | an old plain-text password was upgraded at login | |
| `login_ok`, `login_failed`, `login_locked`, `login_disabled` | `/api/login` | |
| `logout`, `logout_all` | `/api/logout`, `/api/logout-all` | |
| `session_idle_expired` | a session ended after being idle too long | |
| `sessions_revoked` | `app.revokeSessions` | |
| `lockout_cleared` | `app.unlock` | |
| `token_issued` | `app.createAuth` | |
| anything you like | `app.audit(request, event, detail)` | |

For user changes, `Username` is the user who was changed, and `Detail` ends
with who made the change: `by terminal` for `python -m WebServer ...`,
`by python` for code calling the `app.` methods (like `main.py`), followed by
the operating system account that ran it, e.g. `by terminal (d1misgu)`. No one
is logged in to the site there, so the account comes from the machine: it says
which login was used, which is only as trustworthy as access to that machine.

Changes to data made through a table viewer are not in the audit log; they
are in [`tableviewLedger`](tableviewer.md#tableviewledger-what-exactly-changed),
with the old and new values.

Read it back with `app.getAuditLog(limit=100, username=None)`. Each row has
`At` (epoch seconds), `Username`, `Event`, `Detail`, `Ip`. The IP is the direct
peer unless `trustProxy=True`, in which case `X-Forwarded-For` is used.

## Turning auth off

Omit `settings(auth=True)`. Then no login page is shown, no routes are
protected, and `request.user` is always `None`. `public=` flags are ignored.
