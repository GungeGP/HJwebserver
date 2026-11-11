"""Microsoft (Entra ID) login: OpenID Connect sign-in plus Microsoft Graph.

Turned on per app with settings(auth=True, ssoDomains=[...]); the app
registration comes from that app's .env (MS_TENANT_ID, MS_CLIENT_ID,
MS_CLIENT_SECRET). The password login keeps working next to it unless
ssoOnly is set. Spec: docs/SignInForm.md.

Flow:
  POST /api/login/start           decide Microsoft vs password for a typed name;
                                  for Microsoft, set the hj_sso state cookie and
                                  return Microsoft's authorize URL
  GET  /auth/microsoft/callback   check state, swap the code for tokens, validate
                                  the ID token, read Graph, link the user, then
                                  the same session as a password login

Microsoft never connects to this server - the browser carries every redirect,
and the server only makes outbound calls - so it works on localhost and on
internal host names.
"""

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from http.cookies import SimpleCookie

import jwt

from WebServer import auth
from WebServer import database as db
from WebServer.helper import _send_json

AUTHORITY = "https://login.microsoftonline.com"
GRAPH = "https://graph.microsoft.com/v1.0"
CALLBACK_PATH = "/auth/microsoft/callback"
STATE_COOKIE = "hj_sso"
STATE_SECONDS = 600          # the sign-in at Microsoft must finish within this
HTTP_TIMEOUT = 10            # seconds per call to Microsoft
DISCOVERY_TTL = 24 * 3600    # re-read Microsoft's endpoint list daily
CHECK_INTERVAL = 600         # microsoftCheckEnabled: seconds between checks
SECRET_WARN_DAYS = 30        # warn when MS_CLIENT_SECRET_EXPIRES is this close
SSO_ONLY_MESSAGE = ("This system requires Microsoft sign-in. "
                    "Contact your administrator if you believe this is wrong.")

_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_ms = {
    "enabled": False,
    "tenant": None,
    "client_id": None,
    "client_secret": None,
    "domains": [],
    "sso_only": False,
    "local_accounts": set(),
    "new_users": False,
    "roles": None,            # {group id (lower-case): role} or None
    "guests": False,
    "session": timedelta(hours=8),
    "logout": True,
    "check_enabled": False,
    "redirect_uri": None,
}

_discovery = {"doc": None, "at": 0.0, "jwks": None}
_discovery_lock = threading.Lock()
# First logins create or link a Users row; two at once for the same person
# would both try to insert it.
_link_lock = threading.Lock()


class SignInError(Exception):
    """A Microsoft login that can't go on. ``message`` is shown to the user,
    ``reason`` goes to the audit log only."""

    def __init__(self, message, reason, status=403, username=None):
        super().__init__(reason)
        self.message, self.reason, self.status, self.username = message, reason, status, username


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure(sso_domains, sso_only=False, local_accounts=None, new_users=False, roles=None,
              guests=False, session_hours=8, logout=True, check_enabled=False, redirect_uri=None):
    """Validate and store the Microsoft settings. Called from settings(auth=True, ssoDomains=...)."""
    if isinstance(sso_domains, str):
        sso_domains = [sso_domains]
    domains = [str(d).strip().lower().lstrip("@") for d in (sso_domains or []) if str(d).strip()]
    if not domains:
        raise ValueError("ssoDomains needs at least one domain, e.g. ssoDomains=[\"hjoerring.dk\"].")

    missing = [name for name in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET") if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"ssoDomains is set but {', '.join(missing)} is missing. Put the app registration in .env:\n"
            "  MS_TENANT_ID=<directory (tenant) id>\n  MS_CLIENT_ID=<application (client) id>\n"
            "  MS_CLIENT_SECRET=<client secret value>"
        )

    group_roles = None
    if roles:
        group_roles = {}
        for group_id, role in dict(roles).items():
            auth.check_role(str(role))
            group_roles[str(group_id).strip().lower()] = str(role)

    _ms.update(
        enabled=True,
        tenant=os.getenv("MS_TENANT_ID").strip(),
        client_id=os.getenv("MS_CLIENT_ID").strip(),
        client_secret=os.getenv("MS_CLIENT_SECRET"),
        domains=domains,
        sso_only=bool(sso_only),
        local_accounts={auth.normalize_username(n) for n in (local_accounts or [])},
        new_users=bool(new_users),
        roles=group_roles,
        guests=bool(guests),
        session=timedelta(hours=session_hours),
        logout=bool(logout),
        check_enabled=bool(check_enabled),
        redirect_uri=redirect_uri,
    )
    _warn_secret_expiry()


