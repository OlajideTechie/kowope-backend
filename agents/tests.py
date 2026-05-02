import uuid
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.models import AdminProfile, AgentProfile, DriverProfile
from common.models import Area
from payments.models import Payment
from ticket.models import Ticket

User = get_user_model()

INVITE_URL = "/api/v1/invite-agent"
DASHBOARD_URL = "/api/v1/agents/dashboard"
ADMIN_DASHBOARD_URL = "/api/v1/admin/dashboard"
ADMIN_REVENUE_URL = "/api/v1/admin/revenue"
ADMIN_DRIVERS_URL = "/api/v1/admin/drivers"
ADMIN_AGENTS_URL = "/api/v1/admin/agents"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def area(db):
    return Area.objects.create(name="Surulere", lga="Surulere", state="Lagos")


@pytest.fixture
def other_area(db):
    return Area.objects.create(name="Ikeja", lga="Ikeja", state="Lagos")


@pytest.fixture
def admin_user(db):
    user = User.objects.create(
        email="admin@kowope.com",
        role="admin",
        is_active=True,
        is_staff=True,
    )
    user.set_password("adminpass123")
    user.save(update_fields=["password"])
    AdminProfile.objects.create(user=user, level="admin")
    return user


@pytest.fixture
def driver_user(db):
    user = User.objects.create(
        email="driver@kowope.com",
        role="driver",
        is_active=True,
    )
    user.set_password("driverpass123")
    user.save(update_fields=["password"])
    return user


@pytest.fixture
def agent(db, area):
    user = User.objects.create(email="dashagent@kowope.com", role="agent", is_active=True)
    user.set_password("agentpass123")
    user.save(update_fields=["password"])
    return AgentProfile.objects.create(user=user, area=area, status="approved", full_name="Dash Agent")


@pytest.fixture
def driver(db, area):
    user = User.objects.create(phone_number="08031112222", role="driver", is_active=True)
    return DriverProfile.objects.create(
        user=user,
        full_name="Test Driver",
        area=area,
        phone_number="08031112222",
        license_number="LIC12345",
        pin_hash="hashed",
        pin_set=True,
        is_phone_verified=True,
        verified=False,
    )


