"""Authentication: password hashing, sessions, roles, lockout, audit and the login routes.

A session is a signed JWT whose ``jti`` must also exist in the ``Sessions``
table. That makes sessions revocable: logout deletes one row, changing a
password or calling ``revokeSessions`` deletes all rows for a user.

The token travels in an HttpOnly cookie (browsers) or, when enabled, in an
``Authorization: Bearer <token>`` header (scripts). Route enforcement itself
happens in WebHandler; this module decides *who* a request belongs to
(``resolve_user``) and handles login/logout/change-password.

Usernames are case-insensitive: they are lower-cased at every boundary so the
three database backends behave the same.
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
PASSWORD_CHANGE_REQUIRED = "password_change_required"

_settings = {
    "secret": None,
    "lifetime": timedelta(days=1),
    "remember_lifetime": timedelta(days=30),   # None = "remember me" disabled
    "idle_timeout": None,                      # timedelta or None
    "cookie_name": "hj_session",
    "secure_cookie": False,
    "bearer_tokens": True,
    "max_login_attempts": 5,
    "lockout_minutes": 15,
    "min_password_length": 5,
    "audit": True,
    "trust_proxy": False,
    "dummy_hash": None,   # used to equalise timing for unknown usernames
    "login_title": "Access Restricted",
    "login_message": "Please log in to continue.",
    "login_logo": None,
}

_TOUCH_INTERVAL = 60   # seconds between LastSeen writes for one session


def normalize_username(username):
    return str(username or "").strip().lower()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure(jwt_secret=None, token_lifetime_hours=24, secure_cookie=False, bearer_tokens=True,
              max_login_attempts=5, lockout_minutes=15, min_password_length=5, audit=True,
              trust_proxy=False, remember_me_days=30, idle_timeout_minutes=0,
              login_title="Access Restricted", login_message="Please log in to continue.",
              login_logo=None):
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
        remember_lifetime=timedelta(days=remember_me_days) if remember_me_days and remember_me_days > 0 else None,
        idle_timeout=timedelta(minutes=idle_timeout_minutes) if idle_timeout_minutes and idle_timeout_minutes > 0 else None,
        secure_cookie=bool(secure_cookie),
        bearer_tokens=bool(bearer_tokens),
        max_login_attempts=int(max_login_attempts),
        lockout_minutes=float(lockout_minutes),
        min_password_length=int(min_password_length),
        audit=bool(audit),
        trust_proxy=bool(trust_proxy),
        dummy_hash=hash_password(secrets.token_hex(16)),
        login_title=login_title,
        login_message=login_message,
        login_logo=login_logo,
    )


def attach_auth_routes(server):
    """Register the framework's auth routes on the server."""
    server.routes.setdefault('POST', {})
    server.routes.setdefault('GET', {})

    _register(server, 'GET', '/api/login-config', _login_config_route, public=True)
    _register(server, 'POST', '/api/login', _login_route, public=True)
    _register(server, 'POST', '/api/logout', _logout_route, public=True)
    # These three stay reachable while a password change is pending.
    _register(server, 'GET', '/api/verify', _verify_route, public=False, allow_pending=True)
    _register(server, 'POST', '/api/change-password', _change_password_route, public=False, allow_pending=True)
    _register(server, 'POST', '/api/logout-all', _logout_all_route, public=False, allow_pending=True)


def _register(server, method, path, func, public, allow_pending=False):
    if path in server.routes[method]:
        return
    func._hj_public = public
    func._hj_allow_pending_password = allow_pending
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
# Lockout (stored in the LoginAttempts table so it survives restarts and is
# visible to the CLI)
# ---------------------------------------------------------------------------

def _lockout_keys(username, ip):
    return [f"user:{username}", f"ip:{ip}"]


def _lockout_remaining(username, ip):
    """Seconds left on the lockout for this username/IP, or 0."""
    now = time.time()
    remaining = 0
    for key in _lockout_keys(username, ip):
        entry = db.get_login_attempt(key)
        if entry and entry.LockedUntil > now:
            remaining = max(remaining, entry.LockedUntil - now)
    return int(remaining) + (1 if remaining else 0)


