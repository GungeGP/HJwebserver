import json
import os
import re
from datetime import datetime

from WebServer import WebServer
from WebServer.helper import send_json
from WebServer.tableviewer import selectFilter

# Behind Authentik: the proxy reaches the app over the network, so it listens on all interfaces.
app = WebServer(host="0.0.0.0", port=8080)   # reads .env, so os.environ works from here on
# type can be "sqlite", "mssql" or "mysql". Tables are created if missing (pass createTables=False to skip).
app.setDatabase(type="mssql", server="localhost", dbName="Forsorg")  # Windows login; add user=/password= for a SQL Server login
# app.setDatabase(type="sqlite", dbName="workTime.db")
# app.setDatabase(type="mysql", server="localhost", dbName="workTime", user="root", password="secret")
app.addPath('/', 'public/index.html')
app.addPath('/cal', 'public/cal.html')
# Every route/page now requires a user from Authentik unless registered with public=True.
# Needs PROXY_SECRET and JWT_SECRET in .env, and this app's own GROUP_ADMIN: the
# Authentik group whose members are admins. Everyone else Authentik lets in is "user".
app.settings(auth=True,
             roleHierarchy=["admin", "user"],
             authentikRoles={os.environ["GROUP_ADMIN"]: "admin"})
# Local development without Authentik: WebServer(port=8080) instead (listens on 127.0.0.1 only),
# and add  devUser={"username": "test", "groups": [os.environ["GROUP_ADMIN"]]}  to settings().

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

@app.route('POST', '/api/cal')
def cal_selected(request):
    """The two dates picked on /cal, sent as {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}."""
    body = request.body if isinstance(request.body, dict) else {}
    try:
        start = datetime.strptime(str(body.get("start")), "%Y-%m-%d").date()
        end = datetime.strptime(str(body.get("end")), "%Y-%m-%d").date()
    except ValueError:
        send_json(request, 400, {"error": "start og end skal have formatet YYYY-MM-DD"})
        return
    if end < start:
        send_json(request, 400, {"error": "end skal være efter start"})
        return
    # Use the dates for whatever you need here
    print(f"{request.user['username'] if request.user else '?'} picked {start} -> {end}")
    send_json(request, 200, {"start": start.isoformat(), "end": end.isoformat(),
                             "days": (end - start).days + 1})


if __name__ == "__main__":
    app.start()