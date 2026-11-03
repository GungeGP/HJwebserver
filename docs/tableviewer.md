# TableViewer

Show a database table in a page with search, sorting, paging, filters and inline
editing, without writing any HTML, JavaScript or SQL yourself.

```python
app.addTableViewer('/api/worktime', table="WorkTimeEntries", edit=["admin"])
```

```html
<div data-tableviewer="/api/worktime"></div>
```

That's the whole setup. The script and styles are loaded automatically once
`addTableViewer` has been called.

## What you get

- **Search** matches the start of any value. `name=value` searches one column
  exactly (`id=1`, `afdeling=105 IT`).
- **Sorting**: click a column header; click again to reverse.
- **Paging**: `limit` rows per page. A page can ask for fewer with
  `data-tableviewer-limit="20"`, never more.
- **Editing**: an Edit button per row for users allowed to edit. Others don't
  see an Actions column at all.
- **Fields that fit the column type**: calendar for `date`, time picker for
  `time`, both for `datetime`/`datetime2`, number fields, checkboxes for
  `bit`/`boolean`, dropdowns for lookups.
- **Readable values**: dates as `DD-MM-YYYY`, times as `HH:MM`, empty values as `–`.
- **A loading state**: placeholder rows that fill the table while the first
  page loads. After that, the current rows dim under a progress bar while the
  next page, filter or search loads. Answers faster than 150 ms show no
  loader, and only the newest request ever updates the table.

Fields you don't touch aren't sent when saving, so a `datetime2(7)` value
keeps its full precision unless you actually change it.

## Showing the table behind the login

When the data route answers "not logged in", TableViewer keeps its placeholder
rows instead of showing an error. On a protected page that happens by itself:
logged out, the page is shown with the login form on top of a ghost table.

```python
app.addPath('/', 'public/index.html')                 # the page: shown behind the login
app.addTableViewer('/api/daily', table="Employees")   # the data: requires login
```

