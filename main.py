import json

from web_framework.WebServer import WebServer

app = WebServer(port=8080)
app.file('/', 'public/index.html')

@app.route('POST', '/api/data')
def data_route(request):
    # 1. You can now access the parsed frontend data directly!
    print("Data received from frontend:", request.body)
    
    # 2. Prepare the response
    request.send_response(200)
    request.send_header('Content-Type', 'application/json')
    request.end_headers()
    
    # 3. Send a JSON response back
    response_data = {"message": "The framework POST route works!", "status": "success"}
    request.wfile.write(json.dumps(response_data).encode('utf-8'))

@app.route('GET', '/hello')
def hello_route(request):
    request.send_response(200)
    request.send_header('Content-Type', 'text/plain')
    request.end_headers()
    request.wfile.write(b"Hello from the secure internal server!")

if __name__ == "__main__":
    app.start()