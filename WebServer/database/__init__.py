"""Database access layer.

Supports three backends, selected with ``createConnection(type=...)``:

* ``"sqlite"`` - built-in ``sqlite3``; ``dbName`` is the path to the .db file
* ``"mssql"``  - Microsoft SQL Server via ``pyodbc``
* ``"mysql"``  - MySQL / MariaDB via ``pymysql``

All SQL in this package is written with ``?`` placeholders; they are translated
to the driver's native style automatically. Rows returned from queries expose
columns as attributes (``row.Username``) regardless of the backend.

This is a package, split by concern:
  * ``core``        - connection handling, execute/fetch primitives, schema/migrations
  * ``auth``        - Users, Sessions, LoginAttempts, AuditLog queries (used by WebServer.auth)
  * ``tableviewer`` - generic table introspection backing WebServer.addTableViewer

Everything below is re-exported here so existing code can keep doing
``from WebServer.database import get_user_by_username`` etc. without caring
which submodule actually defines it.
"""

from WebServer.database.core import (
    SUPPORTED_TYPES,
    createConnection,
    get_database_type,
    get_connection,
    execute,
    fetch_one,
    fetch_all,
    describe,
    create_tables,
    save_work_time,
)

from WebServer.database.auth import (
    get_user_by_username,
    get_all_users,
    create_user,
    update_user_password,
    set_user_role,
    set_user_disabled,
    delete_user,
    create_session,
    get_session,
    touch_session,
    delete_other_sessions,
    delete_session,
    delete_sessions_for_user,
    delete_expired_sessions,
    get_sessions_for_user,
    get_login_attempt,
    save_login_attempt,
    delete_login_attempt,
    delete_login_attempts_by_user,
    delete_all_login_attempts,
    get_locked_attempts,
    delete_stale_login_attempts,
    insert_audit,
    get_audit_log,
)

from WebServer.database.tableviewer import (
    get_table_names,
    get_table_columns,
    get_table_rows,
    get_table_page,
    get_primary_key_columns,
    update_table_row,
    get_foreign_keys,
    count_rows,
    text_expr,
    select_rows,
    describe_query,
    get_row,
    update_row,
    insert_row,
    lookup_options,
    distinct_values,
    distinct_from,
    quote_name,
)
