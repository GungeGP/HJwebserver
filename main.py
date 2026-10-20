import json

from WebServer import WebServer
from WebServer.tableviewer import dateFilter, duration, selectFilter

app = WebServer(port=8080)
# type can be "sqlite", "mssql" or "mysql". Tables are created if missing (pass createTables=False to skip).
app.setDatabase(type="mssql", server="localhost", dbName="HJWebServer")  # Windows login; add user=/password= for a SQL Server login
# app.setDatabase(type="sqlite", dbName="workTime.db")
# app.setDatabase(type="mysql", server="localhost", dbName="workTime", user="root", password="secret")
app.addPath('/', 'public/index.html', public=True)  # page is only an empty frame; its data (/api/daily) still needs login
app.settings(auth=True)  # Every route/page now requires login unless registered with public=True
    
app.addTableViewer('/api/daily', table="Employees",
    columns={"Medarbejder": "Name", "Afdeling": "DepartmentId"},
    related={"table": "WorkTimeEntries", "match": {"EmployeeId": "Id"},
             "columns": {"Check ind": "CheckIn", "Check ud": "CheckOut"}},
    computed={"Varighed": lambda r: duration(r["CheckIn"], r["CheckOut"])},
    filters={"Vælg dag": dateFilter("WorkTimeEntries.WorkDate"),
             "Vælg afdeling": selectFilter("DepartmentId")},
    editable=["Check ind", "Check ud"], edit=["admin"])

# Create an admin user
# python -m WebServer createuser admin --role admin
user_created = app.createUser("admin", "12345", role="admin")   # False if it already exists
print(f"Admin user created: {user_created}")

if __name__ == "__main__":
    app.start()