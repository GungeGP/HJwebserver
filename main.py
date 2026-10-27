import json

from WebServer import WebServer
from WebServer.tableviewer import selectFilter

app = WebServer(port=8080)
# type can be "sqlite", "mssql" or "mysql". Tables are created if missing (pass createTables=False to skip).
app.setDatabase(type="mssql", server="localhost", dbName="Forsorg")  # Windows login; add user=/password= for a SQL Server login
# app.setDatabase(type="sqlite", dbName="workTime.db")
# app.setDatabase(type="mysql", server="localhost", dbName="workTime", user="root", password="secret")
app.addPath('/', 'public/index.html', public=True)  # page is only an empty frame; its data (/api/forsorgshjem) still needs login
app.settings(auth=True)  # Every route/page now requires login unless registered with public=True
    
app.addTableViewer('/api/forsorgshjem', table="Forsorgshjem",
    columns=["cpr", "Navn", "Botilbud", "Privat tilbud", "Indskr", "Udskr", "Fritaget",
             "Betaling start", "Nedsat dagstakst", "Ny dagstakst", "Botilbud takst", "Bemærkning"],
    filters={"Vælg botilbud": selectFilter("Botilbud", allLabel="-- Alle botilbud --")},
    validate=lambda r: ("Udskr skal være efter Indskr"
                        if r.get("Udskr") and r.get("Indskr") and str(r["Udskr"]) < str(r["Indskr"])
                        else None),
    edit=["admin"])

# Create an admin user
# python -m WebServer createuser admin --role admin
user_created = app.createUser("admin", "12345", role="admin")   # False if it already exists
print(f"Admin user created: {user_created}")

if __name__ == "__main__":
    app.start()