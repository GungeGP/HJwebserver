"""The framework's own bundled js/css assets (auth.js, webserver.js,
TableViewer.js/css) - serving them, overriding them, and the auto-discovery
that injects the js ones into every served page.

Not to be confused with addPath() (core/filehandler.py), which serves a
consumer's own arbitrary files - nothing here is about that.
"""

import os

# Framework js files (in public/js/) that should only load on pages that
# actually use the feature they belong to. Any js file *not* listed here is
# injected on every page unconditionally (e.g. webserver.js) - see
# AssetsMixin.get_inject_js_urls(), which discovers files automatically so a
# new framework asset needs no new attribute or branch, only an entry here
# if it needs to stay conditional.
_CONDITIONAL_ASSETS = {
    'auth.js': lambda server: bool(server.auth),
    'TableViewer.js': lambda server: server.table_viewer_enabled,
}


class AssetsMixin:
    """Framework asset routes and script auto-injection."""

    def _register_asset_route(self, url_path, relative_path, content_type, gate=None, extra_relative_fallback=None):
        """Serve a framework-bundled js/css file, overridable by dropping the
        same relative path under the consumer's own static_dir (e.g. a local
        static_dir/js/auth.js wins over the package's copy).

        gate: optional no-arg callable; a falsy result serves 404 (used so
              auth.js/auth.css 404 when auth isn't enabled).
        extra_relative_fallback: a second relative path tried after the
              primary one, both locally and in the package (webserver.js
              falls back to a consumer's own js/default.js).
        """
        def _find(base):
            if not base:
                return None
            for rel in (relative_path, extra_relative_fallback):
                if not rel:
                    continue
                candidate = os.path.join(base, *rel.split('/'))
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    return candidate
            return None

        @self.route('GET', url_path, public=True)
        def serve(request):
            if gate is not None and not gate():
                request.send_response(404)
                request.end_headers()
                return

            path = _find(self.static_dir) or _find(self.package_public_dir)
            if not path:
                request.send_response(404)
                request.end_headers()
                return

            with open(path, 'rb') as f:
                content = f.read()

            request.send_response(200)
            request.send_header('Content-Type', content_type)
            request.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            request.send_header('Pragma', 'no-cache')
            request.send_header('Expires', '0')
            request.end_headers()
            request.wfile.write(content)

        return serve

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

    def get_inject_js_urls(self):
        """Every framework js file to auto-inject into served pages.

        Scans the package's public/js/ folder, so adding a new framework
        asset there is all it takes - no attribute or branch to add here.
        A file listed in _CONDITIONAL_ASSETS only injects when its gate
        passes (e.g. auth.js only once auth is enabled); everything else
        injects unconditionally (e.g. webserver.js).
        """
        js_dir = os.path.join(self.package_public_dir, 'js')
        if not os.path.isdir(js_dir):
            return []

        urls = []
        for filename in sorted(os.listdir(js_dir), key=str.lower):
            if not filename.endswith('.js'):
                continue
            gate = _CONDITIONAL_ASSETS.get(filename)
            if gate and not gate(self):
                continue
            version = self._asset_version(f'js/{filename}')
            url = f'/js/{filename}'
            urls.append(f"{url}?v={version}" if version else url)
        return urls

    def can_serve_static_js(self, file_name):
        """Allow serving public JS files only when appropriate."""
        if file_name.lower() == 'auth.js':
            return bool(self.auth)
        return True

    def _register_asset_alias_routes(self):
        get_routes = self.routes.setdefault('GET', {})
        for url_path in ('/js/auth.js', '/js/webserver.js', '/js/TableViewer.js', '/js/Dialog.js',
                          '/css/TableViewer.css', '/css/auth.css', '/css/Dialog.css'):
            if url_path in get_routes:
                get_routes[f'/public{url_path}'] = get_routes[url_path]
