
from django.core.cache import cache
from django.db import transaction, IntegrityError
from payments.models import Payment
from ticket.models import Ticket
import uuid
from django.utils import timezone

"""
This module defines a synchronous tasks related to payment processing and ticket generation.
The main task is `generate_ticket`, which creates a ticket for a successful payment.
"""
def generate_ticket(payment_id):
    lock_key = f"generate_ticket_lock_{payment_id}"

    # cache.add() is atomic — succeeds only if key does NOT exist
    lock_acquired = cache.add(lock_key, "locked", timeout=300)

    if not lock_acquired:
        return  # Another process is already handling this payment

    try:
        with transaction.atomic():
            payment = Payment.objects.select_related("driver").get(id=payment_id)

            # Prevent duplicate ticket creation
            if hasattr(payment, "ticket"):
                return

            Ticket.objects.create(
                payment=payment,
                driver=payment.driver,
                area=payment.driver.area,
                valid_for_date=timezone.localdate(),
                ticket_number=f"KWP-LAG-{payment.payment_date.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
            )

    except IntegrityError:
        # If DB-level duplicate happens, ignore safely
        pass

    finally:
        cache.delete(lock_key)