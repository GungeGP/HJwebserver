# Side menu

A ready-made menu on the left of every page: a title, items with a
description and a count, sub-items, an Admin button and "Logget ind som …".
Items the user may not open are hidden. You turn it on with one call in
`main.py`; without that call nothing changes.

```python
app.menu(items=[MenuItem("Oversigt", "/oversigt")])
```

## Pages with `addPath` as usual; the menu points to them

The menu doesn't make pages. You make them with `addPath` (and roles go on the
page, as always), and each menu item points to one.

```python
from WebServer import WebServer, MenuItem
from WebServer.helper import send_json

app.addPath('/p109', 'public/p109.html')
app.addPath('/p110', 'public/p110.html')
app.addPath('/stamdata', 'public/stamdata.html')
app.addPath('/stamdata/tilbud', 'public/tilbud.html')
app.addPath('/stamdata/kommuner', 'public/kommuner.html', roles=["admin"])

@app.route('GET', '/api/p109/antal')
def antal_109(request):
    send_json(request, 200, 12)

app.menu(title="Ophold", items=[
    MenuItem("§ 109", "/p109", short="§109", desc="Ophold på kvindekrisecenter", count="/api/p109/antal"),
    MenuItem("§ 110", "/p110", short="§110", desc="Ophold på forsorgshjem og ...", count="/api/p110/antal"),
    MenuItem("Stamdata", "/stamdata", short="Data", items=[
        MenuItem("Tilbud", "/stamdata/tilbud"),
        MenuItem("Kommuner", "/stamdata/kommuner"),      # hidden from everyone below admin: the page needs admin
    ]),
])
```

Every page the framework serves then has the menu on the left and its own
content to the right of it: `addPath` pages and the HTML files in `public/`.
The server puts the menu right after `<body>`, so a page needs a `<body>` tag
(a partial without one is left alone). A click in the menu is an ordinary page
change, so the page's own scripts — TableViewer, the calendar, your own — run
exactly as without the menu.

## `MenuItem(title, url, short=None, desc=None, count=None, items=None, denied="hide")`

| Parameter | Meaning |
|-----------|---------|
| `title` | The text shown. |
| `url` | The page it opens. Must be a page registered with `addPath` (or a `GET` route); an address with no page stops the app at start, naming the address. |
| `short` | The name shown when the menu is folded to its narrow form. Default: the first four characters of `title`. |
| `desc` | A second line under the title. |
| `count` | An address that answers with a JSON number, e.g. `12`. Fetched after the page is shown, and the number is shown in a small box to the right of the item. If the address fails, or answers with anything but a number, no number is shown and the page works as before. |
| `items` | Sub-items, `MenuItem(...)`s. Clicking the item opens its own page; the arrow next to it folds the sub-items in and out. They are open when you are on the item's page or one of theirs. |
| `denied` | `"hide"` (default): hidden from users who may not open the page. `"disable"`: shown greyed out and not clickable. |

The item for the page you are on is highlighted. Titles, descriptions and
short names are text, never HTML — `"<b>"` shows as `<b>`.

## Who sees what

An item is shown when the user may open its page: the menu reads the page's
`roles=` and `public=` from `addPath` and applies the same rule as the server
(with `roleHierarchy`, "this role or higher"). You never set roles on the
menu. Without `auth=True` every item is shown.

On a page with `public=True` the menu follows whoever is logged in; with no one
logged in, only the items for public pages are shown.

A greyed-out item (`denied="disable"`) doesn't fetch its count.

## Options

```python
app.menu(items=[...])                         # no title at the top
app.menu(items=[...], showUser=False)         # no "Logget ind som"
app.menu(items=[...], admin=False)            # no Admin button and no empty /admin
MenuItem("Kommuner", "/stamdata/kommuner", denied="disable")   # greyed out instead of hidden
app.addPath('/', 'public/forside.html', public=True, menu=False)  # a page without the menu
app.addPath('/admin', 'public/admin.html', roles=["admin"])       # your own admin page instead of the empty one
```

| Parameter of `app.menu` | Default | Meaning |
|-----------|---------|---------|
| `items` | — | The `MenuItem(...)`s, top to bottom. |
| `title` | `None` | Heading at the top. `None`: no heading. |
| `showUser` | `True` | "Logget ind som <role>" at the bottom. Only with `auth=True`. |
| `admin` | `True` | An Admin button under "Kun for administratorer" at the bottom, for the role `admin` (and higher with `roleHierarchy`). It leads to `/admin`. `False` removes the button and the empty page. Only with `auth=True`. |
| `sidebar` | `True` | `False` draws no menu; see [Your own navigation](#your-own-navigation-with-the-frameworks-items). |

**The Admin button and `/admin`.** If the app has no page at `/admin`, the
framework shows an empty page with the menu there (`roles=["admin"]`), so the
button always leads somewhere. Your own `app.addPath('/admin', ...)` replaces
it. With `auth=True` and a `roleHierarchy` that has no `admin`, the app refuses
to start until you add `admin` to `roleHierarchy` or pass `admin=False`.

**Folding the menu.** The `«` button at the top folds the menu to a narrow
strip showing each item's short name; `»` folds it out again. The choice is
kept in the browser (`localStorage`) from page to page.

## Your own navigation with the framework's items

```python
app.menu(sidebar=False, items=[...])
```

```html
<nav id="min-nav"></nav>
<script>
window.addEventListener('hj:ready', () => {
    for (const item of hjMenu.items) {      // only the items the user may see
        document.getElementById('min-nav').insertAdjacentHTML('beforeend',
            `<a href="${item.url}">${item.title}</a>`);
    }
});
</script>
```

`hjMenu.items` holds the items the user may see on this page, already filtered
by role:

```js
[{ title: "§ 109", url: "/p109", desc: "Ophold på kvindekrisecenter", short: "§109",
   count: "/api/p109/antal", active: true, disabled: false, items: [] }, ...]
```

`short`, `desc` and `count` are `null` when not set, `active` is the page you
are on, and `disabled` is an item set to `denied="disable"` that the user may
not open (its `count` is then `null`). Fetching the counts is up to you here.

`hjMenu` is ready before `DOMContentLoaded`, so without `auth=True` (where
there is no `hj:ready`) use `DOMContentLoaded` instead. The example puts the
titles in as HTML; use `textContent` if they may contain `<` or `&`.

## No menu

Don't call `app.menu`.

## Changing the look

The menu's styles are in the framework's `css/menu.css`. A
`public/css/menu.css` in your app replaces it completely, like the other
stylesheets (see [Frontend](frontend.md#injected-scripts)). The classes all
start with `hj-menu`; the page you are on is `.hj-menu-item.active`, the
folded menu is `.hj-menu.collapsed`.
