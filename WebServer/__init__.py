from http.server import HTTPServer
import os
import sys

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

        # Where the installed package's bundled static files live
        self.package_public_dir = os.path.join(os.path.dirname(__file__), 'public')
        self.package_default_js = os.path.join(self.package_public_dir, 'webserver.js')
        self.package_auth_js = os.path.join(self.package_public_dir, 'auth.js')
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
        self.default_js = '/webserver.js'
        self.auth_js = '/auth.js'
        print(f"[ web_framework ] Default script injection enabled: {self.default_js}")

        # Register framework-provided JS routes inside the server.
        @self.route('GET', '/auth.js', public=True)
        def serve_auth_js(request):
            if not self.auth:
                request.send_response(404)
                request.end_headers()
                return

            local_path = os.path.join(self.static_dir, 'auth.js') if self.static_dir else None
            package_path = self.package_auth_js
            if local_path and os.path.exists(local_path) and os.path.isfile(local_path):
                path = local_path
            elif os.path.exists(package_path) and os.path.isfile(package_path):
                path = package_path
            else:
                request.send_response(404)
                request.end_headers()
                return

            with open(path, 'rb') as f:
                content = f.read()

            request.send_response(200)
            request.send_header('Content-Type', 'application/javascript')
            request.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.send_header('Pragma', 'no-cache')
            request.send_header('Expires', '0')
            request.end_headers()
            request.wfile.write(content)

        @self.route('GET', '/webserver.js', public=True)
        def serve_webserver_js(request):
            local_js = None
            if self.static_dir:
                local_js = os.path.join(self.static_dir, 'webserver.js')
                if not os.path.exists(local_js) or not os.path.isfile(local_js):
                    local_js = os.path.join(self.static_dir, 'default.js')
                    if not os.path.exists(local_js) or not os.path.isfile(local_js):
                        local_js = None

            package_js = None
            if os.path.exists(self.package_default_js) and os.path.isfile(self.package_default_js):
                package_js = self.package_default_js
            package_default_js = os.path.join(self.package_public_dir, 'default.js')
            if package_js is None and os.path.exists(package_default_js) and os.path.isfile(package_default_js):
                package_js = package_default_js

            path = local_js or package_js
            if path:
                with open(path, 'rb') as f:
                    content = f.read()
            else:
                request.send_response(404)
                request.end_headers()
                return

            request.send_response(200)
            request.send_header('Content-Type', 'application/javascript')
            request.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.send_header('Pragma', 'no-cache')
            request.send_header('Expires', '0')
            request.end_headers()
            request.wfile.write(content)

    def addPath(self, url_path, file_path, public=False):
        """Maps a URL to ANY file, safely resolving the path.

        When auth is enabled the page requires login unless public=True.
        """
        self.routes = handle_file_request(self, url_path, file_path, public=public)

    def settings(self, auth=None, jwtSecret=None, tokenLifetimeHours=24, secureCookie=False,
                 bearerTokens=True, maxLoginAttempts=5, lockoutMinutes=15, minPasswordLength=5,
                 auditLog=True, trustProxy=False, csp=DEFAULT_CSP, securityHeaders=True):
        """Configure server settings.

        auth:               enable authentication. Every route and page then requires
                            login unless registered with public=True.
        jwtSecret:          signing secret (>= 32 bytes). Defaults to JWT_SECRET from .env.
        tokenLifetimeHours: how long a login stays valid.
        secureCookie:       add the Secure flag to the session cookie (needs HTTPS;
                            set automatically by useHttps()).
        bearerTokens:       also accept "Authorization: Bearer <token>" (for scripts).
                            False = cookie only.
        maxLoginAttempts:   failed logins (per username and per IP) before lockout.
        lockoutMinutes:     how long a lockout lasts.
        minPasswordLength:  enforced by createUser / setPassword.
        auditLog:           write logins, logouts, lockouts and user changes to the AuditLog table.
        trustProxy:         read the client IP from X-Forwarded-For (only behind a reverse proxy).
        csp:                Content-Security-Policy header value, or None to send none.
        securityHeaders:    send X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP.
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

    def createUser(self, username, password):
        """Create a user with a hashed password. Returns False if the username already exists.

        Raises ValueError if the password is shorter than minPasswordLength.
        """
        from WebServer.auth import audit, check_password_policy, hash_password
        from WebServer.database import create_user, get_user_by_username
        username = str(username).strip()
        if not username:
            raise ValueError("Username is required.")
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is not None:
            return False
        create_user(username, hash_password(str(password)))
        audit("user_created", username)
        return True

    def setPassword(self, username, password):
        """Replace a user's password and log them out everywhere. Returns False if the user does not exist."""
        from WebServer.auth import audit, check_password_policy, hash_password, revoke_sessions
        from WebServer.database import get_user_by_username, update_user_password
        username = str(username).strip()
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is None:
            return False
        update_user_password(username, hash_password(str(password)))
        revoke_sessions(username)
        audit("password_changed", username)
        return True

    def deleteUser(self, username):
        """Remove a user and all their sessions. Returns False if the user does not exist."""
        from WebServer.auth import audit, revoke_sessions
        from WebServer.database import delete_user, get_user_by_username
        username = str(username).strip()
        if get_user_by_username(username) is None:
            return False
        revoke_sessions(username)
        delete_user(username)
        audit("user_deleted", username)
        return True

    def revokeSessions(self, username):
        """Log a user out of every browser/device immediately."""
        from WebServer.auth import audit, revoke_sessions
        revoke_sessions(str(username).strip())
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
        """Active sessions for a user (Jti, Username, CreatedAt, ExpiresAt as epoch seconds)."""
        from WebServer.database import get_sessions_for_user
        return get_sessions_for_user(str(username).strip())

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
        """Creates a JWT token for the given username."""
        from WebServer.auth import create_token_for_user
        if self.auth:
            return create_token_for_user(username)
        return "Authentication is not enabled. Please use .settings(auth=True) to enable it."

    def get_inject_js_urls(self):
        urls = []
        if self.default_js:
            version = self._asset_version('webserver.js') or self._asset_version('default.js')
            urls.append(f"/webserver.js?v={version}" if version else '/webserver.js')
        if self.auth and self.auth_js:
            version = self._asset_version('auth.js')
            urls.append(f"/auth.js?v={version}" if version else '/auth.js')
        return urls

    def can_serve_static_js(self, file_name):
        """Allow serving public JS files only when appropriate."""
        if file_name.lower() == 'auth.js':
            return bool(self.auth)
        return True

    def route(self, method, path, public=False):
        """Register a handler. With auth enabled the route requires login unless public=True."""
        def decorator(func):
            func._hj_public = bool(public)
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
        if '/auth.js' in get_routes:
            get_routes['/public/auth.js'] = get_routes['/auth.js']
        if '/webserver.js' in get_routes:
            get_routes['/public/webserver.js'] = get_routes['/webserver.js']

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