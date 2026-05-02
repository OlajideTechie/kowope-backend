# agents/services/complete_registration_service.py

import jwt
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from authentication.models import AgentProfile, AgentStatus
from services.document_verification_service import DocumentVerificationService

User = get_user_model()


class CompleteRegistrationService:

    @staticmethod
    def decode_token(token: str):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ValidationError("Invite link has expired")
        except jwt.InvalidTokenError:
            raise ValidationError("Invalid invite token")

        if payload.get("type") != "agent_invite":
            raise ValidationError("Invalid token type")

        return payload

    @staticmethod
    @transaction.atomic
    def complete_registration(data):
        payload = CompleteRegistrationService.decode_token(data["token"])

        user_id = payload.get("user_id")

        user = User.objects.filter(id=user_id, role="agent").first()
        if not user:
            raise ValidationError("User not found")

        if not hasattr(user, "agent_profile"):
            raise ValidationError("Agent profile not found")

        agent = user.agent_profile

        # prevent re-registration
        if agent.status not in ["invited", "pending_kyc"]:
            raise ValidationError("Registration already completed or invalid state")

        # update agent profile
        agent.full_name = data["full_name"]
        agent.area = data["area"]
        agent.status = "pending_kyc"
        agent.invite_token_used = True
        agent.save()

        # upload NIN document via centralized service
        DocumentVerificationService.upload_agent_document(
            agent_profile=agent,
            file=data["nin_document"],
        )

        # set password
        user.password = make_password(data["password"])
        user.confirm_password = make_password(data["password"])
        user.save(update_fields=["password"])

        return {
            "agent_id": str(agent.id),
            "message": "Registration completed successfully. Awaiting admin approval."
        }