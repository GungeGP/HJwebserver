from http.server import HTTPServer
import os
import sys

from WebServer.FileHandler import handle_file_request
from WebServer.WebHandler import WebHandler

class WebServer:
    """The clean interface your teammates will actually use."""
    
    def __init__(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port
        self.routes = {'GET': {}, 'POST': {}, 'PUT': {}, 'DELETE': {}}
        self.auth = None
        
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        default_public_folder = os.path.join(self.base_dir, 'public')
        if os.path.exists(default_public_folder) and os.path.isdir(default_public_folder):
            print(f"[ web_framework ] Static file serving enabled from: {default_public_folder}")
            self.static_dir = default_public_folder
        else:
            print("[ web_framework ] No 'public' folder found. Static file serving is disabled. To enable, create a 'public' directory in the same location as your script.")
            self.static_dir = None

    def file(self, url_path, file_path):
        """Maps a URL to ANY file, safely resolving the path."""
        self.routes = handle_file_request(self, url_path, file_path)

    def use_auth(self, auth_module):
        """Attach your reusable auth module to the server."""
        self.auth = auth_module

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
        
        print(f"[ web_framework ] Secure Internal Server running on http://{self.host}:{self.port}")
        print("[ web_framework ] Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ web_framework ] Shutting down cleanly...")
            server.server_close()