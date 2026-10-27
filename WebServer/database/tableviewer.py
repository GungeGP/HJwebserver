"""Generic table introspection - lists tables, columns, and paginated/searched/
sorted rows for *any* table, not just the framework's own ones.

Backs WebServer.addTableViewer() / public/js/TableViewer.js. Nothing here knows
about auth, sessions, or any specific table name - that's the whole point.

Table and column names can't be bound as query parameters, so every function
here that puts a name into SQL first checks it against the live schema
(get_table_names / get_table_columns). Callers may pass names that came from
a request; the check is what keeps them from being an injection vector.
"""

import datetime as _dt

from WebServer.database.core import describe, execute, fetch_all, fetch_one, get_database_type

_CAST_TYPE = {"sqlite": "TEXT", "mssql": "NVARCHAR(MAX)", "mysql": "CHAR"}


def quote_name(name):
    """`name` quoted as a table/column identifier for the configured database,
    so names with spaces or symbols ("Privat tilbud", "Mail til/fra B&F")
    work. Quoting isn't validation - names must still be checked first."""
    name = str(name)
    db_type = get_database_type()
    if db_type == "mssql":
        return "[" + name.replace("]", "]]") + "]"
    if db_type == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def get_table_names():
    """All user tables and views in the configured database, sorted by name.

    Views are included so a JOIN saved as a view can be shown like a table.
    """
    db_type = get_database_type()
    if db_type == "sqlite":
        rows = fetch_all("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r.name for r in rows]
    if db_type == "mssql":
        rows = fetch_all("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_NAME")
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
        return [{"name": r.name, "type": r.type} for r in fetch_all(f"PRAGMA table_info({quote_name(table)})")]
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
    column_list = ", ".join(quote_name(c) for c in columns)
    if get_database_type() == "mssql":
        sql = f"SELECT TOP {int(limit)} {column_list} FROM {quote_name(table)}"
    else:
        sql = f"SELECT {column_list} FROM {quote_name(table)} LIMIT {int(limit)}"
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
    column_list = ", ".join(quote_name(c) for c in column_names)
    table_sql = quote_name(table)

    where_sql = ""
    params = []
    search = (search or "").strip()
    if search:
        cast = _CAST_TYPE.get(db_type, "TEXT")
        field, sep, value = search.partition("=")
        exact_column = {c.lower(): c for c in column_names}.get(field.strip().lower()) if sep else None

        if exact_column:
            where_sql = f"WHERE CAST({quote_name(exact_column)} AS {cast}) = ?"
            params = [value.strip()]
        else:
            conditions = [f"CAST({quote_name(c)} AS {cast}) LIKE ?" for c in column_names]
            where_sql = "WHERE " + " OR ".join(conditions)
            params = [f"{search}%"] * len(column_names)  # prefix match, not "contains"

    sort_col = quote_name(sort if sort in column_names else column_names[0])
    sort_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"

    total = fetch_one(f"SELECT COUNT(*) AS N FROM {table_sql} {where_sql}", params).N

    per_page = max(1, int(per_page))
    offset = max(0, (int(page) - 1) * per_page)
    if db_type == "mssql":
        sql = (f"SELECT {column_list} FROM {table_sql} {where_sql} "
               f"ORDER BY {sort_col} {sort_dir} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY")
    else:
        sql = (f"SELECT {column_list} FROM {table_sql} {where_sql} "
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
        rows = fetch_all(f"PRAGMA table_info({quote_name(table)})")
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

    set_clause = ", ".join(f"{quote_name(col)} = ?" for col in changes)
    where_clause = " AND ".join(f"{quote_name(col)} = ?" for col in pk_cols)
    params = list(changes.values()) + [pk_values[col] for col in pk_cols]
    execute(f"UPDATE {quote_name(table)} SET {set_clause} WHERE {where_clause}", params)


# ---------------------------------------------------------------------------
# Building blocks for multi-table viewers (related tables, lookups, filters)
# ---------------------------------------------------------------------------

def _require_columns(table, columns):
    """Raise ValueError unless `table` exists and has every name in `columns`."""
    known = {c["name"] for c in get_table_columns(table)}
    unknown = [c for c in columns if c not in known]
    if unknown:
        raise ValueError(f"Unknown column(s) on '{table}': {', '.join(unknown)}")


def get_foreign_keys(table):
    """{column: (referenced_table, referenced_column)} for every single-column
    foreign key declared on `table`. Empty for views or tables without any."""
    if table not in get_table_names():
        raise ValueError(f"Unknown table '{table}'")

    db_type = get_database_type()
    found = {}
    if db_type == "sqlite":
        rows = [vars(r) for r in fetch_all(f"PRAGMA foreign_key_list({quote_name(table)})")]
        per_constraint = {}
        for r in rows:
            per_constraint.setdefault(r["id"], []).append(r)
        for parts in per_constraint.values():
            if len(parts) != 1:
                continue  # composite key - not a simple id lookup
            r = parts[0]
            ref_col = r["to"]
            if not ref_col:
                pk = get_primary_key_columns(r["table"])
                ref_col = pk[0] if len(pk) == 1 else None
            if ref_col:
                found[r["from"]] = (r["table"], ref_col)
        return found

    if db_type == "mssql":
        rows = fetch_all(
            "SELECT cu.COLUMN_NAME AS col, pk.TABLE_NAME AS ref_table, pku.COLUMN_NAME AS ref_col "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu ON cu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pku ON pku.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
            "  AND pku.ORDINAL_POSITION = cu.ORDINAL_POSITION "
            "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk ON pk.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
            "WHERE cu.TABLE_NAME = ?", (table,))
    elif db_type == "mysql":
        rows = fetch_all(
            "SELECT COLUMN_NAME AS col, REFERENCED_TABLE_NAME AS ref_table, REFERENCED_COLUMN_NAME AS ref_col "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND REFERENCED_TABLE_NAME IS NOT NULL", (table,))
    else:
        return found

    counts = {}
    for r in rows:
        counts[r.col] = counts.get(r.col, 0) + 1
    for r in rows:
        if counts[r.col] == 1:
            found[r.col] = (r.ref_table, r.ref_col)
    return found


def count_rows(table):
    if table not in get_table_names():
        raise ValueError(f"Unknown table '{table}'")
    return fetch_one(f"SELECT COUNT(*) AS N FROM {quote_name(table)}").N


def text_expr(expr):
    """SQL that turns `expr` into text, so LIKE works on any column type."""
    return f"CAST({expr} AS {_CAST_TYPE.get(get_database_type(), 'TEXT')})"


def _limit_sql(select_sql, rest_sql, limit):
    """`SELECT <select_sql> <rest_sql>` capped at `limit` rows, per dialect."""
    if limit is None:
        return f"SELECT {select_sql} {rest_sql}"
    if get_database_type() == "mssql":
        # T-SQL wants "SELECT DISTINCT TOP n", not "SELECT TOP n DISTINCT".
        if select_sql.upper().startswith("DISTINCT "):
            return f"SELECT DISTINCT TOP {int(limit)} {select_sql[9:]} {rest_sql}"
        return f"SELECT TOP {int(limit)} {select_sql} {rest_sql}"
    return f"SELECT {select_sql} {rest_sql} LIMIT {int(limit)}"


def select_rows(select_sql, from_sql, from_params=(), where_sql="", where_params=(),
                order_sql="1", page=1, per_page=40):
    """One page of an arbitrary SELECT, plus the total row count.

    Every name inside select_sql/from_sql/where_sql/order_sql must already be
    validated by the caller - this only adds the paging syntax and runs it.
    Values go through ``?`` placeholders: from_params belong to ON clauses in
    from_sql, where_params to where_sql, in that order.
    """
    params = list(from_params) + list(where_params)
    total = fetch_one(f"SELECT COUNT(*) AS N FROM {from_sql} {where_sql}", params).N

    per_page = max(1, int(per_page))
    offset = max(0, (int(page) - 1) * per_page)
    if get_database_type() == "mssql":
        sql = (f"SELECT {select_sql} FROM {from_sql} {where_sql} "
               f"ORDER BY {order_sql} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY")
        rows = fetch_all(sql, params + [offset, per_page])
    else:
        sql = f"SELECT {select_sql} FROM {from_sql} {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?"
        rows = fetch_all(sql, params + [per_page, offset])
    return [vars(r) for r in rows], total


def describe_query(sql):
    """Column names returned by a consumer-written SELECT (for query= viewers)."""
    return [name for name in describe(f"SELECT * FROM ({sql}) q WHERE 1 = 0") if name]


def get_row(table, key_values):
    """The row of `table` whose key columns equal key_values, as a dict, or None."""
    _require_columns(table, list(key_values))
    where = " AND ".join(f"{quote_name(col)} = ?" for col in key_values)
    row = fetch_one(f"SELECT * FROM {quote_name(table)} WHERE {where}", list(key_values.values()))
    return vars(row) if row else None


# The *_sql builders return (sql, params) without running anything, so a
# change and its Ledger entry can go through execute_all() as one transaction.

def update_row_sql(table, key_values, changes):
    """UPDATE of one row of `table`, identified by key_values ({column: value})."""
    if not key_values:
        raise ValueError(f"No key given for '{table}'; can't tell which row to update")
    if not changes:
        raise ValueError("No editable columns in the request")
    _require_columns(table, list(key_values) + list(changes))
    set_clause = ", ".join(f"{quote_name(col)} = ?" for col in changes)
    where_clause = " AND ".join(f"{quote_name(col)} = ?" for col in key_values)
    return (f"UPDATE {quote_name(table)} SET {set_clause} WHERE {where_clause}",
            list(changes.values()) + list(key_values.values()))


def insert_row_sql(table, values):
    """INSERT of one row into `table`."""
    if not values:
        raise ValueError("Nothing to insert")
    _require_columns(table, list(values))
    columns = ", ".join(quote_name(c) for c in values)
    placeholders = ", ".join("?" for _ in values)
    return f"INSERT INTO {quote_name(table)} ({columns}) VALUES ({placeholders})", list(values.values())


def delete_row_sql(table, key_values):
    """DELETE of the one row of `table` identified by key_values ({column: value})."""
    if not key_values:
        raise ValueError(f"No key given for '{table}'; can't tell which row to delete")
    _require_columns(table, list(key_values))
    where = " AND ".join(f"{quote_name(col)} = ?" for col in key_values)
    return f"DELETE FROM {quote_name(table)} WHERE {where}", list(key_values.values())


def ledger_sql(username, change_type, table, row_key=None, old_values=None, new_values=None, reason=None):
    """INSERT of one Ledger entry. change_type is "edited", "created" or
    "deleted"; row_key, old_values and new_values are JSON text."""
    at = _dt.datetime.now().replace(microsecond=0)
    if get_database_type() == "sqlite":
        at = at.isoformat(sep=" ")   # sqlite has no datetime type
    return ("INSERT INTO Ledger (At, Username, ChangeType, TableName, RowKey, OldValues, NewValues, Reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [at, username, change_type, table, row_key, old_values, new_values, reason])


def update_row(table, key_values, changes):
    """UPDATE one row of `table`, identified by key_values ({column: value})."""
    execute(*update_row_sql(table, key_values, changes))


def insert_row(table, values):
    """INSERT one row into `table`."""
    execute(*insert_row_sql(table, values))


def delete_row(table, key_values):
    """DELETE the one row of `table` identified by key_values ({column: value})."""
    execute(*delete_row_sql(table, key_values))


def lookup_options(table, id_column, label_column, search=None, limit=None):
    """[(id, label), ...] from a lookup table, sorted by label.

    search matches the start of the label or the start of any word in it,
    so "han" finds both "Hanne Olesen" and "Jens Hansen".
    """
    _require_columns(table, [id_column, label_column])
    id_sql, label_sql = quote_name(id_column), quote_name(label_column)
    where_sql, params = "", []
    if search:
        label = text_expr(label_sql)
        where_sql = f"WHERE {label} LIKE ? OR {label} LIKE ?"
        params = [f"{search}%", f"% {search}%"]
    sql = _limit_sql(f"{id_sql} AS v, {label_sql} AS l",
                     f"FROM {quote_name(table)} {where_sql} ORDER BY {label_sql}", limit)
    return [(r.v, r.l) for r in fetch_all(sql, params)]


def distinct_values(table, column, limit=200):
    """Distinct non-empty values of one column, sorted - options for a filter
    on a column that isn't a lookup."""
    _require_columns(table, [column])
    column = quote_name(column)
    sql = _limit_sql(f"DISTINCT {column} AS v",
                     f"FROM {quote_name(table)} WHERE {column} IS NOT NULL ORDER BY v", limit)
    return [r.v for r in fetch_all(sql)]


def distinct_from(from_sql, expr, limit=200):
    """distinct_values over an already-validated FROM clause, for query= viewers
    where there's no single table to name."""
    sql = _limit_sql(f"DISTINCT {expr} AS v",
                     f"FROM {from_sql} WHERE {expr} IS NOT NULL ORDER BY v", limit)
    return [r.v for r in fetch_all(sql)]
