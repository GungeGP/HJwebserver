# HJwebserver

A small Python web framework for internal tools: routes, static files, JSON
parsing, a database layer (SQLite / MSSQL / MySQL) and cookie-based login with
hashed passwords, revocable sessions, lockout, audit log, security headers and
optional HTTPS — with almost no code to write.

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

app.start()
```

## Documentation

The wiki lives in [`docs/`](docs/README.md):

- [Getting started](docs/README.md) - install, minimal app, project layout
- [WebServer reference](docs/webserver.md) - every method and parameter (`setDatabase`, `settings`, `route`, ...)
- [Routes & requests](docs/routes.md) - handlers, `request.body`, `request.user`, sending responses
- [Database](docs/database.md) - backends, drivers, running your own queries
- [Authentication](docs/auth.md) - protecting routes, sessions, roles
- [Managing users](docs/users.md) - `python -m WebServer` CLI and the Python API
- [Frontend](docs/frontend.md) - injected scripts, login overlay, logout button, `Notify`

## Install

```bash
pip install -r requirements.txt
```
