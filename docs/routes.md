# Routes & requests

## Writing a handler

```python
from WebServer.helper import send_json

@app.route('POST', '/api/data')
def save_data(request):
    print(request.body)            # parsed JSON (dict/list) or raw string
    print(request.user)            # {"username": "alice"} when auth is on
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
| `request.user` | `dict` / `None` | `{"username", "role", "mustChangePassword"}` on protected routes when auth is on. `None` on public routes and when auth is off. |
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

Routes take priority over static files with the same path. When auth is on,
static files require login too (see [Authentication](auth.md)). Paths that try
to leave the folder (`..`) and dotfiles (`.env`, `.git`) are always `404`.

Request bodies larger than 10 MB are rejected with `413` before your handler
runs. Change the limit with `app.max_body_bytes = ...` before `start()`.

## Which URLs the framework owns

| Route | Purpose |
|-------|---------|
| `GET /webserver.js` | Framework script injected into every HTML page |
| `GET /auth.js` | Login overlay script (only when auth is on) |
| `GET /api/login-config` | Login form text/options |
| `POST /api/login` | Login, sets the session cookie |
| `POST /api/logout` | Clears the session cookie |
| `POST /api/logout-all` | Ends every session of the current user |
| `GET /api/verify` | Returns the current user, or `401` |
| `POST /api/change-password` | Lets the user change their own password |

Don't register routes on these paths.
