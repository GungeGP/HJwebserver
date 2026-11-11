# Authentication

The app has no login of its own. With `settings(auth=True)` it sits behind
**Authentik**, as *forward auth* in the reverse proxy (Nginx Proxy Manager).
People log in with their d1 account at Authentik, never in the app.

```
browser ──> proxy ──(is this person logged in?)──> Authentik
              │                                       │
              │ <──────── yes: who it is, groups ─────┘
              │
              └──> app   X-authentik-username, X-authentik-groups,
                         X-authentik-email, X-authentik-name,
                         X-Proxy-Secret
```

The proxy asks Authentik before every request. Someone who isn't logged in
is sent to Authentik's login and never reaches the app. When they are, the
proxy passes the request on with the user in `X-authentik-*` headers, plus a
shared secret in `X-Proxy-Secret`.

**The secret is what makes the headers trustworthy.** Every stack behind the
proxy shares its network, and anything on it can call the app directly with
any headers it likes. So with auth on, the app answers a request without the
right secret with a bare `403` — on every path, public pages and static files
included — and only reads the `X-authentik-*` headers after the secret checks out.

## Setup

### 1. `.env`

Next to `main.py`, never committed (the keys are in `.env.example`):

| Key | What |
|---|---|
| `PROXY_SECRET` | The shared secret. The proxy sends the same value in `X-Proxy-Secret`. |
| `JWT_SECRET` | Signs the [form token](#form-token). At least 32 bytes. |

Generate each with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

With `auth=True` the app refuses to start when `PROXY_SECRET` is missing or
empty, or `JWT_SECRET` is missing or shorter than 32 bytes. The message names
the key, never a value.

Your app's own keys go in the same file — typically the names of the
Authentik groups that give a role (`GROUP_ADMIN`, `GROUP_DEV`, ...). They are
your app's, not the framework's. `.env` is read when `WebServer(...)` is
created, so `os.environ` works in `main.py` from that line on, before `settings()`.

### 2. The app

```python
import os
from WebServer import WebServer

app = WebServer(host="0.0.0.0", port=8080)   # reads .env, so os.environ works from here on
app.setDatabase(...)
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_DEV"]: "dev",
                             os.environ["GROUP_ADMIN"]: "admin"})
```

`host="0.0.0.0"` because the proxy reaches the app over the network. All
options: [`settings(...)`](webserver.md#appsettingsauthnone-).

### 3. Authentik

What has to exist there (IT sets it up):

- A **proxy provider** for the app in *forward auth (single application)*
  mode, with the app's public address as its external host, and an
  **application** that uses it. The outpost that serves the proxy must include it.
- Under the provider's **unauthenticated paths**, the app's public paths. The
  app prints them when it starts, ready to paste — see
  [Public paths](#public-paths-for-authentik).
- The **groups** that give roles, with the right people in them. Their names
  go in the app's `.env`.
- Who may use the app at all is decided in Authentik (the application's
  bindings). Everyone Authentik lets through gets at least the lowest role.

### 4. The proxy (Nginx Proxy Manager)

The proxy host for the app needs Authentik's standard forward-auth
configuration for Nginx Proxy Manager. What the app relies on:

- Every request goes through Authentik's `auth_request`, and
  `/outpost.goauthentik.io` is passed to Authentik's outpost (it serves the
  login redirect and the sign-out).
- The four user headers are set from Authentik's answer, replacing anything
  the browser sent:

  ```nginx
  auth_request_set $authentik_username $upstream_http_x_authentik_username;
  auth_request_set $authentik_groups   $upstream_http_x_authentik_groups;
  auth_request_set $authentik_email    $upstream_http_x_authentik_email;
  auth_request_set $authentik_name     $upstream_http_x_authentik_name;
  proxy_set_header X-authentik-username $authentik_username;
  proxy_set_header X-authentik-groups   $authentik_groups;
  proxy_set_header X-authentik-email    $authentik_email;
  proxy_set_header X-authentik-name     $authentik_name;
  ```

- The shared secret is added to every request:

  ```nginx
  proxy_set_header X-Proxy-Secret "<the PROXY_SECRET value>";
  ```

  The value lives only in the proxy host and in the app's `.env` on the stack —
  never in a repository or a document.

## What "auth on" means

| Request | Answer |
|---|---|
| Without the right `X-Proxy-Secret` — any path, any method | `403`, no body. Nothing says why |
| A `public=True` route or page | Served, with or without a user. `request.user` is `None` |
| Anything else, with a user from Authentik | Served, with `request.user` set |
| Anything else, without a user | `401`: `{"error": "Authentication required."}`, or a short HTML page when a browser asks for one |
| A route with `roles=[...]` the user doesn't have | `403`: `{"error": "Forbidden: this requires role admin or higher."}` |
| `POST`, `PUT` or `DELETE` to a protected route without the [form token](#form-token) | `403`: `{"error": "Missing or invalid form token (X-CSRF-Token)."}` |

"Without a user" only happens on a path Authentik lets through without a
login (an unauthenticated path), or when the proxy isn't set up to send the
headers. Normally Authentik has already shown its login.

Mark what should be reachable without a login:

```python
app.settings(auth=True)
app.addPath('/', 'public/index.html', public=True)
app.addPath('/sager', 'public/sager.html')

@app.route('GET', '/api/aabningstider', public=True)
def aabningstider(request): ...
```

Static files in `public/` cannot be marked public individually; use
`addPath(..., public=True)` for the ones you need.

`request.user` is `None` on public routes; use `app.checkAuth(request)` there
to see whether Authentik sent a user.

## `request.user`

```python
@app.route('GET', '/api/me')
def me(request):
    send_json(request, 200, {"user": request.user})
```

```python
{"username": "aje", "name": "Anna Jensen", "email": "aje@example.org",
 "role": "admin", "groups": ["Staff", "Case admins"]}
```

| Key | From |
|---|---|
| `username` | `X-authentik-username`, trimmed and lower-cased |
| `name` | `X-authentik-name`; the username when it is empty |
| `email` | `X-authentik-email`; `""` when it is empty |
| `groups` | `X-authentik-groups`, split on `\|` |
| `role` | worked out from `groups`, see below |

## Roles from Authentik groups

`authentikRoles` maps Authentik group names to the app's roles:

```python
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_DEV"]: "dev",
                             os.environ["GROUP_ADMIN"]: "admin"})

@app.route('DELETE', '/api/sag', roles=["admin"])        # admin and dev may
def slet_sag(request): ...

app.addTableViewer('/api/sager', table=..., edit=["admin"], delete=["admin"])
```

- **With `roleHierarchy`** the user gets the highest role among their groups,
  and `roles=["admin"]` means "admin or higher".
- **Without it** the user gets the role of the first group in
  `authentikRoles` they are a member of, and `roles=[...]` must match exactly.
- **In none of the groups:** the lowest role — the last in `roleHierarchy`,
  or `"user"` without one. Authentik has already decided the person may use the app.

Group names are matched exactly. The role is worked out on every request, so a
change of groups in Authentik applies as soon as Authentik sends the new list.
A role in `authentikRoles` or in a route's `roles=` that isn't in
`roleHierarchy` stops the app at start-up, so a typo can't silently lock people out.

## Form token

Every `POST`, `PUT` and `DELETE` to a protected route must carry a token bound
to the user in the `X-CSRF-Token` header. That stops a page on another site
from sending a form in the user's name: the browser would bring Authentik's
cookie along, but the page can't know the token.

**Pages that use the framework's scripts send it by themselves.** `auth.js`
gets it from `GET /api/verify` and adds it to every changing `fetch()` to the
same site — your own calls, TableViewer and the calendar alike:

```js
fetch('/api/sag', {method: 'DELETE'})   // gets the token from the framework
```

Two things don't get it: a plain HTML `<form method="post">` and
`XMLHttpRequest`. Send those with `fetch()` instead.

The token is an HMAC of the username with `JWT_SECRET`. Changing `JWT_SECRET`
makes every open page fetch a new one on its next reload.

## Logging out

`GET /logout` writes `logout` to the audit log and sends the browser on to
Authentik's sign-out (`/outpost.goauthentik.io/sign_out`). That ends the
login at Authentik, for every app behind it. In a page, a
`<button id="logout">` or `hjAuth.logout()` does the same — see
[Frontend](frontend.md#authjs--who-is-logged-in).

## Local development without Authentik

`devUser` makes the app behave as if a given user with given groups were
logged in:

```python
app = WebServer(port=8080)   # listens on 127.0.0.1 only
app.settings(auth=True,
             roleHierarchy=["dev", "admin", "user"],
             authentikRoles={os.environ["GROUP_ADMIN"]: "admin"},
             devUser={"username": "test", "groups": [os.environ["GROUP_ADMIN"]]})
```

At start it says so:

```
[ auth ] UDVIKLINGSTILSTAND: alle er "test" (admin)
```

- Every request is that user. `X-Proxy-Secret` and the `X-authentik-*`
  headers are not checked, and `PROXY_SECRET` isn't needed. `JWT_SECRET` is,
  and the form token is checked as usual.
- `devUser` may also have `"name"` and `"email"`.
- **The app refuses to start with `devUser` unless `host` is `127.0.0.1`,
  `localhost` or `::1`**, so it can't be reached from other machines.
- `/logout` still goes to Authentik's sign-out, which doesn't exist locally.

## Public paths for Authentik

With `auth=True`, the app prints its public paths at start, one regular
expression per line, ready for the provider's unauthenticated paths in Authentik:

```
[ auth ] Offentlige stier — sæt dem ind i Authentik som "stier uden login":
^/$
^/api/aabningstider$
^(/public)?/js/auth\.js$
^(/public)?/js/webserver\.js$
...
^/logout$
```

Your own `public=True` routes and pages come first. After them come the
framework's scripts and styles, which public pages load, and `/logout`.
Paste the whole list. If a path is public in the app but not in Authentik,
visitors without a login are sent to Authentik's login anyway; the other way
round, the app still refuses them.

## HTTPS

Behind the proxy, TLS ends at the proxy, and the app is reached over the
stack's internal network. Pass `settings(trustProxy=True)` so the audit log
records the client's address from `X-Forwarded-For` instead of the proxy's.
`useHttps` still exists for an app that serves TLS itself; see
[`useHttps`](webserver.md#appusehttpscertfile-keyfile).

## Security headers

Every response carries:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | stops browsers guessing content types |
| `X-Frame-Options` | `DENY` | page cannot be embedded in another site (clickjacking) |
| `Referrer-Policy` | `same-origin` | URLs are not leaked to other sites |
| `Content-Security-Policy` | see below | limits where scripts, styles, images may load from |
| `Strict-Transport-Security` | `max-age=31536000` | HTTPS only; sent when `useHttps` is on |
| `Cache-Control` | `no-store` | only on responses to a user, so protected data is never cached |

The default CSP allows same-origin and `https:` sources plus inline scripts and
styles (teammates' pages commonly use both), and forbids framing. Loading
anything over plain `http://` from another host is blocked. To change it:

```python
app.settings(auth=True, csp="default-src 'self'; frame-ancestors 'none'")   # stricter
app.settings(auth=True, csp=None)                                           # no CSP header
```

A handler that sets one of these headers itself wins over the default. The
bare `403` for a request without the proxy's secret always carries
`Content-Security-Policy: frame-ancestors 'none'` and `X-Frame-Options: DENY`,
whatever `csp` and `securityHeaders` say. Keep `frame-ancestors 'none'` in your
own `csp`, so the app's pages can't be shown in a frame either.

## Audit log

With `auditLog=True` (the default) these events are written to the `AuditLog`
table and printed to the console:

| Event | When | Detail |
|-------|------|--------|
| `logout` | `GET /logout` | |
| `access_denied` | a user calls a route their role doesn't allow (403) | `PUT /api/x needs admin or higher, has user` (no query string) |
| `form_token_rejected` | a `POST`, `PUT` or `DELETE` without a valid form token | `DELETE /api/sag` (no query string) |
| anything you like | `app.audit(request, event, detail)` | |

Logins happen at Authentik, so they are in Authentik's own log, not here.
Rows from before the app moved behind Authentik (`login_ok`, `user_created`,
...) stay in the table.

Changes to data made through a table viewer are not in the audit log; they
are in [`tableviewLedger`](tableviewer.md#tableviewledger-what-exactly-changed),
with the old and new values.

Read it back with `app.getAuditLog(limit=100, username=None)` or
`python -m WebServer audit`. Each row has `At` (epoch seconds), `Username`,
`Event`, `Detail`, `Ip`. The IP is the direct peer unless `trustProxy=True`,
in which case `X-Forwarded-For` is used. `auditRetentionDays` deletes rows
older than that at start.

## Turning auth off

Omit `settings(auth=True)`. Then nothing is protected, no secret or header is
checked, `request.user` is always `None`, and `public=` flags are ignored.
