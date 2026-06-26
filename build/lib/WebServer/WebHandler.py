import json
from http.server import BaseHTTPRequestHandler
import mimetypes
import os
from urllib.parse import urlparse


def inject_js_scripts(content, urls):
    if not urls:
        return content

    injections = [f'<script src="{url}"></script>'.encode('utf-8') for url in urls]
    injection = b''.join(injections)
    lower = content.lower()
    idx = lower.rfind(b'</body>')
    if idx != -1:
        return content[:idx] + injection + content[idx:]
    return content + injection

class WebHandler(BaseHTTPRequestHandler):
    """The engine that handles incoming requests."""

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
                
        # 2. The Static Directory Fallback (and package assets)
        elif method == 'GET' and getattr(self.server, 'static_dir', None):
            safe_path = path.lstrip('/')
            file_path = os.path.join(self.server.static_dir, safe_path)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                file_name = os.path.basename(file_path)
                can_serve = getattr(self.server, 'can_serve_static_js', lambda _: True)(file_name)
                if not can_serve:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"404 - Not Found")
                    return

                with open(file_path, 'rb') as f:
                    content = f.read()
                
                content_type, _ = mimetypes.guess_type(file_path)
                if not content_type:
                    content_type = "application/octet-stream"

                if content_type == 'text/html' and hasattr(self.server, 'get_inject_js_urls'):
                    content = inject_js_scripts(content, self.server.get_inject_js_urls())
                    file_path = None
                    content_type = 'text/html'
                    
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"404 - Not Found")
                
        # 3. Automatic 404
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 - Not Found")

    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_PUT(self): self.handle_request('PUT')
    def do_DELETE(self): self.handle_request('DELETE')