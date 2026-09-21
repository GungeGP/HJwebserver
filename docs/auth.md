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
   app.createUser("alice", "s3cret")   # returns False if alice already exists
   ```

Options: [`settings(auth, jwtSecret, tokenLifetimeHours, secureCookie)`](webserver.md#appsettingsauthnone-jwtsecretnone-tokenlifetimehours24-securecookiefalse).

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

The session is a signed JWT, not a row in the database. There is no server-side
session table and no way to revoke a single session before it expires; changing
`JWT_SECRET` logs everyone out.

### Non-browser clients (scripts, tests, other services)

Send the token as a bearer header instead of a cookie:

```
Authorization: Bearer <token>
```

Get a token from the JSON body of `POST /api/login` (`"token"`) or from
`app.createAuth(username)` in Python.

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

## Turning auth off

Omit `settings(auth=True)`. Then no login page is shown, no routes are
protected, and `request.user` is always `None`. `public=` flags are ignored.
