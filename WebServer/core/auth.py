"""Auth configuration and the audit log - settings(auth=True) itself, plus
app.checkAuth(), app.audit() and app.getAuditLog().

Same feature as WebServer.auth (proxy secret, Authentik's headers, roles,
form token) and WebServer.database.auth (the SQL) - this file is just that
feature's public methods on WebServer itself, one "auth" per layer.
"""

from WebServer.core.server import DEFAULT_CSP


class AuthMixin:
    """settings(auth=...) and the audit log."""

    def settings(self, auth=None, csp=DEFAULT_CSP, securityHeaders=True, trustProxy=False,
                 auditLog=True, auditRetentionDays=None, roleHierarchy=None,
                 authentikRoles=None, devUser=None):
        """Configure server settings.

        auth:               put the app behind Authentik. Every request must then carry
                            PROXY_SECRET (from .env) in X-Proxy-Secret, and every route and
                            page needs a user from Authentik unless registered with public=True.
        csp:                Content-Security-Policy header value, or None to send none.
        securityHeaders:    send X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP.
        trustProxy:         read the client IP from X-Forwarded-For (only behind a reverse proxy).
        auditLog:           write security events (logouts, refused access) to the AuditLog table.
        auditRetentionDays: delete AuditLog rows older than this. None = keep forever.
        roleHierarchy:      ranked roles, highest first, e.g. ["dev", "admin", "user"]. roles=[...]
                            then means "this role or higher". None = exact role match.
        authentikRoles:     {Authentik group name: role}. The user's role is the highest
                            (with roleHierarchy) or first matching one; no match = the lowest role.
        devUser:            {"username": ..., "groups": [...]}: local development without
                            Authentik - everyone is this user. Only allowed when host is the
                            local machine; no proxy secret or headers are checked.
        """
        self.auth = auth
        self.csp = csp
        self.security_headers_enabled = bool(securityHeaders)
        if self.auth:
            from WebServer.auth import attach_auth_routes, configure
            configure(
                host=self.host,
                audit=auditLog,
                trust_proxy=trustProxy,
                role_hierarchy=roleHierarchy,
                audit_retention_days=auditRetentionDays,
                authentik_roles=authentikRoles,
                dev_user=devUser,
            )
            attach_auth_routes(self)

    def checkAuth(self, request):
        """Return the user dict for a request from Authentik, else None.

        Protected routes already have this in ``request.user``; this is only
        useful inside public=True routes that want to know if someone is logged in.
        """
        if not self.auth:
            return None
        from WebServer.auth import resolve_user
        return resolve_user(request)

    def audit(self, request, event, detail=None):
        """Record your own event in the AuditLog, attributed to the request's user and IP."""
        from WebServer.auth import audit
        user = getattr(request, 'user', None) or {}
        audit(event, user.get("username"), detail, request)

    def getAuditLog(self, limit=100, username=None):
        """Most recent audit entries (Id, At, Username, Event, Detail, Ip), newest first."""
        from WebServer.database import get_audit_log
        return get_audit_log(limit=limit, username=username)

    def _resolve_user(self, request):
        from WebServer.auth import resolve_user
        return resolve_user(request)
