import json

from WebServer import WebServer

app = WebServer(port=8080)
# type can be "sqlite", "mssql" or "mysql". Tables are created if missing (pass createTables=False to skip).
app.setDatabase(type="mssql", server="localhost", dbName="workTime")
# app.setDatabase(type="sqlite", dbName="workTime.db")
# app.setDatabase(type="mysql", server="localhost", dbName="workTime", user="root", password="secret")
app.addPath('/', 'public/index.html')
app.settings(auth=True)  # Every route/page now requires login unless registered with public=True

# Users are created by an admin, not by self-registration:
#   python -m WebServer createuser admin --role admin
# or from code:  app.createUser("admin", "change-me-please", role="admin")   # False if it already exists

@app.route('POST', '/api/data')
def data_route(request):
    # 1. You can now access the parsed frontend data directly!
    print("Data received from frontend:", request.body, "from user:", request.user["username"])
    
    # 2. Prepare the response
    request.send_response(200)
    request.send_header('Content-Type', 'application/json')
    request.end_headers()
    
    # 3. Send a JSON response back
    response_data = {"message": "The framework POST route works!", "status": "success"}
    request.wfile.write(json.dumps(response_data).encode('utf-8'))

@app.route('GET', '/hello', public=True)
def hello_route(request):
    request.send_response(200)
    request.send_header('Content-Type', 'text/plain')
    request.end_headers()
    request.wfile.write(b"Hello from the secure internal server!")

if __name__ == "__main__":
    app.start()