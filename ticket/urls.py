# ticket/urls.py
from django.urls import path
from .views import TicketDashboardView, ValidateTicketAPIView

app_name = 'tickets'

urlpatterns = [
    path("validate", ValidateTicketAPIView.as_view(), name="validate-ticket"),
    path("all", TicketDashboardView.as_view(), name="ticket-dashboard"),

]