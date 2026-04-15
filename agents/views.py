# agents/api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import date as date_type

from services.complete_registration_service import CompleteRegistrationService
from .serializers import (
    InviteAgentSerializer, CompleteRegistrationSerializer,
    AgentApprovalSerializer, AgentDashboardSerializer,
)
from middleware.permissions import IsAdmin, IsAgent
from services.invite_agent_service import InviteAgentService
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, OpenApiParameter
from drf_spectacular.utils import extend_schema
from rest_framework import permissions as permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from services.agent_approval_service import AgentApprovalService
from authentication.models import AgentProfile
from ticket.models import Ticket


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


@extend_schema(
    tags=["Agent"],
    parameters=[
        OpenApiParameter(
            name="date",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Date to filter by (YYYY-MM-DD). Defaults to today.",
            required=False,
        )
    ],
    responses={
        200: OpenApiResponse(description="Agent dashboard data"),
        400: OpenApiResponse(description="Invalid date format"),
    },
)
class AgentDashboardView(APIView):
    permission_classes = [IsAgent]

    def get(self, request):
        agent = request.user.agent_profile

        # Parse optional date query param, default to today
        raw_date = request.query_params.get("date")
        if raw_date:
            try:
                query_date = date_type.fromisoformat(raw_date)
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            query_date = timezone.localdate()

        total_active_in_area = 0
        if agent.area:
            total_active_in_area = Ticket.objects.filter(
                area=agent.area,
                valid_for_date=query_date,
                status=Ticket.Status.ACTIVE,
            ).count()

        validated_tickets = (
            Ticket.objects
            .select_related("driver", "area")
            .filter(validated_by=agent, valid_for_date=query_date)
            .order_by("-validated_at")
        )

        payload = {
            "agent": agent,
            "summary": {
                "date": query_date,
                "total_active_in_area": total_active_in_area,
                "total_validated_by_me": validated_tickets.count(),
            },
            "validated_tickets": validated_tickets,
        }

        serializer = AgentDashboardSerializer(payload)
        return Response(serializer.data)


