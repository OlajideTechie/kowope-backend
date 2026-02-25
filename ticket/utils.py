# ticket/utils.py
from django.utils import timezone
from django.db import ProgrammingError, OperationalError
from ticket.models import Ticket

_last_expire_datetime = None  # tracks the exact last run datetime

def expire_old_tickets_once_per_day():
    global _last_expire_datetime

    try:
        now = timezone.localtime()
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Only run if we haven't expired today (i.e., after last run or first run of the day)
        if _last_expire_datetime is not None and _last_expire_datetime >= today_midnight:
            return 0  # already expired today

        # Expire tickets whose valid_for_date < today (i.e., yesterday or earlier)
        expired_qs = Ticket.objects.filter(
            valid_for_date__lt=now.date(),
            status=Ticket.Status.ACTIVE
        )

        updated_count = expired_qs.update(status=Ticket.Status.INACTIVE)

        # Update last run datetime
        _last_expire_datetime = now

        if updated_count > 0:
            print(f"[Ticket Expiration] {updated_count} ticket(s) expired on {now.date()} at {now.time()}")

        return updated_count

    except (ProgrammingError, OperationalError):
        # Table might not exist yet (safe for migrations)
        return 0