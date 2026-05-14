from django.urls import path
from .views import (
   DriverSignupView,
   DriverLoginView,
   DriverLogoutView,
   VerifyOTPView,
   ChangePinView,
   ResendOTPView,
   ResetPinView,
   DriverProfileView,
   AdminLoginView,
   AgentLoginView,
   CookieTokenRefreshView,
)

app_name = 'authentication'

urlpatterns = [
   path('driver/signup', DriverSignupView.as_view(), name='driver-signup'),
   path('driver/login', DriverLoginView.as_view(), name='driver-login'),
   path('token/refresh', CookieTokenRefreshView.as_view(), name='token-refresh'),
   path('driver/logout', DriverLogoutView.as_view(), name='driver-logout'),
   path('driver/verify-otp', VerifyOTPView.as_view(), name='verify-otp'),
   path('driver/change-pin', ChangePinView.as_view(), name='change-pin'),

   path('driver/forgot-pin', ResetPinView.as_view(), name='forgot-pin'),
   path('driver/resend-otp', ResendOTPView.as_view(), name='resend-otp'),
   path('driver/me', DriverProfileView.as_view(), name='driver-profile'),

   path('admin/login', AdminLoginView.as_view(), name='admin-login'),
   path('agent/login', AgentLoginView.as_view(), name='agent-login'),
]