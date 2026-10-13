"""Queries for the auth-related tables: Users, Sessions, LoginAttempts, AuditLog.

Consumed by WebServer.auth (session/login/lockout logic) and WebServer's user
management methods (createUser, setRole, ...) - this module only knows SQL,
not hashing, tokens, or HTTP.
"""

from WebServer.database.core import execute, fetch_all, fetch_one, get_database_type

_USER_COLUMNS = "Username, PasswordHash, Role, Disabled, MustChangePassword"


def get_user_by_username(username):
    return fetch_one(f"SELECT {_USER_COLUMNS} FROM Users WHERE Username = ?", (username,))


def get_all_users():
    return fetch_all(f"SELECT {_USER_COLUMNS} FROM Users ORDER BY Username")


def create_user(username, password_hash, role="user", must_change_password=False):
    sql = """
    INSERT INTO Users (Username, PasswordHash, Role, Disabled, MustChangePassword)
    VALUES (?, ?, ?, 0, ?)
    """
    execute(sql, (username, password_hash, role, 1 if must_change_password else 0))
    return username


def update_user_password(username, password_hash, must_change_password=False):
    execute("UPDATE Users SET PasswordHash = ?, MustChangePassword = ? WHERE Username = ?",
            (password_hash, 1 if must_change_password else 0, username))


def set_user_role(username, role):
    execute("UPDATE Users SET Role = ? WHERE Username = ?", (role, username))


def set_user_disabled(username, disabled):
    execute("UPDATE Users SET Disabled = ? WHERE Username = ?", (1 if disabled else 0, username))


def delete_user(username):
    execute("DELETE FROM Users WHERE Username = ?", (username,))


# --- Sessions -------------------------------------------------------------

def create_session(jti, username, created_at, expires_at):
    execute("INSERT INTO Sessions (Jti, Username, CreatedAt, ExpiresAt, LastSeen) VALUES (?, ?, ?, ?, ?)",
            (jti, username, int(created_at), int(expires_at), int(created_at)))


def get_session(jti):
    return fetch_one("SELECT Jti, Username, CreatedAt, ExpiresAt, LastSeen FROM Sessions WHERE Jti = ?", (jti,))


def touch_session(jti, now):
    execute("UPDATE Sessions SET LastSeen = ? WHERE Jti = ?", (int(now), jti))


def delete_other_sessions(username, keep_jti):
    execute("DELETE FROM Sessions WHERE Username = ? AND Jti <> ?", (username, keep_jti))


def delete_session(jti):
    execute("DELETE FROM Sessions WHERE Jti = ?", (jti,))


def delete_sessions_for_user(username):
    execute("DELETE FROM Sessions WHERE Username = ?", (username,))


def delete_expired_sessions(now):
    execute("DELETE FROM Sessions WHERE ExpiresAt < ?", (int(now),))


def get_sessions_for_user(username):
    return fetch_all("SELECT Jti, Username, CreatedAt, ExpiresAt, LastSeen FROM Sessions WHERE Username = ? ORDER BY CreatedAt DESC",
                     (username,))


# --- Login attempts / lockouts --------------------------------------------

def get_login_attempt(key):
    return fetch_one("SELECT AttemptKey, FailCount, LastAt, LockedUntil, LastUser FROM LoginAttempts WHERE AttemptKey = ?", (key,))


def save_login_attempt(key, fail_count, last_at, locked_until, last_user):
    if get_login_attempt(key) is None:
        execute("INSERT INTO LoginAttempts (AttemptKey, FailCount, LastAt, LockedUntil, LastUser) VALUES (?, ?, ?, ?, ?)",
                (key, int(fail_count), int(last_at), int(locked_until), last_user))
    else:
        execute("UPDATE LoginAttempts SET FailCount = ?, LastAt = ?, LockedUntil = ?, LastUser = ? WHERE AttemptKey = ?",
                (int(fail_count), int(last_at), int(locked_until), last_user, key))


def delete_login_attempt(key):
    execute("DELETE FROM LoginAttempts WHERE AttemptKey = ?", (key,))


def delete_login_attempts_by_user(last_user):
    execute("DELETE FROM LoginAttempts WHERE LastUser = ? AND AttemptKey LIKE 'ip:%'", (last_user,))


def delete_all_login_attempts():
    execute("DELETE FROM LoginAttempts")


def get_locked_attempts(now):
    return fetch_all("SELECT AttemptKey, FailCount, LastAt, LockedUntil, LastUser FROM LoginAttempts WHERE LockedUntil > ?", (int(now),))


def delete_stale_login_attempts(before):
    execute("DELETE FROM LoginAttempts WHERE LastAt < ? AND LockedUntil < ?", (int(before), int(before)))


# --- Audit log ------------------------------------------------------------

def insert_audit(at, username, event, detail, ip):
    execute("INSERT INTO AuditLog (At, Username, Event, Detail, Ip) VALUES (?, ?, ?, ?, ?)",
            (int(at), username, event, detail, ip))


def get_audit_log(limit=100, username=None):
    where = "WHERE Username = ?" if username else ""
    params = (username,) if username else ()
    if get_database_type() == "mssql":
        sql = f"SELECT TOP {int(limit)} Id, At, Username, Event, Detail, Ip FROM AuditLog {where} ORDER BY Id DESC"
    else:
        sql = f"SELECT Id, At, Username, Event, Detail, Ip FROM AuditLog {where} ORDER BY Id DESC LIMIT {int(limit)}"
    return fetch_all(sql, params)
