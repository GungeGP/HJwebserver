"""Authentication behind Authentik: proxy secret, user headers, roles, form token, audit.

The app has no login of its own. Authentik sits in front of it as forward
auth in the proxy (Nginx Proxy Manager): the proxy asks Authentik before every
request and only passes it on when the user is logged in. It then adds the
user in ``X-authentik-*`` headers, and a shared secret in ``X-Proxy-Secret``.

The secret is what makes the headers trustworthy. Anything on the proxy's
network can call the app directly with whatever headers it likes, so with
auth on every request without the right secret is refused (WebHandler calls
``proxy_secret_ok`` before anything else), and the user headers are only read
after that.

Roles come from the user's Authentik groups (``authentikRoles``). Requests
that change something carry a form token bound to the user (``form_token``),
so a page elsewhere can't send them in the user's name.

Usernames are case-insensitive: they are lower-cased at every boundary.
"""

import hashlib
import hmac
import os
import re
import time

from WebServer import database as db
from WebServer.helper import _send_json

MIN_SECRET_LENGTH = 32
PROXY_SECRET_HEADER = "X-Proxy-Secret"
FORM_TOKEN_HEADER = "X-CSRF-Token"
AUTHENTIK_SIGN_OUT = "/outpost.goauthentik.io/sign_out"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

_settings = {
    "secret": None,              # JWT_SECRET: signs the form token
    "proxy_secret": None,        # PROXY_SECRET: what the proxy sends in X-Proxy-Secret
    "audit": True,
    "trust_proxy": False,
    "role_hierarchy": None,      # list of roles, highest first, or None = exact role match
    "audit_retention": None,     # seconds or None = keep the audit log forever
    "authentik_roles": {},       # {Authentik group name: role}
    "dev_user": None,            # {"username", "name", "email", "groups"} in development mode
}


def normalize_username(username):
    return str(username or "").strip().lower()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure(host, audit=True, trust_proxy=False, role_hierarchy=None, audit_retention_days=None,
              authentik_roles=None, dev_user=None):
    """Validate and store auth settings. Called from WebServer.settings(auth=True).

    Raises (so the app refuses to start) when a secret is missing, or when
    devUser is set on a server that doesn't only listen on the local machine.
    """
    if role_hierarchy is not None:
        role_hierarchy = [str(r) for r in role_hierarchy]
        if not role_hierarchy or len(set(role_hierarchy)) != len(role_hierarchy):
            raise ValueError("roleHierarchy must be a non-empty list of distinct roles, highest first.")
    _settings["role_hierarchy"] = role_hierarchy

    if authentik_roles is not None and not isinstance(authentik_roles, dict):
        raise ValueError('authentikRoles must be a dict: {"<Authentik group>": "<role>"}.')
    authentik_roles = {str(group): str(role) for group, role in (authentik_roles or {}).items()}
    for role in authentik_roles.values():
        check_role(role)

    if dev_user is not None:
        dev_user = _dev_user(dev_user, host)

    secret = os.getenv("JWT_SECRET")
    if not secret or len(secret.encode("utf-8")) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            "JWT_SECRET is missing or shorter than 32 bytes. Set it in .env. Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    proxy_secret = os.getenv("PROXY_SECRET")
    if dev_user is None and not (proxy_secret or "").strip():
        # Only the name, never a value: this ends up in logs.
        raise RuntimeError(
            "PROXY_SECRET is missing or empty. Set it in .env; the proxy sends the same "
            "value in the X-Proxy-Secret header."
        )

    _settings.update(
        secret=secret,
        proxy_secret=proxy_secret if dev_user is None else None,
        audit=bool(audit),
        trust_proxy=bool(trust_proxy),
        audit_retention=audit_retention_days * 86400 if audit_retention_days else None,
        authentik_roles=authentik_roles,
        dev_user=dev_user,
    )


