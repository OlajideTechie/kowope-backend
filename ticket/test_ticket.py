import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import AgentProfile, DriverProfile, User
from common.models import Area
from payments.models import Payment
from ticket.models import Ticket
from utils.task import generate_ticket
from ticket.utils import expire_old_tickets_once_per_day


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def area(db):
    return Area.objects.create(name="Surulere", state="Lagos")


@pytest.fixture
def other_area(db):
    return Area.objects.create(name="Ikeja", state="Lagos")


@pytest.fixture
def driver(db, area):
    user = User.objects.create(phone_number="08031234567", role="driver", is_active=True)
    profile = DriverProfile.objects.create(
        user=user,
        full_name="Test Driver",
        area=area,
        lga="Surulere",
        phone_number="08031234567",
        license_number="ABCDE1234",
        pin_hash="hashed",
        pin_set=True,
        is_phone_verified=True,
        verified=True,
    )
    return profile


@pytest.fixture
def agent(db, area):
    user = User.objects.create(email="agent@kowope.com", role="agent", is_active=True)
    user.set_password("agentpass123")
    user.save(update_fields=["password"])
    profile = AgentProfile.objects.create(user=user, area=area, status="approved")
    return profile


@pytest.fixture
def agent_other_area(db, other_area):
    user = User.objects.create(email="agent2@kowope.com", role="agent", is_active=True)
    user.set_password("agentpass123")
    user.save(update_fields=["password"])
    profile = AgentProfile.objects.create(user=user, area=other_area, status="approved")
    return profile


