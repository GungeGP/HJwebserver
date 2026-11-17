"""Queries for the AuditLog table.

Consumed by WebServer.auth (writing events, deleting old ones) and
app.getAuditLog() - this module only knows SQL, not HTTP or Authentik.

Users, Sessions and LoginAttempts are still created by create_tables() (see
database/core.py) and left as they are, but nothing reads or writes them.
"""

from WebServer.database.core import execute, fetch_all, get_database_type


# --- Audit log ------------------------------------------------------------

def insert_audit(at, username, event, detail, ip):
    execute("INSERT INTO AuditLog (At, Username, Event, Detail, Ip) VALUES (?, ?, ?, ?, ?)",
            (int(at), username, event, detail, ip))


def delete_audit_before(before):
    execute("DELETE FROM AuditLog WHERE At < ?", (int(before),))


def get_audit_log(limit=100, username=None):
    where = "WHERE Username = ?" if username else ""
    params = (username,) if username else ()
    if get_database_type() == "mssql":
        sql = f"SELECT TOP {int(limit)} Id, At, Username, Event, Detail, Ip FROM AuditLog {where} ORDER BY Id DESC"
    else:
        sql = f"SELECT Id, At, Username, Event, Detail, Ip FROM AuditLog {where} ORDER BY Id DESC LIMIT {int(limit)}"
    return fetch_all(sql, params)
