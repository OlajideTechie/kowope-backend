from django.utils import timezone
from django.core.cache import cache
from django.db import ProgrammingError, OperationalError
from django.apps import apps


def expire_old_tickets_once_per_day():
    """
    Lazily expires old tickets.
    Safe during migrations and fresh deployments.
    Runs at most once per day.
    """

    today = timezone.now().date()

    # Prevent multiple executions per day
    if cache.get("ticket_expire_last_run") == today:
        return

    try:
        Ticket = apps.get_model("ticket", "Ticket")

        Ticket.objects.filter(
            expiry_date__lt=today,
            status=Ticket.Status.ACTIVE
        ).update(status=Ticket.Status.INACTIVE)

        cache.set("ticket_expire_last_run", today, timeout=86400)

    except (ProgrammingError, OperationalError):
        # Happens during migrations or before table exists
        # Fail silently to avoid breaking startup
        return