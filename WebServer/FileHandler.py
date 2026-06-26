import mimetypes
import os


def inject_js_scripts(content, urls):
    if not urls:
        return content

    injections = [f'<script src="{url}"></script>'.encode('utf-8') for url in urls if url]
    if not injections:
        return content

    injection = b''.join(injections)
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

            if content_type == 'text/html':
                inject_urls = getattr(self, 'get_inject_js_urls', lambda: [])()
                content = inject_js_scripts(content, inject_urls)

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