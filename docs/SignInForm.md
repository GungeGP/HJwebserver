# Sign-in form — Microsoft login + local accounts

**Status: implemented** in `WebServer/microsoft.py` (sign-in, Graph, linking,
account check), `WebServer/auth.py` (roles, ssoOnly, logout) and
`public/js/auth.js` (the form). Where the code differs from the original
design, this document has been updated to match it.

HJwebserver is a framework, so everything here is **opt-in per app**. An app that
only calls `settings(auth=True)` keeps today's username + password form and
behaves exactly as before. Microsoft login is added *next to* the normal
login, never instead of it; each app decides what its login shows through
`settings()` parameters.

Build order: [threading](#prerequisite-threading) first, then the Microsoft
login, then the sign-in form, then [ranked roles](#ranked-roles-rolehierarchy).

## Goal

One login form, one input field, that:

- Lets Microsoft (Entra ID) accounts and local username + password accounts
  coexist in the same app.
- Picks the right path from what the user types. No "Sign in with Microsoft"
  button and no "I'm an employee / service account" toggle.
- Accepts a bare name: typing `mgu` is enough, the domain is added for you.
- Can be locked down to **Microsoft only** (`ssoOnly`), with an optional
  break-glass local account.

## Settings

```python
# Today, unchanged: username + password form
app.settings(auth=True)

# Both kinds of account
app.settings(auth=True, ssoDomains=["hjoerring.dk"])

# Microsoft only, with one emergency local admin, ranked roles and Graph groups
app.settings(auth=True,
             ssoDomains=["hjoerring.dk"], ssoOnly=True, localAccounts=["admin"],
             roleHierarchy=["dev", "admin", "manager", "user"],
             microsoftRoles={"<admin-group-id>": "admin", "<manager-group-id>": "manager"})
```

The app registration comes from each app's own `.env`, never from code:

```
MS_TENANT_ID=...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
```

If `ssoDomains` is set and one of them is missing, the server refuses to start
(the same way it does today when `JWT_SECRET` is missing).

| Parameter | Default | Meaning |
|---|---|---|
| `ssoDomains` | `None` | Turns on Microsoft login and the username-first form. Typed addresses in these domains go to Microsoft; the first entry is added to bare names |
| `ssoOnly` | `False` | No password login, in the form **or** on the server, except for `localAccounts` |
| `localAccounts` | `[]` | Under `ssoOnly`: local names that may still use a password (break-glass admin, service accounts) |
| `microsoftNewUsers` | `False` | `True`: create a user on their first Microsoft login. `False`: an admin creates them first (`createuser ... --sso`) |
| `microsoftRoles` | `None` | `{group object id: role}` read from Microsoft Graph at every Microsoft login. `None`: roles are managed locally, as today |
| `microsoftGuests` | `False` | Allow guest accounts (`#EXT#` users from other organizations) in the tenant |
| `microsoftSessionHours` | `8` | Session lifetime for Microsoft users. "Remember me" is not offered on the Microsoft path |
| `microsoftLogout` | `True` | Logout also signs out at Microsoft (important on shared PCs) |
| `microsoftCheckEnabled` | `False` | Periodically ask Graph whether each signed-in Microsoft user is still enabled, and end their sessions if not. Needs the `User.Read.All` application permission |
| `microsoftRedirectUri` | built from the request's host | Override when behind a proxy or when the host name differs |
| `roleHierarchy` | `None` | Ranked roles, highest first. See [Ranked roles](#ranked-roles-rolehierarchy) |
| `auditRetentionDays` | `None` | Delete audit log rows older than this. `None`: keep forever (as today) |

## What the user sees

| Settings | Login form |
|---|---|
| `settings(auth=True)` | Username + password, exactly as today |
| `ssoDomains=[...]` | A username field and **Continue**. Then either Microsoft, or a password field appears and the button becomes **Sign in** |
| `ssoDomains=[...], ssoOnly=True` | A username field and **Continue**. A password field appears only for names in `localAccounts` |

Editing the field after a step has resolved resets the form to its first step,
with no stale password field left over.

## Who decides: `POST /api/login/start`

The **server** decides where a typed name goes, not `auth.js`. That keeps the
rules in one place (Python, set per app), means a replaced `auth.js` can't get
them wrong, and lets local accounts look like mail addresses.

```
POST /api/login/start
{"username": "mgu", "next": "/cal", "rememberMe": false}
```

| Typed | Without `ssoOnly` | With `ssoOnly` |
|---|---|---|
| `mgu@hjoerring.dk` (domain in `ssoDomains`) | Microsoft | Microsoft |
| `mgu`, and a local password account `mgu` exists | Password field | Password field only if `mgu` is in `localAccounts`, else Microsoft |
| `mgu`, no local password account by that name | Microsoft, as `mgu@hjoerring.dk` | Microsoft, as `mgu@hjoerring.dk` |
| `x@gmail.com` (other domain) | Password field (a local account may look like a mail address) | `403` "This system requires Microsoft sign-in." |

Responses:

- `200 {"method": "microsoft", "redirect": "<Microsoft authorize URL>"}`, plus
  the `hj_sso` state cookie. `auth.js` navigates to `redirect`.
- `200 {"method": "password"}`: `auth.js` shows the password field and signs in
  through the existing `POST /api/login`.
- `403 {"error": "..."}`: shown as a message, no password field.

With several domains, the first one is used for bare names; type the full
address for the others. A local account with the same bare name wins: type the
full address to reach Microsoft instead.

`next` must be a relative path on the same site (starting with `/`, not `//`),
otherwise it is ignored and the user lands on `/`. This prevents an open redirect.

**The typed name is only a hint.** It is sent to Microsoft as `login_hint` so the
sign-in page is pre-filled, and the user can change it there. Who someone is
comes only from the token Microsoft sends back.

## Microsoft login flow

```
Browser ──► POST /api/login/start          (sets hj_sso cookie, returns redirect)
Browser ──► login.microsoftonline.com      (user signs in, MFA)
Browser ──► GET /auth/microsoft/callback?code=...&state=...
Server  ──► login.microsoftonline.com      (code → tokens)        outbound only
Server  ──► graph.microsoft.com            (/me, /me/transitiveMemberOf)  outbound only
Browser ◄── session cookie, then on to `next`
```

Microsoft never connects to the server, so it can be tested on `localhost` and
never has to be reachable from the internet.

| Route | Public | What it does |
|---|---|---|
| `POST /api/login/start` | yes | Decides the path (above). For Microsoft: creates `state`, `nonce` and a PKCE verifier, stores them in the `hj_sso` cookie and returns the authorize URL with `login_hint` |
| `GET /auth/microsoft/callback` | yes | Checks `state`, exchanges the code (client secret + PKCE), validates the ID token, reads Graph, links the user, starts the session |

Scopes: `openid profile email offline_access User.Read`, plus
`GroupMember.Read.All` when `microsoftRoles` is set.

### Callback checks

- `state` matches the `hj_sso` cookie, and the cookie is at most 10 minutes old.
- ID token signature (via the tenant's published keys), `iss`, `aud`, `exp`,
  `nonce`, and `tid` equal to `MS_TENANT_ID`.
- The user is not a guest, unless `microsoftGuests=True`.
- Failures are audited as `sso_login_failed` with the reason, and the user
  sees a neutral message.

### Cookies

- `hj_sso` (state, nonce, PKCE verifier, `next`) is signed with `JWT_SECRET`,
  `HttpOnly`, **`SameSite=Lax`** and lives 10 minutes. It must be `Lax`: the
  callback arrives through a cross-site redirect from Microsoft, and a
  `Strict` cookie would not be sent with it.
- The session cookie stays `hj_session` with `SameSite=Strict`. Because a
  redirect chain that started on Microsoft counts as cross-site, the callback
  must **not** answer with a `302` to `next` (the browser would drop the new
  `Strict` cookie on that hop). It answers `200` with a tiny page that moves
  on with `<meta http-equiv="refresh">`, which is a same-site navigation.

### Session

The callback ends in the existing `create_token_for_user()`. Sessions,
revocation, idle timeout, `disableUser`, `request.user`, `roles=` and the audit
log work the same for both kinds of user. The lifetime is
`microsoftSessionHours` instead of `tokenLifetimeHours`.

## Users

New columns on `Users` (added by `_MIGRATIONS`, so existing databases keep working):

| Column | Meaning |
|---|---|
| `ExternalId` | Microsoft's `oid` for the user. Set means "this is a Microsoft user" |
| `DisplayName`, `Email` | From Graph, refreshed at every Microsoft login |
| `RolePinned` | `1`: Graph never changes this user's role (see [Roles](#roles)) |

`PasswordHash` is already nullable. A Microsoft user has no password, so
password login and change-password already fail for them, and the UI hides
"Change password".

### Linking a Microsoft login to a user

1. Look up `ExternalId = oid`. Found: that's the user.
2. Otherwise look up `Username = UPN`, lowercased. Found **and it has no
   password** (created with `--sso`): link it by setting `ExternalId`.
3. Found **with a password**: refuse, audited as `sso_login_failed` ("name
   belongs to a local account"). A Microsoft login never takes over a local
   account, or a Microsoft account named `admin@...` could become the local `admin`.
4. Not found: create the user if `microsoftNewUsers=True`, else refuse.

**The username never changes after the first login**, even if the person's
UPN does. Apps store `request.user["username"]` in their own tables, and the
framework can't rename data there. `DisplayName` and `Email` carry the
current name instead.

New users get the lowest role in `roleHierarchy`, or `"user"` without one.

### CLI and Python API

```bash
python -m WebServer createuser mgu@hjoerring.dk --sso --role admin   # no password, linked at first login
python -m WebServer setrole mgu@hjoerring.dk admin --pin             # Graph won't overwrite it
python -m WebServer setrole mgu@hjoerring.dk admin --unpin
```

In Python: `app.createUser("mgu@hjoerring.dk", role="admin", sso=True)` and
`app.setRole("mgu@hjoerring.dk", "admin", pin=True)`.
`listusers` shows the source (`local` / `microsoft`) and pinned roles.

## Roles

`Users.Role` stays the **only** place a role is stored, for both kinds of
account. Everything that reads it (`route(roles=)`, `addPath(roles=)`,
TableViewer `edit=`/`delete=`, the 403 audit) is unchanged.

| Account | Who sets the role |
|---|---|
| Local (has a password) | As today: `createUser(role=)`, `setRole`, `python -m WebServer setrole`. Microsoft and Graph never touch it |
| Microsoft, without `microsoftRoles` | Like a local account: managed with `setRole` |
| Microsoft, with `microsoftRoles` | Graph groups decide, written into `Role` at every Microsoft login. Unless the role is pinned |

With `microsoftRoles`:

- A user in several mapped groups gets the **highest** role (by
  `roleHierarchy`; without one, the first match in the dict).
- A user in no mapped group gets the lowest role.
- `setRole` on such a user without `--pin` prints a warning that Graph will
  overwrite it at their next login.
- Group changes in Entra take effect at the next Microsoft login, not mid-session.
- Every change is audited as `sso_role_changed`
  (`manager -> admin, from group <id>`).

The usual way to make one person the owner of a Graph-managed system is to
add them to the admin group in Entra; `--pin` is for the exception.

### Ranked roles: `roleHierarchy`

```python
app.settings(auth=True, roleHierarchy=["dev", "admin", "role1", "role2", "role3", "user"])   # highest first
```

With a hierarchy, `roles=` means **"this role or higher"** everywhere:

| Code | Who gets in |
|---|---|
| `route(..., roles=["admin"])` | dev, admin |
| `addPath(..., roles=["role2"])` | dev, admin, role1, role2 |
| `addTableViewer(..., edit=["role1"], delete=["admin"])` | edit: dev, admin, role1. delete: dev, admin |
| `roles=["user"]` | everyone with a role from the list |

Without `roleHierarchy` roles keep today's exact match, so existing apps don't change.

- **`dev` is the top role and sees everything**, including all data in
  production. Give it only to people who are allowed that.
- `createUser` / `setRole` refuse roles that aren't in the list, and a route
  using an unknown role stops the server at startup (catches typos like `admn`).
- A user whose role isn't in the list gets only exact matches, and the
  server warns about them at startup.
- One helper, `has_role(user_role, required_roles)` in `auth.py`, replaces the
  three checks in `WebHandler._authorize` and `core/tableviewer.py`. The 403
  message and the audit say "needs admin or higher".
- `/api/verify` includes the hierarchy, so pages can use
  `hjAuth.hasRole("role1")` to show or hide buttons. The server still decides.
- If a web page for managing users is added later: a user may only grant
  roles below their own, and can't change the role of someone above them.

## Admin accounts

| System | How to get an admin |
|---|---|
| Both kinds of account | A local admin (`createuser admin --role admin`, sign in as `admin`), or a Microsoft user given `admin` (`createuser ... --sso --role admin`, `setrole`, or a group in `microsoftRoles`) |
| `ssoOnly` | A Microsoft user, preferably through a group in `microsoftRoles` |
| `ssoOnly`, emergency | A local account listed in `localAccounts` (long password; lockout still applies; every login audited) |
| Last resort | `python -m WebServer setrole ...` on the server itself, no login needed |

## Logout and shared PCs

With `microsoftLogout=True`, logout ends the local session **and** signs out at
Microsoft, so the next person at a shared PC isn't signed straight in as the
previous user. `POST /api/logout` and `/api/logout-all` answer with a
`redirect` to Microsoft's sign-out page for Microsoft users, which `auth.js`
follows; `GET /logout` redirects there directly. Microsoft sends the browser
back to `https://<host>/` only if that address is registered on the app
registration; otherwise it shows its own "You signed out" page.

The typed name is sent as `login_hint`, so Microsoft signs in that account
rather than whichever one the browser remembers.

## Disabled users

A session outlives a block in Entra. Two layers handle that:

1. `microsoftSessionHours` (default 8) and no "Remember me" for Microsoft users.
2. Optional `microsoftCheckEnabled=True`: a background check asks Graph for
   `accountEnabled` and ends the sessions of users who were disabled.

A user disabled locally with `disableUser` is blocked immediately, as today.

## Audit events

New events: `sso_login_ok`, `sso_login_failed` (with reason),
`sso_user_provisioned`, `sso_user_linked`, `sso_role_changed`, `role_pinned`,
`role_unpinned`, `sso_user_expired` (from `microsoftCheckEnabled`).

## Personal data

Store only what the framework uses: `oid`, display name, mail and the role.
Nothing else from Graph (department, phone, ...) is written. The audit log
holds mail addresses, so `auditRetentionDays` lets each app delete old rows to
match the kommune's retention rules.

## Security considerations

- **The domain check isn't the security boundary.** It decides which path to
  show. Access is enforced by the Microsoft token checks and by the password
  check against a real `Users` row.
- **Account enumeration.** Only bare names involve a lookup: typing `admin`
  shows a password field if a local `admin` exists. Names like that are
  guessable anyway, and lockout protects the password. Mail addresses are
  decided by the domain alone, and `ssoOnly` apps only reveal what's in
  `localAccounts`.
- `ssoOnly` is enforced on the server: `/api/login` refuses everyone not in
  `localAccounts`. Tokens from `app.createAuth()` are unaffected.
- `state` against CSRF, PKCE, `nonce`, full ID-token validation, the secret
  only in `.env`, `next` limited to relative paths.

## Frontend (`auth.js`)

```
stage = "name"

on Continue / Enter:
    if stage == "password":
        POST /api/login (existing flow); return
    value = field.value.trim()
    if empty: show "Enter your username or work email"; return
    response = POST /api/login/start {username: value, next: location.pathname + location.search, rememberMe}
    if response.method == "microsoft":
        show "Taking you to Microsoft sign-in…"; location.href = response.redirect
    else if response.method == "password":
        stage = "password"; show password field; relabel button "Sign in"
    else:
        show response.error

on field input:
    stage = "name"; hide and clear the password field
```

Without `ssoDomains`, `/api/login-config` says so and `auth.js` draws today's
form unchanged. `/api/login-config` gains `ssoEnabled` and `ssoOnly` (not the
domain rules, which stay on the server).

## Infrastructure and IT

Per system, IT creates one Entra app registration:

1. Redirect URIs: `http://localhost:<port>/auth/microsoft/callback` for
   testing, `https://<internal host>/auth/microsoft/callback` for production.
2. A client secret. It expires (at most 24 months): put the date in `.env`
   as `MS_CLIENT_SECRET_EXPIRES=YYYY-MM-DD` and the server warns at startup
   from 30 days before. (Certificates instead of secrets are not supported yet.)
3. Delegated permissions `User.Read` (and `GroupMember.Read.All` with
   `microsoftRoles`), admin consent granted. `User.Read.All` (application)
   only with `microsoftCheckEnabled`.
4. "Assignment required = Yes" for systems using `microsoftNewUsers=True`.
5. The group object ids for `microsoftRoles`.

6. Optionally `https://<internal host>/` as a redirect URI too, so Microsoft
   sends people back after signing out.

Production needs an internal host name and HTTPS: `useHttps()` with an
internal-CA certificate, or IIS / nginx in front with
`settings(secureCookie=True, trustProxy=True)`. The server needs outbound
HTTPS to `login.microsoftonline.com` and `graph.microsoft.com` (check for a
proxy). Nothing has to be reachable from the internet.

## Requirements

`cryptography` (in `requirements.txt`) is needed to check the signature on
Microsoft's tokens. Calls to Microsoft go through `HTTPS_PROXY` if it is set.

## Prerequisite: threading

`HTTPServer` handles one request at a time, and a Microsoft login makes 2–3
outbound calls (about 0.5 s) during which everyone else waits.

**Done:** `WebServer(threaded=True)` is now the default (`ThreadingHTTPServer`,
at most `app.max_threads` at once, TLS handshake per thread, 30 s socket
timeout, password-login lockout and TableViewer writes serialized). See
[WebServer → Threads](webserver.md#threads).
