# agents/api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from services.complete_registration_service import CompleteRegistrationService
from .serializers import (
    InviteAgentSerializer, CompleteRegistrationSerializer,
    AgentApprovalSerializer,

)
from middleware.permissions import IsAdmin
from services.invite_agent_service import InviteAgentService
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions as permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from services.agent_approval_service import AgentApprovalService
from authentication.models import AgentProfile


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
    

@extend_schema(
    request=CompleteRegistrationSerializer,
    tags=["Agent"]
        )
class CompleteRegistrationView(APIView):
    serializer_class = CompleteRegistrationSerializer
    permission_classes = [permission_classes.AllowAny]

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = CompleteRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = CompleteRegistrationService.complete_registration(
            serializer.validated_data
        )

        return Response({
            "success": True,
            "message": result["message"]
        }, status=status.HTTP_200_OK)



@extend_schema(
    request=AgentApprovalSerializer,
    tags=["Admin"]
        )

class AgentApprovalView(APIView):
    serializer_class = AgentApprovalSerializer
    permission_classes = [IsAdmin]

    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, agent_id):
        serializer = AgentApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]

        agent = AgentProfile.objects.filter(id=agent_id).first()
        if not agent:
            return Response(
                {"success": False, "message": "Agent not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        result = AgentApprovalService.process(
            agent=agent,
            action=action,
            admin_user=request.user
        )

        return Response({
            "success": True,
            "message": result["message"],
            "agent_status": agent.status
        }, status=status.HTTP_200_OK)
    


