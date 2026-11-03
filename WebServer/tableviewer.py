"""TableViewer's engine. Turns the arguments of app.addTableViewer(...) into a
validated spec, and answers the three requests TableViewer.js makes: a page of
rows, the options for a lookup field, and saving an edit.

Same layering as auth: core/tableviewer.py is the public method and routes,
this file decides what to ask the database, database/tableviewer.py holds the
SQL. Every table and column name a consumer passes in is resolved against the
live schema here before it is put into SQL, and the resolved spec is reused
for SPEC_TTL seconds instead of re-reading the schema on every request.

Helpers for main.py live here too: dateFilter(), selectFilter(), duration().
"""

import datetime as _dt
import json
import re
import time
from decimal import Decimal

from WebServer.database import (
    count_rows, delete_row_sql, describe_query, distinct_from, distinct_values, execute_all,
    get_database_type, get_foreign_keys, get_primary_key_columns, get_row, get_table_columns,
    get_table_names, insert_row_sql, ledger_sql, lookup_options, quote_name, select_rows, text_expr,
    update_row_sql,
)

SELECT_MAX = 20       # lookups up to this many rows edit as a plain dropdown
LOCAL_MAX = 200       # ...up to this many as a searchable field with all options sent along
OPTIONS_LIMIT = 20    # bigger lookups: matches returned per keystroke from /options
FILTER_OPTIONS_MAX = 500
REASON_MAX = 500      # longest delete reason; it goes into AuditLog.Detail (1024 chars)
SPEC_TTL = 60         # seconds a resolved spec is trusted before the schema is read again

KINDS = ("text", "number", "bool", "date", "time", "datetime")


# ---------------------------------------------------------------------------
# Helpers consumers use in main.py
# ---------------------------------------------------------------------------

def dateFilter(column, default="today", arrows=True):
    """A date picker that limits rows to one day.

    column:  "Column" or "Table.Column". Works on date and datetime columns.
    default: "today", a "YYYY-MM-DD" string, or None for "no filter until a
             date is picked".
    arrows:  show previous/next-day buttons beside the picker.
    """
    return {"kind": "date", "column": column, "default": default, "arrows": bool(arrows)}


def selectFilter(column, allLabel="All"):
    """A dropdown that limits rows to one value of a column. The options come
    from the lookup table when the column is a lookup, otherwise from the
    column's own distinct values. allLabel is the "no filter" option."""
    return {"kind": "select", "column": column, "allLabel": allLabel}


def duration(start, end):
    """Time between two times or datetimes as "H:MM", or None if either is
    missing or end is before start. Accepts objects or ISO strings - whatever
    the database returned - so it works the same on every backend."""
    a, b = _as_datetime(start), _as_datetime(end)
    if a is None or b is None or b < a:
        return None
    minutes = int((b - a).total_seconds() // 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


def _as_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, _dt.date):
        return _dt.datetime.combine(value, _dt.time())
    if isinstance(value, _dt.time):
        return _dt.datetime.combine(_dt.date(2000, 1, 1), value)
    text = str(value).strip()
    for parse in (_dt.datetime.fromisoformat, _dt.time.fromisoformat):
        try:
            return _as_datetime(parse(text))
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Column types: what the database says -> which editor TableViewer.js shows
# ---------------------------------------------------------------------------

_NUMBER_TYPES = {"int", "integer", "bigint", "smallint", "tinyint", "mediumint", "decimal",
                 "numeric", "float", "real", "double", "money", "smallmoney"}


def kind_of(sql_type):
    """Map a column's declared type to one of KINDS."""
    t = (sql_type or "").lower()
    base = t.split("(")[0].strip()
    if "datetime" in t or "timestamp" in t:
        return "datetime"
    if base == "date":
        return "date"
    if base == "time":
        return "time"
    if base in ("bit", "bool", "boolean"):
        return "bool"
    if base in _NUMBER_TYPES or base.startswith("double"):
        return "number"
    if get_database_type() == "sqlite" and "int" in t:
        return "number"  # sqlite affinity: any declared type containing INT is an integer
    return "text"


