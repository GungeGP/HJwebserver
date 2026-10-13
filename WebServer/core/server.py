"""Server bootstrapping: construction, routing, TLS, database wiring, startup.

This is the part of WebServer that exists regardless of which features
(auth, TableViewer, ...) a consumer actually turns on.
"""

from http.server import HTTPServer
import os
import sys

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


class ServerMixin:
    """Construction, routing, TLS, database wiring, and serve_forever()."""

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
        self.package_public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'public')
        self.framework_assets_prefix = '/framework-assets/'

        # Allow callers to override where static files live. If not provided,
        # try several sensible locations so the framework works when used
        # either as a script or when imported as a package.
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

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
            candidates.append(self.package_public_dir)

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

        # TableViewer.js only auto-injects once a table is actually exposed
        # (see addTableViewer() and core/assets.py's _CONDITIONAL_ASSETS).
        self.table_viewer_enabled = False
        print("[ web_framework ] Framework script injection enabled (public/js/*.js, auto-discovered)")

        # Register framework-provided js/css asset routes (see core/assets.py).
        self._register_asset_route('/js/auth.js', 'js/auth.js', 'application/javascript',
                                    gate=lambda: bool(self.auth))
        self._register_asset_route('/js/webserver.js', 'js/webserver.js', 'application/javascript',
                                    extra_relative_fallback='js/default.js')
        self._register_asset_route('/js/TableViewer.js', 'js/TableViewer.js', 'application/javascript')
        self._register_asset_route('/css/TableViewer.css', 'css/TableViewer.css', 'text/css')
        self._register_asset_route('/css/auth.css', 'css/auth.css', 'text/css')

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

    def start(self):
        """Boots the server."""
        self._register_asset_alias_routes()
        server = HTTPServer((self.host, self.port), WebHandler)
        server.routes = self.routes
        server.auth = self.auth
        server.static_dir = self.static_dir
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
