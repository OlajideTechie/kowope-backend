from rest_framework.exceptions import PermissionDenied

# Middleware to require specific user roles
def require_roles(allowed_roles):
    def middleware(view_func):
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user_context", None)

            if not user or user["role"] not in allowed_roles:
                raise PermissionDenied("You do not have permission")

            return view_func(request, *args, **kwargs)
        return wrapper
    return middleware