def to_json(value):
    """A database value as something json.dumps and the browser understand.
    Dates and times go out as ISO strings, which the pickers accept."""
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def _ledger_json(values):
    """{column: value} as JSON text for the tableviewLedger, e.g. {"Navn": "Mette Holm"}."""
    if values is None:
        return None
    return json.dumps({k: to_json(v) for k, v in values.items()}, ensure_ascii=False, default=str)


def parse_value(value, kind):
    """A value from the browser, converted for the database. sqlite stores
    dates as text, so it gets strings; mssql/mysql get real date objects."""
    if kind == "text":
        return value
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    sqlite = get_database_type() == "sqlite"
    text = str(value).strip()
    try:
        if kind == "number":
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return value
            return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
        if kind == "bool":
            if isinstance(value, bool):
                return 1 if value else 0
            return 1 if text.lower() in ("1", "true", "yes", "on") else 0
        if kind == "date":
            parsed = _dt.date.fromisoformat(text[:10])
            return parsed.isoformat() if sqlite else parsed
        if kind == "time":
            parsed = _dt.time.fromisoformat(text)
            if sqlite:
                return parsed.strftime("%H:%M" if parsed.second == 0 else "%H:%M:%S")
            return parsed
        if kind == "datetime":
            parsed = _dt.datetime.fromisoformat(text)
            return parsed.strftime("%Y-%m-%d %H:%M:%S") if sqlite else parsed
    except ValueError:
        raise ValueError(f"'{value}' isn't a valid {kind}") from None
    return value


# ---------------------------------------------------------------------------
# The viewer
# ---------------------------------------------------------------------------

