from http.server import HTTPServer
import os
import sys

from WebServer.FileHandler import handle_file_request
from WebServer.WebHandler import WebHandler
from WebServer.database import createConnection, get_connection

class WebServer:
    """The clean interface your teammates will actually use."""
    
    def __init__(self, host="127.0.0.1", port=8000, static_dir: str = None):
        self.host = host
        self.port = port
        self.routes = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
        self.auth = None

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

            self.default_js = None
            for js_file in ['webserver.js', 'default.js']:
                candidate_path = os.path.join(self.static_dir, js_file)
                if os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                    self.default_js = '/webserver.js'
                    print(f"[ web_framework ] Default script injection enabled: {self.default_js}")
                    break

            if self.default_js is None and os.path.exists(self.package_default_js) and os.path.isfile(self.package_default_js):
                self.default_js = '/webserver.js'
                print(f"[ web_framework ] Default script injection enabled from package assets: {self.default_js}")

            auth_js_path = os.path.join(self.static_dir, 'auth.js')
            if os.path.exists(auth_js_path) and os.path.isfile(auth_js_path):
                self.auth_js = '/auth.js'
            elif os.path.exists(self.package_auth_js) and os.path.isfile(self.package_auth_js):
                self.auth_js = '/auth.js'
            else:
                self.auth_js = None
        else:
            print("[ web_framework ] No 'public' folder found. Static file serving is disabled. To enable, create a 'public' directory next to your script or pass `static_dir` to WebServer.")
            self.default_js = None
            self.auth_js = None

        # Register framework-provided JS routes inside the server.
        @self.route('GET', '/auth.js')
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
            request.end_headers()
            request.wfile.write(content)

        @self.route('GET', '/webserver.js')
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
            if not path:
                request.send_response(404)
                request.end_headers()
                return

            with open(path, 'rb') as f:
                content = f.read()
            request.send_response(200)
            request.send_header('Content-Type', 'application/javascript')
            request.end_headers()
            request.wfile.write(content)

    def addPath(self, url_path, file_path):
        """Maps a URL to ANY file, safely resolving the path."""
        self.routes = handle_file_request(self, url_path, file_path)

    def settings(self, auth=None):
        """Configure server settings.
        Defaults: 
        auth=None 
        """
        self.auth = auth
        if self.auth:
            from WebServer.auth import attach_auth_routes
            attach_auth_routes(self)

    def setDatabase(self, server, dbName):
        createConnection(server, dbName)

    def getDatabaseConnection():
        return get_connection()

    def checkAuth(self, request):
        """Checks if the request is authenticated. Returns user data if valid, else None.\n Remeber to use .settings before to enable auth"""
        if self.auth:
            from WebServer.auth import check_auth
            return check_auth(request)
        return "Authentication is not enabled. Please use .settings(auth=True) to enable it."
    
    def createAuth(self, username):
        """Creates a JWT token for the given username."""
        from WebServer.auth import create_token_for_user
        if self.auth:
            return create_token_for_user(username)
        return "Authentication is not enabled. Please use .settings(auth=True) to enable it."

    def get_inject_js_urls(self):
        urls = []
        if self.default_js:
            # Use canonical framework routes so injection works even when
            # the host project's public folder does not contain framework JS.
            urls.append('/webserver.js')
        if self.auth and self.auth_js:
            urls.append('/auth.js')
        return urls

    def can_serve_static_js(self, file_name):
        """Allow serving public JS files only when appropriate."""
        if file_name.lower() == 'auth.js':
            return bool(self.auth)
        return True

    def route(self, method, path):
        def decorator(func):
            if method not in self.routes:
                self.routes[method] = {}
            self.routes[method][path] = func
            return func
        return decorator

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
        
        print(f"[ web_framework ] Secure Internal Server running on http://{self.host}:{self.port}")
        print("[ web_framework ] Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ web_framework ] Shutting down cleanly...")
            server.server_close()