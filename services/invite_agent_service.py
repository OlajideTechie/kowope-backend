# agents/services/invite_agent_service.py

import uuid
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from authentication.models import AgentProfile
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone
import jwt

User = get_user_model()


class InviteAgentService:

    @staticmethod
    @transaction.atomic
    def invite_agent(email: str, invited_by):
        # 1. Create User
        user = User.objects.create(
            email=email,
            role="agent",
            is_active=True
        )

        # 2. Create Agent Profile
        agent = AgentProfile.objects.create(
            user=user,
            status="invited",
            invited_by=invited_by,
            invite_token_used=False
        )

        # 3. Generate Invite Token (expires in 24hrs)
        payload = {
            "user_id": str(user.id),
            "exp": timezone.now() + timedelta(hours=24),
            "type": "agent_invite"
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        # 4. Build Invite URL
        invite_url = f"{settings.FRONTEND_DOMAIN}/complete-registration?token={token}"

        # 5. Send Email (simple version)
        send_mail(
            subject="Your invitation to join Kowope Platform",
            message=f" Hello, You're invited to join the Kowope Platform. Click the link to complete your registration: {invite_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
        
        # for staging/testing
        return {
            "email": email,
            "invite_url": invite_url  
        }