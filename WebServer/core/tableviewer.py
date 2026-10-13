"""The TableViewer feature: app.addTableViewer(...) and nothing else.

Everything TableViewer-specific that isn't pure SQL lives here - the SQL
itself is in WebServer.database.tableviewer. The frontend is public/js/TableViewer.js
and public/css/TableViewer.css.
"""

import json
from urllib.parse import parse_qs, urlparse


class TableViewerMixin:
    """app.addTableViewer(...) - the only method this feature adds."""

    def addTableViewer(self, url_path, table, roles=None, public=False, limit=40):
        """Expose a database table as a paginated/searchable/sortable/editable JSON feed for TableViewer.js.

        GET url_path?page=1&limit=40&search=...&sort=Column&dir=asc returns
            {"rows", "columns", "page", "limit", "total", "totalPages", "sort", "sortDir", "search", "primaryKey"}
        PUT url_path with body {"pk": {col: value, ...}, "values": {col: value, ...}}
            updates one row, identified by its primary key. Only tables with a
            primary key can be edited - TableViewer.js greys out Edit when
            "primaryKey" comes back empty.

        table:  real table name; re-checked against the live schema on every
                request (table names can't be bound as query parameters).
        limit:  rows PER PAGE, and also the ceiling - the client may ask for
                fewer with ?limit=N (or via data-tableviewer-limit in HTML),
                but never more than this.
        roles/public: same meaning as route() - defaults to requiring login,
                no specific role. Applies to both reading and editing.

        Also turns on TableViewer.js injection (see AssetsMixin.get_inject_js_urls()),
        so in your own HTML you only need:
            <div data-tableviewer="url_path"></div>
        """
        from WebServer.database import get_primary_key_columns, get_table_page, update_table_row

        @self.route('GET', url_path, public=public, roles=roles)
        def table_viewer_route(request):
            query = parse_qs(urlparse(request.path).query)

            def _int(name, default):
                try:
                    return int(query.get(name, [default])[0])
                except (TypeError, ValueError):
                    return default

            page = max(1, _int('page', 1))
            per_page = max(1, min(_int('limit', limit), limit))
            search = (query.get('search', [''])[0] or '').strip()
            sort = (query.get('sort', [None])[0]) or None
            sort_dir = (query.get('dir', ['asc'])[0]) or 'asc'

            try:
                rows, total, columns = get_table_page(
                    table, page=page, per_page=per_page, search=search or None,
                    sort=sort, sort_dir=sort_dir)
                primary_key = get_primary_key_columns(table)
            except ValueError as e:
                request.send_response(404)
                request.send_header('Content-Type', 'application/json')
                request.end_headers()
                request.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

            total_pages = max(1, -(-total // per_page))  # ceil division
            payload = {
                "rows": rows,
                "columns": columns,
                "page": page,
                "limit": per_page,
                "total": total,
                "totalPages": total_pages,
                "sort": sort,
                "sortDir": sort_dir,
                "search": search,
                "primaryKey": primary_key,
            }

            request.send_response(200)
            request.send_header('Content-Type', 'application/json')
            request.end_headers()
            # mssql/mysql drivers return DATE/TIME/DECIMAL columns as native
            # Python objects (date, time, Decimal, ...) that json can't
            # serialize directly; default=str renders them the same way
            # TableViewer.js would display them anyway.
            request.wfile.write(json.dumps(payload, default=str).encode('utf-8'))

        @self.route('PUT', url_path, public=public, roles=roles)
        def table_viewer_update_route(request):
            body = request.body if isinstance(request.body, dict) else {}
            pk_values = body.get('pk')
            changes = body.get('values')

            if not isinstance(pk_values, dict) or not isinstance(changes, dict):
                request.send_response(400)
                request.send_header('Content-Type', 'application/json')
                request.end_headers()
                request.wfile.write(json.dumps(
                    {"error": "Body must be {\"pk\": {...}, \"values\": {...}}."}).encode('utf-8'))
                return

            try:
                update_table_row(table, pk_values, changes)
            except ValueError as e:
                request.send_response(400)
                request.send_header('Content-Type', 'application/json')
                request.end_headers()
                request.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

            if getattr(self, 'auth', None) and getattr(request, 'user', None):
                self.audit(request, 'table_row_edited', f"table={table} pk={pk_values}")

            request.send_response(200)
            request.send_header('Content-Type', 'application/json')
            request.end_headers()
            request.wfile.write(json.dumps({"ok": True}).encode('utf-8'))

        self.table_viewer_enabled = True
        return table_viewer_route
