from django.conf import settings

REFRESH_COOKIE = "refresh_token"

def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/api/v1/auth/",
    )

"""Utility functions for managing authentication cookies in the Kowope backend."""
def clear_auth_cookies(response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/v1/auth/",
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/",
    )