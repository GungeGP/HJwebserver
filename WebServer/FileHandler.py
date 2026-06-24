

import mimetypes
import os

def inject_default_js(content, default_js_url):
    if not default_js_url:
        return content

    if isinstance(default_js_url, (list, tuple)):
        injections = [f'<script src="{url}"></script>'.encode('utf-8') for url in default_js_url if url]
        if not injections:
            return content
        injection = b''.join(injections)
    else:
        injection = f'<script src="{default_js_url}"></script>'.encode('utf-8')

    lower = content.lower()
    idx = lower.rfind(b'</body>')
    if idx != -1:
        return content[:idx] + injection + content[idx:]
    return content + injection


def handle_file_request(self, url_path, file_path):
    safe_file_path = file_path.lstrip('/').lstrip('\\')
    absolute_path = os.path.join(self.base_dir, safe_file_path)

    def automatic_handler(request):
        try:
            # Open the file using the bulletproof absolute path
            with open(absolute_path, 'rb') as f:
                content = f.read()
                
            content_type, _ = mimetypes.guess_type(absolute_path)
            if not content_type:
                content_type = "text/plain"

            if content_type == "text/html":
                inject_urls = getattr(request.server, 'get_inject_js_urls', lambda: [])()
                content = inject_default_js(content, inject_urls)

            request.send_response(200)
            request.send_header("Content-Type", content_type)
            request.end_headers()
            request.wfile.write(content)
            
        except FileNotFoundError:
            request.send_response(404)
            request.end_headers()
            # Print the absolute path in the error so the teammate knows EXACTLY where it looked
            request.wfile.write(f"Framework Error: Could not find file at {absolute_path}".encode('utf-8'))

    if 'GET' not in self.routes:
        self.routes['GET'] = {}
    self.routes['GET'][url_path] = automatic_handler

    # return the routes
    return self.routes