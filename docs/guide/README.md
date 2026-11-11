# HJwebserver Wiki

A small Python web framework for internal tools. You write a `main.py`, register a
few routes, and the framework handles static files, JSON parsing, the database
connection and — behind Authentik — who is logged in.

## Pages

| Page | What it covers |
|------|----------------|
| [Getting started](#getting-started) | Install, minimal app, project layout |
| [WebServer reference](webserver.md) | Every method on the `app` object and its parameters |
| [Routes & requests](routes.md) | Writing handlers, reading the request, sending responses |
| [Database](database.md) | `setDatabase` backends, running your own queries |
| [Authentication](auth.md) | Login via Authentik: `.env`, Authentik and the proxy, protecting routes, the form token |
| [Users and roles](users.md) | Roles from Authentik groups, and the audit log on the command line |
| [Frontend](frontend.md) | Shared header/footer includes, `hjAuth`, `Notify` |
| [Side menu](menu.md) | `app.menu(...)`: a menu on the left of every page, filtered by role |
| [TableViewer](tableviewer.md) | Database tables in a page: search, filters, lookups, related tables, editing |

## Getting started

### Install

```bash
pip install -r requirements.txt
```

Only the database driver you use is required (see [Database](database.md#drivers)).
SQLite needs nothing extra.

### Minimal app

```python
from WebServer import WebServer
from WebServer.helper import send_json

app = WebServer(port=8080)
app.setDatabase(type="sqlite", dbName="app.db")
app.addPath('/', 'public/index.html')

@app.route('GET', '/api/me')
def me(request):
    send_json(request, 200, {"user": request.user})

if __name__ == "__main__":
    app.start()
```

That app is open to everyone, which is fine on your own machine. To put it
behind Authentik, so people log in with their d1 account, add one line:

```python
app.settings(auth=True)   # needs PROXY_SECRET and JWT_SECRET in .env; the user comes from Authentik
```

The app then needs a proxy and Authentik in front of it, and `request.user`
holds who is logged in. What to put in `.env`, and what to set up in Authentik
and the proxy, is in [Authentication](auth.md#setup). To try it on your own
machine without Authentik, see
[Local development](auth.md#local-development-without-authentik).

### Project layout

```
my-app/
├── main.py          # your app: routes, settings
├── .env             # PROXY_SECRET=..., JWT_SECRET=..., your own keys
└── public/          # static files, served automatically
    └── index.html
```

Anything in `public/` is served at its own path (`public/style.css` → `/style.css`).
HTML files automatically get the framework scripts injected before `</body>`.

### The order of calls

`WebServer(...)` → `setDatabase` → `settings` → `addPath` / `route` → `start`. In practice only two
rules matter:

- `WebServer(...)` reads `.env`, so `os.environ` can be used for `settings()` on the lines after it.
- `start()` is last; it blocks until Ctrl+C. It also prints the public paths to paste into Authentik.
