"""Authentication: password hashing, JWT sessions and the login/logout routes.

Sessions are JWTs carried in an HttpOnly cookie (set on login) or, for
non-browser clients, in an ``Authorization: Bearer <token>`` header.
Route enforcement itself happens in WebHandler; this module only decides
*who* a request belongs to (``resolve_user``) and handles login/logout.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import jwt
from dotenv import load_dotenv

from WebServer.database import create_user, get_user_by_username, update_user_password
from WebServer.helper import _send_json

MIN_SECRET_LENGTH = 32

_settings = {
    "secret": None,
    "lifetime": timedelta(days=1),
    "cookie_name": "hj_session",
    "secure_cookie": False,
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure(jwt_secret=None, token_lifetime_hours=24, secure_cookie=False):
    """Validate and store auth settings. Called from WebServer.settings(auth=True)."""
    load_dotenv()
    secret = jwt_secret or os.getenv("JWT_SECRET")
    if not secret or len(secret.encode("utf-8")) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET is missing or shorter than 32 bytes. Set it in .env "
            "(or pass jwtSecret= to settings()). Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    _settings["secret"] = secret
    _settings["lifetime"] = timedelta(hours=token_lifetime_hours)
    _settings["secure_cookie"] = bool(secure_cookie)


def attach_auth_routes(server):
    """Register the framework's login/verify/logout routes on the server."""
    server.routes.setdefault('POST', {})
    server.routes.setdefault('GET', {})

    _register(server, 'POST', '/api/login', _login_route, public=True)
    _register(server, 'POST', '/api/logout', _logout_route, public=True)
    _register(server, 'GET', '/api/verify', _verify_route, public=False)


def _register(server, method, path, func, public):
    if path in server.routes[method]:
        return
    func._hj_public = public
    server.routes[method][path] = func


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


def hash_password(password):
    """Return a salted scrypt hash in the form ``scrypt$<salt hex>$<hash hex>``."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    """Check ``password`` against a stored hash. Returns False for empty/NULL hashes."""
    if not stored or password is None:
        return False
    if stored.startswith("scrypt$"):
        try:
            _, salt_hex, digest_hex = stored.split("$", 2)
            digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                    n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
            return hmac.compare_digest(digest.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
    # Legacy row: password stored in plaintext by an older version of this
    # framework. Accept it once so the login route can upgrade it to a hash.
    return hmac.compare_digest(password, stored)


def needs_rehash(stored):
    return bool(stored) and not stored.startswith("scrypt$")


# ---------------------------------------------------------------------------
# Tokens / sessions
# ---------------------------------------------------------------------------

def create_token_for_user(username):
    now = datetime.now(timezone.utc)
    payload = {"username": username, "iat": now, "exp": now + _settings["lifetime"]}
    return jwt.encode(payload, _settings["secret"], algorithm="HS256")


def verify_token(token):
    try:
        return jwt.decode(token, _settings["secret"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _token_from_request(request):
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    cookie_header = request.headers.get('Cookie')
    if cookie_header:
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
        except Exception:
            return None
        morsel = cookies.get(_settings["cookie_name"])
        if morsel:
            return morsel.value
    return None


def resolve_user(request):
    """Return the user dict for an authenticated request, else None. Never writes a response."""
    token = _token_from_request(request)
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    return {"username": payload.get("username")}


# Backwards-compatible name used by WebServer.checkAuth.
check_auth = resolve_user


def _session_cookie(token=None):
    """Build the Set-Cookie header value. ``token=None`` produces a clearing cookie."""
    parts = [f"{_settings['cookie_name']}={token or ''}", "Path=/", "HttpOnly", "SameSite=Strict"]
    if token:
        parts.append(f"Max-Age={int(_settings['lifetime'].total_seconds())}")
    else:
        parts.append("Max-Age=0")
    if _settings["secure_cookie"]:
        parts.append("Secure")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _login_route(request):
    credentials = getattr(request, 'body', None)
    if credentials is None:
        content_length = int(request.headers.get('Content-Length', 0))
        try:
            credentials = json.loads(request.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _send_json(request, 400, {"error": "Invalid JSON payload."})
            return
    if not isinstance(credentials, dict):
        _send_json(request, 400, {"error": "Invalid JSON payload."})
        return

    username = credentials.get("username")
    password = credentials.get("password")
    if not username or password is None:
        _send_json(request, 400, {"error": "Username and password are required."})
        return

    username = str(username).strip()
    password = str(password)

    user_record = get_user_by_username(username)
    if user_record is None or not verify_password(password, user_record.PasswordHash):
        _send_json(request, 401, {"error": "Invalid username or password."})
        return

    if needs_rehash(user_record.PasswordHash):
        update_user_password(username, hash_password(password))

    token = create_token_for_user(username)
    _send_json(
        request, 200,
        {"valid": True, "message": "Login successful", "token": token},
        headers={"Set-Cookie": _session_cookie(token)},
    )


def _logout_route(request):
    _send_json(request, 200, {"valid": False, "message": "Logged out"},
               headers={"Set-Cookie": _session_cookie(None)})


def _verify_route(request):
    # WebHandler already enforced authentication and populated request.user.
    _send_json(request, 200, {"valid": True, "user": request.user})


# ---------------------------------------------------------------------------
# Login shell
# ---------------------------------------------------------------------------

_LOGIN_SHELL = b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in</title>
</head>
<body>
</body>
</html>"""


def login_shell_html(inject_urls):
    """Minimal page that only carries the framework scripts, so auth.js can render the login form."""
    from WebServer.WebHandler import inject_js_scripts
    return inject_js_scripts(_LOGIN_SHELL, inject_urls)
