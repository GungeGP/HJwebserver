"""The side menu: app.menu(...).

The engine (the items, the checks at start, the menu for one user on one
page) is WebServer.menu, and the frontend is public/js/menu.js and
public/css/menu.css. The server puts the menu into each page in the same
step as the framework scripts (WebServer.page).
"""

from urllib.parse import urlparse

from WebServer.page import inject_js_scripts, inject_menu

_EMPTY_PAGE = b'<!DOCTYPE html>\n<html lang="da">\n<head><meta charset="utf-8"><title>Admin</title></head>\n<body>\n</body>\n</html>\n'


class MenuMixin:
    """app.menu(...) - the only method this feature adds."""

    menu_config = None   # a WebServer.menu.Menu once app.menu() is called

    def menu(self, items, title=None, showUser=True, admin=True, sidebar=True):
        """A menu on the left of every page, the content to the right of it.

            app.menu(title="Ophold", items=[
                MenuItem("§ 109", "/p109", short="§109", desc="...", count="/api/p109/antal"),
                MenuItem("Stamdata", "/stamdata", items=[MenuItem("Tilbud", "/stamdata/tilbud")]),
            ])

        items:    MenuItem(...)s. Each points to a page made with addPath; an
                  item whose page the user may not open is hidden (or greyed
                  out with denied="disable"). An address with no page stops the start.
        title:    heading at the top. None: no heading.
        showUser: "Logget ind som <role>" at the bottom (only with auth=True).
        admin:    an Admin button for the role admin (and higher), leading to
                  /admin - an empty page with the menu unless the app has its
                  own. False removes both. With auth=True and a roleHierarchy
                  without "admin", the app refuses to start unless admin=False.
        sidebar:  False draws no menu; the page reads the items the user may
                  see from hjMenu.items instead.

        A page registered with addPath(..., menu=False) gets no menu.
        """
        from WebServer.menu import Menu
        self.menu_config = Menu(items, title=title, showUser=showUser, admin=admin, sidebar=sidebar)
        # Only now, so an app without a menu has no new routes (nor new public paths for Authentik).
        self._register_asset_route('/js/menu.js', 'js/menu.js', 'application/javascript')
        self._register_asset_route('/css/menu.css', 'css/menu.css', 'text/css')

    def _menu_on_start(self):
        """Checks and the empty /admin page, once every page is registered. Called from start()."""
        menu = self.menu_config
        if menu is None:
            return
        get_routes = self.routes.setdefault('GET', {})
        if self.auth and menu.admin and '/admin' not in get_routes:
            @self.route('GET', '/admin', roles=["admin"])
            def empty_admin_page(request):
                content = self.add_menu(_EMPTY_PAGE, request)
                content = inject_js_scripts(content, self.get_inject_js_urls())
                request.send_response(200)
                request.send_header('Content-Type', 'text/html')
                request.end_headers()
                request.wfile.write(content)
            empty_admin_page._hj_framework = True
        menu.check(self.routes, self.auth)   # after /admin, which an item may point to

    def add_menu(self, content, request):
        """The page (bytes) with the menu right after <body>, for this request's
        user and path. Unchanged when app.menu() isn't called."""
        menu = self.menu_config
        if menu is None:
            return content
        user = getattr(request, 'user', None)
        if user is None and self.auth:
            # A public page: who is logged in, if anyone (the proxy's secret is already checked).
            user = self._resolve_user(request)
        version = self._asset_version('css/menu.css')
        css_url = f"/css/menu.css?v={version}" if version else "/css/menu.css"
        markup = menu.render(user, urlparse(request.path).path, self.routes, self.auth, css_url)
        return inject_menu(content, markup.encode('utf-8'))
