from django.utils import timezone
from django.core.cache import cache
from ticket.models import Ticket

EXPIRATION_CACHE_KEY = "last_ticket_expiration_date"

def expire_old_tickets_once_per_day():
    today = timezone.localdate()

    last_run = cache.get(EXPIRATION_CACHE_KEY)

    # If already run today, do nothing
    if last_run == str(today):
        return

    expired_count = Ticket.objects.filter(
        status=Ticket.Status.ACTIVE,
        valid_for_date__lt=today
    ).update(status=Ticket.Status.INACTIVE)

    # Store today's date in cache
    cache.set(EXPIRATION_CACHE_KEY, str(today), timeout=60 * 60 * 24)

    print(f"[Lazy Expiration] {expired_count} tickets expired.")