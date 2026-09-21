"""Authentication: password hashing, sessions, lockout, audit and the login routes.

A session is a signed JWT whose ``jti`` must also exist in the ``Sessions``
table. That makes sessions revocable: logout deletes one row, changing a
password or calling ``revokeSessions`` deletes all rows for a user.

The token travels in an HttpOnly cookie (browsers) or, when enabled, in an
``Authorization: Bearer <token>`` header (scripts). Route enforcement itself
happens in WebHandler; this module decides *who* a request belongs to
(``resolve_user``) and handles login/logout.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import timedelta
from http.cookies import SimpleCookie

import jwt
from dotenv import load_dotenv

from WebServer import database as db
from WebServer.helper import _send_json

MIN_SECRET_LENGTH = 32

_settings = {
    "secret": None,
    "lifetime": timedelta(days=1),
    "cookie_name": "hj_session",
    "secure_cookie": False,
    "bearer_tokens": True,
    "max_login_attempts": 5,
    "lockout_minutes": 15,
    "min_password_length": 8,
    "audit": True,
    "trust_proxy": False,
    "dummy_hash": None,   # used to equalise timing for unknown usernames
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure(jwt_secret=None, token_lifetime_hours=24, secure_cookie=False, bearer_tokens=True,
              max_login_attempts=5, lockout_minutes=15, min_password_length=8, audit=True,
              trust_proxy=False):
    """Validate and store auth settings. Called from WebServer.settings(auth=True)."""
    load_dotenv()
    secret = jwt_secret or os.getenv("JWT_SECRET")
    if not secret or len(secret.encode("utf-8")) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET is missing or shorter than 32 bytes. Set it in .env "
            "(or pass jwtSecret= to settings()). Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    _settings.update(
        secret=secret,
        lifetime=timedelta(hours=token_lifetime_hours),
        secure_cookie=bool(secure_cookie),
        bearer_tokens=bool(bearer_tokens),
        max_login_attempts=int(max_login_attempts),
        lockout_minutes=float(lockout_minutes),
        min_password_length=int(min_password_length),
        audit=bool(audit),
        trust_proxy=bool(trust_proxy),
        dummy_hash=hash_password(secrets.token_hex(16)),
    )
    _lockouts.clear()


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


def check_password_policy(password):
    """Raise ValueError if the password does not meet the configured policy."""
    if not password:
        raise ValueError("Password is required.")
    if len(password) < _settings["min_password_length"]:
        raise ValueError(f"Password must be at least {_settings['min_password_length']} characters.")


# ---------------------------------------------------------------------------
# Lockout (in-memory; the server is single-threaded)
# ---------------------------------------------------------------------------

_lockouts = {}   # key -> {"count": int, "last": ts, "until": ts}


def _lockout_keys(username, ip):
    return [f"user:{username.lower()}", f"ip:{ip}"]


def _lockout_remaining(username, ip):
    """Seconds left on the lockout for this username/IP, or 0."""
    now = time.time()
    remaining = 0
    for key in _lockout_keys(username, ip):
        entry = _lockouts.get(key)
        if entry and entry["until"] > now:
            remaining = max(remaining, entry["until"] - now)
    return int(remaining) + (1 if remaining else 0)


def _record_failure(username, ip):
    now = time.time()
    window = _settings["lockout_minutes"] * 60
    for key in _lockout_keys(username, ip):
        entry = _lockouts.get(key)
        if not entry or now - entry["last"] > window:
            entry = {"count": 0, "last": now, "until": 0}
        entry["count"] += 1
        entry["last"] = now
        if entry["count"] >= _settings["max_login_attempts"]:
            entry["until"] = now + window
        _lockouts[key] = entry


def _clear_failures(username, ip):
    for key in _lockout_keys(username, ip):
        _lockouts.pop(key, None)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def client_ip(request):
    """Best-effort client address; honours X-Forwarded-For only when trustProxy is on."""
    if _settings["trust_proxy"]:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
    try:
        return request.client_address[0]
    except Exception:
        return None


def audit(event, username=None, detail=None, request=None):
    """Record a security-relevant event. Also printed to the console."""
    ip = client_ip(request) if request is not None else None
    print(f"[ audit ] {event} user={username!r} ip={ip} {detail or ''}".rstrip())
    if _settings["audit"]:
        try:
            db.insert_audit(time.time(), username, event, detail, ip)
        except Exception as e:
            print(f"[ audit ] could not write AuditLog: {e}")


# ---------------------------------------------------------------------------
# Tokens / sessions
# ---------------------------------------------------------------------------

def create_token_for_user(username):
    """Mint a token and register its session row."""
    now = int(time.time())
    expires = now + int(_settings["lifetime"].total_seconds())
    jti = secrets.token_hex(16)
    db.create_session(jti, username, now, expires)
    payload = {"username": username, "jti": jti, "iat": now, "exp": expires}
    return jwt.encode(payload, _settings["secret"], algorithm="HS256")


def verify_token(token):
    """Signature + expiry + the session row must still exist. Returns the payload or None."""
    try:
        payload = jwt.decode(token, _settings["secret"], algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    jti = payload.get("jti")
    if not jti:
        return None
    session = db.get_session(jti)
    if session is None or session.Username != payload.get("username") or session.ExpiresAt < time.time():
        return None
    return payload


def revoke_token(token):
    """Delete the session behind a token (ignores invalid tokens)."""
    try:
        payload = jwt.decode(token, _settings["secret"], algorithms=["HS256"], options={"verify_exp": False})
    except jwt.InvalidTokenError:
        return
    if payload.get("jti"):
        db.delete_session(payload["jti"])


def revoke_sessions(username):
    db.delete_sessions_for_user(username)


def _token_from_request(request):
    if _settings["bearer_tokens"]:
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
    ip = client_ip(request) or "?"

    remaining = _lockout_remaining(username, ip)
    if remaining:
        audit("login_locked", username, f"retry in {remaining}s", request)
        _send_json(request, 429, {"error": f"Too many failed attempts. Try again in {remaining} seconds."},
                   headers={"Retry-After": str(remaining)})
        return

    user_record = db.get_user_by_username(username)
    if user_record is None:
        # Spend the same time as a real check so timing can't reveal which usernames exist.
        verify_password(password, _settings["dummy_hash"])
        ok = False
    else:
        ok = verify_password(password, user_record.PasswordHash)

    if not ok:
        _record_failure(username, ip)
        audit("login_failed", username, None, request)
        _send_json(request, 401, {"error": "Invalid username or password."})
        return

    _clear_failures(username, ip)
    if needs_rehash(user_record.PasswordHash):
        db.update_user_password(username, hash_password(password))
        audit("password_rehashed", username, "legacy plaintext upgraded", request)

    db.delete_expired_sessions(time.time())
    token = create_token_for_user(username)
    audit("login_ok", username, None, request)
    _send_json(
        request, 200,
        {"valid": True, "message": "Login successful", "token": token},
        headers={"Set-Cookie": _session_cookie(token)},
    )


def _logout_route(request):
    token = _token_from_request(request)
    username = None
    if token:
        user = resolve_user(request)
        username = user["username"] if user else None
        revoke_token(token)
    audit("logout", username, None, request)
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