class TableViewer:
    """One addTableViewer(...) call. Holds the consumer's configuration and
    builds the schema-checked spec from it on first use."""

    def __init__(self, table=None, columns=None, editable=None, lookups=None, related=None,
                 computed=None, filters=None, types=None, validate=None, primaryKey=None,
                 query=None):
        if not table and not query:
            raise ValueError("addTableViewer needs either table= or query=")
        if query and (related or lookups):
            raise ValueError("query= viewers are read-only and can't use related= or lookups=")
        for kind in (types or {}).values():
            if kind not in KINDS:
                raise ValueError(f"Unknown type '{kind}' in types=; use one of {', '.join(KINDS)}")
        self.config = {
            "table": table, "columns": columns, "editable": editable, "lookups": lookups or {},
            "related": related, "computed": computed or {}, "filters": filters or {},
            "types": types or {}, "primaryKey": primaryKey, "query": query,
        }
        self.validate = validate
        self._spec = None
        self._spec_at = 0.0

    # --- spec ---------------------------------------------------------------

    def spec(self):
        if self._spec is None or time.monotonic() - self._spec_at > SPEC_TTL:
            self._spec = self._resolve()
            self._spec_at = time.monotonic()
        return self._spec

    def _resolve(self):
        cfg = self.config
        tables = {name.lower(): name for name in get_table_names()}

        def real_table(name, what):
            found = tables.get(str(name).lower())
            if not found:
                raise ValueError(f"Unknown {what} table '{name}'")
            return found

        if cfg["query"]:
            names = describe_query(cfg["query"])
            if not names:
                raise ValueError("query= returned no named columns")
            base = self._source(None, "q", names, {n: "text" for n in names}, [], {})
            from_head = f"({cfg['query']}) q"
        else:
            table = real_table(cfg["table"], "base")
            base = self._table_source(table, "b", cfg["primaryKey"])
            from_head = f"{quote_name(table)} b"

        related = None
        join_on = []
        if cfg["related"]:
            rel_cfg = cfg["related"]
            related = self._table_source(real_table(rel_cfg.get("table"), "related"), "r", None)
            match = rel_cfg.get("match") or {}
            if not match:
                raise ValueError("related= needs match={relatedColumn: baseColumn}")
            related["match"] = {}
            for rel_col, base_col in match.items():
                rc, bc = self._col(related, rel_col), self._col(base, base_col)
                related["match"][rc] = bc
                join_on.append(f"r.{quote_name(rc)} = b.{quote_name(bc)}")
            related["keepUnmatched"] = rel_cfg.get("keepUnmatched", True)

        # Columns, in display order: base, related, computed.
        columns = []
        for label, name in self._pairs(cfg["columns"], base["names"]):
            columns.append(self._column(label, base, self._col(base, name), "base"))
        if related:
            default = [n for n in related["names"]
                       if n not in related["key"] and n not in related["match"]]
            for label, name in self._pairs(cfg["related"].get("columns"), default):
                columns.append(self._column(label, related, self._col(related, name), "related"))

        # Lookups: explicit ones, plus foreign keys to plain id | string tables.
        lookups = []
        explicit = {"base": cfg["lookups"], "related": (cfg["related"] or {}).get("lookups") or {}}
        for c in columns:
            source = base if c["owner"] == "base" else related
            lk = self._lookup_for(source, c["column"], explicit[c["owner"]], real_table, len(lookups))
            if lk:
                lookups.append(lk)
                c["lookup"] = lk
                c["kind"] = lk["id_kind"]
        # A lookup on a column that isn't shown is fine (a selectFilter can
        # use it), but the column itself has to exist.
        for owner, mapping in explicit.items():
            source = base if owner == "base" else related
            for name in mapping:
                if source is None:
                    raise ValueError(f"lookups= names '{name}', but there's no {owner} table")
                self._col(source, name)

        for label, fn in cfg["computed"].items():
            if not callable(fn):
                raise ValueError(f"computed['{label}'] must be a function of the row")
            columns.append({"key": label, "owner": "computed", "column": None, "fn": fn,
                            "kind": "text", "lookup": None, "editable": False})

        # Types override, by label or real column name.
        for name, kind in cfg["types"].items():
            hits = [c for c in columns if c["owner"] != "computed" and not c["lookup"]
                    and name.lower() in (c["key"].lower(), c["column"].lower())]
            if not hits:
                raise ValueError(f"types= names '{name}', which isn't a shown column")
            for c in hits:
                c["kind"] = kind

        seen = set()
        for c in columns:
            if c["key"] == "__meta" or c["key"].lower() in seen:
                raise ValueError(f"Two columns are labeled '{c['key']}'; rename one with columns={{...}}")
            seen.add(c["key"].lower())

        self._mark_editable(columns, base, related)
        spec_filters = self._filters(base, related, explicit, real_table)

        select = [f"{s['alias']}.{quote_name(n)} AS {s['sel'][n]}" for s in (base, related) if s for n in s["names"]]
        select += [f"{lk['alias']}.{quote_name(lk['label'])} AS {lk['sel']}" for lk in lookups]

        from_sql = from_head
        if related:
            join = "LEFT JOIN" if related["keepUnmatched"] else "JOIN"
            from_sql += f" {join} {quote_name(related['table'])} r ON {{related_on}}"
        for lk in lookups:
            from_sql += (f" LEFT JOIN {quote_name(lk['table'])} {lk['alias']} "
                         f"ON {lk['alias']}.{quote_name(lk['id'])} = {lk['owner_alias']}.{quote_name(lk['column'])}")

        return {"base": base, "related": related, "columns": columns, "lookups": lookups,
                "filters": spec_filters, "select": ", ".join(select), "from": from_sql,
                "join_on": join_on, "query": bool(cfg["query"])}

    def _table_source(self, table, alias, key_override):
        cols = get_table_columns(table)
        names = [c["name"] for c in cols]
        kinds = {c["name"]: kind_of(c["type"]) for c in cols}
        source = self._source(table, alias, names, kinds, [], get_foreign_keys(table))
        if key_override:
            source["key"] = [self._col(source, k) for k in key_override]
        else:
            source["key"] = get_primary_key_columns(table)
        return source

    @staticmethod
    def _source(table, alias, names, kinds, key, fks):
        return {"table": table, "alias": alias, "names": names, "kinds": kinds, "key": key,
                "fks": fks, "lower": {n.lower(): n for n in names},
                "sel": {n: f"{alias}{i}" for i, n in enumerate(names)}}

    @staticmethod
    def _col(source, name):
        name = str(name)
        if "." in name:
            table_part, name = name.split(".", 1)
            if source["table"] and table_part.lower() != source["table"].lower():
                raise ValueError(f"'{table_part}.{name}' isn't a column of '{source['table']}'")
        found = source["lower"].get(name.lower())
        if not found:
            raise ValueError(f"Unknown column '{name}' on '{source['table'] or 'query'}'")
        return found

    @staticmethod
    def _pairs(spec, default_names):
        """columns= as (label, column) pairs: None -> defaults, list -> same
        label as column, dict -> {label: column}."""
        if spec is None:
            return [(n, n) for n in default_names]
        if isinstance(spec, dict):
            return list(spec.items())
        return [(n, n) for n in spec]

    @staticmethod
    def _column(label, source, name, owner):
        return {"key": str(label), "owner": owner, "column": name,
                "expr": f"{source['alias']}.{quote_name(name)}", "alias": source["sel"][name],
                "kind": source["kinds"][name], "lookup": None, "editable": False}

    def _lookup_for(self, source, column, explicit, real_table, index):
        """The lookup for one column, or None. Explicit lookups win; otherwise
        a foreign key to a two-column (id | string) table becomes one."""
        id_col = label_col = None
        match = next((v for k, v in explicit.items() if self._col(source, k) == column), None)
        if match is not None:
            if isinstance(match, (tuple, list)):
                ltable, label_col = real_table(match[0], "lookup"), match[1]
            else:
                ltable = real_table(match, "lookup")
            if column in source["fks"] and source["fks"][column][0].lower() == ltable.lower():
                id_col = source["fks"][column][1]
        elif column in source["fks"]:
            ltable = real_table(source["fks"][column][0], "lookup")
            if len(get_table_columns(ltable)) != 2:
                return None  # wider table: label is ambiguous, so don't guess
            id_col = source["fks"][column][1]
        else:
            return None

        lcols = get_table_columns(ltable)
        lnames = [c["name"] for c in lcols]
        lsource = self._source(ltable, "x", lnames, {c["name"]: kind_of(c["type"]) for c in lcols}, [], {})
        if id_col is None:
            key = get_primary_key_columns(ltable)
            id_col = key[0] if len(key) == 1 else lnames[0]
        id_col = self._col(lsource, id_col)
        if label_col is None:
            others = [n for n in lnames if n != id_col]
            if len(others) != 1:
                raise ValueError(f"Lookup table '{ltable}' has several columns; name the label: "
                                 f"lookups={{'{column}': ('{ltable}', 'ColumnName')}}")
            label_col = others[0]
        label_col = self._col(lsource, label_col)

        count = count_rows(ltable)
        mode = "select" if count <= SELECT_MAX else "local" if count <= LOCAL_MAX else "remote"
        return {"table": ltable, "id": id_col, "label": label_col, "alias": f"lk{index}",
                "sel": f"l{index}", "owner_alias": source["alias"], "column": column,
                "mode": mode, "id_kind": lsource["kinds"][id_col]}

    def _mark_editable(self, columns, base, related):
        """Which shown columns may be edited. Defaults to every shown base and
        related column that isn't a key or a join column; computed columns,
        query= viewers and tables without a key are never editable."""
        cfg = self.config
        if cfg["query"]:
            return

        def names_of(owner):
            return {c["key"].lower() for c in columns if c["owner"] == owner} | \
                   {c["column"].lower() for c in columns if c["owner"] == owner}

        top = [str(n).lower() for n in cfg["editable"]] if cfg["editable"] is not None else None
        rel_listed = (cfg["related"] or {}).get("editable")
        rel = [str(n).lower() for n in rel_listed] if rel_listed is not None else None

        for name in (top or []) + (rel or []):
            if name not in names_of("base") | names_of("related"):
                raise ValueError(f"editable= names '{name}', which isn't a shown column")

        for c in columns:
            if c["owner"] == "computed":
                continue
            source = base if c["owner"] == "base" else related
            if c["owner"] == "base":
                wanted = top
            else:
                wanted = rel if rel is not None else top
            listed = wanted is not None and (c["key"].lower() in wanted or c["column"].lower() in wanted)
            protected = c["column"] in source["key"] or c["column"] in source.get("match", {})
            if listed and protected:
                raise ValueError(f"'{c['key']}' is a key or join column and can't be editable")
            c["editable"] = bool(source["key"]) and not protected and (listed if wanted is not None else True)

    def _filters(self, base, related, explicit, real_table):
        result = []
        for i, (label, f) in enumerate(self.config["filters"].items()):
            if not isinstance(f, dict) or f.get("kind") not in ("date", "select"):
                raise ValueError(f"filters['{label}'] must be dateFilter(...) or selectFilter(...)")
            ref = str(f["column"])
            owner, source = "base", base
            if related and "." in ref and ref.split(".", 1)[0].lower() == related["table"].lower():
                owner, source = "related", related
            elif related and "." not in ref and ref.lower() not in base["lower"]:
                owner, source = "related", related
            column = self._col(source, ref)
            entry = {"key": f"f{i}", "label": label, "kind": f["kind"], "owner": owner,
                     "column": column, "expr": f"{source['alias']}.{quote_name(column)}",
                     "col_kind": self.config["types"].get(column) or source["kinds"][column],
                     "source": source, "lookup": None}
            if f["kind"] == "date":
                if entry["col_kind"] not in ("date", "datetime", "text"):
                    raise ValueError(f"dateFilter on '{column}', which isn't a date column")
                entry.update(default=f.get("default"), arrows=f.get("arrows", True))
            else:
                entry["allLabel"] = f.get("allLabel", "All")
                if source["table"]:
                    entry["lookup"] = self._lookup_for(source, column, explicit[owner], real_table, 0)
                    if entry["lookup"]:
                        entry["col_kind"] = entry["lookup"]["id_kind"]
            result.append(entry)
        return result

    # --- GET: one page ------------------------------------------------------

    def page(self, params, can_edit, page=1, per_page=40, search="", sort=None, sort_dir="asc"):
        spec = self.spec()
        where, where_params, on, on_params, filter_state = [], [], list(spec["join_on"]), [], []

        for f in spec["filters"]:
            value = self._filter_value(f, params.get(f["key"]))
            state = {"key": f["key"], "label": f["label"], "kind": f["kind"], "value": value}
            if f["kind"] == "date":
                state["arrows"] = f["arrows"]
                if value:
                    day = _dt.date.fromisoformat(value)
                    clause = f"{f['expr']} >= ? AND {f['expr']} < ?"
                    args = [day.isoformat(), (day + _dt.timedelta(days=1)).isoformat()]
                else:
                    clause = None
            else:
                state["allLabel"] = f["allLabel"]
                state["options"] = self._filter_options(f, spec)
                clause = f"{f['expr']} = ?" if value != "" else None
                args = [parse_value(value, f["col_kind"])] if clause else []
            if clause:
                (on if f["owner"] == "related" else where).append(clause)
                (on_params if f["owner"] == "related" else where_params).extend(args)
            filter_state.append(state)

        shown = [c for c in spec["columns"] if c["owner"] != "computed"]
        search = (search or "").strip()
        if search:
            field, sep, value = search.partition("=")
            exact = None
            if sep:
                exact = next((c for c in shown
                              if field.strip().lower() in (c["key"].lower(), c["column"].lower())), None)
            if exact:
                where.append(f"{text_expr(self._shown_expr(exact))} = ?")
                where_params.append(value.strip())
            else:
                like = [f"{text_expr(self._shown_expr(c))} LIKE ?" for c in shown]
                where.append("(" + " OR ".join(like) + ")")
                where_params.extend([f"{search}%"] * len(like))

        sort_col = next((c for c in shown if sort and c["key"] == sort), None)
        direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
        base_key = spec["base"]["key"]
        if sort_col:
            primary = self._shown_expr(sort_col)
        elif base_key:
            primary, direction = f"b.{quote_name(base_key[0])}", "ASC"
        else:
            primary, direction = shown[0]["expr"], "ASC"
        # Keys as tie-breakers keep paging stable. Never repeat the sort
        # column itself - SQL Server rejects a column listed twice in ORDER BY.
        tie = [f"b.{quote_name(k)}" for k in base_key]
        if spec["related"]:
            tie += [f"r.{quote_name(k)}" for k in spec["related"]["key"]]
        order = [f"{primary} {direction}"] + [f"{t} ASC" for t in tie if t != primary]

        from_sql = spec["from"].replace("{related_on}", " AND ".join(on)) if spec["related"] else spec["from"]
        rows, total = select_rows(spec["select"], from_sql, on_params,
                                  ("WHERE " + " AND ".join(where)) if where else "", where_params,
                                  ", ".join(order), page, per_page)

        editable_now = can_edit and any(c["editable"] for c in spec["columns"])
        return {
            "rows": [self._row_out(d, spec) for d in rows],
            "columns": [c["key"] for c in spec["columns"]],
            "columnsMeta": [self._column_meta(c, editable_now) for c in spec["columns"]],
            "filters": filter_state,
            "page": page,
            "limit": per_page,
            "total": total,
            "totalPages": max(1, -(-total // per_page)),
            "sort": sort_col["key"] if sort_col else None,
            "sortDir": direction.lower(),
            "search": search,
            "primaryKey": base_key,
            "canEdit": editable_now,
        }

    @staticmethod
    def _shown_expr(c):
        """What a column shows - the lookup's label, not the stored id - which
        is also what search and sort should work on."""
        return f"{c['lookup']['alias']}.{quote_name(c['lookup']['label'])}" if c["lookup"] else c["expr"]

    @staticmethod
    def _filter_value(f, raw):
        if f["kind"] == "date":
            if raw is None:
                default = f["default"]
                return _dt.date.today().isoformat() if default == "today" else (default or "")
            raw = raw.strip()
            if raw:
                try:
                    _dt.date.fromisoformat(raw)
                except ValueError:
                    raise ValueError(f"'{raw}' isn't a date") from None
            return raw
        return (raw or "").strip()

    @staticmethod
    def _filter_options(f, spec):
        lk = f["lookup"]
        if lk:
            values = lookup_options(lk["table"], lk["id"], lk["label"], limit=FILTER_OPTIONS_MAX)
            return [{"value": to_json(v), "label": l} for v, l in values]
        if f["source"]["table"]:
            values = distinct_values(f["source"]["table"], f["column"], FILTER_OPTIONS_MAX)
        else:
            values = distinct_from(spec["from"], f["expr"], FILTER_OPTIONS_MAX)
        if f["col_kind"] == "bool":   # same words as the table cells (TableViewer.js)
            return [{"value": to_json(v), "label": "Yes" if v else "No"} for v in values]
        return [{"value": to_json(v), "label": str(to_json(v))} for v in values]

    def _row_out(self, d, spec):
        base, related = spec["base"], spec["related"]
        out, labels = {}, {}
        named = {n: d[base["sel"][n]] for n in base["names"]}
        if related:
            for n in related["names"]:
                named.setdefault(n, d[related["sel"][n]])
        for c in spec["columns"]:
            if c["owner"] == "computed":
                continue
            value = d[c["alias"]]
            out[c["key"]] = to_json(value)
            named[c["key"]] = value
            if c["lookup"]:
                labels[c["key"]] = to_json(d[c["lookup"]["sel"]])
        for c in spec["columns"]:
            if c["owner"] == "computed":
                try:
                    out[c["key"]] = to_json(c["fn"](named))
                except Exception as e:
                    print(f"[ tableviewer ] computed column '{c['key']}' failed: {e!r}")
                    out[c["key"]] = None

        keys = {"base": {k: to_json(d[base["sel"][k]]) for k in base["key"]} or None, "related": None}
        if related and related["key"]:
            rel_key = {k: to_json(d[related["sel"][k]]) for k in related["key"]}
            keys["related"] = rel_key if all(v is not None for v in rel_key.values()) else None
        out["__meta"] = {"labels": labels, "keys": keys}
        return out

    @staticmethod
    def _column_meta(c, editable_now):
        meta = {"key": c["key"], "kind": c["kind"], "sortable": c["owner"] != "computed",
                "editable": bool(editable_now and c["editable"]), "lookup": None}
        lk = c["lookup"]
        if lk:
            meta["lookup"] = {"mode": lk["mode"]}
            if meta["editable"] and lk["mode"] != "remote":
                limit = SELECT_MAX if lk["mode"] == "select" else LOCAL_MAX
                values = lookup_options(lk["table"], lk["id"], lk["label"], limit=limit)
                meta["lookup"]["options"] = [{"value": to_json(v), "label": l} for v, l in values]
        return meta

    # --- GET /options: matches for a big lookup -----------------------------

    def options(self, key, search):
        c = next((c for c in self.spec()["columns"] if c["key"] == key and c["lookup"]), None)
        if not c:
            raise ValueError(f"'{key}' isn't a lookup column")
        lk = c["lookup"]
        values = lookup_options(lk["table"], lk["id"], lk["label"], (search or "").strip() or None,
                                OPTIONS_LIMIT)
        return [{"value": to_json(v), "label": l} for v, l in values]

    # --- PUT: save one row --------------------------------------------------

    def save(self, body, username=None):
        """Apply one row's edits. Returns "edited" or "created" on success,
        raises ValueError with a message for the user otherwise.

        An edit goes to whichever table owns each column. If the row has no
        related row yet (a "-" row), the related values are inserted instead,
        with the join column taken from the base row and any related-table
        filter (like the selected day) filled in from the current filters.

        Every change is written to the tableviewLedger (old and new values, by
        `username`) in the same transaction as the change itself.
        """
        spec = self.spec()
        base, related = spec["base"], spec["related"]
        values = body.get("values")
        if not isinstance(values, dict):
            raise ValueError("Body must include \"values\": {...}")
        keys = body.get("keys") if isinstance(body.get("keys"), dict) else {"base": body.get("pk")}
        filters_in = body.get("filters") if isinstance(body.get("filters"), dict) else {}

        by_key = {c["key"]: c for c in spec["columns"]}
        by_column = {c["column"]: c for c in spec["columns"] if c["owner"] == "base"}
        changes = {"base": {}, "related": {}}
        for key, raw in values.items():
            c = by_key.get(key) or by_column.get(key)
            if not c or not c["editable"]:
                continue
            changes[c["owner"]][c["column"]] = parse_value(raw, c["kind"])
        if not changes["base"] and not changes["related"]:
            raise ValueError("No editable columns in the request")

        base_key = self._key_values(base, keys.get("base"))
        rel_key = self._key_values(related, keys.get("related")) if related else None
        if changes["base"] and not base_key:
            raise ValueError("Missing the row's key; reload the page and try again")
        inserting = bool(changes["related"]) and not rel_key
        if inserting and not base_key:
            raise ValueError("Missing the row's key; reload the page and try again")

        base_row = get_row(base["table"], base_key) if base_key else None
        if base_key and base_row is None:
            raise ValueError("That row no longer exists; reload the page")
        rel_row = get_row(related["table"], rel_key) if rel_key else None

        insert_values = None
        if inserting:
            insert_values = dict(changes["related"])
            for rel_col, base_col in related["match"].items():
                insert_values[rel_col] = base_row[base_col]
            for f in spec["filters"]:
                if f["owner"] != "related" or f["column"] in insert_values:
                    continue
                value = self._filter_value(f, filters_in.get(f["key"]))
                if f["kind"] == "date" and value and f["col_kind"] in ("date", "text"):
                    insert_values[f["column"]] = parse_value(value, "date")
                elif f["kind"] == "select" and value != "":
                    insert_values[f["column"]] = parse_value(value, f["col_kind"])

        if self.validate:
            merged = dict(base_row or {})
            for k, v in (rel_row or insert_values or {}).items():
                merged.setdefault(k, v)
            merged.update(changes["base"])
            for k, v in changes["related"].items():
                merged[k] = v
            for c in spec["columns"]:
                if c["owner"] != "computed" and c["column"] in merged:
                    merged[c["key"]] = (changes[c["owner"]].get(c["column"])
                                        if c["column"] in changes[c["owner"]] else merged[c["column"]])
            message = self.validate(merged)
            if message:
                raise ValueError(str(message))

        try:
            statements = []
            if changes["base"]:
                statements.append(update_row_sql(base["table"], base_key, changes["base"]))
                statements += self._ledger_edit(username, base["table"], base_key, base_row, changes["base"])
            if inserting:
                statements.append(insert_row_sql(related["table"], insert_values))
                statements.append(ledger_sql(username, "created", related["table"],
                                             new_values=_ledger_json(insert_values)))
            elif changes["related"]:
                statements.append(update_row_sql(related["table"], rel_key, changes["related"]))
                statements += self._ledger_edit(username, related["table"], rel_key, rel_row, changes["related"])
            execute_all(statements)
        except ValueError:
            raise
        except Exception as e:
            print(f"[ tableviewer ] save failed: {e!r}")
            raise ValueError("The database rejected the change") from None

        return "created" if inserting else "edited"

    # --- POST /delete: remove one row ---------------------------------------

    def delete(self, body, username=None):
        """Delete one base-table row. A reason is required; the whole row as
        it was goes into the tableviewLedger with the reason, in the same
        transaction as the delete. Raises ValueError with a message for the
        user otherwise."""
        spec = self.spec()
        base = spec["base"]
        if spec["query"] or not base["key"]:
            raise ValueError("Rows here can't be deleted")
        keys = body.get("keys") if isinstance(body.get("keys"), dict) else {}
        key = self._key_values(base, keys.get("base"))
        if not key:
            raise ValueError("Missing the row's key; reload the page and try again")
        reason = str(body.get("reason") or "").strip()
        if not reason:
            raise ValueError("A reason is required")
        if len(reason) > REASON_MAX:
            raise ValueError(f"The reason can be at most {REASON_MAX} characters")
        old_row = get_row(base["table"], key)
        if old_row is None:
            raise ValueError("That row no longer exists; reload the page")

        try:
            execute_all([
                delete_row_sql(base["table"], key),
                ledger_sql(username, "deleted", base["table"], _ledger_json(key),
                           old_values=_ledger_json(old_row), reason=reason),
            ])
        except Exception as e:
            print(f"[ tableviewer ] delete failed: {e!r}")
            raise ValueError("The database rejected the delete") from None

    @staticmethod
    def _ledger_edit(username, table, key, old_row, changes):
        """The tableviewLedger entry for an edit: old and new value of every column
        whose value really changed. Empty list when nothing did."""
        old_row = old_row or {}
        changed = [c for c in changes if to_json(old_row.get(c)) != to_json(changes[c])]
        if not changed:
            return []
        return [ledger_sql(username, "edited", table, _ledger_json(key),
                           old_values=_ledger_json({c: old_row.get(c) for c in changed}),
                           new_values=_ledger_json({c: changes[c] for c in changed}))]

    @staticmethod
    def _key_values(source, given):
        if not source or not source["key"] or not isinstance(given, dict):
            return None
        values = {k: given.get(k) for k in source["key"]}
        return values if all(v is not None for v in values.values()) else None
