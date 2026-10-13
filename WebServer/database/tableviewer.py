"""Generic table introspection - lists tables, columns, and paginated/searched/
sorted rows for *any* table, not just the framework's own ones.

Backs WebServer.addTableViewer() / public/js/TableViewer.js. Nothing here knows
about auth, sessions, or any specific table name - that's the whole point.
"""

from WebServer.database.core import execute, fetch_all, fetch_one, get_database_type

_CAST_TYPE = {"sqlite": "TEXT", "mssql": "NVARCHAR(MAX)", "mysql": "CHAR"}


def get_table_names():
    """All user tables in the configured database, sorted by name."""
    db_type = get_database_type()
    if db_type == "sqlite":
        rows = fetch_all("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r.name for r in rows]
    if db_type == "mssql":
        rows = fetch_all("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
        return [r.TABLE_NAME for r in rows]
    if db_type == "mysql":
        rows = fetch_all("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY TABLE_NAME")
        return [r.TABLE_NAME for r in rows]
    return []


def get_table_columns(table):
    """All columns of `table` as [{"name", "type"}, ...], in column order.

    Raises ValueError if `table` is not a real table. Table names can't be
    passed as query parameters, so they're checked against get_table_names()
    before being interpolated into SQL.
    """
    if table not in get_table_names():
        raise ValueError(f"Unknown table '{table}'")

    db_type = get_database_type()
    if db_type == "sqlite":
        return [{"name": r.name, "type": r.type} for r in fetch_all(f"PRAGMA table_info({table})")]
    if db_type == "mssql":
        rows = fetch_all(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION", (table,))
        return [{"name": r.COLUMN_NAME, "type": r.DATA_TYPE} for r in rows]
    if db_type == "mysql":
        rows = fetch_all(
            "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = ? ORDER BY ORDINAL_POSITION", (table,))
        return [{"name": r.COLUMN_NAME, "type": r.DATA_TYPE} for r in rows]
    return []


def get_table_rows(table, limit=200):
    """Up to `limit` rows of `table`, every column included, as a list of dicts.

    Column order (and therefore dict key order) matches the table's real
    column order, which is what TableViewer defaults its displayed columns to.
    """
    columns = [c["name"] for c in get_table_columns(table)]
    column_list = ", ".join(columns)
    if get_database_type() == "mssql":
        sql = f"SELECT TOP {int(limit)} {column_list} FROM {table}"
    else:
        sql = f"SELECT {column_list} FROM {table} LIMIT {int(limit)}"
    return [vars(row) for row in fetch_all(sql)]


def get_table_page(table, page=1, per_page=40, search=None, sort=None, sort_dir="asc"):
    """One page of `table`, optionally searched and ordered by `sort`.
    Backs TableViewer's pagination/search/sort UI.

    search is either:
      - "value"        - prefix match ("starts with") across every column
      - "column=value" - exact match on just that column, e.g. "id=1" or
                          "starttime=07:30" (column name is case-insensitive;
                          falls back to the plain prefix search above if it
                          isn't a real column of this table)

    Returns (rows, total_row_count, column_names). `sort` falls back to the
    table's first column when it isn't a real column name (also closes off
    SQL injection via the ORDER BY clause, which can't be parameterized).
    """
    db_type = get_database_type()
    column_names = [c["name"] for c in get_table_columns(table)]
    column_list = ", ".join(column_names)

    where_sql = ""
    params = []
    search = (search or "").strip()
    if search:
        cast = _CAST_TYPE.get(db_type, "TEXT")
        field, sep, value = search.partition("=")
        exact_column = {c.lower(): c for c in column_names}.get(field.strip().lower()) if sep else None

        if exact_column:
            where_sql = f"WHERE CAST({exact_column} AS {cast}) = ?"
            params = [value.strip()]
        else:
            conditions = [f"CAST({c} AS {cast}) LIKE ?" for c in column_names]
            where_sql = "WHERE " + " OR ".join(conditions)
            params = [f"{search}%"] * len(column_names)  # prefix match, not "contains"

    sort_col = sort if sort in column_names else column_names[0]
    sort_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

    total = fetch_one(f"SELECT COUNT(*) AS N FROM {table} {where_sql}", params).N

    per_page = max(1, int(per_page))
    offset = max(0, (int(page) - 1) * per_page)
    if db_type == "mssql":
        sql = (f"SELECT {column_list} FROM {table} {where_sql} "
               f"ORDER BY {sort_col} {sort_dir} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY")
    else:
        sql = (f"SELECT {column_list} FROM {table} {where_sql} "
               f"ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?")
    rows = fetch_all(sql, params + [offset, per_page] if db_type == "mssql" else params + [per_page, offset])

    return [vars(row) for row in rows], total, column_names


def get_primary_key_columns(table):
    """Primary key column name(s) of `table`, in key order. Empty list if the
    table has no primary key - TableViewer disables editing in that case,
    since there'd be no safe way to identify which row to update.
    """
    if table not in get_table_names():
        raise ValueError(f"Unknown table '{table}'")

    db_type = get_database_type()
    if db_type == "sqlite":
        rows = fetch_all(f"PRAGMA table_info({table})")
        return [r.name for r in sorted((r for r in rows if r.pk), key=lambda r: r.pk)]
    if db_type == "mssql":
        rows = fetch_all(
            "SELECT ku.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
            "  ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME AND tc.TABLE_NAME = ku.TABLE_NAME "
            "WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' AND tc.TABLE_NAME = ? "
            "ORDER BY ku.ORDINAL_POSITION", (table,))
        return [r.COLUMN_NAME for r in rows]
    if db_type == "mysql":
        rows = fetch_all(
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND CONSTRAINT_NAME = 'PRIMARY' "
            "ORDER BY ORDINAL_POSITION", (table,))
        return [r.COLUMN_NAME for r in rows]
    return []


def update_table_row(table, pk_values, changes):
    """Update one row of `table`, identified by pk_values ({column: value} for
    every primary key column), setting the columns named in changes.

    Raises ValueError if: the table has no primary key, pk_values doesn't
    cover exactly that key, or changes is empty once unknown columns and the
    primary key itself (never editable through this call) are filtered out.
    """
    column_names = {c["name"] for c in get_table_columns(table)}
    pk_cols = get_primary_key_columns(table)
    if not pk_cols:
        raise ValueError(f"Table '{table}' has no primary key; rows can't be edited")
    if set(pk_values) != set(pk_cols):
        raise ValueError(f"Expected primary key column(s): {', '.join(pk_cols)}")

    changes = {k: v for k, v in changes.items() if k in column_names and k not in pk_cols}
    if not changes:
        raise ValueError("No editable columns in the request")

    set_clause = ", ".join(f"{col} = ?" for col in changes)
    where_clause = " AND ".join(f"{col} = ?" for col in pk_cols)
    params = list(changes.values()) + [pk_values[col] for col in pk_cols]
    execute(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)