def _record_failure(username, ip):
    now = time.time()
    window = _settings["lockout_minutes"] * 60
    for key in _lockout_keys(username, ip):
        entry = db.get_login_attempt(key)
        count = entry.FailCount if entry and now - entry.LastAt <= window else 0
        count += 1
        until = now + window if count >= _settings["max_login_attempts"] else 0
        db.save_login_attempt(key, count, now, until, username)
    db.delete_stale_login_attempts(now - window * 2)


def _clear_failures(username, ip):
    for key in _lockout_keys(username, ip):
        db.delete_login_attempt(key)


def unlock(username=None, ip=None):
    """Clear the failed-login counter and lockout for a username and/or IP.

    With no arguments, clears every lockout. Returns the number of entries removed.
    """
    if username is None and ip is None:
        count = len(db.fetch_all("SELECT AttemptKey FROM LoginAttempts"))
        db.delete_all_login_attempts()
        return count
    removed = 0
    if username is not None:
        username = normalize_username(username)
        if db.get_login_attempt(f"user:{username}"):
            db.delete_login_attempt(f"user:{username}")
            removed += 1
        # Also lift IP lockouts caused by this user's own attempts, so the
        # person on the phone can log in straight away.
        ip_rows = [r for r in db.fetch_all("SELECT AttemptKey FROM LoginAttempts WHERE LastUser = ? AND AttemptKey LIKE 'ip:%'", (username,))]
        db.delete_login_attempts_by_user(username)
        removed += len(ip_rows)
    if ip is not None:
        if db.get_login_attempt(f"ip:{ip}"):
            db.delete_login_attempt(f"ip:{ip}")
            removed += 1
    return removed


def get_lockouts():
    """Currently locked-out usernames and IPs with seconds remaining."""
    now = time.time()
    result = []
    for entry in db.get_locked_attempts(now):
        kind, _, value = entry.AttemptKey.partition(":")
        result.append({"type": "username" if kind == "user" else "ip", "value": value,
                       "failures": entry.FailCount, "remaining": int(entry.LockedUntil - now) + 1})
    return result


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

def create_token_for_user(username, remember=False):
    """Mint a token and register its session row. Returns (token, lifetime_seconds)."""
    username = normalize_username(username)
    lifetime = _settings["lifetime"]
    if remember and _settings["remember_lifetime"]:
        lifetime = _settings["remember_lifetime"]
    now = int(time.time())
    expires = now + int(lifetime.total_seconds())
    jti = secrets.token_hex(16)
    db.create_session(jti, username, now, expires)
    payload = {"username": username, "jti": jti, "iat": now, "exp": expires}
    return jwt.encode(payload, _settings["secret"], algorithm="HS256"), int(lifetime.total_seconds())


def _decode(token, verify_exp=True):
    try:
        return jwt.decode(token, _settings["secret"], algorithms=["HS256"], options={"verify_exp": verify_exp})
    except jwt.InvalidTokenError:
        return None


def revoke_token(token):
    """Delete the session behind a token (ignores invalid tokens)."""
    payload = _decode(token, verify_exp=False)
    if payload and payload.get("jti"):
        db.delete_session(payload["jti"])


def revoke_sessions(username):
    db.delete_sessions_for_user(normalize_username(username))


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


def _user_dict(record):
    return {
        "username": record.Username,
        "role": record.Role or "user",
        "mustChangePassword": bool(record.MustChangePassword),
    }


def resolve_user(request):
    """Return the user dict for an authenticated request, else None. Never writes a response.

    Checks: signature + expiry, session row exists, user exists and is not
    disabled, idle timeout. Stores the session id on ``request._hj_jti``.
    """
    token = _token_from_request(request)
    if not token:
        return None
    payload = _decode(token)
    if not payload or not payload.get("jti"):
        return None

    now = time.time()
    session = db.get_session(payload["jti"])
    if session is None or session.Username != payload.get("username") or session.ExpiresAt < now:
        return None

    idle = _settings["idle_timeout"]
    if idle and session.LastSeen and now - session.LastSeen > idle.total_seconds():
        db.delete_session(session.Jti)
        audit("session_idle_expired", session.Username, None, request)
        return None

    record = db.get_user_by_username(session.Username)
    if record is None or record.Disabled:
        return None

    if now - (session.LastSeen or 0) > _TOUCH_INTERVAL:
        db.touch_session(session.Jti, now)

    request._hj_jti = session.Jti
    return _user_dict(record)