def _warn_secret_expiry():
    """MS_CLIENT_SECRET_EXPIRES=YYYY-MM-DD (optional): warn before the secret stops working."""
    raw = os.getenv("MS_CLIENT_SECRET_EXPIRES")
    if not raw:
        return
    try:
        expires = date.fromisoformat(raw.strip())
    except ValueError:
        print(f"[ microsoft ] warning: MS_CLIENT_SECRET_EXPIRES={raw!r} is not a YYYY-MM-DD date")
        return
    days = (expires - date.today()).days
    if days < 0:
        print(f"[ microsoft ] WARNING: the client secret expired {-days} days ago - Microsoft login will fail")
    elif days <= SECRET_WARN_DAYS:
        print(f"[ microsoft ] warning: the client secret expires in {days} days ({expires}); ask IT for a new one")


def enabled():
    return _ms["enabled"]


def sso_only():
    return _ms["enabled"] and _ms["sso_only"]


def groups_set_roles():
    """True when microsoftRoles decides Microsoft users' roles."""
    return _ms["enabled"] and bool(_ms["roles"])


def password_login_allowed(username):
    """Under ssoOnly only localAccounts may use a password. Otherwise anyone may."""
    return not sso_only() or auth.normalize_username(username) in _ms["local_accounts"]


def attach_routes(server):
    auth._register(server, 'POST', '/api/login/start', _start_route, public=True)
    auth._register(server, 'GET', CALLBACK_PATH, _callback_route, public=True)


def on_server_start():
    if _ms["enabled"] and _ms["check_enabled"]:
        threading.Thread(target=_check_loop, name="microsoft-check", daemon=True).start()


# ---------------------------------------------------------------------------
# Talking to Microsoft
# ---------------------------------------------------------------------------

def _http_json(url, data=None, token=None):
    """GET (or POST a form when ``data`` is given) and return the JSON answer."""
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            detail = {}
        err = detail.get("error")
        if isinstance(err, dict):   # Graph: {"error": {"code", "message"}}
            err = f"{err.get('code')}: {err.get('message')}"
        elif detail.get("error_description"):   # token endpoint
            err = f"{err}: {detail['error_description'].splitlines()[0]}"
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {err or e.reason}") from None


def _endpoints():
    """Microsoft's OpenID configuration for the tenant (cached), plus a key client for its signing keys."""
    with _discovery_lock:
        if _discovery["doc"] is None or time.time() - _discovery["at"] > DISCOVERY_TTL:
            doc = _http_json(f"{AUTHORITY}/{_ms['tenant']}/v2.0/.well-known/openid-configuration")
            _discovery.update(doc=doc, at=time.time(),
                              jwks=jwt.PyJWKClient(doc["jwks_uri"], cache_keys=True, timeout=HTTP_TIMEOUT))
        return _discovery["doc"], _discovery["jwks"]


def _scopes():
    scopes = ["openid", "profile", "email", "User.Read"]
    if _ms["roles"]:
        scopes.append("GroupMember.Read.All")
    return " ".join(scopes)


def _redirect_uri(request):
    if _ms["redirect_uri"]:
        return _ms["redirect_uri"]
    host = request.headers.get("Host") or "localhost"
    scheme = "https" if auth._settings["secure_cookie"] else "http"
    if auth._settings["trust_proxy"]:
        host = (request.headers.get("X-Forwarded-Host") or host).split(",")[0].strip()
        scheme = (request.headers.get("X-Forwarded-Proto") or scheme).split(",")[0].strip()
    return f"{scheme}://{host}{CALLBACK_PATH}"


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _safe_next(value):
    """Only paths on this site: "/cal?x=1" yes, "//evil.example" or "https://..." no."""
    value = str(value or "")
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    return value


# ---------------------------------------------------------------------------
# POST /api/login/start
# ---------------------------------------------------------------------------

def _start_route(request):
    body = auth._json_body(request)
    if body is None:
        _send_json(request, 400, {"error": "Invalid JSON payload."})
        return
    typed = str(body.get("username") or "").strip().lower()
    if not typed:
        _send_json(request, 400, {"error": "Enter your username or work email."})
        return
    if not _ms["enabled"]:
        _send_json(request, 200, {"method": "password"})
        return

    method, hint = _decide(typed)
    if method == "refuse":
        _send_json(request, 403, {"error": SSO_ONLY_MESSAGE})
    elif method == "password":
        _send_json(request, 200, {"method": "password"})
    else:
        _begin_microsoft(request, hint, _safe_next(body.get("next")))


