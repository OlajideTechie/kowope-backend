import uuid
from django.core.cache import cache
from django.db import transaction, IntegrityError
from payments.models import Payment
from ticket.models import Ticket
import qrcode
import io
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone


"""
This module defines a synchronous tasks related to payment processing and ticket generation.
The main task is `generate_ticket`, which creates a ticket for a successful payment.
"""

def generate_unique_qr_code():
    while True:
        qr = uuid.uuid4()
        if not Ticket.objects.filter(qr_code=qr).exists():
            return qr
        
def generate_ticket(payment_id):
    """
    Generate a ticket for a payment, ensuring:
    - Only one active ticket per driver per day
    - QR code token is generated alongside ticket
    - Safe concurrency using cache lock
    """

    lock_key = f"generate_ticket_lock_{payment_id}"
    lock_acquired = cache.add(lock_key, "locked", timeout=300)

    if not lock_acquired:
        print (f"another process is handling this payment")
        return

    try:
        today = timezone.localdate()

        payment = Payment.objects.select_related("driver").filter(id=payment_id).first()
        if not payment:
            print(f"No payment found for id {payment_id}")
            return None

        # ---------------------------------------------------
        # STEP 1: IDENTITY CHECK (return real object, not bool)
        # ---------------------------------------------------
        existing_ticket = Ticket.objects.filter(
           payment=payment,
            ).first()
        
        if existing_ticket:
            return existing_ticket
        
        # ---------------------------------------------------
        # STEP 2: SAFER GLOBAL DAILY CHECK
        # ---------------------------------------------------
        existing_daily_ticket = Ticket.objects.filter(
            driver=payment.driver,
            valid_for_date=today,
            status=Ticket.Status.ACTIVE
        ).select_for_update().first()

        if existing_daily_ticket:
            return existing_daily_ticket

        
        # ---------------------------------------------------
        # STEP 3: CREATE ATOMICALLY
        # ---------------------------------------------------

        with transaction.atomic():

            ticket = Ticket.objects.create(
                payment=payment,
                driver=payment.driver,
                area=payment.driver.area,
                valid_for_date=today,
                ticket_number=f"KWP-LAG-{today.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}",
                qr_code=generate_unique_qr_code(), 
                status=Ticket.Status.ACTIVE,
            )
            return ticket

    except IntegrityError:
        # Return existing ticket in case of DB-level uniqueness conflict
        return Ticket.objects.filter(payment_id=payment_id).first()

    finally:
        cache.delete(lock_key)