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
  * ``auth``        - AuditLog queries (used by WebServer.auth and app.getAuditLog)
  * ``tableviewer`` - generic table introspection backing WebServer.addTableViewer

Everything below is re-exported here so existing code can keep doing
``from WebServer.database import get_audit_log`` etc. without caring
which submodule actually defines it.
"""

from WebServer.database.core import (
    SUPPORTED_TYPES,
    createConnection,
    get_database_type,
    get_connection,
    execute,
    execute_all,
    fetch_one,
    fetch_all,
    describe,
    create_tables,
)

from WebServer.database.auth import (
    insert_audit,
    delete_audit_before,
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
    delete_row,
    update_row_sql,
    insert_row_sql,
    delete_row_sql,
    ledger_sql,
    lookup_options,
    distinct_values,
    distinct_from,
    quote_name,
)
