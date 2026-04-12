import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import DriverProfile, User
from common.models import Area
from payments.models import Payment
from ticket.models import Ticket
from utils.task import generate_ticket

from ticket.utils import expire_old_tickets_once_per_day

@pytest.mark.django_db
def test_full_payment_ticket_expire_flow():
    """
    Simulates full flow:
    1. Driver makes payment → ticket generated
    2. Ticket expires on next day → lazy expiration
    3. Driver can buy new ticket for the new day
    """

    # --------------------------
    # Step 0: Create Driver
    # --------------------------
    area = Area.objects.create(name="Ikeja", state="Lagos")

    user = User.objects.create(
        password="password123"
    )

    driver = DriverProfile.objects.create(
        user=user,
        full_name="Test Driver",
        area=area,
        lga="Ikeja",
        phone_number=f"080{uuid.uuid4().int % 100000000:08d}",  # unique
        license_number=str(uuid.uuid4())[:12],
        pin_hash="hashed_pin_value",
        pin_set=True,
        is_phone_verified=True,
        verified=True,
    )

    # --------------------------
    # Step 1: Initial Payment → Ticket
    # --------------------------
    today = timezone.localdate()
    payment1 = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today
    )

    ticket1 = generate_ticket(payment1.id)

    assert ticket1 is not None
    assert ticket1.status == Ticket.Status.ACTIVE
    assert ticket1.valid_for_date == today

    # --------------------------
    # Step 2: Simulate Next Day → Expire Ticket
    # --------------------------
    yesterday = today - timedelta(days=1)
    ticket1.valid_for_date = yesterday
    ticket1.save()

    # Run expiration logic
    expire_old_tickets_once_per_day()

    ticket1.refresh_from_db()
    assert ticket1.status == Ticket.Status.INACTIVE

    # --------------------------
    # Step 3: Driver Makes Payment Next Day → New Ticket
    # --------------------------
    next_day = today + timedelta(days=1)
    payment2 = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=next_day
    )

    # Patch timezone.localdate() so ticket valid_for_date matches next_day
    with patch("django.utils.timezone.localdate", return_value=next_day):
        ticket2 = generate_ticket(payment2.id)

    assert ticket2 is not None
    assert ticket2.status == Ticket.Status.ACTIVE
    assert ticket2.valid_for_date == next_day

    # --------------------------
    # Step 4: Ensure Driver Has 1 Inactive + 1 Active
    # --------------------------
    all_tickets = Ticket.objects.filter(driver=driver).order_by("valid_for_date")
    assert all_tickets.count() == 2
    assert all_tickets[0].status == Ticket.Status.INACTIVE
    assert all_tickets[1].status == Ticket.Status.ACTIVE