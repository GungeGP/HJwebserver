import json
import re
from datetime import datetime

from WebServer import WebServer
from WebServer.tableviewer import dateFilter, selectFilter

app = WebServer(port=8080)
# type can be "sqlite", "mssql" or "mysql". Tables are created if missing (pass createTables=False to skip).
app.setDatabase(type="mssql", server="localhost", dbName="Forsorg")  # Windows login; add user=/password= for a SQL Server login
# app.setDatabase(type="sqlite", dbName="workTime.db")
# app.setDatabase(type="mysql", server="localhost", dbName="workTime", user="root", password="secret")
app.addPath('/', 'public/index.html', public=True)  # page is only an empty frame; its data (/api/forsorgshjem) still needs login
app.settings(auth=True)  # Every route/page now requires login unless registered with public=True


def valid_cpr(cpr):
    """ddmmyy-xxxx where ddmmyy is a real date."""
    if not re.fullmatch(r"\d{6}-\d{4}", cpr or ""):
        return False
    try:
        datetime.strptime(cpr[:6], "%d%m%y")
    except ValueError:
        return False
    return True


def validate_forsorgshjem(r):
    """Called before every save with the row as it would be after the edit."""
    if not valid_cpr(r.get("CPR")):
        return "CPR skal have formatet ddmmåå-xxxx, fx 010190-1234"
    if r.get("Udskr") and r.get("Indskr") and str(r["Udskr"]) < str(r["Indskr"]):
        return "Udskr skal være efter Indskr"
    return None


app.addTableViewer('/api/forsorgshjem', table="Forsorgshjem",
    columns=["cpr", "Navn", "Botilbud", "Privat tilbud", "Indskr", "Udskr", "Fritaget",
             "Betaling start", "Nedsat dagstakst", "Ny dagstakst", "Botilbud takst", "Bemærkning"],
    filters={"Vælg botilbud": selectFilter("Botilbud", allLabel="-- Alle botilbud --"),
             "Privat tilbud": selectFilter("Privat tilbud", allLabel="-- Alle --"),
             "Fritaget": selectFilter("Fritaget", allLabel="-- Alle --")},
    validate=validate_forsorgshjem,
    edit=["admin"], delete=["admin"])

# Every edit and delete made in a table viewer, with old and new values.
app.addPath('/ledger', 'public/ledger.html', public=True)  # empty frame; its data needs an admin
app.addTableViewer('/api/ledger', table="Ledger", roles=["admin"], readOnly=True,
    columns={"#": "Id", "Tidspunkt": "At", "Bruger": "Username", "Handling": "ChangeType",
             "Tabel": "TableName", "Række": "RowKey", "Før": "OldValues", "Efter": "NewValues",
             "Begrundelse": "Reason"},
    filters={"Vælg tabel": selectFilter("TableName", allLabel="-- Alle tabeller --"),
             "Handling": selectFilter("ChangeType", allLabel="-- Alle --"),
             "Dag": dateFilter("At", default=None)},
    sort=("Id", "desc"))

# Create an admin user
# python -m WebServer createuser admin --role admin
user_created = app.createUser("admin", "12345", role="admin")   # False if it already exists
print(f"Admin user created: {user_created}")

if __name__ == "__main__":
    app.start()