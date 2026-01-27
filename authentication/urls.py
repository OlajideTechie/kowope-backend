from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
   DriverSignupView,
   DriverLoginView
)

app_name = 'authentication'

urlpatterns = [
   path('driver/signup', DriverSignupView.as_view(), name='driver-signup'),
   path('driver/login', DriverLoginView.as_view(), name='driver-login'),
   path('token/refresh', TokenRefreshView.as_view(), name='token-refresh'),
]