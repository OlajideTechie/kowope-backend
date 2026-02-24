# ticket/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta

from .models import Ticket
from .serializers import TicketSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=["Tickets"],)
class TicketDashboardView(APIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

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