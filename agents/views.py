# agents/api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import date as date_type, timedelta
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncWeek
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Admin Dashboard Summary
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Admin"],
    responses={200: OpenApiResponse(description="Platform summary for today")},
)
class AdminDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from authentication.models import DriverDocument
        from common.models import Area
        from payments.models import Payment

        today = timezone.localdate()

        # Today's numbers
        tickets_today = Ticket.objects.filter(valid_for_date=today)
        tickets_issued = tickets_today.count()
        validations_done = tickets_today.filter(validated_at__isnull=False).count()
        total_revenue = (
            Payment.objects
            .filter(status=Payment.Status.SUCCESS, payment_date=today)
            .aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        )

        # Pending actions
        drivers_awaiting_verification = DriverDocument.objects.filter(status="pending").count()
        agents_pending_approval = AgentProfile.objects.filter(
            status="pending_approval"
        ).count()
        areas_without_agent = Area.objects.exclude(
            agents__status="approved"
        ).count()

        # Per-area breakdown for today
        area_breakdown = (
            Ticket.objects
            .filter(valid_for_date=today)
            .values(area_name=F("area__name"), ticket_area_id=F("area__id"))
            .annotate(
                tickets_today=Count("id"),
                revenue_today=Sum("payment__amount"),
            )
            .order_by("-tickets_today")
        )

        return Response({
            "today": {
                "tickets_issued": tickets_issued,
                "total_revenue": str(total_revenue),
                "active_drivers": tickets_issued,
                "validations_done": validations_done,
            },
            "pending": {
                "drivers_awaiting_verification": drivers_awaiting_verification,
                "agents_pending_approval": agents_pending_approval,
                "areas_without_agent": areas_without_agent,
            },
            "areas": [
                {
                    "area_id": str(row["ticket_area_id"]),
                    "name": row["area_name"],
                    "tickets_today": row["tickets_today"],
                    "revenue_today": str(row["revenue_today"] or Decimal("0.00")),
                }
                for row in area_breakdown
            ],
        })


# ---------------------------------------------------------------------------
# Admin Revenue Breakdown
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Admin"],
    parameters=[
        OpenApiParameter("period", str, OpenApiParameter.QUERY, description="daily or weekly", required=False),
        OpenApiParameter("area", str, OpenApiParameter.QUERY, description="Area UUID", required=False),
        OpenApiParameter("from", str, OpenApiParameter.QUERY, description="Start date YYYY-MM-DD", required=False),
        OpenApiParameter("to", str, OpenApiParameter.QUERY, description="End date YYYY-MM-DD", required=False),
    ],
    responses={200: OpenApiResponse(description="Revenue breakdown")},
)
class AdminRevenueView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from payments.models import Payment

        period = request.query_params.get("period", "daily")
        if period not in ("daily", "weekly"):
            return Response(
                {"error": "period must be 'daily' or 'weekly'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        default_from = today - timedelta(days=6 if period == "daily" else 27)

        try:
            from_date = date_type.fromisoformat(request.query_params.get("from", str(default_from)))
            to_date = date_type.fromisoformat(request.query_params.get("to", str(today)))
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        qs = Payment.objects.filter(
            status=Payment.Status.SUCCESS,
            payment_date__range=(from_date, to_date),
        )

        area_filter = request.query_params.get("area")
        if area_filter:
            qs = qs.filter(driver__area__id=area_filter)

        if period == "daily":
            rows = (
                qs.values(
                    "payment_date",
                    area_id=F("driver__area__id"),
                    area_name=F("driver__area__name"),
                )
                .annotate(total_payments=Count("id"), total_revenue=Sum("amount"))
                .order_by("payment_date", "area_name")
            )
            breakdown = [
                {
                    "date": str(row["payment_date"]),
                    "area_id": str(row["area_id"]),
                    "area": row["area_name"],
                    "total_payments": row["total_payments"],
                    "total_revenue": str(row["total_revenue"]),
                }
                for row in rows
            ]
        else:
            rows = (
                qs.annotate(week_start=TruncWeek("payment_date"))
                .values(
                    "week_start",
                    area_id=F("driver__area__id"),
                    area_name=F("driver__area__name"),
                )
                .annotate(total_payments=Count("id"), total_revenue=Sum("amount"))
                .order_by("week_start", "area_name")
            )
            breakdown = [
                {
                    "week_start": str(row["week_start"].date() if hasattr(row["week_start"], "date") else row["week_start"]),
                    "area_id": str(row["area_id"]),
                    "area": row["area_name"],
                    "total_payments": row["total_payments"],
                    "total_revenue": str(row["total_revenue"]),
                }
                for row in rows
            ]

        totals = qs.aggregate(total_payments=Count("id"), total_revenue=Sum("amount"))

        return Response({
            "period": period,
            "from": str(from_date),
            "to": str(to_date),
            "breakdown": breakdown,
            "totals": {
                "total_payments": totals["total_payments"] or 0,
                "total_revenue": str(totals["total_revenue"] or Decimal("0.00")),
            },
        })


# ---------------------------------------------------------------------------
# Admin Driver List
# ---------------------------------------------------------------------------

@extend_schema(
    tags=["Admin"],
    parameters=[
        OpenApiParameter("area", str, OpenApiParameter.QUERY, description="Area UUID", required=False),
        OpenApiParameter("verified", str, OpenApiParameter.QUERY, description="true or false", required=False),
    ],
    responses={200: OpenApiResponse(description="Driver list")},
)
class AdminDriverListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from authentication.models import DriverProfile

        qs = DriverProfile.objects.select_related("user", "area").order_by("-user__created_at")

        area_filter = request.query_params.get("area")
        if area_filter:
            qs = qs.filter(area__id=area_filter)

        verified_filter = request.query_params.get("verified")
        if verified_filter is not None:
            if verified_filter.lower() == "true":
                qs = qs.filter(verified=True)
            elif verified_filter.lower() == "false":
                qs = qs.filter(verified=False)

        drivers = [
            {
                "id": str(d.id),
                "full_name": d.full_name,
                "phone_number": d.phone_number,
                "license_number": d.license_number,
                "area": d.area.name if d.area else None,
                "area_id": str(d.area.id) if d.area else None,
                "verified": d.verified,
                "registered_at": d.user.created_at.isoformat(),
            }
            for d in qs
        ]

        return Response({"count": len(drivers), "drivers": drivers})

