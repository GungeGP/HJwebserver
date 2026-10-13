# Sign-in form — SSO + local accounts

**Status: design only.** Nothing in this document is implemented. It records what
was agreed on in design discussion, as a spec to build from later.

## Goal

One login form, on one input field, that:

- Lets Microsoft/Entra ID (SSO) and local username+password accounts coexist in
  the same app.
- Picks the right path automatically from what the user types — no "I'm an
  employee" / "I'm a service account" toggle for them to get wrong.
- Can be locked down to **SSO-only** for deployments that don't want local
  accounts at all.

Depends on the Microsoft SSO login feature itself (separate design, see prior
discussion — `useMicrosoftLogin()`, `autoProvision`, tenant/client config).
This document is specifically the **sign-in form's** behavior on top of that.

## The three recognized states

One field, one button (`Continue`, relabeled as the flow progresses — never a
second button stacked underneath). Resolved by checking the typed value
against the configured SSO domain(s):

| Typed value | Example | Resolves to |
|---|---|---|
| Ends in a configured SSO domain | `alice@hjorring.dk` | Redirect straight to Microsoft sign-in — pressing `Continue` navigates immediately, there is no intermediate "Continue with Microsoft" confirmation step |
| No `@` at all | `svc-backup` | Treated as a local account — a password field appears in place, `Continue` relabels itself to `Sign in` |
| Contains `@` but not a configured SSO domain | `alice@gmail.com` | Rejected with a neutral message; no password field is ever offered for this case |

Editing the field after a state has resolved resets the form back to the
initial `Continue` state — no stale password field left over from a previous
attempt.

## SSO-only mode

A single setting, `ssoOnly`. When on:

- SSO domain match → unchanged, redirects to Microsoft as above.
- Everything else (local-looking username **or** unrecognized domain) →
  rejected with: *"This organization requires Microsoft sign-in. Contact your
  administrator if you believe this is wrong."* No password field is ever
  shown, regardless of what the input looks like — local accounts are not
  offered at all in this mode, not even attempted.

## Settings API (proposed)

```python
app.settings(auth=True, ssoDomains=["hjorring.dk"], ssoOnly=False)
app.useMicrosoftLogin(
    tenantId=os.environ["MS_TENANT_ID"],
    clientId=os.environ["MS_CLIENT_ID"],
    clientSecret=os.environ["MS_CLIENT_SECRET"],
    autoProvision=False, # True: auto create users
    defaultRole="user",
)

# No SSO:
app.settings(auth=True)
```

| Parameter | Where | Meaning |
|---|---|---|
| `ssoDomains` | `settings()` | list of email domains that route to SSO (e.g. `["hjorring.dk"]`); anything not ending in one of these is treated as local, unless `ssoOnly` |
| `ssoOnly` | `settings()` | `True` disables the local-account path entirely, regardless of what's typed |
| `autoProvision` | `useMicrosoftLogin()` | create a local `Users` row automatically on first successful Microsoft login, vs requiring an admin to have pre-created it (see prior SSO design doc/discussion) |

## Backend pieces needed

- **`GET /api/login-config`** (existing route) gains two new fields in its
  response: `ssoDomains` and `ssoOnly`, so `auth.js` can do the domain check
  client-side without a server round-trip per keystroke — same mechanism it
  already uses for `title`/`message`/`logo`/`rememberMe`.
- **`GET /auth/microsoft/login`** and **`GET /auth/microsoft/callback`** — from
  the separate SSO design, unchanged by this document.
- **`createUser` needs to accept `password=None`** for SSO-only accounts —
  today it always hashes a password. `Users.PasswordHash` is already a
  nullable column, so this is a code change only, no schema change.

## Frontend state machine (`auth.js`)

Single mutable state, not a set of independent toggles:

```
stage = "email"

on Continue / Enter:
    value = field.value.trim().lower()

    if stage == "password":
        submit login (existing POST /api/login flow)
        return

    if value is empty:
        show "Enter your work email first"; return

    if value ends with a configured ssoDomain:
        hide field + button, show "Taking you to Microsoft sign-in…"
        window.location.href = "/auth/microsoft/login"
        return

    looksLocal = "@" not in value

    if ssoOnly:
        show rejection message (wording depends on looksLocal); return

    if looksLocal:
        stage = "password"
        reveal password field, relabel button to "Sign in"
        return

    show "This isn't a <org> address" rejection message

on field input (any edit):
    reset to stage "email", clear password field, re-enable button
```

## Security considerations

- **No account enumeration.** The "unrecognized domain" and "SSO-only
  rejection" messages never confirm or deny whether a specific account exists
  — they only describe the *domain*, which is public information, not account
  state.
- **The domain check is cosmetic, not the security boundary.** `ssoDomains`
  only decides which UI path to *show*; it is not what prevents a non-org
  email from logging in. That enforcement already exists server-side (the
  Microsoft callback only succeeds for real tenant accounts; local login
  already requires a correct password against a real `Users` row). This form
  is a convenience, not an access-control mechanism in itself.
- Everything from the separate SSO design doc still applies on the Microsoft
  side: `state` param for CSRF, PKCE, ID token signature/`aud`/`iss`/`exp`
  validation, `client_secret` in `.env` only.

## Open questions / decisions still needed before building

1. **Local accounts must use plain usernames, not email-shaped identifiers**,
   for the domain check to tell "local account" apart from "mistyped
   external email." If local accounts should also be allowed to look like
   emails, the client-side domain check alone can't disambiguate — you'd need
   a real lookup against `Users` before deciding which path to show, which is
   slower and reopens the account-enumeration question.
2. **`ssoDomains` is a list** — confirm whether this project ever needs more
   than one domain (e.g. a merged municipality, or a shared service across
   kommunes) or whether a single `ssoDomain` string is simpler for the common
   case.
3. **Default for `ssoOnly`** — proposed default `False` (local accounts stay
   available unless explicitly turned off), consistent with every other
   opt-in flag in this framework (`readOnly`, `public`, `auto_provision` all
   default to the less restrictive... actually the *safer* choice, not the
   more permissive one — worth double-checking this one specifically since
   `ssoOnly=False` is the more permissive default, not the safer one).
