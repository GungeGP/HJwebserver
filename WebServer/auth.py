import json

from dotenv import load_dotenv

from WebServer import WebServer
from WebServer.database import create_user, get_user_by_username
from WebServer.helper import _send_json
from datetime import datetime, timedelta, timezone
from os import getenv
import jwt

def attach_auth_routes(server: WebServer):
    load_dotenv()
    if 'POST' not in server.routes:
        server.routes['POST'] = {}
    if '/api/login' not in server.routes['POST']:
        server.routes['POST']['/api/login'] = lambda request, server=server: _login_route(request)

    if 'GET' not in server.routes:
        server.routes['GET'] = {}
    if '/api/verify' not in server.routes['GET']:
        server.routes['GET']['/api/verify'] = lambda request, server=server: _verify_route(request, server)


def _login_route(request):
    content_length = int(request.headers.get('Content-Length', 0))
    credentials = getattr(request, 'body', None)
    
    if credentials is None:
        try:
            credentials = json.loads(request.rfile.read(content_length).decode('utf-8'))
        except json.JSONDecodeError:
            _send_json(request, 400, {"error": "Invalid JSON payload."})
            return

    username = credentials.get("username")
    password = credentials.get("password")
    if username is None or password is None:
        _send_json(request, 400, {"error": "Username and password are required."})
        return

    username = str(username)
    password = str(password)
    user_record = get_user_by_username(username)
    
    if user_record is None:
        print("New User created")
        create_user(username, password)
        user_record = get_user_by_username(username)
    if username == user_record.Username and (user_record.PasswordHash is None or password == user_record.PasswordHash):
        token = create_token_for_user(username)
        _send_json(request, 200, {"valid": True, "message": "Login successful", "token": token})
    else:
        _send_json(request, 401, {"error": "Invalid username or password."})

def _verify_route(request, server: WebServer):
    user_data = server.checkAuth(request)
    if user_data is None:
        return

    _send_json(request, 200, {"valid": True, "user": user_data})

def check_auth(self):
    """Helper method to verify the JWT token from headers."""
    auth_header = self.headers.get('Authorization')

    if not auth_header or not auth_header.startswith("Bearer "):
        _send_json(self, 401, {"error": "Missing or invalid Authorization header."})
        return None

    token = auth_header.split(" ", 1)[1]
    user_data = verify_token(token)

    if not user_data:
        _send_json(self, 401, {"error": "Invalid or expired token."})
        return None

    return user_data

def verify_token(token):
    try:
        decoded = jwt.decode(token, getenv("JWT_SECRET"), algorithms=["HS256"], options={"verify_signature": True})
        return decoded
    except jwt.ExpiredSignatureError:
        print("Token has expired.")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token.")
        return None
    
def create_token_for_user(username):
    expiration_time = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "username": username,
        "exp": expiration_time
    }
    token = jwt.encode(payload, getenv("JWT_SECRET"), algorithm="HS256")
    return token