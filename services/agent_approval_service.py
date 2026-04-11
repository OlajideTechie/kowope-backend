# agents/services/agent_approval_service.py

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from authentication.models import AgentProfile, AgentStatus


class AgentApprovalService:

    @staticmethod
    def process(agent: AgentProfile, action: str, admin_user):

        if agent.status != AgentStatus.PENDING_KYC:
            raise ValidationError("Agent has no pending KYC")

        if action == "approve":
            agent.status = AgentStatus.APPROVED

        elif action == "reject":
            agent.status = AgentStatus.REJECTED

        agent.is_active = action == "approve"

        agent.save(update_fields=["status", "updated_at"])

        return {
            "message": f"Your account has been {action}d successfully, you can now login to your dashboard"
        }