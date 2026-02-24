from django.core.cache import cache
from django.db import transaction, IntegrityError
from payments.models import Payment
from ticket.models import Ticket
import uuid
from django.conf import settings
from django.utils import timezone


"""
This module defines a synchronous tasks related to payment processing and ticket generation.
The main task is `generate_ticket`, which creates a ticket for a successful payment.
"""
def generate_ticket(payment_id):
    lock_key = f"generate_ticket_lock_{payment_id}"
    lock_acquired = cache.add(lock_key, "locked", timeout=300)
    if not lock_acquired:
        return  # another process is handling this payment

    try:
        today = timezone.localdate()

        payment = Payment.objects.select_related("driver").filter(id=payment_id).first()
        if not payment:
            print(f"No payment found for id {payment_id}")
            return

        # Check for existing active ticket today
        existing_ticket = Ticket.objects.filter(driver=payment.driver, valid_for_date=today, status=Ticket.Status.ACTIVE).exists()
        if existing_ticket:
            return existing_ticket

        with transaction.atomic():
            ticket = Ticket.objects.create(
                payment=payment,
                driver=payment.driver,
                area=payment.driver.area,
                valid_for_date=today,
                ticket_number=f"KWP-LAG-{payment.payment_date.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}",
                status=Ticket.Status.ACTIVE,
            )
            return ticket

    except IntegrityError:
        # Return existing ticket in case of DB-level uniqueness conflict
        return Ticket.objects.filter(payment=payment).first()

    finally:
        cache.delete(lock_key)