import json

def send_json(request, status, payload, headers=None):
    """Write a JSON response: status code, optional extra headers, then the payload as JSON."""
    request.send_response(status)
    request.send_header('Content-Type', 'application/json')
    for name, value in (headers or {}).items():
        request.send_header(name, value)
    request.end_headers()
    # default=str: values from the database (dates, Decimal, ...) or from a
    # consumer's computed column shouldn't crash the response.
    request.wfile.write(json.dumps(payload, default=str).encode('utf-8'))


# Internal name kept for the framework's own modules.
_send_json = send_json
