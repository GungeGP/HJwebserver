"""The TableViewer feature: app.addTableViewer(...) and its routes.

The engine (spec building, filters, lookups, saving) is WebServer.tableviewer,
the SQL is WebServer.database.tableviewer, and the frontend is
public/js/TableViewer.js and public/css/TableViewer.css.
"""

from urllib.parse import parse_qs, urlparse

from WebServer.helper import send_json


class TableViewerMixin:
    """app.addTableViewer(...) - the only method this feature adds."""

    def addTableViewer(self, url_path, table=None, roles=None, public=False, limit=40,
                       readOnly=False, edit=None, columns=None, editable=None, lookups=None,
                       related=None, computed=None, filters=None, types=None, validate=None,
                       primaryKey=None, query=None, delete=None, sort=None):
        """Show a database table (or view, or query) in a searchable, sortable,
        pageable, editable table. In your HTML you only need:

            <div data-tableviewer="url_path"></div>

        What to show:
          table       table or view name.
          columns     which base columns, in order: a list of names, or
                      {"Label": "Column"} to rename them. Default: all.
          related     a second table joined to each row:
                        {"table": "WorkTimeEntries",
                         "match": {"EmployeeId": "Id"},   # its column: base column
                         "keepUnmatched": True,            # LEFT JOIN (default)
                         "columns": {...}, "lookups": {...}, "editable": [...]}
                      With keepUnmatched, base rows without a related row still
                      show; editing one of those inserts the related row.
          lookups     {"DepartmentId": "Departments"} shows the name instead of
                      the id and edits with a dropdown. For tables with more
                      than id + one column, name the label:
                      {"DepartmentId": ("Departments", "Name")}. Foreign keys
                      to plain id | string tables are found automatically.
          computed    {"Varighed": lambda row: duration(row["StartTime"], row["EndTime"])}
                      read-only columns calculated per row in Python.
          filters     {"Vælg dag": dateFilter("WorkTimeEntries.WorkDate"),
                       "Afdeling": selectFilter("DepartmentId")}
                      drawn above the table by TableViewer.js.
          types       {"WorkDate": "date"} overrides the editor picked from the
                      column type (needed on sqlite, where dates are plain text).
                      One of text, number, bool, date, time, datetime.
          query       a SELECT to show instead of a table. Always read-only.
          sort        starting order until a header is clicked: "Column" or
                      ("Column", "desc"). Default: the primary key, ascending.

        Who may do what:
          roles/public  who may view - same as route(). Default: logged in.
          edit          roles allowed to edit, e.g. ["admin"]. None: anyone
                        logged in. Editing always requires login, even with
                        public=True, and is impossible without settings(auth=True).
          delete        roles allowed to delete rows, e.g. ["admin"], or True for
                        anyone logged in. Default None: no deleting. Each row
                        gets a trash button that asks for a reason, which is
                        recorded in the audit log with the row's key.
          readOnly      True disables editing and deleting entirely.
          editable      which shown columns can be edited. Default: every
                        shown column that isn't a key, join column, or computed.
          primaryKey    key columns for a view, which has none in the schema
                        (needed to edit through it).
          validate      function(row) -> error message or None, called before
                        saving with the row as it would be after the edit.
          limit         rows per page, and the most a page may ask for.

        Routes: GET url_path (a page of rows), plus when editing is possible
        PUT url_path (save one row) and GET url_path/options (lookup search),
        and with delete= POST url_path/delete ({"keys": ..., "reason": ...}).
        """
        from WebServer.tableviewer import TableViewer

        viewer = TableViewer(table=table, columns=columns, editable=editable, lookups=lookups,
                             related=related, computed=computed, filters=filters, types=types,
                             validate=validate, primaryKey=primaryKey, query=query, sort=sort)
        # No auth means no identity to check a role against, so no editing at
        # all rather than silently letting everyone edit.
        editing_enabled = bool(self.auth) and not readOnly and not query
        deleting_enabled = bool(self.auth) and bool(delete) and not readOnly and not query
        delete_roles = list(delete) if isinstance(delete, (list, tuple, set)) else None

        def can_edit(request):
            if not editing_enabled:
                return False
            user = getattr(request, 'user', None)
            if not user:
                return False
            return not edit or user.get('role') in edit

        def can_delete(request):
            user = getattr(request, 'user', None)
            if not deleting_enabled or not user:
                return False
            return not delete_roles or user.get('role') in delete_roles

        def query_of(request):
            # keep_blank_values: "f0=" means "filter cleared", not "use the default".
            parsed = parse_qs(urlparse(request.path).query, keep_blank_values=True)
            return {k: v[0] for k, v in parsed.items()}

        @self.route('GET', url_path, public=public, roles=roles)
        def table_viewer_route(request):
            q = query_of(request)

            def _int(name, default):
                try:
                    return int(q.get(name, default))
                except (TypeError, ValueError):
                    return default

            page = max(1, _int('page', 1))
            per_page = max(1, min(_int('limit', limit), limit))
            try:
                payload = viewer.page(q, can_edit(request), page, per_page, q.get('search', ''),
                                      q.get('sort') or None, q.get('dir') or 'asc')
            except ValueError as e:
                send_json(request, 404, {"error": str(e)})
                return
            payload["canDelete"] = can_delete(request) and bool(payload["primaryKey"])
            send_json(request, 200, payload)

        if deleting_enabled:
            # Like editing, deleting never inherits public=True.
            @self.route('POST', url_path.rstrip('/') + '/delete', public=False, roles=delete_roles)
            def table_viewer_delete_route(request):
                body = request.body if isinstance(request.body, dict) else {}
                try:
                    detail = viewer.delete(body, (getattr(request, 'user', None) or {}).get('username'))
                except ValueError as e:
                    send_json(request, 400, {"error": str(e)})
                    return
                self.audit(request, "table_row_deleted", detail)
                send_json(request, 200, {"ok": True, "action": "deleted"})

        if editing_enabled:
            # Editing routes never inherit public=True.
            @self.route('PUT', url_path, public=False, roles=edit)
            def table_viewer_update_route(request):
                body = request.body if isinstance(request.body, dict) else {}
                try:
                    action, detail = viewer.save(body, (getattr(request, 'user', None) or {}).get('username'))
                except ValueError as e:
                    send_json(request, 400, {"error": str(e)})
                    return
                self.audit(request, f"table_row_{action}", detail)
                send_json(request, 200, {"ok": True, "action": action})

            # Only editors need lookup options, and a lookup table can hold
            # more than the viewer ever shows - so same roles as editing.
            @self.route('GET', url_path.rstrip('/') + '/options', public=False, roles=edit)
            def table_viewer_options_route(request):
                q = query_of(request)
                try:
                    options = viewer.options(q.get('column', ''), q.get('search', ''))
                except ValueError as e:
                    send_json(request, 404, {"error": str(e)})
                    return
                send_json(request, 200, {"options": options})

        self.table_viewer_enabled = True
        return table_viewer_route
