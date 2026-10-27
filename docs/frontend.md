# Frontend

## Injected scripts

Every HTML file the framework serves (via `addPath` or from `public/`) gets these
tags inserted just before `</body>`:

```html
<script src="/js/webserver.js?v=…"></script>
<script src="/js/Dialog.js?v=…"></script>
<script src="/js/auth.js?v=…"></script>   <!-- only when auth is on -->
<script src="/js/TableViewer.js?v=…"></script>   <!-- only once addTableViewer() is used -->
```

The `?v=` value changes whenever the file changes, so browsers never use a stale copy.

You can override any of these by putting your own copy at the same relative path
under your `public/` folder (`public/js/auth.js`, `public/css/auth.css`, ...); the
framework serves yours instead of its bundled copy. Stylesheets (`css/auth.css`,
`css/TableViewer.css`, `css/Dialog.css`) are linked at runtime by their matching
script, not injected server-side.

## Shared header, footer, navigation — includes

Any HTML page the framework serves can pull in another file:

```html
<!-- public/index.html -->
<!DOCTYPE html>
<html>
<head><title>Home</title></head>
<body>
  <!--#include file="partials/header.html" -->
  <main>…</main>
  <!--#include file="partials/footer.html" -->
</body>
</html>
```

```html
<!-- public/partials/header.html -->
<header>
  <nav><a href="/">Home</a> <a href="/reports.html">Reports</a></nav>
  <span id="who"></span>
</header>
```

The include is expanded on the server before the page is sent, so the header
is part of the HTML from the first byte — no JavaScript involved and no flash
of a missing header.

Rules:

- The path is relative to the file doing the including. A leading `/` means
  "from the `public/` root" — handy in sub-folders: `<!--#include file="/partials/header.html" -->`.
- Included files can include other files (up to 5 levels). Circular includes stop.
- Includes can't reach outside `public/`. A bad or missing path is replaced by an
  HTML comment (`<!-- include "x" not found -->`) rather than breaking the page.
- Works for pages from `public/` and for `addPath` pages. Included files are
  plain HTML — no variables or logic. For per-user content, put a placeholder in
  the partial and fill it from JS (the `hj:ready` example above).
- `<!--#include virtual="…" -->` is accepted as an alias, so partials also work
  unchanged under Apache/nginx/IIS SSI.

Partials in `public/` are served as normal files too. If you'd rather they
weren't reachable directly, keep them in a folder like `public/partials/` — they're
harmless, but you can also block that folder with a route that returns 404.

## `webserver.js`

Defines one global:

```js
Notify(message, type)   // type: "error" | "info" | ...
```

The default implementation is `console.log`. Define your own `Notify` **before**
the framework scripts run (i.e. in the `<head>` or in a script earlier in the
body) to show toasts, banners, etc.:

```html
<script>
  window.Notify = (msg, type) => alert(`[${type}] ${msg}`);
</script>
```

The login overlay uses it to report "Invalid username or password." and
connection failures.

## `Dialog.js` — popups: `hjDialog`

A dialog centred on the screen over a dimmed page, available on every page.
One function, `hjDialog.open(options)`, covers every kind; it returns a
promise with the answer, or `null` when the user cancels (Cancel, Escape or a
click outside the box).

```js
// Ask for a reason before doing something destructive
const reason = await hjDialog.open({
    type: 'textarea',
    title: 'Delete row',
    message: 'This cannot be undone.',
    label: 'Reason',
    confirmText: 'Delete',
    danger: true,
});
if (reason === null) return;   // cancelled

// Plain yes/no
if (await hjDialog.confirm('Send the report now?')) { … }

// Pick one
const team = await hjDialog.open({ type: 'select', title: 'Move to team', options: ['IT', 'HR', 'Økonomi'] });
```

| Option | Default | Meaning |
|---|---|---|
| `type` | `'confirm'` | `'confirm'` (OK/Cancel), `'alert'` (only OK), `'text'`, `'textarea'` (Ctrl+Enter confirms), `'select'` |
| `title`, `message` | — | Heading and text. Plain text, never HTML; line breaks in `message` are kept |
| `label`, `placeholder`, `value` | — | Caption, placeholder and starting value of the field |
| `options` | — | For `'select'`: `['a', 'b']` or `[{ value, label }]` |
| `required` | `true` | The confirm button stays disabled while the field is empty |
| `maxLength` | — | Longest text the field accepts |
| `confirmText`, `cancelText` | `'OK'`, `'Cancel'` | Button texts |
| `danger` | `false` | Red confirm button, for deleting and other destructive actions |
| `onConfirm` | — | `async (value) => {…}` run on confirm. Throw to show the error inside the dialog and keep it open, e.g. when the server refuses |