def _dev_user(dev_user, host):
    """Check devUser and return it in the shape request.user is built from."""
    if str(host).strip().lower().strip("[]") not in LOCAL_HOSTS:
        raise RuntimeError(
            f"devUser is only allowed when the server listens on the local machine "
            f"(host {', '.join(LOCAL_HOSTS)}), not {host!r}. Remove devUser, or use WebServer(port=...)."
        )
    if not isinstance(dev_user, dict) or not normalize_username(dev_user.get("username")):
        raise ValueError('devUser must be a dict with at least a username: {"username": "test", "groups": [...]}.')
    groups = dev_user.get("groups") or []
    if isinstance(groups, str) or not isinstance(groups, (list, tuple)):
        raise ValueError("devUser groups must be a list of Authentik group names.")
    return {"username": normalize_username(dev_user["username"]),
            "name": dev_user.get("name"), "email": dev_user.get("email"),
            "groups": [str(g) for g in groups]}


def attach_auth_routes(server):
    """Register the framework's auth routes on the server."""
    server.routes.setdefault('GET', {})
    _register(server, 'GET', '/logout', _logout_route, public=True)
    _register(server, 'GET', '/api/verify', _verify_route, public=False)


def on_server_start(routes):
    """Checks and messages that only make sense in a running server (not in
    the CLI, which also loads the app). Called from WebServer.start()."""
    hierarchy = _settings["role_hierarchy"]
    if hierarchy:
        for method, table in routes.items():
            for path, func in table.items():
                unknown = [r for r in (getattr(func, '_hj_roles', None) or []) if r not in hierarchy]
                if unknown:
                    raise RuntimeError(f"{method} {path} requires role {', '.join(unknown)}, which is not in "
                                       f"roleHierarchy {hierarchy}. Fix the spelling or add the role.")
    if _settings["audit_retention"]:
        db.delete_audit_before(time.time() - _settings["audit_retention"])

    print('[ auth ] Offentlige stier — sæt dem ind i Authentik som "stier uden login":')
    for pattern in public_path_patterns(routes):
        print(pattern)

    dev = _settings["dev_user"]
    if dev:
        print(f'[ auth ] UDVIKLINGSTILSTAND: alle er "{dev["username"]}" ({role_for_groups(dev["groups"])})')


def public_path_patterns(routes):
    """The public=True paths as anchored regular expressions, for Authentik's
    unauthenticated paths: the app's own first, then the framework's (its
    scripts and styles, which public pages load too, and /logout).

    A framework file served at both /x and /public/x becomes one line,
    ^(/public)?/x$.
    """
    public = {}
    for table in routes.values():
        for path, func in table.items():
            if getattr(func, '_hj_public', False):
                public.setdefault(path, func)

    own, framework = [], []
    for path, func in public.items():
        if path.startswith('/public/') and public.get(path[len('/public'):]) is func:
            continue   # folded into the line for path[len('/public'):]
        prefix = "(/public)?" if public.get('/public' + path) is func else ""
        pattern = f"^{prefix}{_regex_escape(path)}$"
        (framework if getattr(func, '_hj_framework', False) else own).append(pattern)
    return own + framework


def _regex_escape(path):
    # re.escape also escapes characters like "-" and "/", which is harmless in
    # Python but noisy to paste; only the ones that mean something in a regex.
    return re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", path)


def _register(server, method, path, func, public):
    if path in server.routes[method]:
        return
    func._hj_public = public
    func._hj_framework = True
    server.routes[method][path] = func


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def has_role(user_role, required):
    """True when ``user_role`` satisfies ``required`` (a list of roles).

    Without roleHierarchy the role must be one of them exactly. With one,
    "this role or higher" counts too: admin satisfies ["role1"].
    """
    if not required:
        return True
    if user_role in required:
        return True
    hierarchy = _settings["role_hierarchy"]
    if not hierarchy or user_role not in hierarchy:
        return False
    rank = hierarchy.index(user_role)
    return any(r in hierarchy and rank <= hierarchy.index(r) for r in required)


def describe_roles(roles):
    """"admin or role1", plus " or higher" when roles are ranked - for 403 messages and the audit log."""
    text = " or ".join(roles)
    return text + " or higher" if _settings["role_hierarchy"] else text


def lowest_role():
    """The role of a user in none of the authentikRoles groups."""
    hierarchy = _settings["role_hierarchy"]
    return hierarchy[-1] if hierarchy else "user"


