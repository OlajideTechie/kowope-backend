# agents/api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import InviteAgentSerializer
from middleware.permissions import IsAdmin
from services.invite_agent_service import InviteAgentService
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema


@extend_schema(
    request=InviteAgentSerializer,
    tags=["Admin"],
    responses={
        201: OpenApiResponse(
            response=InviteAgentSerializer,
            description="Agent invited successfully"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid request"
        )
    }
)
class InviteAgentView(APIView):
    serializer_class = InviteAgentSerializer
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = InviteAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        result = InviteAgentService.invite_agent(
            email=email,
            invited_by=request.user
        )

        response_data = {
            "success": True,
            "message": "Agent invited successfully",
        }

        # expose invite link in non-prod
    
        if getattr(settings, "RETURN_INVITE_LINK", False):
            response_data["invite_url"] = result["invite_url"]

        return Response(response_data, status=status.HTTP_201_CREATED)