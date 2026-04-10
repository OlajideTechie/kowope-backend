from django.urls import path
from .views import InviteAgentView

app_name = "agents"

urlpatterns = [
    path("invite-agent", InviteAgentView.as_view(), name="invite-agent"),
]