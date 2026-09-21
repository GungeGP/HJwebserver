# Database

## Choosing a backend

```python
app.setDatabase(type="sqlite", dbName="workTime.db")
app.setDatabase(type="mssql",  server="localhost", dbName="workTime")
app.setDatabase(type="mssql",  server="localhost", dbName="workTime", user="sa", password="…")
app.setDatabase(type="mysql",  server="localhost", dbName="workTime", user="root", password="…")
```

Full parameter list: [`setDatabase`](webserver.md#appsetdatabasetypemssql-serverlocalhost-dbnametest-usernone-passwordnone-portnone-createtablestrue).

### Drivers

| `type` | Driver | Install | Notes |
|--------|--------|---------|-------|
| `sqlite` | `sqlite3` (Python stdlib) | nothing | `dbName` is a file path. Good for development and single-user tools. |
| `mssql` | `pyodbc` | `pip install pyodbc` + "ODBC Driver 18 for SQL Server" | No `user` → Windows authentication. Encryption on, certificate not verified. |
| `mysql` | `PyMySQL` | `pip install PyMySQL` | Also works with MariaDB. |

Drivers are imported the first time a connection is opened, so you only need the
one you use installed.

### Tables

By default `setDatabase` creates these if they are missing (`createTables=False` skips it):

```
Users            (Id, Username, PasswordHash, Role, Disabled, MustChangePassword)
Sessions         (Jti, Username, CreatedAt, ExpiresAt, LastSeen)
LoginAttempts    (AttemptKey, FailCount, LastAt, LockedUntil, LastUser)
AuditLog         (Id, At, Username, Event, Detail, Ip)
WorkTimeEntries  (Id, Username, WorkDate, StartTime, EndTime)
```

The first four are used by the login system. Tables are created only if
missing; columns added by newer versions (`Role`, `Disabled`, ... ) are added to
existing tables with `ALTER TABLE ... ADD`, so a database from an older version
keeps working. Nothing is ever dropped or renamed.

## Your own queries

Import the helpers from `WebServer.database`. They open a connection, run the
statement, commit/close, and give you rows with attribute access — the same on
all three backends.

```python
from WebServer.database import execute, fetch_one, fetch_all

execute("INSERT INTO Notes (Username, Text) VALUES (?, ?)", (request.user["username"], text))

note = fetch_one("SELECT Id, Text FROM Notes WHERE Id = ?", (note_id,))
if note:
    print(note.Id, note.Text)

for row in fetch_all("SELECT Id, Text FROM Notes WHERE Username = ?", (username,)):
    print(row.Text)
```

| Function | Returns |
|----------|---------|
| `execute(sql, params=())` | nothing; commits |
| `fetch_one(sql, params=())` | one row object or `None` |
| `fetch_all(sql, params=())` | list of row objects (possibly empty) |

Rules:

- **Always use `?` placeholders** and pass values in `params`. The framework
  translates `?` for MySQL. Never build SQL with f-strings — that is how SQL
  injection happens.
- `params` is a tuple. For a single value write `(value,)` — the trailing comma matters.
- Column names on the row object are exactly what the `SELECT` returns
  (`SELECT Text AS body` → `row.body`).
- Write portable SQL where you can. `AUTO_INCREMENT`, `TOP`, `LIMIT`, `GETDATE()`
  etc. differ per backend; check `get_database_type()` if you must branch:

  ```python
  from WebServer.database import get_database_type
  if get_database_type() == "mssql": ...
  ```

### Creating your own tables

Run the DDL once at startup, one statement per backend where the syntax differs:

```python
from WebServer.database import execute, get_database_type

if get_database_type() == "sqlite":
    execute("CREATE TABLE IF NOT EXISTS Notes (Id INTEGER PRIMARY KEY AUTOINCREMENT, Username TEXT, Text TEXT)")
elif get_database_type() == "mysql":
    execute("CREATE TABLE IF NOT EXISTS Notes (Id INT AUTO_INCREMENT PRIMARY KEY, Username VARCHAR(255), Text TEXT)")
else:  # mssql
    execute("IF OBJECT_ID('Notes','U') IS NULL CREATE TABLE Notes (Id INT IDENTITY PRIMARY KEY, Username NVARCHAR(255), Text NVARCHAR(MAX))")
```

### Raw connection

If the helpers aren't enough (transactions spanning several statements, bulk
inserts, driver-specific features):

```python
conn = app.getDatabaseConnection()
try:
    cur = conn.cursor()
    cur.execute(sql, params)     # use %s placeholders yourself on mysql
    conn.commit()
finally:
    conn.close()
```

Note that at this level the placeholder style is the driver's own (`?` for
sqlite/mssql, `%s` for mysql) and rows are plain tuples.

## Built-in queries

Used by the framework itself, but you can call them:

| Function | Purpose |
|----------|---------|
| `get_user_by_username(username)` | row with `Username`, `PasswordHash`, or `None` |
| `create_user(username, password_hash)` | inserts a user. Prefer `app.createUser`, which hashes the password for you |
| `update_user_password(username, password_hash)` | prefer `app.setPassword` |
| `save_work_time(username, work_date, start_time, end_time)` | inserts a `WorkTimeEntries` row |