Anyone can read the page's HTML this way, just never its rows (see
[auth.md](auth.md#what-a-logged-out-visitor-sees)). On a `public=True` page the
login form never appears, so the placeholder rows simply stay.

Because the page is shown, your own CSS applies on the login screen too, for
example a see-through overlay instead of the default dark one:

```html
<style>
  html #login-overlay { background-color: rgba(255, 255, 255, 0.35); backdrop-filter: none; }
</style>
```

(`html #login-overlay` rather than `#login-overlay`, so it wins over the
framework's `auth.css` no matter which loads first.)

## Choosing columns

```python
app.addTableViewer('/api/employees', table="Employees",
                   columns={"Navn": "Name", "Afdeling": "DepartmentId", "Fødselsdato": "BirthDate"})
```

A list (`columns=["Name", "BirthDate"]`) picks columns without renaming them.
On the page, `data-tableviewer-columns="Navn,Afdeling"` hides others
without changing the server side.

## Lookups (id → name)

For a column that stores an id from a small `id | name` table:

```python
lookups={"DepartmentId": "Departments"}
```

The page shows the department's name, editing shows a list of names, and the
id is what gets saved. The lookup table itself is never written to. Search
and sort use the name.

- If the lookup table has more than two columns, name the label column:
  `{"EmployeeId": ("Employees", "Name")}`.
- **Foreign keys are detected automatically.** If the column is declared as
  `REFERENCES Departments(Id)` and `Departments` is a plain `id | name` table,
  you don't need `lookups=` at all.
- How the field looks depends on the lookup's size: up to 20 rows is a normal
  dropdown, up to 200 is a search field, and above that the field asks the
  server for matches as you type (`GET <url>/options?column=...&search=...`).
  Typing `han` finds both "Hanne Olesen" and "Jens Hansen".

## A second table: `related=`

One row per employee, with that employee's time entry next to it:

```python
from WebServer import dateFilter, duration, selectFilter

app.addTableViewer(
    '/api/daily',
    table="Employees",
    columns={"Medarbejder": "Name", "Afdeling": "DepartmentId"},
    related={
        "table": "WorkTimeEntries",
        "match": {"EmployeeId": "Id"},       # WorkTimeEntries.EmployeeId = Employees.Id
        "keepUnmatched": True,                # default: employees without an entry still show
        "columns": {"Check ind": "CheckIn", "Check ud": "CheckOut", "Type": "TypeId"},
    },
    computed={"Varighed": lambda row: duration(row["CheckIn"], row["CheckOut"])},
    filters={
        "Vælg dag": dateFilter("WorkTimeEntries.WorkDate"),
        "Vælg afdeling": selectFilter("Employees.DepartmentId", allLabel="-- Vælg en afdeling --"),
    },
    editable=["Check ind", "Check ud", "Type"],
    edit=["admin"],
)
```

- Each edit is saved to the table that owns the column.
- **A row without a related row (shown as `–`)**: editing it *inserts* a new
  row in the related table. The join column (`EmployeeId`) comes from the row,
  and filters on the related table, like the selected day, are filled in too.
- `"keepUnmatched": False` makes it an inner join: rows without a related row
  are left out.
- The related table can have its own `"lookups"` and `"editable"`.

## Filters

Drawn above the table, left of the search box:

| Helper | Shows | Filters with |
|---|---|---|
| `dateFilter(column, default="today", arrows=True)` | date picker, with ← → for previous/next day | rows on that day (works on `date` and `datetime` columns) |
| `selectFilter(column, allLabel="All")` | dropdown | rows equal to the chosen value |

`column` is `"Column"` or `"Table.Column"`. A `selectFilter` on a lookup
column gets its options from the lookup table; otherwise from the column's
distinct values. `dateFilter(..., default=None)` shows all rows until a date
is picked.

## Computed columns

```python
computed={"Varighed": lambda row: duration(row["CheckIn"], row["CheckOut"])}
```

Calculated in Python per row, after the query, so it's the same on every
database. `row` holds every column of both tables (by real name) and every
shown column (by label). Computed columns are read-only and can't be sorted
on. `duration(start, end)` is included and returns `"H:MM"`.

## Who can edit

| Option | Effect |
|---|---|
| `roles=[...]`, `public=True` | Who may *view* (same as `route()`) |
| `edit=["admin"]` | Only these roles may edit. Default: anyone logged in |
| `editable=[...]` | Which shown columns can be edited (labels or column names). Default: every shown column except keys, join columns and computed ones |
| `delete=["admin"]` | These roles get a red trash button per row (`delete=True`: anyone logged in). Default: no deleting |
| `readOnly=True` | No editing or deleting at all |

- Editing always requires login, even with `public=True`.
- **Without `settings(auth=True)` nothing is editable.** There's no login to
  check a role against.
- Only tables with a primary key can be edited, since the key is how a row is found.

## Deleting rows

```python
app.addTableViewer('/api/forsorgshjem', table="Forsorgshjem", edit=["admin"], delete=["admin"])
```

Each row gets a red trash button next to Edit. It opens an
[`hjDialog`](frontend.md#dialogjs--popups-hjdialog) asking for a reason; the
row is only deleted once a reason is typed and confirmed.

- The row disappears from the table, but the [tableviewLedger](#tableviewledger-what-exactly-changed)
  keeps every value it had, with the reason, so it can be put back by hand.
- The reason is required (the server refuses an empty one) and at most 500
  characters.
- Only the base table's row is deleted, never a related row. If the database
  refuses (a foreign key still points at the row), the dialog says so and
  nothing changes.
- Like editing, deleting needs `settings(auth=True)` and a primary key, and
  never works for `query=` viewers or with `readOnly=True`.

## tableviewLedger: what exactly changed

Every change made through a table viewer is written to the `tableviewLedger` table,
in the same transaction as the change itself: if the ledger entry can't be
written, the change isn't saved either. The table is created automatically
with the framework's other tables.

| Column | Contents |
|---|---|
| `Id`, `At` | Running number and date/time (server's local time) |
| `Username` | Who made the change |
| `ChangeType` | `edited`, `created` (a new related row) or `deleted` |
| `TableName`, `RowKey` | Which row, e.g. `Forsorgshjem` and `{"ID": 5}` |
| `OldValues` | Before: for an edit only the columns that changed, for a delete the whole row |
| `NewValues` | After: the changed columns, or the inserted row |
| `Reason` | The reason given for a delete |

Values are JSON, written the way the table shows them: `{"Navn": "Mette Holm",
"Indskr": "2025-07-25"}`. Edits that don't actually change a value leave no
entry.

To undo a mistake, find the entry and write the `OldValues` back, either in
the table viewer or with SQL. A deleted row can be inserted again from its
`OldValues` (with `SET IDENTITY_INSERT ... ON` on mssql to keep its old id).
The ledger is read in the database itself (SSMS); it has no page.

Only changes made through a table viewer are recorded. Changes made directly
in the database (SSMS, scripts) are not.

## Checking a value before saving

```python
validate=lambda row: ("Check ud skal være efter check ind"
                      if row.get("CheckOut") and row.get("CheckIn") and str(row["CheckOut"]) < str(row["CheckIn"])
                      else None)
```

Called with the row as it would be after the edit: stored values plus the
change, by column name and by label. Return a message to refuse the save;
the message is shown above the table.

## Column types on sqlite

sqlite stores dates as text, so it can't tell a date column from any other
text column (unless the column was declared `DATE`/`DATETIME`/`TIME`). Say so
with `types=`:

```python
types={"WorkDate": "date", "StartTime": "time", "EndTime": "time"}
```

Types: `text`, `number`, `bool`, `date`, `time`, `datetime`. mssql and mysql
don't need this; the column types come from the schema.

## Views and queries

- **Database views** work like tables:
  `addTableViewer('/api/x', table="WorkTimeWithRole")`. A view has no primary
  key, so it's read-only. Pass `primaryKey=["Id"]` to edit through it, if the
  database allows that: mssql and mysql allow it for most views, sqlite
  never does.
- **`query=`** shows any SELECT. It's always read-only. Search, sort, paging and
  `filters=` work; `related=` and `lookups=` don't. On mssql the query can't
  contain its own `ORDER BY`.

  ```python
  app.addTableViewer('/api/roles', query="SELECT u.Role, w.Username, w.WorkDate FROM WorkTimeEntries w JOIN Users u ON u.Username = w.Username")
  ```

## Routes

| Route | Who | What |
|---|---|---|
| `GET <url>` | viewers | a page of rows |
| `PUT <url>` | editors | save one row |
| `GET <url>/options` | editors | lookup matches for large lookups |
| `POST <url>/delete` | `delete=` roles | delete one row: `{"keys": {"base": {...}}, "reason": "..."}` |

The PUT and options routes only exist when editing is possible, the delete
route only with `delete=`. Saves and deletes are recorded in
`tableviewLedger`, not in the audit log.

Table and column names are checked against the database schema before they're
used in any SQL, and the result is cached for 60 seconds. If you change the
schema while the server runs, it picks the change up within a minute.

## Using TableViewer.js directly

```js
const viewer = new TableViewer(document.getElementById('box'), { url: '/api/x', limit: 20 });
viewer.load();

new TableViewer(el).setData([{ Name: 'Alice' }, { Name: 'Bob' }]);   // static rows, no server
```
