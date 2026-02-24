# ticket/urls.py
from django.urls import path
from .views import TicketDashboardView

app_name = 'tickets'

urlpatterns = [
    path("dashboard", TicketDashboardView.as_view(), name="ticket-dashboard")
]