def _decide(typed):
    """("microsoft", login hint) / ("password", None) / ("refuse", None) for a typed name.

    Mail addresses are decided by the domain alone. Only a bare name looks in
    Users, and only when local accounts are allowed at all.
    """
    if "@" in typed:
        if typed.rsplit("@", 1)[1] in _ms["domains"]:
            return "microsoft", typed
        return ("refuse", None) if _ms["sso_only"] else ("password", None)
    name = auth.normalize_username(typed)
    full = f"{name}@{_ms['domains'][0]}"
    if _ms["sso_only"]:
        return ("password", None) if name in _ms["local_accounts"] else ("microsoft", full)
    record = db.get_user_by_username(name)
    if record is not None and record.PasswordHash:
        return "password", None   # a local account with this exact name wins
    return "microsoft", full


def _begin_microsoft(request, hint, next_path):
    try:
        doc, _ = _endpoints()
    except Exception as e:
        print(f"[ microsoft ] could not read Microsoft's sign-in configuration: {e}")
        _send_json(request, 502, {"error": "Could not reach Microsoft sign-in. Try again in a moment."})
        return

    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    redirect_uri = _redirect_uri(request)
    cookie = jwt.encode({"state": state, "nonce": nonce, "verifier": verifier, "next": next_path,
                         "redirect_uri": redirect_uri, "exp": int(time.time()) + STATE_SECONDS},
                        auth._settings["secret"], algorithm="HS256")
    params = {
        "client_id": _ms["client_id"],
        "response_type": "code",
        "response_mode": "query",
        "redirect_uri": redirect_uri,
        "scope": _scopes(),
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
        # Pre-fills Microsoft's page, and makes it sign in this account rather
        # than whichever one the browser remembers (shared PCs).
        "login_hint": hint,
    }
    url = doc["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    _send_json(request, 200, {"method": "microsoft", "redirect": url},
               headers={"Set-Cookie": _state_cookie(cookie)})


def _state_cookie(value=None):
    """hj_sso: SameSite=Lax because it must ride along on the redirect back from
    Microsoft (a cross-site navigation, which Strict cookies sit out)."""
    parts = [f"{STATE_COOKIE}={value or ''}", f"Path={CALLBACK_PATH}", "HttpOnly", "SameSite=Lax",
             f"Max-Age={STATE_SECONDS if value else 0}"]
    if auth._settings["secure_cookie"]:
        parts.append("Secure")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# GET /auth/microsoft/callback
# ---------------------------------------------------------------------------

def _callback_route(request):
    query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(request.path).query).items()}
    state = _read_state_cookie(request)
    next_path = state["next"] if state else "/"
    try:
        username = _finish_sign_in(request, query, state)
    except SignInError as e:
        auth.audit("sso_login_failed", e.username, e.reason, request)
        _page(request, e.status, "Sign-in failed", e.message, next_path)
        return
    except Exception as e:
        auth.audit("sso_login_failed", None, f"error: {e}", request)
        _page(request, 502, "Sign-in failed", "Could not complete the Microsoft sign-in. Try again in a moment.",
              next_path)
        return

    auth._housekeeping()
    token, max_age = auth.create_token_for_user(username, lifetime=_ms["session"])
    auth.audit("sso_login_ok", username, None, request)
    # A 200 page that moves on by itself, not a 302: the redirect chain began
    # at Microsoft, so the browser would treat a 302 hop as cross-site and
    # leave out the new SameSite=Strict session cookie. The refresh below is a
    # fresh, same-site navigation, so the cookie goes along.
    target = html.escape(next_path, quote=True)
    body = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={target}">'
            f'<title>Signing in</title></head><body><p>Signing in&hellip; <a href="{target}">Continue</a></p></body></html>')
    request.send_response(200)
    request.send_header("Content-Type", "text/html; charset=utf-8")
    request.send_header("Cache-Control", "no-store")
    request.send_header("Set-Cookie", auth._session_cookie(token, max_age))
    request.send_header("Set-Cookie", _state_cookie(None))
    request.end_headers()
    request.wfile.write(body.encode("utf-8"))


