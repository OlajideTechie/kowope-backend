from django.urls import path
from .views import (
    InviteAgentView, CompleteRegistrationView, AgentApprovalView,
    AgentDashboardView, AdminDashboardView, AdminRevenueView, AdminDriverListView,
)

app_name = "agents"

urlpatterns = [
    path("invite-agent", InviteAgentView.as_view(), name="invite-agent"),
    path("agents/complete-registration", CompleteRegistrationView.as_view(), name="complete-registration"),
    path("agents/<uuid:agent_id>/approval", AgentApprovalView.as_view()),
    path("agents/dashboard", AgentDashboardView.as_view(), name="agent-dashboard"),
    path("admin/dashboard", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/revenue", AdminRevenueView.as_view(), name="admin-revenue"),
    path("admin/drivers", AdminDriverListView.as_view(), name="admin-drivers"),
]