@pytest.fixture
def auth_admin_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def auth_agent_client(api_client, agent):
    refresh = RefreshToken.for_user(agent.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


# ---------------------------------------------------------------------------
# Unit Tests: InviteAgentSerializer
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInviteAgentSerializer:

    def test_valid_email_passes(self):
        from agents.serializers import InviteAgentSerializer
        s = InviteAgentSerializer(data={"email": "newagent@test.com"})
        assert s.is_valid(), s.errors

    def test_invalid_email_format_rejected(self):
        from agents.serializers import InviteAgentSerializer
        s = InviteAgentSerializer(data={"email": "not-an-email"})
        assert not s.is_valid()
        assert "email" in s.errors

    def test_existing_user_email_rejected(self, admin_user):
        from agents.serializers import InviteAgentSerializer
        s = InviteAgentSerializer(data={"email": admin_user.email})
        assert not s.is_valid()
        assert "already exists" in str(s.errors)

    def test_missing_email_rejected(self):
        from agents.serializers import InviteAgentSerializer
        s = InviteAgentSerializer(data={})
        assert not s.is_valid()
        assert "email" in s.errors


# ---------------------------------------------------------------------------
# Integration Tests: InviteAgentView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInviteAgentView:

    def test_unauthenticated_request_denied(self, api_client):
        response = api_client.post(INVITE_URL, {"email": "agent@test.com"}, format="json")
        assert response.status_code == 401

    def test_non_admin_role_denied(self, api_client, driver_user):
        refresh = RefreshToken.for_user(driver_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = api_client.post(INVITE_URL, {"email": "agent@test.com"}, format="json")
        assert response.status_code == 403

    @patch("services.invite_agent_service.send_mail")
    def test_admin_invites_agent_successfully(self, mock_mail, auth_admin_client):
        response = auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Agent invited successfully"

    @patch("services.invite_agent_service.send_mail")
    def test_invite_sends_one_email(self, mock_mail, auth_admin_client):
        auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        mock_mail.assert_called_once()

    @patch("services.invite_agent_service.send_mail")
    def test_invite_creates_user_with_agent_role(self, mock_mail, auth_admin_client):
        auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        user = User.objects.get(email="newagent@test.com")
        assert user.role == "agent"
        assert user.is_active is True

    @patch("services.invite_agent_service.send_mail")
    def test_invite_creates_agent_profile_with_invited_status(self, mock_mail, auth_admin_client):
        auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        user = User.objects.get(email="newagent@test.com")
        assert hasattr(user, "agent_profile")
        assert user.agent_profile.status == "invited"

    @patch("services.invite_agent_service.send_mail")
    def test_invite_records_invited_by(self, mock_mail, auth_admin_client, admin_user):
        auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        user = User.objects.get(email="newagent@test.com")
        assert user.agent_profile.invited_by == admin_user

    @patch("services.invite_agent_service.send_mail")
    def test_duplicate_invite_rejected(self, mock_mail, auth_admin_client):
        auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        response = auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        assert response.status_code == 400

    def test_missing_email_rejected(self, auth_admin_client):
        response = auth_admin_client.post(INVITE_URL, {}, format="json")
        assert response.status_code == 400

    def test_invalid_email_format_rejected(self, auth_admin_client):
        response = auth_admin_client.post(INVITE_URL, {"email": "not-an-email"}, format="json")
        assert response.status_code == 400

    @patch("services.invite_agent_service.send_mail")
    def test_invite_url_exposed_when_setting_enabled(self, mock_mail, auth_admin_client, settings):
        settings.RETURN_INVITE_LINK = True
        response = auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        assert "invite_url" in response.json()
        assert "complete-registration?token=" in response.json()["invite_url"]

    @patch("services.invite_agent_service.send_mail")
    def test_invite_url_hidden_when_setting_disabled(self, mock_mail, auth_admin_client, settings):
        settings.RETURN_INVITE_LINK = False
        response = auth_admin_client.post(INVITE_URL, {"email": "newagent@test.com"}, format="json")
        assert "invite_url" not in response.json()


# ---------------------------------------------------------------------------
# Agent Dashboard
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_dashboard_unauthenticated(api_client):
    response = api_client.get(DASHBOARD_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_dashboard_returns_agent_info(auth_agent_client, agent):
    response = auth_agent_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["agent"]["name"] == agent.full_name
    assert data["agent"]["area"] == agent.area.name
    assert data["agent"]["status"] == agent.status


@pytest.mark.django_db
def test_dashboard_summary_defaults_to_today(auth_agent_client):
    today = timezone.localdate().isoformat()
    response = auth_agent_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["date"] == today


@pytest.mark.django_db
def test_dashboard_counts_active_tickets_in_area(auth_agent_client, agent, driver, area):
    today = timezone.localdate()
    payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    Ticket.objects.create(
        payment=payment,
        driver=driver,
        area=area,
        ticket_number=f"KWP-TEST-{uuid.uuid4().hex[:6].upper()}",
        valid_for_date=today,
        status=Ticket.Status.ACTIVE,
    )
    response = auth_agent_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    assert response.json()["summary"]["total_active_in_area"] >= 1


@pytest.mark.django_db
def test_dashboard_lists_validated_tickets(auth_agent_client, agent, driver, area):
    today = timezone.localdate()
    payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    ticket = Ticket.objects.create(
        payment=payment,
        driver=driver,
        area=area,
        ticket_number=f"KWP-TEST-{uuid.uuid4().hex[:6].upper()}",
        valid_for_date=today,
        status=Ticket.Status.ACTIVE,
        validated_by=agent,
        validated_at=timezone.now(),
    )
    response = auth_agent_client.get(DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_validated_by_me"] == 1
    assert data["validated_tickets"][0]["ticket_number"] == ticket.ticket_number


@pytest.mark.django_db
def test_dashboard_date_filter(auth_agent_client, agent, driver, area):
    today = timezone.localdate()
    yesterday = today.replace(day=today.day - 1)

    payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=yesterday,
    )
    Ticket.objects.create(
        payment=payment,
        driver=driver,
        area=area,
        ticket_number=f"KWP-TEST-{uuid.uuid4().hex[:6].upper()}",
        valid_for_date=yesterday,
        status=Ticket.Status.INACTIVE,
        validated_by=agent,
        validated_at=timezone.now(),
    )

    # Today's dashboard — should not include yesterday's ticket
    response = auth_agent_client.get(DASHBOARD_URL)
    assert response.json()["summary"]["total_validated_by_me"] == 0

    # Yesterday's dashboard — should include it
    response = auth_agent_client.get(DASHBOARD_URL, {"date": yesterday.isoformat()})
    assert response.status_code == 200
    assert response.json()["summary"]["total_validated_by_me"] == 1


@pytest.mark.django_db
def test_dashboard_invalid_date_returns_400(auth_agent_client):
    response = auth_agent_client.get(DASHBOARD_URL, {"date": "not-a-date"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_dashboard_non_agent_denied(api_client, driver_user):
    refresh = RefreshToken.for_user(driver_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    response = api_client.get(DASHBOARD_URL)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Admin Dashboard Summary
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_admin_dashboard_unauthenticated(api_client):
    response = api_client.get(ADMIN_DASHBOARD_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_dashboard_non_admin_denied(api_client, driver_user):
    refresh = RefreshToken.for_user(driver_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    response = api_client.get(ADMIN_DASHBOARD_URL)
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_dashboard_returns_expected_shape(auth_admin_client):
    response = auth_admin_client.get(ADMIN_DASHBOARD_URL)
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "pending" in data
    assert "areas" in data
    assert "tickets_issued" in data["today"]
    assert "total_revenue" in data["today"]
    assert "validations_done" in data["today"]
    assert "drivers_awaiting_verification" in data["pending"]
    assert "agents_pending_approval" in data["pending"]
    assert "areas_without_agent" in data["pending"]


@pytest.mark.django_db
def test_admin_dashboard_counts_todays_tickets(auth_admin_client, driver, area):
    today = timezone.localdate()
    payment = Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=500,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    Ticket.objects.create(
        payment=payment,
        driver=driver,
        area=area,
        ticket_number=f"KWP-ADM-{uuid.uuid4().hex[:6].upper()}",
        valid_for_date=today,
        status=Ticket.Status.ACTIVE,
    )
    response = auth_admin_client.get(ADMIN_DASHBOARD_URL)
    data = response.json()
    assert data["today"]["tickets_issued"] >= 1
    assert float(data["today"]["total_revenue"]) >= 500


@pytest.mark.django_db
def test_admin_dashboard_pending_verification_count(auth_admin_client, driver):
    from authentication.models import DriverDocument
    import tempfile
    from django.core.files.uploadedfile import SimpleUploadedFile
    from unittest.mock import patch

    with patch("cloudinary.uploader.upload", return_value={"public_id": "test", "secure_url": "http://test.com/doc"}):
        DriverDocument.objects.create(
            driver=driver,
            document_type="nin",
            document_file="test_doc",
            status="pending",
        )
    response = auth_admin_client.get(ADMIN_DASHBOARD_URL)
    assert response.json()["pending"]["drivers_awaiting_verification"] >= 1


# ---------------------------------------------------------------------------
# Admin Revenue Breakdown
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_admin_revenue_unauthenticated(api_client):
    response = api_client.get(ADMIN_REVENUE_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_revenue_returns_daily_by_default(auth_admin_client):
    response = auth_admin_client.get(ADMIN_REVENUE_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "daily"
    assert "breakdown" in data
    assert "totals" in data
    assert "from" in data
    assert "to" in data


@pytest.mark.django_db
def test_admin_revenue_daily_includes_payment(auth_admin_client, driver):
    today = timezone.localdate()
    Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    response = auth_admin_client.get(ADMIN_REVENUE_URL, {"period": "daily"})
    data = response.json()
    assert int(data["totals"]["total_payments"]) >= 1
    assert float(data["totals"]["total_revenue"]) >= 1000


@pytest.mark.django_db
def test_admin_revenue_weekly_period(auth_admin_client):
    response = auth_admin_client.get(ADMIN_REVENUE_URL, {"period": "weekly"})
    assert response.status_code == 200
    assert response.json()["period"] == "weekly"


@pytest.mark.django_db
def test_admin_revenue_invalid_period(auth_admin_client):
    response = auth_admin_client.get(ADMIN_REVENUE_URL, {"period": "monthly"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_admin_revenue_invalid_date(auth_admin_client):
    response = auth_admin_client.get(ADMIN_REVENUE_URL, {"from": "bad-date"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_admin_revenue_area_filter(auth_admin_client, driver, area, other_area):
    today = timezone.localdate()
    Payment.objects.create(
        driver=driver,
        reference=str(uuid.uuid4()),
        amount=1000,
        currency="NGN",
        status=Payment.Status.SUCCESS,
        payment_date=today,
    )
    # Filter by other_area — should return zero payments
    response = auth_admin_client.get(ADMIN_REVENUE_URL, {"area": str(other_area.id)})
    assert response.status_code == 200
    assert response.json()["totals"]["total_payments"] == 0


# ---------------------------------------------------------------------------
# Admin Driver List
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_admin_drivers_unauthenticated(api_client):
    response = api_client.get(ADMIN_DRIVERS_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_drivers_returns_list(auth_admin_client, driver):
    response = auth_admin_client.get(ADMIN_DRIVERS_URL)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "drivers" in data
    assert data["count"] >= 1


@pytest.mark.django_db
def test_admin_drivers_verified_filter(auth_admin_client, driver):
    # driver fixture has verified=False
    response = auth_admin_client.get(ADMIN_DRIVERS_URL, {"verified": "false"})
    assert response.status_code == 200
    assert response.json()["count"] >= 1

    response = auth_admin_client.get(ADMIN_DRIVERS_URL, {"verified": "true"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_admin_drivers_area_filter(auth_admin_client, driver, area, other_area):
    response = auth_admin_client.get(ADMIN_DRIVERS_URL, {"area": str(area.id)})
    assert response.status_code == 200
    assert response.json()["count"] >= 1

    response = auth_admin_client.get(ADMIN_DRIVERS_URL, {"area": str(other_area.id)})
    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_admin_drivers_response_shape(auth_admin_client, driver):
    response = auth_admin_client.get(ADMIN_DRIVERS_URL)
    d = response.json()["drivers"][0]
    assert "id" in d
    assert "full_name" in d
    assert "phone_number" in d
    assert "license_number" in d
    assert "area" in d
    assert "verified" in d
    assert "registered_at" in d


# ---------------------------------------------------------------------------
# Admin Driver Detail
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_admin_driver_detail_unauthenticated(api_client, driver):
    response = api_client.get(f"{ADMIN_DRIVERS_URL}/{driver.id}")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_driver_detail_non_admin_denied(api_client, driver_user, driver):
    refresh = RefreshToken.for_user(driver_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    response = api_client.get(f"{ADMIN_DRIVERS_URL}/{driver.id}")
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_driver_detail_returns_profile(auth_admin_client, driver):
    response = auth_admin_client.get(f"{ADMIN_DRIVERS_URL}/{driver.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == driver.full_name
    assert data["license_number"] == driver.license_number


@pytest.mark.django_db
def test_admin_driver_detail_not_found(auth_admin_client):
    response = auth_admin_client.get(f"{ADMIN_DRIVERS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin Agent List
# ---------------------------------------------------------------------------

@pytest.fixture
def pending_agent(db, area):
    user = User.objects.create(email="pending@kowope.com", role="agent", is_active=True)
    return AgentProfile.objects.create(
        user=user, area=area, full_name="Pending Agent", status="pending_kyc"
    )


@pytest.mark.django_db
def test_admin_agent_list_unauthenticated(api_client):
    response = api_client.get(ADMIN_AGENTS_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_agent_list_non_admin_denied(api_client, driver_user):
    refresh = RefreshToken.for_user(driver_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    response = api_client.get(ADMIN_AGENTS_URL)
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_agent_list_returns_all(auth_admin_client, agent, pending_agent):
    response = auth_admin_client.get(ADMIN_AGENTS_URL)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "agents" in data
    assert data["count"] >= 2


@pytest.mark.django_db
def test_admin_agent_list_status_filter(auth_admin_client, agent, pending_agent):
    response = auth_admin_client.get(ADMIN_AGENTS_URL, {"status": "pending_kyc"})
    assert response.status_code == 200
    agents = response.json()["agents"]
    assert all(a["status"] == "pending_kyc" for a in agents)


@pytest.mark.django_db
def test_admin_agent_list_response_shape(auth_admin_client, agent):
    response = auth_admin_client.get(ADMIN_AGENTS_URL)
    a = response.json()["agents"][0]
    assert "id" in a
    assert "full_name" in a
    assert "email" in a
    assert "area" in a
    assert "lga" in a
    assert "status" in a


# ---------------------------------------------------------------------------
# Admin Agent Detail
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_admin_agent_detail_unauthenticated(api_client, agent):
    response = api_client.get(f"{ADMIN_AGENTS_URL}/{agent.id}")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_agent_detail_non_admin_denied(api_client, driver_user, agent):
    refresh = RefreshToken.for_user(driver_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    response = api_client.get(f"{ADMIN_AGENTS_URL}/{agent.id}")
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_agent_detail_returns_profile(auth_admin_client, agent):
    response = auth_admin_client.get(f"{ADMIN_AGENTS_URL}/{agent.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == agent.full_name
    assert data["email"] == agent.user.email
    assert data["status"] == agent.status
    assert "nin_document" in data
    assert "lga" in data


@pytest.mark.django_db
def test_admin_agent_detail_not_found(auth_admin_client):
    response = auth_admin_client.get(f"{ADMIN_AGENTS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404
