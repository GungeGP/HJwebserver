"""Auth configuration and user/session/audit management - the app.createUser(),
app.setRole(), app.getAuditLog() etc. surface, plus settings(auth=True) itself.

Same feature as WebServer.auth (the hashing/token/lockout engine) and
WebServer.database.auth (the SQL) - this file is just that feature's public
methods on WebServer itself, one "auth" per layer.
"""

from WebServer.core.server import DEFAULT_CSP


class AuthMixin:
    """settings(auth=...) and every user/session/audit management method."""

    def settings(self, auth=None, jwtSecret=None, tokenLifetimeHours=24, secureCookie=False,
                 bearerTokens=True, maxLoginAttempts=5, lockoutMinutes=15, minPasswordLength=5,
                 auditLog=True, trustProxy=False, csp=DEFAULT_CSP, securityHeaders=True,
                 rememberMeDays=30, idleTimeoutMinutes=0,
                 loginTitle="Access Restricted", loginMessage="Please log in to continue.", loginLogo=None):
        """Configure server settings.

        auth:               enable authentication. Every route and page then requires
                            login unless registered with public=True.
        jwtSecret:          signing secret (>= 32 bytes). Defaults to JWT_SECRET from .env.
        tokenLifetimeHours: how long a normal login stays valid.
        rememberMeDays:     lifetime when the user ticks "Remember me". 0 hides the checkbox.
        idleTimeoutMinutes: log out sessions with no activity for this long. 0 = off.
        secureCookie:       add the Secure flag to the session cookie (needs HTTPS;
                            set automatically by useHttps()).
        bearerTokens:       also accept "Authorization: Bearer <token>" (for scripts).
                            False = cookie only.
        maxLoginAttempts:   failed logins (per username and per IP) before lockout.
        lockoutMinutes:     how long a lockout lasts.
        minPasswordLength:  enforced by createUser / setPassword / change-password.
        auditLog:           write logins, logouts, lockouts and user changes to the AuditLog table.
        trustProxy:         read the client IP from X-Forwarded-For (only behind a reverse proxy).
        csp:                Content-Security-Policy header value, or None to send none.
        securityHeaders:    send X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP.
        loginTitle/loginMessage/loginLogo: text and optional image URL shown on the login form.
        """
        self.auth = auth
        self.csp = csp
        self.security_headers_enabled = bool(securityHeaders)
        if self.auth:
            from WebServer.auth import attach_auth_routes, configure
            configure(
                jwt_secret=jwtSecret,
                token_lifetime_hours=tokenLifetimeHours,
                secure_cookie=secureCookie or bool(self.certfile),
                bearer_tokens=bearerTokens,
                max_login_attempts=maxLoginAttempts,
                lockout_minutes=lockoutMinutes,
                min_password_length=minPasswordLength,
                audit=auditLog,
                trust_proxy=trustProxy,
                remember_me_days=rememberMeDays,
                idle_timeout_minutes=idleTimeoutMinutes,
                login_title=loginTitle,
                login_message=loginMessage,
                login_logo=loginLogo,
            )
            attach_auth_routes(self)

    def checkAuth(self, request):
        """Return the user dict for an authenticated request, else None.

        Protected routes already have this in ``request.user``; this is only
        useful inside public=True routes that want to know if someone is logged in.
        """
        if not self.auth:
            return None
        from WebServer.auth import resolve_user
        return resolve_user(request)

    def _by(self, *details):
        """Audit detail for a user change made from code, ending with who made
        it: "by terminal (d1misgu)" (python -m WebServer) or "by python (d1misgu)"
        (anything else calling these methods, e.g. main.py), with the operating
        system account that ran it. No one is logged in to the site there, so
        this is the best the log can say."""
        import getpass
        actor = getattr(self, '_audit_actor', None) or "python"
        try:
            actor += f" ({getpass.getuser()})"
        except Exception:
            pass   # no account name available (e.g. some service accounts)
        return ", ".join([d for d in details if d] + [f"by {actor}"])

    def createUser(self, username, password, role="user", mustChangePassword=False):
        """Create a user with a hashed password. Returns False if the username already exists.

        role:               free-form string, e.g. "user" or "admin"; checked by route(roles=[...]).
        mustChangePassword: True forces the user to pick a new password on first login.
        Raises ValueError if the password is shorter than minPasswordLength.
        """
        from WebServer.auth import audit, check_password_policy, hash_password, normalize_username
        from WebServer.database import create_user, get_user_by_username
        username = normalize_username(username)
        if not username:
            raise ValueError("Username is required.")
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is not None:
            return False
        create_user(username, hash_password(str(password)), role=str(role or "user"), must_change_password=mustChangePassword)
        audit("user_created", username, self._by(f"role={role}"))
        return True

    def setPassword(self, username, password, mustChangePassword=False):
        """Replace a user's password and log them out everywhere. Returns False if the user does not exist.

        mustChangePassword=True makes it a temporary password the user must replace at next login.
        """
        from WebServer.auth import audit, check_password_policy, hash_password, normalize_username, revoke_sessions
        from WebServer.database import get_user_by_username, update_user_password
        username = normalize_username(username)
        check_password_policy(str(password) if password is not None else "")
        if get_user_by_username(username) is None:
            return False
        update_user_password(username, hash_password(str(password)), must_change_password=mustChangePassword)
        revoke_sessions(username)
        audit("password_changed", username, self._by("temporary" if mustChangePassword else None))
        return True

    def setRole(self, username, role):
        """Change a user's role. Takes effect on their next request. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username
        from WebServer.database import get_user_by_username, set_user_role
        username = normalize_username(username)
        record = get_user_by_username(username)
        if record is None:
            return False
        set_user_role(username, str(role))
        audit("role_changed", username, self._by(f"{record.Role or 'user'} -> {role}"))
        return True

    def disableUser(self, username):
        """Block logins and end all sessions, keeping the account. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        from WebServer.database import get_user_by_username, set_user_disabled
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        set_user_disabled(username, True)
        revoke_sessions(username)
        audit("user_disabled", username, self._by())
        return True

    def enableUser(self, username):
        """Re-enable a disabled account. Returns False if no such user."""
        from WebServer.auth import audit, normalize_username
        from WebServer.database import get_user_by_username, set_user_disabled
        username = normalize_username(username)
        if get_user_by_username(username) is None:
            return False
        set_user_disabled(username, False)
        audit("user_enabled", username, self._by())
        return True

    def deleteUser(self, username):
        """Remove a user and all their sessions. Returns False if the user does not exist."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        from WebServer.database import delete_user, get_user_by_username
        username = normalize_username(username)
        record = get_user_by_username(username)
        if record is None:
            return False
        revoke_sessions(username)
        delete_user(username)
        audit("user_deleted", username, self._by(f"role={record.Role or 'user'}"))
        return True

    def getUser(self, username):
        """{"username", "role", "disabled", "mustChangePassword"} or None."""
        from WebServer.auth import normalize_username
        from WebServer.database import get_user_by_username
        record = get_user_by_username(normalize_username(username))
        return self._public_user(record) if record else None

    def listUsers(self):
        """All users as [{"username", "role", "disabled", "mustChangePassword"}], sorted by name."""
        from WebServer.database import get_all_users
        return [self._public_user(r) for r in get_all_users()]

    @staticmethod
    def _public_user(record):
        return {"username": record.Username, "role": record.Role or "user",
                "disabled": bool(record.Disabled), "mustChangePassword": bool(record.MustChangePassword)}

    def revokeSessions(self, username):
        """Log a user out of every browser/device immediately."""
        from WebServer.auth import audit, normalize_username, revoke_sessions
        username = normalize_username(username)
        revoke_sessions(username)
        audit("sessions_revoked", username, self._by())

    def unlock(self, username=None, ip=None):
        """Lift a login lockout early. unlock("alice") or unlock(ip="10.0.0.5"); no arguments = all."""
        from WebServer.auth import audit, unlock
        removed = unlock(username, ip)
        audit("lockout_cleared", username, self._by(f"ip={ip}" if ip else ("all" if username is None else None)))
        return removed

    def getLockouts(self):
        """Who is currently locked out: [{"type": "username"|"ip", "value", "failures", "remaining"}]."""
        from WebServer.auth import get_lockouts
        return get_lockouts()

    def getSessions(self, username):
        """Active sessions for a user (Jti, Username, CreatedAt, ExpiresAt, LastSeen as epoch seconds)."""
        from WebServer.auth import normalize_username
        from WebServer.database import get_sessions_for_user
        return get_sessions_for_user(normalize_username(username))

    def audit(self, request, event, detail=None):
        """Record your own event in the AuditLog, attributed to the request's user and IP."""
        from WebServer.auth import audit
        user = getattr(request, 'user', None) or {}
        audit(event, user.get("username"), detail, request)

    def getAuditLog(self, limit=100, username=None):
        """Most recent audit entries (Id, At, Username, Event, Detail, Ip), newest first."""
        from WebServer.database import get_audit_log
        return get_audit_log(limit=limit, username=username)

    def createAuth(self, username):
        """Create a session token for a user without a password (for scripts/tests). Requires settings(auth=True)."""
        from WebServer.auth import audit, create_token_for_user
        if not self.auth:
            raise RuntimeError("Authentication is not enabled. Use settings(auth=True) first.")
        token, _ = create_token_for_user(username)
        audit("token_issued", username, self._by("createAuth"))
        return token

    def _login_shell_html(self):
        from WebServer.auth import login_shell_html
        return login_shell_html(self.get_inject_js_urls())

    def _resolve_user(self, request):
        from WebServer.auth import resolve_user
        return resolve_user(request)
