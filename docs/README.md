# HJwebserver Wiki

A small Python web framework for internal tools. You write a `main.py`, register a
few routes, and the framework handles static files, JSON parsing, the database
connection and login.

## Pages

| Page | What it covers |
|------|----------------|
| [Getting started](#getting-started) | Install, minimal app, project layout |
| [WebServer reference](webserver.md) | Every method on the `app` object and its parameters |
| [Routes & requests](routes.md) | Writing handlers, reading the request, sending responses |
| [Database](database.md) | `setDatabase` backends, running your own queries |
| [Authentication](auth.md) | How login works, protecting routes, managing users |
| [Frontend](frontend.md) | The injected scripts, the login overlay, logout button, `Notify` |

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
app.settings(auth=True)
app.addPath('/', 'public/index.html')

@app.route('GET', '/api/me')
def me(request):
    send_json(request, 200, {"user": request.user})

if __name__ == "__main__":
    app.start()
```

Before the first run, create `.env` with a signing secret (see [Authentication](auth.md#setup)):

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))" > .env
```

and create at least one user (nobody can log in otherwise):

```python
app.createUser("alice", "s3cret")
```

### Project layout

```
my-app/
├── main.py          # your app: routes, settings
├── .env             # JWT_SECRET=...
└── public/          # static files, served automatically
    └── index.html
```

Anything in `public/` is served at its own path (`public/style.css` → `/style.css`).
HTML files automatically get the framework scripts injected before `</body>`.

### The order of calls

`setDatabase` → `settings` → `addPath` / `route` → `start`. In practice only two
rules matter:

- `setDatabase` must come before `createUser` / `setPassword` (they need the database).
- `start()` is last; it blocks until Ctrl+C.
