from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from utils.cookies import ACCESS_COOKIE


class CookieJWTAuthentication(JWTAuthentication):
    """
    Reads the access token from the HttpOnly cookie.
    Falls back to the Authorization header so Bearer tokens used in
    tests and API tooling continue to work without changes.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(ACCESS_COOKIE)

        if raw_token:
            try:
                validated = self.get_validated_token(raw_token)
                return self.get_user(validated), validated
            except (InvalidToken, TokenError):
                # Expired or invalid cookie — treat as unauthenticated
                # so AllowAny views (e.g. logout) still reach the handler
                return None

        return super().authenticate(request)
