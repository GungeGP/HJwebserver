import json

def _send_json(request, status, payload):
    request.send_response(status)
    request.send_header('Content-Type', 'application/json')
    request.end_headers()
    request.wfile.write(json.dumps(payload).encode('utf-8'))