def check_role(role):
    """Raise ValueError for a role that isn't in roleHierarchy (catches typos like "admn")."""
    hierarchy = _settings["role_hierarchy"]
    if hierarchy and role not in hierarchy:
        raise ValueError(f"Unknown role '{role}'. roleHierarchy allows: {', '.join(hierarchy)}")


def role_for_groups(groups):
    """The role for a user in these Authentik groups, by authentikRoles.

    With roleHierarchy the highest of the matching roles; without it the first
    match in the order authentikRoles lists the groups. No match: lowest_role().
    """
    mapping = _settings["authentik_roles"]
    groups = set(groups)
    matches = [role for group, role in mapping.items() if group in groups]
    if not matches:
        return lowest_role()
    hierarchy = _settings["role_hierarchy"]
    if hierarchy:
        return min(matches, key=hierarchy.index)
    return matches[0]


# ---------------------------------------------------------------------------
# Proxy secret and Authentik's headers
# ---------------------------------------------------------------------------

def proxy_secret_ok(request):
    """True when the request carries the proxy's secret (always in development mode).

    Compared in constant time. The header is then removed from the request,
    so nothing later (a handler printing its headers) can echo it.
    """
    if _settings["dev_user"]:
        return True
    expected = _settings["proxy_secret"]
    sent = request.headers.get(PROXY_SECRET_HEADER)
    if not expected or sent is None:
        return False
    # http.server decodes headers as latin-1, so that gives back the bytes that were sent.
    ok = hmac.compare_digest(sent.encode("latin-1", "replace"), expected.encode("utf-8"))
    if ok:
        del request.headers[PROXY_SECRET_HEADER]
    return ok


def _header(request, name):
    """A header as text. http.server decodes headers as latin-1, but Authentik
    sends names like "Søren" as UTF-8, so they are decoded again."""
    value = request.headers.get(name)
    if value is None:
        return None
    try:
        return value.encode("latin-1").decode("utf-8").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value.strip()


def _user(username, name, email, groups):
    return {"username": username, "name": name or username, "email": email or "",
            "role": role_for_groups(groups), "groups": list(groups)}


def resolve_user(request):
    """The user dict for a request, from Authentik's headers, else None. Never writes a response.

    Only call it once proxy_secret_ok() has passed: before that the headers
    can say anything. In development mode it is always the devUser.
    """
    dev = _settings["dev_user"]
    if dev:
        return _user(dev["username"], dev["name"], dev["email"], dev["groups"])
    username = normalize_username(_header(request, "X-authentik-username"))
    if not username:
        return None
    groups = [g.strip() for g in (_header(request, "X-authentik-groups") or "").split("|") if g.strip()]
    return _user(username, _header(request, "X-authentik-name"), _header(request, "X-authentik-email"), groups)


# Backwards-compatible name used by WebServer.checkAuth.
check_auth = resolve_user


# ---------------------------------------------------------------------------
# Form token
# ---------------------------------------------------------------------------

def form_token(username):
    """HMAC of the username with JWT_SECRET. auth.js sends it in X-CSRF-Token
    on every POST, PUT and DELETE; a page on another site can't know it."""
    return hmac.new(_settings["secret"].encode("utf-8"), normalize_username(username).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def form_token_ok(request, user):
    sent = request.headers.get(FORM_TOKEN_HEADER)
    if not sent or not user:
        return False
    return hmac.compare_digest(sent.encode("latin-1", "replace"), form_token(user["username"]).encode("utf-8"))


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
# Routes
# ---------------------------------------------------------------------------

def _logout_route(request):
    """GET /logout - to Authentik's sign-out, which ends the login for every app behind it."""
    user = resolve_user(request)
    audit("logout", user["username"] if user else None, None, request)
    request.send_response(302)
    request.send_header('Location', AUTHENTIK_SIGN_OUT)
    request.send_header('Cache-Control', 'no-store')
    request.end_headers()


def _verify_route(request):
    # WebHandler already enforced authentication and populated request.user.
    # roleHierarchy lets pages ask hjAuth.hasRole() with the same rule as the server.
    _send_json(request, 200, {"valid": True, "user": request.user, "roleHierarchy": _settings["role_hierarchy"],
                              "csrfToken": form_token(request.user["username"])})
