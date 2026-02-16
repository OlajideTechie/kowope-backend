from celery import shared_task
from django.conf import settings

from kowope.settings import REDIS_CLIENT
from .models import Payment, Ticket
import uuid


"""
This module defines asynchronous tasks related to payment processing and ticket generation.
The main task is `generate_ticket`, which creates a ticket for a successful payment.
"""
@shared_task
def generate_ticket(payment_id):

    lock_key = f"generate_ticket_lock_{payment_id}"
    lock = settings.REDIS_CLIENT.lock(lock_key, timeout=300)  # Lock expires after 5 minutes

    # Attempt to acquire lock to prevent concurrent ticket generation for the same payment ie 
    # race condition between multiple webhook calls for the same payment

    if not REDIS_CLIENT.set(lock_key, "locked", nx=True, ex=300):

        # If lock is not acquired, return early
        return
   
    try: 
        payment = Payment.objects.get(id=payment_id)

        if hasattr(payment, "ticket"):
            return
        
        Ticket.objects.create(
        payment=payment,
        driver=payment.driver,
        zone=payment.zone,
        valid_for_date=payment.payment_date,

        # Generate a unique ticket number, e.g., "KWP-LAG-20240101-ABC123"
        ticket_number=f"KWP-LAG-{payment.payment_date.strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
    )

    finally:

    # Release the lock after processing
        REDIS_CLIENT.delete(lock_key)