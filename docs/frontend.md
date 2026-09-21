# Frontend

## Injected scripts

Every HTML file the framework serves (via `addPath` or from `public/`) gets these
tags inserted just before `</body>`:

```html
<script src="/webserver.js?v=…"></script>
<script src="/auth.js?v=…"></script>   <!-- only when auth is on -->
```

The `?v=` value changes whenever the file changes, so browsers never use a stale copy.

You can override either script by putting your own `webserver.js` or `auth.js` in
your `public/` folder; the framework serves yours instead of its bundled copy.

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

## `auth.js` — the login overlay

Present only when `settings(auth=True)`. On page load it:

1. Adds a hidden full-screen login form to the page.
2. Calls `GET /api/verify`. If that fails, the overlay is shown; otherwise it stays hidden.
3. Wraps `window.fetch`: if any of *your* API calls returns `401` (session
   expired), the overlay pops up again. Your code doesn't need to handle that.

On a successful login the page reloads, so the server can send the protected
content it withheld earlier.

### Adding a logout button

Give any element `id="logout"`:

```html
<button id="logout">Log out</button>
```

`auth.js` wires it to `POST /api/logout` followed by a reload. Alternatively
call the global `logout()` function yourself.

### Styling the overlay

The form's ids and classes are stable, so a stylesheet in your page can restyle it:

| Selector | Element |
|----------|---------|
| `#login-overlay` | full-screen dimmed backdrop |
| `.login-box` | the white card |
| `#login-form` | the `<form>` |
| `#username`, `#password` | the inputs |
| `#login-btn` | the submit button (disabled until both fields are filled) |

Your page's CSS loads before the injected script's inline styles, so use
slightly more specific selectors (e.g. `body #login-btn`) or `!important` to win.

## Calling your API from the page

Nothing special is needed. The session cookie travels with every request:

```js
const res = await fetch('/api/my-entries');
if (res.ok) {
    const data = await res.json();
}
// a 401 here is already handled by auth.js (overlay re-appears)
```

For `POST`, send JSON so the server parses `request.body` for you:

```js
await fetch('/api/data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours: 7.5 })
});
```
