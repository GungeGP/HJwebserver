import json
from http.server import BaseHTTPRequestHandler
import mimetypes
import os
from urllib.parse import urlparse

# Largest request body a route will accept (override with WebServer(...).max_body_bytes).
MAX_BODY_BYTES = 10 * 1024 * 1024


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

    def __init__(self, *args, **kwargs):
        self._sent_headers = set()
        self.user = None
        super().__init__(*args, **kwargs)

    # --- security headers on every response -------------------------------

    def send_response(self, code, message=None):
        self._sent_headers = set()
        super().send_response(code, message)

    def send_header(self, keyword, value):
        self._sent_headers.add(keyword.lower())
        super().send_header(keyword, value)

    def end_headers(self):
        get_headers = getattr(self.server, 'security_headers', None)
        if get_headers:
            for name, value in get_headers(self).items():
                if name.lower() not in self._sent_headers:
                    self.send_header(name, value)
        super().end_headers()

    # --- static files -----------------------------------------------------

    def _resolve_static(self, url_path):
        """Map a URL path to a file inside static_dir, or None if it escapes it.

        Rejects '..' segments, backslashes, and dotfiles (.env, .git, ...), and
        re-checks the resolved real path so symlinks can't lead outside either.
        """
        static_root = os.path.realpath(self.server.static_dir)
        segments = [s for s in url_path.replace('\\', '/').split('/') if s]
        if any(seg in ('.', '..') or seg.startswith('.') for seg in segments):
            return None
        candidate = os.path.realpath(os.path.join(static_root, *segments)) if segments else static_root
        if os.path.commonpath([static_root, candidate]) != static_root:
            return None
        return candidate

    # --- authentication ---------------------------------------------------

    def _authorize(self, method, handler_function=None):
        """Enforce authentication for this request.

        Returns True when the request may proceed (and sets ``self.user``).
        Otherwise writes a 401 response and returns False. When auth is
        disabled, or the route is marked ``public=True``, everything passes.
        """
        self.user = None
        if not getattr(self.server, 'auth', None):
            return True
        if handler_function is not None and getattr(handler_function, '_hj_public', False):
            return True

        resolve_user = getattr(self.server, 'resolve_user', None)
        user = resolve_user(self) if resolve_user else None
        wants_html = method == 'GET' and 'text/html' in self.headers.get('Accept', '')

        if not user:
            # Browser navigation to a protected page gets the login shell; API
            # calls get a JSON 401 that auth.js turns into the login overlay.
            return self._deny(401, {"error": "Authentication required."}, login_shell=wants_html)

        # A pending password change blocks everything except the routes that
        # let the user complete it (verify / change-password / logout-all).
        if user.get("mustChangePassword") and not getattr(handler_function, '_hj_allow_pending_password', False):
            return self._deny(403, {"error": "password_change_required"}, login_shell=wants_html)

        roles = getattr(handler_function, '_hj_roles', None)
        if roles and user.get("role") not in roles:
            return self._deny(403, {"error": "Forbidden: this requires role " + " or ".join(roles) + "."},
                              login_shell=False, html=wants_html)

        self.user = user
        return True

    def _deny(self, status, payload, login_shell=False, html=False):
        self.send_response(status)
        if login_shell and hasattr(self.server, 'login_shell_html'):
            self.send_header('Content-Type', 'text/html')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(self.server.login_shell_html())
        elif html:
            self.send_header('Content-Type', 'text/html')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(f"<!DOCTYPE html><title>{status}</title><h1>{status}</h1><p>{payload.get('error', '')}</p>".encode('utf-8'))
        else:
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        return False

    def handle_request(self, method):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        routes = getattr(self.server, 'routes', {})
        
        # 1. Check if the teammate wrote a specific route
        if method in routes and path in routes[method]:
            handler_function = routes[method][path]

            if not self._authorize(method, handler_function):
                return
            
            # --- NEW: AUTOMATIC DATA PARSER ---
            # Create a clean .body property for the teammate to use
            self.body = None 
            
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                except ValueError:
                    content_length = -1
                if content_length < 0:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"400 - Bad Request: Invalid Content-Length")
                    return
                max_body = getattr(self.server, 'max_body_bytes', MAX_BODY_BYTES)
                if content_length > max_body:
                    self.send_response(413)
                    self.end_headers()
                    self.wfile.write(b"413 - Request body too large")
                    return
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
            if not self._authorize(method):
                return

            file_path = self._resolve_static(path)

            if file_path and os.path.isfile(file_path):
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