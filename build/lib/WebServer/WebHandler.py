import json
from http.server import BaseHTTPRequestHandler
import mimetypes
import os
from urllib.parse import urlparse

from WebServer.FileHandler import inject_default_js

FRAMEWORK_ASSETS_PREFIX = '/framework-assets/'

class WebHandler(BaseHTTPRequestHandler):
    """The engine that handles incoming requests."""

    framework_public_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'public'
    )

    def serve_file(self, file_path):
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'

        with open(file_path, 'rb') as f:
            content = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(content)
    
    def handle_request(self, method):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        routes = getattr(self.server, 'routes', {})
        
        # 1. Check if the teammate wrote a specific route
        if method in routes and path in routes[method]:
            handler_function = routes[method][path]
            
            # --- NEW: AUTOMATIC DATA PARSER ---
            # Create a clean .body property for the teammate to use
            self.body = None 
            
            if method in ['POST', 'PUT', 'PATCH']:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    raw_data = self.rfile.read(content_length)
                    content_type = self.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            # Automatically convert JSON to a Python dictionary
                            self.body = json.loads(raw_data.decode('utf-8'))
                        except json.JSONDecodeError:
                            # Protect the server if the user sends broken JSON
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write(b"400 - Bad Request: Invalid JSON")
                            return # Stop execution so their function doesn't crash!
                    else:
                        # If it's plain text or form data, just give them the string
                        self.body = raw_data.decode('utf-8')
            # ----------------------------------

            try:
                # Execute the teammate's function
                handler_function(self)
            except Exception as e:
                print(f"Internal Server Error in {path}: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"500 - Internal Server Error")
                
        # 2. The Static Directory Fallback
        elif method == 'GET':
            if path.startswith(FRAMEWORK_ASSETS_PREFIX):
                relative_path = path[len(FRAMEWORK_ASSETS_PREFIX):].lstrip('/')
                safe_path = os.path.normpath(relative_path).replace('\\', '/')
                if safe_path.startswith('..'):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'404 - Not Found')
                    return

                framework_file = os.path.join(self.framework_public_dir, safe_path)
                if os.path.exists(framework_file) and os.path.isfile(framework_file):
                    self.serve_file(framework_file)
                    return

                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'404 - Not Found')
                return

            if getattr(self.server, 'static_dir', None):
                project_file = os.path.join(self.server.static_dir, path.lstrip('/'))
                if os.path.exists(project_file) and os.path.isfile(project_file):
                    self.serve_file(project_file)
                    return

            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 - Not Found')
            return
                
        # 3. Automatic 404
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 - Not Found")

    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_PUT(self): self.handle_request('PUT')
    def do_DELETE(self): self.handle_request('DELETE')