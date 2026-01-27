from rest_framework.exceptions import AuthenticationFailed
import jwt

# Middleware to require authentication from users
class RequireAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            raise AuthenticationFailed("Authentication required")

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, "SECRET_KEY", algorithms=["HS256"])
        except Exception:
            raise AuthenticationFailed("Invalid or expired token")

        request.user_context = {
            "id": payload.get("user_id"),
            "role": payload.get("role")
        }

        return self.get_response(request)
