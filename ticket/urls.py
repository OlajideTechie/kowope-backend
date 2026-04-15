# ticket/urls.py
from django.urls import path
from .views import TicketDashboardView, ValidateTicketAPIView, FallbackValidateTicketAPIView

app_name = 'tickets'

urlpatterns = [
    path("agents/validate", ValidateTicketAPIView.as_view(), name="validate-ticket"),
    path("agents/validate/fallback", FallbackValidateTicketAPIView.as_view(), name="validate-ticket-fallback"),
    path("all", TicketDashboardView.as_view(), name="ticket-dashboard"),
]