@pytest.fixture
def auth_agent_client(api_client, agent):
    refresh = RefreshToken.for_user(agent.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def auth_agent_other_area_client(api_client, agent_other_area):
    refresh = RefreshToken.for_user(agent_other_area.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def auth_driver_client(api_client, driver):
    refresh = RefreshToken.for_user(driver.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def active_ticket(db, driver):
    today = timezone.localdate()
    payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    return generate_ticket(payment.id)


# ---------------------------------------------------------------------------
# Payment → Ticket → Expiry Flow
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_full_payment_ticket_expire_flow(area):
    user = User.objects.create(password="password123")
    driver = DriverProfile.objects.create(
        user=user,
        full_name="Test Driver",
        area=area,
        lga="Surulere",
        phone_number=f"080{uuid.uuid4().int % 100000000:08d}",
        license_number=str(uuid.uuid4())[:12],
        pin_hash="hashed_pin_value",
        pin_set=True,
        is_phone_verified=True,
        verified=True,
    )

    today = timezone.localdate()
    payment1 = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )

    ticket1 = generate_ticket(payment1.id)
    assert ticket1 is not None
    assert ticket1.status == Ticket.Status.ACTIVE
    assert ticket1.valid_for_date == today

    # Simulate next day → expire
    ticket1.valid_for_date = today - timedelta(days=1)
    ticket1.save()
    expire_old_tickets_once_per_day()
    ticket1.refresh_from_db()
    assert ticket1.status == Ticket.Status.INACTIVE

    # New payment next day → new ticket
    next_day = today + timedelta(days=1)
    payment2 = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=next_day,
    )
    with patch("django.utils.timezone.localdate", return_value=next_day):
        ticket2 = generate_ticket(payment2.id)

    assert ticket2 is not None
    assert ticket2.status == Ticket.Status.ACTIVE
    assert ticket2.valid_for_date == next_day

    all_tickets = Ticket.objects.filter(driver=driver).order_by("valid_for_date")
    assert all_tickets.count() == 2
    assert all_tickets[0].status == Ticket.Status.INACTIVE
    assert all_tickets[1].status == Ticket.Status.ACTIVE


# ---------------------------------------------------------------------------
# QR Code Validation
# ---------------------------------------------------------------------------

QR_VALIDATE_URL = "/api/v1/ticket/agents/validate"


@pytest.mark.django_db
def test_qr_validate_active_ticket(auth_agent_client, active_ticket, agent):
    response = auth_agent_client.get(
        QR_VALIDATE_URL, {"qr_code": str(active_ticket.qr_code)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["ticket_number"] == active_ticket.ticket_number
    assert data["status"] == "ACTIVE"

    active_ticket.refresh_from_db()
    assert active_ticket.validated_by == agent
    assert active_ticket.validated_at is not None


@pytest.mark.django_db
def test_qr_validate_invalid_qr_code(auth_agent_client):
    response = auth_agent_client.get(
        QR_VALIDATE_URL, {"qr_code": str(uuid.uuid4())}
    )
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_qr_validate_missing_qr_code(auth_agent_client):
    response = auth_agent_client.get(QR_VALIDATE_URL)
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_qr_validate_expired_ticket(auth_agent_client, active_ticket):
    active_ticket.valid_for_date = timezone.localdate() - timedelta(days=1)
    active_ticket.save()
    response = auth_agent_client.get(
        QR_VALIDATE_URL, {"qr_code": str(active_ticket.qr_code)}
    )
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_qr_validate_area_mismatch(auth_agent_other_area_client, active_ticket):
    response = auth_agent_other_area_client.get(
        QR_VALIDATE_URL, {"qr_code": str(active_ticket.qr_code)}
    )
    assert response.status_code == 403
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_qr_validate_unauthenticated(api_client, active_ticket):
    response = api_client.get(
        QR_VALIDATE_URL, {"qr_code": str(active_ticket.qr_code)}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Fallback Validation (phone number)
# ---------------------------------------------------------------------------

FALLBACK_URL = "/api/v1/ticket/agents/validate/fallback"


@pytest.mark.django_db
def test_fallback_validate_active_ticket(auth_agent_client, active_ticket, driver, agent):
    response = auth_agent_client.get(
        FALLBACK_URL, {"phone_number": driver.phone_number}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["ticket_number"] == active_ticket.ticket_number
    assert data["status"] == "ACTIVE"

    active_ticket.refresh_from_db()
    assert active_ticket.validated_by == agent
    assert active_ticket.validated_at is not None


@pytest.mark.django_db
def test_fallback_validate_no_ticket_today(auth_agent_client):
    # Driver with no ticket
    area = Area.objects.get_or_create(name="Surulere", state="Lagos")[0]
    user = User.objects.create(phone_number="08099999999", role="driver", is_active=True)
    DriverProfile.objects.create(
        user=user,
        full_name="No Ticket Driver",
        area=area,
        lga="Surulere",
        phone_number="08099999999",
        license_number="ZZZ99999",
        pin_hash="hashed",
        pin_set=True,
        is_phone_verified=True,
        verified=True,
    )
    response = auth_agent_client.get(FALLBACK_URL, {"phone_number": "08099999999"})
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_fallback_validate_missing_phone(auth_agent_client):
    response = auth_agent_client.get(FALLBACK_URL)
    assert response.status_code == 400
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_fallback_validate_area_mismatch(auth_agent_other_area_client, active_ticket, driver):
    response = auth_agent_other_area_client.get(
        FALLBACK_URL, {"phone_number": driver.phone_number}
    )
    assert response.status_code == 400
    assert response.json()["valid"] is False
    error = str(response.json()["error"])
    assert "not authorised" in error.lower() or "authorised" in error.lower()


@pytest.mark.django_db
def test_fallback_validate_unauthenticated(api_client, driver):
    response = api_client.get(FALLBACK_URL, {"phone_number": driver.phone_number})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Ticket Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_URL = "/api/v1/ticket/all"


@pytest.mark.django_db
def test_dashboard_with_active_ticket(auth_driver_client, active_ticket):
    response = auth_driver_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["can_work_today"] is True
    assert data["active_ticket"]["ticket_number"] == active_ticket.ticket_number


@pytest.mark.django_db
def test_dashboard_no_ticket(auth_driver_client):
    response = auth_driver_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["can_work_today"] is False
    assert data["active_ticket"] is None


@pytest.mark.django_db
def test_dashboard_recent_tickets_included(auth_driver_client, driver, area):
    today = timezone.localdate()
    # Create a ticket dated 3 days ago
    old_payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today - timedelta(days=3),
    )
    Ticket.objects.create(
        payment=old_payment,
        driver=driver,
        area=area,
        ticket_number=f"KWP-LAG-OLD-{uuid.uuid4().hex[:6].upper()}",
        valid_for_date=today - timedelta(days=3),
        status=Ticket.Status.INACTIVE,
    )
    response = auth_driver_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    assert len(response.json()["recent_tickets"]) >= 1


@pytest.mark.django_db
def test_dashboard_unauthenticated(api_client):
    response = api_client.get(DASHBOARD_URL)
    assert response.status_code == 401
