from datetime import datetime
from os import getenv
import json
import jwt

def check_auth(self):
        """Helper method to verify the JWT token from headers."""
        auth_header = self.headers.get('Authorization')
    
        if not auth_header or not auth_header.startswith("Bearer "):
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing or invalid Authorization header."}).encode("utf-8"))
            return None
            
        token = auth_header.split(" ")[1]
        user_data = verify_token(token)
        
        if not user_data:
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid or expired token."}).encode("utf-8"))
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
    expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    payload = {
        "username": username,
        "exp": expiration_time
    }
    token = jwt.encode(payload, getenv("JWT_SECRET"), algorithm="HS256")
    return token    