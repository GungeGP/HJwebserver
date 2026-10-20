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

Fields you don't touch aren't sent when saving, so a `datetime2(7)` value
keeps its full precision unless you actually change it.

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
| `readOnly=True` | No editing at all |

- Editing always requires login, even with `public=True`.
- **Without `settings(auth=True)` nothing is editable.** There's no login to
  check a role against.
- Only tables with a primary key can be edited, since the key is how a row is found.

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

The PUT and options routes only exist when editing is possible. Saves are
recorded in the audit log as `table_row_edited` / `table_row_created`.

Table and column names are checked against the database schema before they're
used in any SQL, and the result is cached for 60 seconds. If you change the
schema while the server runs, it picks the change up within a minute.

## Using TableViewer.js directly

```js
const viewer = new TableViewer(document.getElementById('box'), { url: '/api/x', limit: 20 });
viewer.load();

new TableViewer(el).setData([{ Name: 'Alice' }, { Name: 'Bob' }]);   // static rows, no server
```
