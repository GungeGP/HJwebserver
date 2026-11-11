"""The side menu's engine: the items, the checks at start, and the menu for
one user on one page.

app.menu(...) (core/menu.py) stores a Menu here; the server then puts
Menu.render() right after <body> in every page it serves (see page.py), and
public/js/menu.js does the rest in the browser: collapsing, the arrows at
sub-items, and fetching the counts.

An item is shown when the user may open the page it points to: the roles
come from the route table, the same place WebHandler checks them, so the
menu and the access rules can't drift apart. No database.
"""

import html
import json

ADMIN_PATH = '/admin'
ADMIN_ROLE = 'admin'
DENIED = ('hide', 'disable')
COLLAPSED_KEY = 'hj:menu-collapsed'   # localStorage, shared with menu.js


class MenuItem:
    """One entry in the menu.

    title:  the text shown.
    url:    the page it opens. Must be a page registered with addPath (or a GET route).
    short:  the name shown when the menu is collapsed. Default: the first characters of title.
    desc:   a second line under the title.
    count:  an address answering with a JSON number, shown in a small box next to the item.
    items:  sub-items (MenuItem). Shown open on this page and on theirs; an arrow folds them.
    denied: "hide" (default) hides the item from users who may not open its page;
            "disable" shows it greyed out instead.
    """

    def __init__(self, title, url, short=None, desc=None, count=None, items=None, denied="hide"):
        if not isinstance(title, str) or not title.strip():
            raise ValueError("MenuItem: title must be a non-empty string.")
        if not isinstance(url, str) or not url.startswith('/'):
            raise ValueError(f"MenuItem '{title}': url must be a path starting with '/', got {url!r}.")
        if count is not None and (not isinstance(count, str) or not count.startswith('/')):
            raise ValueError(f"MenuItem '{title}': count must be a path starting with '/', got {count!r}.")
        if denied not in DENIED:
            raise ValueError(f"MenuItem '{title}': denied must be \"hide\" or \"disable\", got {denied!r}.")
        self.title = title
        self.url = url
        self.short = short
        self.desc = desc
        self.count = count
        self.items = _check_items(items or [], f"MenuItem '{title}' items")
        self.denied = denied


def _check_items(items, where):
    if not isinstance(items, (list, tuple)) or not all(isinstance(i, MenuItem) for i in items):
        raise ValueError(f"{where} must be a list of MenuItem(...).")
    return list(items)


def _walk(items):
    for item in items:
        yield item
        yield from _walk(item.items)


