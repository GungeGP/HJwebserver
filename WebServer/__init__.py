from http.server import HTTPServer
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

from WebServer.FileHandler import handle_file_request
from WebServer.WebHandler import WebHandler
from WebServer.database import createConnection, get_connection, create_tables

DEFAULT_CSP = (
    "default-src 'self' https:; "
    "script-src 'self' https: 'unsafe-inline'; "
    "style-src 'self' https: 'unsafe-inline'; "
    "img-src 'self' https: data:; "
    "font-src 'self' https: data:; "
    "connect-src 'self' https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class WebServer:
    """The clean interface your teammates will actually use."""
    
    def __init__(self, host="127.0.0.1", port=8000, static_dir: str = None):
        self.host = host
        self.port = port
        self.routes = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
        self.auth = None
        self.certfile = None
        self.keyfile = None
        self.csp = DEFAULT_CSP
        self.security_headers_enabled = True
        self.max_body_bytes = 10 * 1024 * 1024   # largest accepted request body

        # Where the installed package's bundled static files live, split into
        # public/js and public/css the same way a consumer's own static_dir
        # may override any of them (e.g. static_dir/js/auth.js).
        self.package_public_dir = os.path.join(os.path.dirname(__file__), 'public')
        self.framework_assets_prefix = '/framework-assets/'

        # Allow callers to override where static files live. If not provided,
        # try several sensible locations so the framework works when used
        # either as a script or when imported as a package.
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

        self.static_dir = None
        if static_dir:
            candidate = os.path.abspath(static_dir)
            if os.path.exists(candidate) and os.path.isdir(candidate):
                self.static_dir = candidate

        if not self.static_dir:
            candidates = []
            # 1) directory of the calling script (works when run as script)
            try:
                caller_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                if caller_dir:
                    candidates.append(caller_dir)
            except Exception:
                pass
            # 2) current working directory (common when running from project root)
            try:
                candidates.append(os.getcwd())
            except Exception:
                pass
            # 3) package parent dir (works when imported as a package)
            candidates.append(self.base_dir)
            # 4) package internal public folder (works for installed pip packages)
            candidates.append(os.path.join(os.path.dirname(__file__), 'public'))

            for candidate in candidates:
                if candidate.endswith(os.sep + 'public') or candidate.endswith('/public'):
                    default_public_folder = candidate
                else:
                    default_public_folder = os.path.join(candidate, 'public')

                if os.path.exists(default_public_folder) and os.path.isdir(default_public_folder):
                    self.static_dir = default_public_folder
                    self.base_dir = os.path.dirname(default_public_folder)
                    break

        if self.static_dir:
            print(f"[ web_framework ] Static file serving enabled from: {self.static_dir}")
        else:
            print("[ web_framework ] No 'public' folder found. Static file serving is disabled. To enable, create a 'public' directory next to your script or pass `static_dir` to WebServer.")

        # Always inject canonical framework routes.
        self.default_js = '/js/webserver.js'
        self.auth_js = '/js/auth.js'
        print(f"[ web_framework ] Default script injection enabled: {self.default_js}")

        # TableViewer.js is only injected once a table is actually exposed
        # (see addTableViewer()), so pages that never use it don't load it.
        self.table_viewer_js = '/js/TableViewer.js'
        self.table_viewer_enabled = False

        # Register framework-provided js/css asset routes inside the server.
        self._register_asset_route('/js/auth.js', 'js/auth.js', 'application/javascript',
                                    gate=lambda: bool(self.auth))
        self._register_asset_route('/js/webserver.js', 'js/webserver.js', 'application/javascript',
                                    extra_relative_fallback='js/default.js')
        self._register_asset_route('/js/TableViewer.js', 'js/TableViewer.js', 'application/javascript')
        self._register_asset_route('/css/TableViewer.css', 'css/TableViewer.css', 'text/css')
        self._register_asset_route('/css/auth.css', 'css/auth.css', 'text/css')

    def _register_asset_route(self, url_path, relative_path, content_type, gate=None, extra_relative_fallback=None):
        """Serve a framework-bundled js/css file, overridable by dropping the
        same relative path under the consumer's own static_dir (e.g. a local
        static_dir/js/auth.js wins over the package's copy).

        gate: optional no-arg callable; a falsy result serves 404 (used so
              auth.js/auth.css 404 when auth isn't enabled).
        extra_relative_fallback: a second relative path tried after the
              primary one, both locally and in the package (webserver.js
              falls back to a consumer's own js/default.js).
        """
        def _find(base):
            if not base:
                return None
            for rel in (relative_path, extra_relative_fallback):
                if not rel:
                    continue
                candidate = os.path.join(base, *rel.split('/'))
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    return candidate
            return None

        @self.route('GET', url_path, public=True)
        def serve(request):
            if gate is not None and not gate():
                request.send_response(404)
                request.end_headers()
                return

            path = _find(self.static_dir) or _find(self.package_public_dir)
            if not path:
                request.send_response(404)
                request.end_headers()
                return

            with open(path, 'rb') as f:
                content = f.read()

            request.send_response(200)
            request.send_header('Content-Type', content_type)
            request.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.send_header('Pragma', 'no-cache')
            request.send_header('Expires', '0')
            request.end_headers()
            request.wfile.write(content)

        return serve

    def addPath(self, url_path, file_path, public=False, roles=None):
        """Maps a URL to ANY file, safely resolving the path.

        When auth is enabled the page requires login unless public=True.
        roles=["admin"] restricts it to users with one of those roles.
        """
        self.routes = handle_file_request(self, url_path, file_path, public=public, roles=roles)

    def addTableViewer(self, url_path, table, roles=None, public=False, limit=40):
        """Expose a database table as a paginated/searchable/sortable JSON feed for TableViewer.js.

        GET url_path?page=1&limit=40&search=...&sort=Column&dir=asc returns
            {"rows", "columns", "page", "limit", "total", "totalPages", "sort", "sortDir", "search"}

        table:  real table name; re-checked against the live schema on every
                request (table names can't be bound as query parameters).
        limit:  rows PER PAGE, and also the ceiling - the client may ask for
                fewer with ?limit=N (or via data-tableviewer-limit in HTML),
                but never more than this.
        roles/public: same meaning as route() - defaults to requiring login,
                no specific role.

        Also turns on TableViewer.js injection (see get_inject_js_urls()), so
        in your own HTML you only need:
            <div data-tableviewer="url_path"></div>
        """
        from WebServer.database import get_table_page

        @self.route('GET', url_path, public=public, roles=roles)
        def table_viewer_route(request):
            query = parse_qs(urlparse(request.path).query)

            def _int(name, default):
                try:
                    return int(query.get(name, [default])[0])
                except (TypeError, ValueError):
                    return default

            page = max(1, _int('page', 1))
            per_page = max(1, min(_int('limit', limit), limit))
            search = (query.get('search', [''])[0] or '').strip()
            sort = (query.get('sort', [None])[0]) or None
            sort_dir = (query.get('dir', ['asc'])[0]) or 'asc'

            try:
                rows, total, columns = get_table_page(
                    table, page=page, per_page=per_page, search=search or None,
                    sort=sort, sort_dir=sort_dir)
            except ValueError as e:
                request.send_response(404)
                request.send_header('Content-Type', 'application/json')
                request.end_headers()
                request.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

            total_pages = max(1, -(-total // per_page))  # ceil division
            payload = {
                "rows": rows,
                "columns": columns,
                "page": page,
                "limit": per_page,
                "total": total,
                "totalPages": total_pages,
                "sort": sort,
                "sortDir": sort_dir,
                "search": search,
            }

            request.send_response(200)
            request.send_header('Content-Type', 'application/json')
            request.end_headers()
            # mssql/mysql drivers return DATE/TIME/DECIMAL columns as native
            # Python objects (date, time, Decimal, ...) that json can't
            # serialize directly; default=str renders them the same way
            # TableViewer.js would display them anyway.
            request.wfile.write(json.dumps(payload, default=str).encode('utf-8'))

        self.table_viewer_enabled = True
        return table_viewer_route

    def settings(self, auth=None, jwtSecret=None, tokenLifetimeHours=24, secureCookie=False,
                 bearerTokens=True, maxLoginAttempts=5, lockoutMinutes=15, minPasswordLength=5,
                 auditLog=True, trustProxy=False, csp=DEFAULT_CSP, securityHeaders=True,
                 rememberMeDays=30, idleTimeoutMinutes=0,
                 loginTitle="Access Restricted", loginMessage="Please log in to continue.", loginLogo=None):
        """Configure server settings.

        auth:               enable authentication. Every route and page then requires
                            login unless registered with public=True.
        jwtSecret:          signing secret (>= 32 bytes). Defaults to JWT_SECRET from .env.
        tokenLifetimeHours: how long a normal login stays valid.
        rememberMeDays:     lifetime when the user ticks "Remember me". 0 hides the checkbox.
        idleTimeoutMinutes: log out sessions with no activity for this long. 0 = off.
        secureCookie:       add the Secure flag to the session cookie (needs HTTPS;
                            set automatically by useHttps()).
        bearerTokens:       also accept "Authorization: Bearer <token>" (for scripts).
                            False = cookie only.
        maxLoginAttempts:   failed logins (per username and per IP) before lockout.
        lockoutMinutes:     how long a lockout lasts.
        minPasswordLength:  enforced by createUser / setPassword / change-password.
        auditLog:           write logins, logouts, lockouts and user changes to the AuditLog table.
        trustProxy:         read the client IP from X-Forwarded-For (only behind a reverse proxy).
        csp:                Content-Security-Policy header value, or None to send none.
        securityHeaders:    send X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP.
        loginTitle/loginMessage/loginLogo: text and optional image URL shown on the login form.
        """
        self.auth = auth
        self.csp = csp
        self.security_headers_enabled = bool(securityHeaders)
        if self.auth:
            from WebServer.auth import attach_auth_routes, configure
            configure(
                jwt_secret=jwtSecret,
                token_lifetime_hours=tokenLifetimeHours,
                secure_cookie=secureCookie or bool(self.certfile),
                bearer_tokens=bearerTokens,
                max_login_attempts=maxLoginAttempts,
                lockout_minutes=lockoutMinutes,
                min_password_length=minPasswordLength,
                audit=auditLog,
                trust_proxy=trustProxy,
                remember_me_days=rememberMeDays,
                idle_timeout_minutes=idleTimeoutMinutes,
                login_title=loginTitle,
                login_message=loginMessage,
                login_logo=loginLogo,
            )
            attach_auth_routes(self)

    def useHttps(self, certfile, keyfile):
        """Serve over TLS using a PEM certificate and private key.

        Also turns on the Secure cookie flag and HSTS. For a local self-signed pair:
          openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
        """
        for path in (certfile, keyfile):
            if not os.path.isfile(path):
                raise FileNotFoundError(f"useHttps: file not found: {path}")
        self.certfile = certfile
        self.keyfile = keyfile
        if self.auth:
            from WebServer.auth import _settings
            _settings["secure_cookie"] = True

    def setDatabase(self, type="mssql", server="localhost", dbName="test", user=None, password=None, port=None, createTables=True):
        """Configure the database backend.

        type:         "sqlite", "mssql" or "mysql"
        server:       hostname of the database server (ignored for sqlite)
        dbName:       database name, or the .db file path for sqlite
        user:         username (mysql, or mssql SQL-auth; omit for mssql Windows auth)
        password:     password for `user`
        port:         optional port override
        createTables: create the Users / WorkTimeEntries tables if they don't exist (default True)
        """
        createConnection(type=type, server=server, dbName=dbName, user=user, password=password, port=port)
        if createTables:
            create_tables()

    def getDatabaseConnection(self):
        """Return a new raw DB-API connection for the configured backend. Caller must close it."""
        return get_connection()

    def checkAuth(self, request):
        """Return the user dict for an authenticated request, else None.

        Protected routes already have this in ``request.user``; this is only
        useful inside public=True routes that want to know if someone is logged in.
        """
        if not self.auth:
            return None
        from WebServer.auth import resolve_user
        return resolve_user(request)

    def createUser(self, username, password, role="user", mustChangePassword=False):
        """Create a user with a hashed password. Returns False if the username already exists.

        role:               free-form string, e.g. "user" or "admin"; checked by route(roles=[...]).
        mustChangePassword: True forces the user to pick a new password on first login.
        Raises ValueError if the password is shorter than minPasswordLength.
        """
        from WebServer.auth import audit, check_password_policy, hash_password, normalize_username
        from WebServer.database import create_user, get_user_by_username
        username = normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is not None:
            return False
        create_user(username, hash_password(str(password)), role=str(role or "user"), must_change_password=mustChangePassword)
        audit("user_created", username, f"role={role}")
        return True

    def setPassword(self, username, password, mustChangePassword=False):
        """Replace a user's password and log them out everywhere. Returns False if the user does not exist.

        mustChangePassword=True makes it a temporary password the user must replace at next login.
        """
        from WebServer.auth import audit, check_password_policy, hash_password, normalize_username, revoke_sessions
        from WebServer.database import get_user_by_username, update_user_password
        username = normalize_username(username)
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is None:
            return False
        update_user_password(username, hash_password(str(password)), must_change_password=mustChangePassword)
        revoke_sessions(username)
        audit("password_changed", username, "by admin" + (", temporary" if mustChangePassword else ""))
        return True

    def setRole(self, username, role):
        """Change a user's role. Takes effect on their next request. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username
        from WebServer.database import get_user_by_username, set_user_role
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        set_user_role(username, str(role))
        audit("role_changed", username, f"role={role}")
        return True

    def disableUser(self, username):
        """Block logins and end all sessions, keeping the account. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        from WebServer.database import get_user_by_username, set_user_disabled
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        set_user_disabled(username, True)
        revoke_sessions(username)
        audit("user_disabled", username)
        return True

    def enableUser(self, username):
        """Re-enable a disabled account. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username
        from WebServer.database import get_user_by_username, set_user_disabled
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        set_user_disabled(username, False)
        audit("user_enabled", username)
        return True

    def deleteUser(self, username):
        """Remove a user and all their sessions. Returns False if the user does not exist."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        from WebServer.database import delete_user, get_user_by_username
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        revoke_sessions(username)
        delete_user(username)
        audit("user_deleted", username)
        return True

    def getUser(self, username):
        """{"username", "role", "disabled", "mustChangePassword"} or None."""
        from WebServer.auth import normalize_username
        from WebServer.database import get_user_by_username
        record = get_user_by_username(normalize_username(username))
        return self._public_user(record) if record else None

    def listUsers(self):
        """All users as [{"username", "role", "disabled", "mustChangePassword"}], sorted by name."""
        from WebServer.database import get_all_users
        return [self._public_user(r) for r in get_all_users()]

    @staticmethod
    def _public_user(record):
        return {"username": record.Username, "role": record.Role or "user",
                "disabled": bool(record.Disabled), "mustChangePassword": bool(record.MustChangePassword)}

    def revokeSessions(self, username):
        """Log a user out of every browser/device immediately."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        username = normalize_username(username)
        revoke_sessions(username)
        audit("sessions_revoked", username)

    def unlock(self, username=None, ip=None):
        """Lift a login lockout early. unlock("alice") or unlock(ip="10.0.0.5"); no arguments = all."""
        from WebServer.auth import audit, unlock
        removed = unlock(username, ip)
        audit("lockout_cleared", username, f"ip={ip}" if ip else ("all" if username is None else None))
        return removed

    def getLockouts(self):
        """Who is currently locked out: [{"type": "username"|"ip", "value", "failures", "remaining"}]."""
        from WebServer.auth import get_lockouts
        return get_lockouts()

    def getSessions(self, username):
        """Active sessions for a user (Jti, Username, CreatedAt, ExpiresAt, LastSeen as epoch seconds)."""
        from WebServer.auth import normalize_username
        from WebServer.database import get_sessions_for_user
        return get_sessions_for_user(normalize_username(username))

    def audit(self, request, event, detail=None):
        """Record your own event in the AuditLog, attributed to the request's user and IP."""
        from WebServer.auth import audit
        user = getattr(request, 'user', None) or {}
        audit(event, user.get("username"), detail, request)

    def getAuditLog(self, limit=100, username=None):
        """Most recent audit entries (Id, At, Username, Event, Detail, Ip), newest first."""
        from WebServer.database import get_audit_log
        return get_audit_log(limit=limit, username=username)

    def _asset_version(self, relative_file_name):
        """Return a stable cache-busting token for the active JS asset."""
        candidate_paths = []
        if self.static_dir:
            candidate_paths.append(os.path.join(self.static_dir, relative_file_name))
        candidate_paths.append(os.path.join(self.package_public_dir, relative_file_name))

        for candidate_path in candidate_paths:
            if os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                return str(int(os.path.getmtime(candidate_path)))
        return None
    
    def createAuth(self, username):
        """Create a session token for a user without a password (for scripts/tests). Requires settings(auth=True)."""
        from WebServer.auth import audit, create_token_for_user
        if not self.auth:
            raise RuntimeError("Authentication is not enabled. Use settings(auth=True) first.")
        token, _ = create_token_for_user(username)
        audit("token_issued", username, "createAuth")
        return token

    def get_inject_js_urls(self):
        urls = []
        if self.default_js:
            version = self._asset_version('js/webserver.js') or self._asset_version('js/default.js')
            urls.append(f"{self.default_js}?v={version}" if version else self.default_js)
        if self.auth and self.auth_js:
            version = self._asset_version('js/auth.js')
            urls.append(f"{self.auth_js}?v={version}" if version else self.auth_js)
        if self.table_viewer_enabled:
            version = self._asset_version('js/TableViewer.js')
            urls.append(f"{self.table_viewer_js}?v={version}" if version else self.table_viewer_js)
        return urls

    def can_serve_static_js(self, file_name):
        """Allow serving public JS files only when appropriate."""
        if file_name.lower() == 'auth.js':
            return bool(self.auth)
        return True

    def route(self, method, path, public=False, roles=None):
        """Register a handler. With auth enabled the route requires login unless public=True.

        roles=["admin"] additionally requires request.user["role"] to be one of them (else 403).
        """
        def decorator(func):
            func._hj_public = bool(public)
            func._hj_roles = list(roles) if roles else None
            if method not in self.routes:
                self.routes[method] = {}
            self.routes[method][path] = func
            return func
        return decorator

    def _security_headers(self, request):
        """Headers added to every response unless the handler already set them."""
        if not self.security_headers_enabled:
            return {}
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
        }
        if self.csp:
            headers["Content-Security-Policy"] = self.csp
        if self.certfile:
            headers["Strict-Transport-Security"] = "max-age=31536000"
        if getattr(request, 'user', None):
            # Authenticated responses must not end up in shared/disk caches.
            headers["Cache-Control"] = "no-store"
        return headers

    def _login_shell_html(self):
        from WebServer.auth import login_shell_html
        return login_shell_html(self.get_inject_js_urls())

    def _resolve_user(self, request):
        from WebServer.auth import resolve_user
        return resolve_user(request)

    def _register_asset_alias_routes(self):
        get_routes = self.routes.setdefault('GET', {})
        for url_path in ('/js/auth.js', '/js/webserver.js', '/js/TableViewer.js',
                          '/css/TableViewer.css', '/css/auth.css'):
            if url_path in get_routes:
                get_routes[f'/public{url_path}'] = get_routes[url_path]

    def start(self):
        """Boots the server."""
        self._register_asset_alias_routes()
        server = HTTPServer((self.host, self.port), WebHandler)
        server.routes = self.routes 
        server.auth = self.auth
        server.static_dir = self.static_dir
        server.default_js = self.default_js
        server.auth_js = self.auth_js
        server.framework_assets_prefix = self.framework_assets_prefix
        server.package_public_dir = self.package_public_dir
        server.can_serve_static_js = self.can_serve_static_js
        server.get_inject_js_urls = self.get_inject_js_urls
        server.resolve_user = self._resolve_user
        server.login_shell_html = self._login_shell_html
        server.security_headers = self._security_headers
        server.max_body_bytes = self.max_body_bytes

        scheme = "http"
        if self.certfile:
            import ssl
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.certfile, self.keyfile)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            scheme = "https"

        print(f"[ web_framework ] Secure Internal Server running on {scheme}://{self.host}:{self.port}")
        print("[ web_framework ] Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ web_framework ] Shutting down cleanly...")
            server.server_close()