# Backwards-compatible name used by WebServer.checkAuth.
check_auth = resolve_user


def _session_cookie(token=None, max_age=None):
    """Build the Set-Cookie header value. ``token=None`` produces a clearing cookie."""
    parts = [f"{_settings['cookie_name']}={token or ''}", "Path=/", "HttpOnly", "SameSite=Strict"]
    parts.append(f"Max-Age={int(max_age) if token else 0}")
    if _settings["secure_cookie"]:
        parts.append("Secure")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _json_body(request):
    body = getattr(request, 'body', None)
    if body is None:
        content_length = int(request.headers.get('Content-Length', 0))
        try:
            body = json.loads(request.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None
    return body if isinstance(body, dict) else None


def _login_config_route(request):
    _send_json(request, 200, {
        "title": _settings["login_title"],
        "message": _settings["login_message"],
        "logo": _settings["login_logo"],
        "rememberMe": _settings["remember_lifetime"] is not None,
        "minPasswordLength": _settings["min_password_length"],
    })


def _login_route(request):
    credentials = _json_body(request)
    if credentials is None:
        _send_json(request, 400, {"error": "Invalid JSON payload."})
        return

    username = credentials.get("username")
    password = credentials.get("password")
    if not username or password is None:
        _send_json(request, 400, {"error": "Username and password are required."})
        return

    username = normalize_username(username)
    password = str(password)
    remember = bool(credentials.get("rememberMe"))
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

    if user_record.Disabled:
        audit("login_disabled", username, None, request)
        _send_json(request, 403, {"error": "This account is disabled."})
        return

    _clear_failures(username, ip)
    if needs_rehash(user_record.PasswordHash):
        db.update_user_password(username, hash_password(password), bool(user_record.MustChangePassword))
        audit("password_rehashed", username, "legacy plaintext upgraded", request)

    db.delete_expired_sessions(time.time())
    token, max_age = create_token_for_user(username, remember=remember)
    audit("login_ok", username, "remember me" if remember else None, request)
    _send_json(
        request, 200,
        {"valid": True, "message": "Login successful", "token": token, "user": _user_dict(user_record)},
        headers={"Set-Cookie": _session_cookie(token, max_age)},
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


def _logout_all_route(request):
    revoke_sessions(request.user["username"])
    audit("logout_all", request.user["username"], None, request)
    _send_json(request, 200, {"valid": False, "message": "Logged out everywhere"},
               headers={"Set-Cookie": _session_cookie(None)})


def _verify_route(request):
    # WebHandler already enforced authentication and populated request.user.
    _send_json(request, 200, {"valid": True, "user": request.user})


def _change_password_route(request):
    body = _json_body(request)
    if body is None:
        _send_json(request, 400, {"error": "Invalid JSON payload."})
        return
    current = body.get("currentPassword")
    new = body.get("newPassword")
    if current is None or new is None:
        _send_json(request, 400, {"error": "currentPassword and newPassword are required."})
        return

    username = request.user["username"]
    record = db.get_user_by_username(username)
    if record is None or not verify_password(str(current), record.PasswordHash):
        audit("password_change_failed", username, "wrong current password", request)
        _send_json(request, 401, {"error": "Current password is incorrect."})
        return
    try:
        check_password_policy(str(new))
    except ValueError as e:
        _send_json(request, 400, {"error": str(e)})
        return
    if str(new) == str(current):
        _send_json(request, 400, {"error": "New password must be different from the current one."})
        return

    db.update_user_password(username, hash_password(str(new)), must_change_password=False)
    # Keep this session, drop every other one (a stolen session dies here).
    keep = getattr(request, '_hj_jti', None)
    if keep:
        db.delete_other_sessions(username, keep)
    else:
        db.delete_sessions_for_user(username)
    audit("password_changed", username, "by user", request)
    _send_json(request, 200, {"valid": True, "message": "Password changed"})


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
