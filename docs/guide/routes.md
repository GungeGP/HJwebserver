# Routes & requests

## Writing a handler

```python
from WebServer.helper import send_json

@app.route('POST', '/api/data')
def save_data(request):
    print(request.body)            # parsed JSON (dict/list) or raw string
    print(request.user)            # {"username": "alice", "role": "user", ...} when auth is on
    send_json(request, 200, {"status": "ok"})
```

A handler takes exactly one argument, `request`, and returns nothing. It is
responsible for writing the response. If it raises, the framework logs the error
and answers `500`.

Routes match on the exact path. `/api/data` and `/api/data/` are different
routes; `/api/data?id=5` matches `/api/data`.

## Reading the request

| Attribute | Type | Notes |
|-----------|------|-------|
| `request.body` | `dict` / `list` / `str` / `None` | For `POST`/`PUT` with `Content-Type: application/json` the body is parsed for you. Other content types give the raw text. `GET`/`DELETE` → `None`. Invalid JSON is rejected with `400` before your handler runs. |
| `request.user` | `dict` / `None` | `{"username", "name", "email", "role", "groups"}` from Authentik, on protected routes when auth is on (see [Authentication](auth.md#requestuser)). `None` on public routes and when auth is off. |
| `request.path` | `str` | Full request path including the query string, e.g. `/api/data?id=5`. |
| `request.headers` | mapping | HTTP headers, e.g. `request.headers.get('Content-Type')`. |
| `request.command` | `str` | The HTTP method. |

### Query strings

```python
from urllib.parse import urlparse, parse_qs

@app.route('GET', '/api/items')
def items(request):
    params = parse_qs(urlparse(request.path).query)   # {'id': ['5']}
    item_id = params.get('id', [None])[0]
```

## Sending a response

### JSON (most routes)

```python
from WebServer.helper import send_json

send_json(request, 200, {"items": [1, 2, 3]})
send_json(request, 404, {"error": "Not found"})
send_json(request, 201, {"id": 7}, headers={"Location": "/api/items/7"})
```

`send_json(request, status, payload, headers=None)` sets the status, the
`Content-Type: application/json` header, any extra headers, and writes the payload.

### Anything else

The request object is a standard `http.server.BaseHTTPRequestHandler`, so the
raw API is always available:

```python
request.send_response(200)
request.send_header('Content-Type', 'text/plain')
request.end_headers()
request.wfile.write(b"Hello")
```

Order matters: `send_response` → `send_header` (any number) → `end_headers` →
`wfile.write`. Write bytes, not `str`.

## Static files

Files in the static folder (normally `public/`) are served automatically at their
own path — no route needed:

```
public/style.css      →  GET /style.css
public/img/logo.png   →  GET /img/logo.png
public/index.html     →  GET /index.html
```

HTML files can share a header/footer with `<!--#include file="…" -->` — see
[Frontend → includes](frontend.md#shared-header-footer-navigation--includes).

Routes take priority over static files with the same path. When auth is on,
static files need a user from Authentik too (see [Authentication](auth.md)). Paths that try
to leave the folder (`..`) and dotfiles (`.env`, `.git`) are always `404`.

Request bodies larger than 10 MB are rejected with `413` before your handler
runs. Change the limit with `app.max_body_bytes = ...` before `start()`.

## Which URLs the framework owns

| Route | Purpose |
|-------|---------|
| `GET /js/webserver.js` | Framework script injected into every HTML page |
| `GET /js/auth.js` | Who is logged in, and the form token on changing calls (only when auth is on) |
| `GET /css/auth.css` | Styling from the old login form; no longer loaded by `auth.js` |
| `GET /js/TableViewer.js` | TableViewer script (only once `addTableViewer()` is used) |
| `GET /css/TableViewer.css` | TableViewer styling (loaded by TableViewer.js itself) |
| `GET /api/verify` | The current user, `roleHierarchy` and the form token, or `401` (only when auth is on) |
| `GET /logout` | Sends the browser to Authentik's sign-out (only when auth is on) |

Don't register routes on these paths.
