# ticket/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from middleware.permissions import IsAgent, IsDriver

from .models import Ticket
from .serializers import TicketSerializer, TicketQRValidationSerializer, TicketFallbackValidationSerializer

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse


TICKET_VALID_EXAMPLE = OpenApiExample(
    "Valid ticket",
    value={
        "valid": True,
        "ticket_number": "KWP-LAG-20260415-A1B2C3",
        "driver_name": "Bola Tinubu",
        "area": "Surulere",
        "valid_for_date": "2026-04-15",
        "status": "ACTIVE",
    },
    response_only=True,
    status_codes=["200"],
)

TICKET_INVALID_EXAMPLE = OpenApiExample(
    "Ticket not found / invalid",
    value={"valid": False, "error": {"qr_code": ["Ticket not found"]}},
    response_only=True,
    status_codes=["400"],
)

TICKET_AREA_DENIED_EXAMPLE = OpenApiExample(
    "Area mismatch",
    value={"valid": False, "error": "You are not authorized to validate tickets for this area"},
    response_only=True,
    status_codes=["403"],
)


"""API Views for Ticket Management"""
@extend_schema(
    tags=["Agent"],
    parameters=[
        OpenApiParameter(name="qr_code", type=str, location=OpenApiParameter.QUERY, required=True),
    ],
    responses={
        200: OpenApiResponse(description="Ticket is valid", examples=[TICKET_VALID_EXAMPLE]),
        400: OpenApiResponse(description="Invalid or expired QR code", examples=[TICKET_INVALID_EXAMPLE]),
        403: OpenApiResponse(description="Area mismatch", examples=[TICKET_AREA_DENIED_EXAMPLE]),
    },
)
class ValidateTicketAPIView(APIView):
    permission_classes = [IsAgent]
    def get(self, request):
        serializer = TicketQRValidationSerializer(data=request.query_params)

        if not serializer.is_valid():
            return Response({
                "valid": False,
                "error": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        ticket = serializer.validated_data["ticket"]

        # Agents can only validate tickets for drivers in their assigned area
        agent_profile = request.user.agent_profile
        if agent_profile.area_id != ticket.area_id:
            return Response(
                {"valid": False, "error": "You are not authorized to validate tickets for this area"},
                status=status.HTTP_403_FORBIDDEN
            )

        ticket.validated_by = agent_profile
        ticket.validated_at = timezone.now()
        ticket.save(update_fields=["validated_by", "validated_at"])

        return Response({
            "valid": True,
            "ticket_number": ticket.ticket_number,
            "driver_name": ticket.driver.full_name,
            "area": ticket.area.name,
            "license_number": ticket.driver.license_number,
            "valid_for_date": ticket.valid_for_date,
            "status": ticket.computed_status,
        })



@extend_schema(
    tags=["Agent"],
    parameters=[
        OpenApiParameter(name="phone_number", type=str, location=OpenApiParameter.QUERY, required=True),
    ],
    responses={
        200: OpenApiResponse(description="Ticket is valid", examples=[TICKET_VALID_EXAMPLE]),
        400: OpenApiResponse(
            description="No active ticket for this number today",
            examples=[
                OpenApiExample(
                    "No ticket found",
                    value={"valid": False, "error": {"phone_number": ["No active ticket found for today."]}},
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
        403: OpenApiResponse(description="Area mismatch", examples=[TICKET_AREA_DENIED_EXAMPLE]),
    },
)
class FallbackValidateTicketAPIView(APIView):
    permission_classes = [IsAgent]

    def get(self, request):
        agent_area = request.user.agent_profile.area
        serializer = TicketFallbackValidationSerializer(
            data=request.query_params,
            context={"agent_area": agent_area},
        )

        if not serializer.is_valid():
            return Response({
                "valid": False,
                "error": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        ticket = serializer.validated_data["ticket"]

        ticket.validated_by = request.user.agent_profile
        ticket.validated_at = timezone.now()
        ticket.save(update_fields=["validated_by", "validated_at"])

        return Response({
            "valid": True,
            "ticket_number": ticket.ticket_number,
            "driver_name": ticket.driver.full_name,
            "area": ticket.area.name,
            "license_number": ticket.driver.license_number,
            "valid_for_date": ticket.valid_for_date,
            "status": ticket.computed_status,
        })


@extend_schema(tags=["Tickets"],)
class TicketDashboardView(APIView):
    serializer_class = TicketSerializer
    permission_classes = [IsDriver]

    def get(self, request):
        driver = request.user.driver_profile
        today = timezone.localdate()

        # Get active ticket
        active_ticket = Ticket.objects.filter(
            driver=driver,
            status=Ticket.Status.ACTIVE,
            valid_for_date=today
        ).first()

        # Get last 7 days history (excluding today)
        start_date = today - timedelta(days=7)

        recent_tickets = Ticket.objects.filter(
            driver=driver,
            valid_for_date__gte=start_date,
            valid_for_date__lt=today
        ).order_by("-valid_for_date")

        return Response({
            "can_work_today": bool(active_ticket),
            "active_ticket": TicketSerializer(active_ticket).data if active_ticket else None,
            "recent_tickets": TicketSerializer(recent_tickets, many=True).data
        })