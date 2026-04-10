from rest_framework.permissions import BasePermission

# Middleware to require specific user roles

class IsAdmin(BasePermission):

    message = "You must be an admin user to access this resource."
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'super_admin']

class IsAgent(BasePermission):
    message = "You must be an agent user to access this resource."
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'agent'


class IsDriver(BasePermission):
    message = "You must be a driver user to access this resource."
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'driver'