"""Database access layer.

Supports three backends, selected with ``createConnection(type=...)``:

* ``"sqlite"`` - built-in ``sqlite3``; ``dbName`` is the path to the .db file
* ``"mssql"``  - Microsoft SQL Server via ``pyodbc``
* ``"mysql"``  - MySQL / MariaDB via ``pymysql``

All SQL in this module is written with ``?`` placeholders; they are translated
to the driver's native style automatically. Rows returned from queries expose
columns as attributes (``row.Username``) regardless of the backend.
"""

from contextlib import contextmanager
from types import SimpleNamespace

SUPPORTED_TYPES = ("sqlite", "mssql", "mysql")

_config = {
    "type": None,
    "server": None,
    "dbName": None,
    "user": None,
    "password": None,
    "port": None,
}


def createConnection(type="mssql", server="localhost", dbName="test", user=None, password=None, port=None):
    """Store the connection settings. No connection is opened until it is needed."""
    db_type = str(type).lower()
    if db_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported database type '{type}'. Choose one of: {', '.join(SUPPORTED_TYPES)}")

    _config.update(
        type=db_type,
        server=server,
        dbName=dbName,
        user=user,
        password=password,
        port=port,
    )


def get_database_type():
    return _config["type"]


def get_connection():
    """Open and return a new raw DB-API connection for the configured backend."""
    db_type = _config["type"]
    if db_type is None or _config["dbName"] is None:
        return None

    if db_type == "sqlite":
        import sqlite3
        return sqlite3.connect(_config["dbName"])

    if db_type == "mssql":
        import pyodbc
        server = _config["server"]
        if _config["port"]:
            server = f"{server},{_config['port']}"
        parts = [
            "Driver={ODBC Driver 18 for SQL Server};",
            f"Server={server};",
            f"Database={_config['dbName']};",
            "Encrypt=yes;",
            "TrustServerCertificate=yes;",
        ]
        if _config["user"]:
            parts.append(f"UID={_config['user']};")
            parts.append(f"PWD={_config['password'] or ''};")
        else:
            parts.append("Trusted_Connection=yes;")
        return pyodbc.connect("".join(parts))

    if db_type == "mysql":
        import pymysql
        return pymysql.connect(
            host=_config["server"],
            port=int(_config["port"] or 3306),
            user=_config["user"],
            password=_config["password"] or "",
            database=_config["dbName"],
        )

    raise ValueError(f"Unsupported database type '{db_type}'")


@contextmanager
def _connection():
    """Yield a connection and always close it afterwards.

    The drivers disagree on what ``with conn:`` does (pyodbc/sqlite3 commit but
    stay open, pymysql closes), so closing is handled explicitly here.
    """
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database is not configured. Call setDatabase(...) first.")
    try:
        yield conn
    finally:
        conn.close()


def _prepare(sql):
    """Translate ``?`` placeholders to the driver's paramstyle."""
    if _config["type"] == "mysql":
        return sql.replace("?", "%s")
    return sql


def _to_record(cursor, row):
    """Turn a raw row into an object with attribute access to its columns."""
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return SimpleNamespace(**dict(zip(columns, row)))


def execute(sql, params=()):
    """Run a statement that returns no rows (INSERT/UPDATE/DELETE) and commit."""
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_prepare(sql), tuple(params))
        conn.commit()
        cursor.close()


def fetch_one(sql, params=()):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_prepare(sql), tuple(params))
        record = _to_record(cursor, cursor.fetchone())
        cursor.close()
        return record


def fetch_all(sql, params=()):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_prepare(sql), tuple(params))
        records = [_to_record(cursor, row) for row in cursor.fetchall()]
        cursor.close()
        return records


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = {
    "sqlite": [
        """
        CREATE TABLE IF NOT EXISTS Users (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT NOT NULL UNIQUE,
            PasswordHash TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS WorkTimeEntries (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT NOT NULL,
            WorkDate TEXT NOT NULL,
            StartTime TEXT NOT NULL,
            EndTime TEXT NOT NULL
        )
        """,
    ],
    "mssql": [
        """
        IF OBJECT_ID('Users', 'U') IS NULL
        CREATE TABLE Users (
            Id INT IDENTITY(1,1) PRIMARY KEY,
            Username NVARCHAR(255) NOT NULL UNIQUE,
            PasswordHash NVARCHAR(255) NULL
        )
        """,
        """
        IF OBJECT_ID('WorkTimeEntries', 'U') IS NULL
        CREATE TABLE WorkTimeEntries (
            Id INT IDENTITY(1,1) PRIMARY KEY,
            Username NVARCHAR(255) NOT NULL,
            WorkDate DATE NOT NULL,
            StartTime TIME NOT NULL,
            EndTime TIME NOT NULL
        )
        """,
    ],
    "mysql": [
        """
        CREATE TABLE IF NOT EXISTS Users (
            Id INT AUTO_INCREMENT PRIMARY KEY,
            Username VARCHAR(255) NOT NULL UNIQUE,
            PasswordHash VARCHAR(255) NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS WorkTimeEntries (
            Id INT AUTO_INCREMENT PRIMARY KEY,
            Username VARCHAR(255) NOT NULL,
            WorkDate DATE NOT NULL,
            StartTime TIME NOT NULL,
            EndTime TIME NOT NULL
        )
        """,
    ],
}


def create_tables():
    """Create the Users and WorkTimeEntries tables if they do not already exist."""
    for statement in _SCHEMA[_config["type"]]:
        execute(statement)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def save_work_time(username, work_date, start_time, end_time):
    sql = """
    INSERT INTO WorkTimeEntries (Username, WorkDate, StartTime, EndTime)
    VALUES (?, ?, ?, ?)
    """
    execute(sql, (username, work_date, start_time, end_time))


def get_user_by_username(username):
    sql = "SELECT Username, PasswordHash FROM Users WHERE Username = ?"
    return fetch_one(sql, (username,))


def create_user(username, password_hash):
    sql = """
    INSERT INTO Users (Username, PasswordHash)
    VALUES (?, ?)
    """
    execute(sql, (username, password_hash))
    return username


def update_user_password(username, password_hash):
    sql = "UPDATE Users SET PasswordHash = ? WHERE Username = ?"
    execute(sql, (password_hash, username))
