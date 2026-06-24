from http.server import HTTPServer
import os
import sys

from WebServer.FileHandler import handle_file_request
from WebServer.WebHandler import WebHandler
from WebServer.database import createConnection, get_connection

class WebServer:
    """The clean interface your teammates will actually use."""
    
    def __init__(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port
        self.routes = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
        self.auth = None
        
        # Resolve base directory relative to the package so static files
        # are found whether the server is run as a script or imported.
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

        default_public_folder = os.path.join(self.base_dir, 'public')
        if os.path.exists(default_public_folder) and os.path.isdir(default_public_folder):
            print(f"[ web_framework ] Static file serving enabled from: {default_public_folder}")
            self.static_dir = default_public_folder

            self.default_js = None
            for js_file, js_url in [('webserver.js', '/webserver.js'), ('default.js', '/default.js')]:
                candidate_path = os.path.join(default_public_folder, js_file)
                if os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                    self.default_js = js_url
                    print(f"[ web_framework ] Default script injection enabled: {self.default_js}")
                    break

            auth_js_path = os.path.join(default_public_folder, 'auth.js')
            self.auth_js = auth_js_path if os.path.exists(auth_js_path) and os.path.isfile(auth_js_path) else None
        else:
            print("[ web_framework ] No 'public' folder found. Static file serving is disabled. To enable, create a 'public' directory in the same location as your script.")
            self.static_dir = None
            self.default_js = None
            self.auth_js = None

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

    def get_inject_js_urls(self):
        urls = []
        if self.default_js:
            urls.append(self.default_js)
        if self.auth and self.auth_js:
            urls.append('/auth.js')
        return urls

    def can_serve_static_js(self, file_name):
        """Allow serving public JS files only when appropriate."""
        if file_name.lower() == 'auth.js':
            return bool(self.auth)
        return True

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

    def route(self, method, path):
        def decorator(func):
            if method not in self.routes:
                self.routes[method] = {}
            self.routes[method][path] = func
            return func
        return decorator

    def start(self):
        """Boots the server."""
        server = HTTPServer((self.host, self.port), WebHandler)
        server.routes = self.routes 
        server.auth = self.auth
        server.static_dir = self.static_dir
        server.default_js = self.default_js
        server.auth_js = self.auth_js
        server.can_serve_static_js = self.can_serve_static_js
        server.get_inject_js_urls = self.get_inject_js_urls
        
        print(f"[ web_framework ] Secure Internal Server running on http://{self.host}:{self.port}")
        print("[ web_framework ] Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ web_framework ] Shutting down cleanly...")
            server.server_close()