What it resolves to: the trimmed text for `'text'`/`'textarea'`, the chosen
value for `'select'`, `true` for `'confirm'`/`'alert'`, `null` when cancelled.

Shorthands: `hjDialog.confirm(message, options)`, `hjDialog.alert(message, options)`,
`hjDialog.prompt(message, options)` (a text field; pass `type: 'textarea'` for
several lines).

Styling: the classes all start with `hj-dialog` (`.hj-dialog-box`,
`.hj-dialog-confirm`, …); see `css/Dialog.css`, or override it with your own
`public/css/Dialog.css`.

## `auth.js` — the login overlay

Present only when `settings(auth=True)`. On page load it:

1. Fetches `/api/login-config` (title, message, logo, whether "Remember me" is on)
   and `/api/verify` in parallel, and builds a hidden overlay with two forms:
   **login** and **change password**.
2. If the session is valid the overlay stays hidden — unless the account has a
   temporary password, in which case the change-password form is shown and
   cannot be dismissed. If no one is logged in, the login form is shown.
3. Wraps `window.fetch`: a `401` from any of *your* API calls re-shows the login
   form; a `403 password_change_required` shows the change-password form.
4. Fires `hj:ready` on `window` once, with the user (or `null`).

On a **public page** (`addPath(..., public=True)`) steps 2 and 3 never show the
login form; a `401` there is left to your page. `hjAuth.showLogin()` still opens
it, for a "Log in" button.

On a successful login or password change the page reloads, so its data loads
with the new session.

### Knowing who is logged in

```js
window.addEventListener('hj:ready', (e) => {
    const user = e.detail.user;          // {username, role, mustChangePassword} or null
    if (user) { header.textContent = `Hi ${user.username}`; }
    if (user?.role === 'admin') { adminPanel.hidden = false; }
});
```

`window.currentUser` holds the same object after `hj:ready` has fired. Hiding
an element in the page is cosmetic only — the server still enforces `roles=`
on the routes behind it.

### Buttons that just work

Give any element one of these ids and `auth.js` wires it up:

| id | Action |
|----|--------|
| `logout` | `POST /api/logout`, then reload |
| `logout-all` | `POST /api/logout-all` (every device), then reload |
| `change-password` | opens the change-password form (with a Cancel button) |

```html
<button id="change-password">Change password</button>
<button id="logout">Log out</button>
```

### `window.hjAuth`

For your own code:

```js
hjAuth.user                          // same as window.currentUser
await hjAuth.logout()                // reloads
await hjAuth.logoutEverywhere()      // reloads
hjAuth.showChangePassword()          // opens the form
hjAuth.showLogin()                   // opens the login form
const { ok, error } = await hjAuth.changePassword(current, next)   // no reload; error is a message or null
```

### Customising the form

Text, message and logo come from the server:

```python
app.settings(auth=True, loginTitle="WorkTime", loginMessage="Sign in with your company account", loginLogo="/logo.png")
```

(`loginLogo` must be served publicly — `app.addPath('/logo.png', 'public/logo.png', public=True)`.)

For styling, the ids and classes are stable:

| Selector | Element |
|----------|---------|
| `#login-overlay` | full-screen dimmed backdrop |
| `.login-box` | the white card |
| `#login-form`, `#change-form` | the two `<form>`s |
| `#username`, `#password`, `#remember-me` | login inputs |
| `#current-password`, `#new-password`, `#confirm-password` | change-password inputs |
| `#login-btn`, `#change-btn`, `#change-cancel` | buttons |

Your page's CSS loads before the injected script's inline styles, so use
slightly more specific selectors (e.g. `body #login-btn`) or `!important` to win.

## Calling your API from the page

Nothing special is needed. The session cookie travels with every request:

```js
const res = await fetch('/api/my-entries');
if (res.ok) {
    const data = await res.json();
}
// a 401 here is already handled by auth.js (overlay re-appears; not on public pages)
```

For `POST`, send JSON so the server parses `request.body` for you:

```js
await fetch('/api/data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours: 7.5 })
});
```