class Menu:
    """What app.menu(...) was called with. Read-only once the server runs."""

    def __init__(self, items, title=None, showUser=True, admin=True, sidebar=True):
        self.items = _check_items(items, "app.menu: items")
        self.title = title
        self.show_user = bool(showUser)
        self.admin = bool(admin)
        self.sidebar = bool(sidebar)

    # --- at start -------------------------------------------------------

    def check(self, routes, auth):
        """Raise (so the app refuses to start) on an item pointing nowhere,
        or an Admin button for a role roleHierarchy doesn't have."""
        pages = routes.get('GET', {})
        for item in _walk(self.items):
            if item.url not in pages:
                raise RuntimeError(f"app.menu: no page is registered at {item.url} (menu item '{item.title}'). "
                                   f"Register it with app.addPath('{item.url}', ...) or fix the address.")
        if auth and self.admin:
            from WebServer.auth import check_role
            try:
                check_role(ADMIN_ROLE)
            except ValueError:
                raise RuntimeError(f"app.menu: the Admin button is for the role '{ADMIN_ROLE}', which is not in "
                                   f"roleHierarchy. Add '{ADMIN_ROLE}' to roleHierarchy in app.settings(), "
                                   f"or pass app.menu(..., admin=False).") from None

    # --- one user, one page ---------------------------------------------

    def items_for(self, user, path, routes, auth):
        """The items this user may see on this page, as plain dicts - the
        same list menu.js exposes as hjMenu.items."""
        return [entry for entry in (self._entry(item, user, path, routes, auth) for item in self.items) if entry]

    def _entry(self, item, user, path, routes, auth):
        allowed = _may_open(item.url, user, routes, auth)
        if not allowed and item.denied == 'hide':
            return None
        children = [entry for entry in (self._entry(i, user, path, routes, auth) for i in item.items) if entry]
        return {
            "title": item.title,
            "url": item.url,
            "desc": item.desc,
            "short": item.short,
            # No count for an item the user may not open: its address is
            # likely as closed as the page, and every refusal is audited.
            "count": item.count if allowed else None,
            "active": item.url == path,
            "disabled": not allowed,
            "items": children,
        }

    def show_admin(self, user, auth):
        if not (auth and self.admin and user):
            return False
        from WebServer.auth import has_role
        return has_role(user.get("role"), [ADMIN_ROLE])

    def render(self, user, path, routes, auth, css_url):
        """The markup put right after <body>: the items as JSON (always), and
        with sidebar=True the menu itself. Every text is escaped."""
        items = self.items_for(user, path, routes, auth)
        data = (json.dumps(items, ensure_ascii=False)
                .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))
        parts = [f'<script type="application/json" id="hj-menu-data">{data}</script>']
        if not self.sidebar:
            return ''.join(parts)

        parts.append(f'<link rel="stylesheet" href="{_e(css_url)}" id="hj-menu-styles">')
        parts.append('<nav class="hj-menu" id="hj-menu" aria-label="Menu">')
        parts.append('<div class="hj-menu-head">')
        if self.title:
            parts.append(f'<div class="hj-menu-title">{_e(self.title)}</div>')
        parts.append('<button type="button" class="hj-menu-toggle" title="Klap menuen sammen" '
                     'aria-label="Klap menuen sammen" aria-expanded="true">&laquo;</button>')
        parts.append('</div>')
        parts.append(_list(items, 'hj-menu-items'))

        show_admin = self.show_admin(user, auth)
        show_user = bool(auth and self.show_user and user)
        if show_admin or show_user:
            parts.append('<div class="hj-menu-foot">')
            if show_admin:
                active = ' active' if path == ADMIN_PATH else ''
                parts.append('<div class="hj-menu-admin-label">Kun for administratorer</div>'
                             f'<a class="hj-menu-admin{active}" href="{ADMIN_PATH}">Admin</a>')
            if show_user:
                parts.append(f'<div class="hj-menu-user">Logget ind som <strong>{_e(user.get("role"))}</strong></div>')
            parts.append('</div>')
        parts.append('</nav>')
        # Collapsed before the first paint, so the menu doesn't flash open on
        # every page. menu.js applies the same choice again if this is blocked.
        parts.append('<script>try{if(localStorage.getItem(%s)==="1"){document.getElementById("hj-menu")'
                     '.classList.add("collapsed")}}catch(e){}</script>' % json.dumps(COLLAPSED_KEY))
        return ''.join(parts)


def _may_open(url, user, routes, auth):
    """True when this user may open the page at url - the rule WebHandler applies."""
    if not auth:
        return True
    handler = routes.get('GET', {}).get(url)
    if handler is not None and getattr(handler, '_hj_public', False):
        return True
    if not user:
        return False
    from WebServer.auth import has_role
    return has_role(user.get("role"), getattr(handler, '_hj_roles', None))


def _e(text):
    return html.escape(str(text), quote=True)


def _list(items, css_class):
    return f'<ul class="{css_class}">' + ''.join(_item(i) for i in items) + '</ul>'


def _item(item):
    is_open = item["active"] or _has_active(item["items"])
    classes = ['hj-menu-item']
    if item["active"]:
        classes.append('active')
    if item["disabled"]:
        classes.append('disabled')
    if item["items"]:
        classes.append('has-items')
        if is_open:
            classes.append('open')

    short = item["short"] or item["title"][:4]
    inner = (f'<span class="hj-menu-text"><span class="hj-menu-label">{_e(item["title"])}</span>'
             + (f'<span class="hj-menu-desc">{_e(item["desc"])}</span>' if item["desc"] else '')
             + f'</span><span class="hj-menu-short">{_e(short)}</span>'
             + (f'<span class="hj-menu-count" data-hj-count="{_e(item["count"])}" hidden></span>'
                if item["count"] else ''))
    if item["disabled"]:
        link = f'<span class="hj-menu-link" aria-disabled="true" title="{_e(item["title"])}">{inner}</span>'
    else:
        current = ' aria-current="page"' if item["active"] else ''
        link = f'<a class="hj-menu-link" href="{_e(item["url"])}"{current} title="{_e(item["title"])}">{inner}</a>'

    if item["items"]:
        expanded = 'true' if is_open else 'false'
        arrow = (f'<button type="button" class="hj-menu-arrow" aria-expanded="{expanded}" '
                 f'aria-label="Vis eller skjul underpunkter"></button>')
        return (f'<li class="{" ".join(classes)}"><div class="hj-menu-row">{link}{arrow}</div>'
                + _list(item["items"], 'hj-menu-sub') + '</li>')
    return f'<li class="{" ".join(classes)}">{link}</li>'


def _has_active(items):
    return any(i["active"] or _has_active(i["items"]) for i in items)
