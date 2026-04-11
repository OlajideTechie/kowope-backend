from django.urls import path
from .views import (
    InviteAgentView, CompleteRegistrationView, AgentApprovalView
)

app_name = "agents"

urlpatterns = [
    path("invite-agent", InviteAgentView.as_view(), name="invite-agent"),
    path("agents/complete-registration", CompleteRegistrationView.as_view(), name="complete-registration"),
    path("agents/<uuid:agent_id>/approval", AgentApprovalView.as_view()),
]