def _read_state_cookie(request):
    cookies = SimpleCookie()
    try:
        cookies.load(request.headers.get("Cookie") or "")
    except Exception:
        return None
    morsel = cookies.get(STATE_COOKIE)
    if not morsel:
        return None
    try:
        return jwt.decode(morsel.value, auth._settings["secret"], algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def _finish_sign_in(request, query, state):
    """Everything between Microsoft's redirect and the session. Returns the username."""
    if not _ms["enabled"]:
        raise SignInError("Microsoft sign-in is not enabled here.", "callback while disabled", status=404)
    if state is None:
        raise SignInError("The sign-in took too long or was started in another browser. Please try again.",
                          "missing or expired state cookie", status=400)
    if query.get("error"):
        # e.g. access_denied (cancelled, or the user isn't assigned to the app in Entra)
        description = (query.get("error_description") or "").splitlines()[0][:200]
        raise SignInError("Microsoft sign-in was cancelled or refused.",
                          f"microsoft: {query['error']} {description}".strip())
    if not hmac.compare_digest(str(query.get("state") or ""), state["state"]):
        raise SignInError("The sign-in could not be verified. Please try again.", "state mismatch", status=400)
    if not query.get("code"):
        raise SignInError("The sign-in could not be verified. Please try again.", "no code", status=400)

    doc, jwks = _endpoints()
    tokens = _http_json(doc["token_endpoint"], data={
        "grant_type": "authorization_code",
        "client_id": _ms["client_id"],
        "client_secret": _ms["client_secret"],
        "code": query["code"],
        "redirect_uri": state["redirect_uri"],
        "code_verifier": state["verifier"],
        "scope": _scopes(),
    })
    claims = _validate_id_token(tokens.get("id_token"), doc, jwks, state["nonce"])

    access = tokens.get("access_token")
    profile = _http_json(f"{GRAPH}/me?$select=id,displayName,mail,userPrincipalName,userType", token=access)
    upn = auth.normalize_username(profile.get("userPrincipalName") or claims.get("preferred_username"))
    oid = str(claims["oid"])
    if profile.get("id") and str(profile["id"]) != oid:
        raise SignInError("The sign-in could not be verified. Please try again.", "Graph id differs from token oid")
    is_guest = profile.get("userType") == "Guest" or "#ext#" in upn
    if is_guest and not _ms["guests"]:
        raise SignInError("Guest accounts can't sign in to this system.", "guest account", username=upn)

    groups = _group_ids(access) if _ms["roles"] else set()
    return _link_user(request, oid, upn, profile.get("displayName"), profile.get("mail"), groups)


def _validate_id_token(id_token, doc, jwks, nonce):
    if not id_token:
        raise SignInError("The sign-in could not be verified. Please try again.", "no id_token")
    try:
        key = jwks.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=_ms["client_id"],
                            issuer=doc["issuer"], leeway=60,
                            options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.PyJWTError as e:
        raise SignInError("The sign-in could not be verified. Please try again.", f"id_token: {e}") from None
    if not hmac.compare_digest(str(claims.get("nonce") or ""), nonce):
        raise SignInError("The sign-in could not be verified. Please try again.", "nonce mismatch")
    if not claims.get("oid"):
        raise SignInError("The sign-in could not be verified. Please try again.", "no oid claim")
    if _GUID.match(_ms["tenant"]) and str(claims.get("tid", "")).lower() != _ms["tenant"].lower():
        raise SignInError("This account belongs to another organization.", f"tid {claims.get('tid')}")
    return claims


def _group_ids(access_token):
    """Object ids of every group the user is in, nested groups included."""
    ids = set()
    url = f"{GRAPH}/me/transitiveMemberOf/microsoft.graph.group?$select=id&$top=999"
    while url:
        page = _http_json(url, token=access_token)
        ids.update(str(g["id"]).lower() for g in page.get("value", []) if g.get("id"))
        url = page.get("@odata.nextLink")
    return ids


def _role_from_groups(group_ids):
    """Highest mapped role among the user's groups (roleHierarchy order, else
    the order of microsoftRoles); the lowest role when no group matches."""
    matched = [role for group_id, role in _ms["roles"].items() if group_id in group_ids]
    if not matched:
        return auth.lowest_role()
    hierarchy = auth._settings["role_hierarchy"]
    return min(matched, key=hierarchy.index) if hierarchy else matched[0]


def _link_user(request, oid, upn, display_name, email, groups):
    """Find, link or create the Users row for a Microsoft account. Returns its username.

    The username is fixed at the first login and never renamed (apps store it
    in their own tables); DisplayName and Email carry the current name.
    """
    with _link_lock:
        record = db.get_user_by_external_id(oid)
        if record is None:
            record = db.get_user_by_username(upn)
            if record is not None:
                if record.PasswordHash:
                    # Never take over a local account: a Microsoft "admin@..." must not become the local admin.
                    raise SignInError("This name belongs to a local account. Ask an administrator.",
                                      "name belongs to a local account", username=upn)
                if record.ExternalId and record.ExternalId != oid:
                    raise SignInError("This name is linked to another Microsoft account. Ask an administrator.",
                                      "linked to another oid", username=upn)
                db.set_sso_profile(upn, oid, display_name, email)
                auth.audit("sso_user_linked", upn, None, request)
            elif _ms["new_users"]:
                role = _role_from_groups(groups) if _ms["roles"] else auth.lowest_role()
                db.create_sso_user(upn, role=role, external_id=oid, display_name=display_name, email=email)
                auth.audit("sso_user_provisioned", upn, f"role={role}", request)
            else:
                raise SignInError("You don't have access to this system. Ask an administrator.",
                                  "no such user (microsoftNewUsers=False)", username=upn)
            record = db.get_user_by_external_id(oid)

    username = record.Username
    if record.Disabled:
        raise SignInError("This account is disabled.", "account disabled", username=username)
    if (record.DisplayName, record.Email) != (display_name, email):
        db.set_sso_profile(username, oid, display_name, email)
    if _ms["roles"] and not record.RolePinned:
        role = _role_from_groups(groups)
        if role != (record.Role or "user"):
            db.set_user_role(username, role)
            auth.audit("sso_role_changed", username, f"{record.Role or 'user'} -> {role}, from Microsoft groups", request)
    return username


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout_url(request, user):
    """Microsoft's sign-out URL for a Microsoft user when microsoftLogout is on, else None."""
    if not (_ms["enabled"] and _ms["logout"] and user and user.get("source") == "microsoft"):
        return None
    try:
        doc, _ = _endpoints()
    except Exception:
        return None   # Microsoft unreachable: the local logout still happened
    end_session = doc.get("end_session_endpoint")
    if not end_session:
        return None
    parts = urllib.parse.urlsplit(_redirect_uri(request))
    home = f"{parts.scheme}://{parts.netloc}/"
    return end_session + "?" + urllib.parse.urlencode({"post_logout_redirect_uri": home})


# ---------------------------------------------------------------------------
# microsoftCheckEnabled: end sessions of accounts disabled in Entra
# ---------------------------------------------------------------------------

def _check_loop():
    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            check_enabled_accounts()
        except Exception as e:
            print(f"[ microsoft ] account check failed: {e}")


def check_enabled_accounts():
    """Ask Graph (as the app itself) whether each signed-in Microsoft user is
    still enabled; revoke the sessions of those who aren't, or no longer exist.
    Needs the User.Read.All application permission."""
    users = db.get_sso_users_with_sessions(time.time())
    if not users:
        return
    doc, _ = _endpoints()
    token = _http_json(doc["token_endpoint"], data={
        "grant_type": "client_credentials",
        "client_id": _ms["client_id"],
        "client_secret": _ms["client_secret"],
        "scope": "https://graph.microsoft.com/.default",
    })["access_token"]
    for user in users:
        try:
            info = _http_json(f"{GRAPH}/users/{urllib.parse.quote(user.ExternalId)}?$select=accountEnabled", token=token)
            gone = info.get("accountEnabled") is False
        except RuntimeError as e:
            if "HTTP 404" not in str(e):
                print(f"[ microsoft ] could not check {user.Username}: {e}")
                continue
            gone = True
        if gone:
            auth.revoke_sessions(user.Username)
            auth.audit("sso_user_expired", user.Username, "disabled or deleted in Entra")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def _page(request, status, title, message, next_path):
    """A small styled page for a sign-in that didn't work, with a way back."""
    target = html.escape(next_path, quote=True)
    body = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{html.escape(title)}</title><link rel="stylesheet" href="/css/auth.css"></head>'
        '<body><div id="login-overlay" style="display:flex"><div class="login-box"><div class="headerLine"></div>'
        f'<form><h2>{html.escape(title)}</h2><p>{html.escape(message)}</p>'
        f'<a class="button" href="{target}">Try again</a></form></div></div></body></html>'
    )
    request.send_response(status)
    request.send_header("Content-Type", "text/html; charset=utf-8")
    request.send_header("Cache-Control", "no-store")
    request.send_header("Set-Cookie", _state_cookie(None))
    request.end_headers()
    request.wfile.write(body.encode("utf-8"))
