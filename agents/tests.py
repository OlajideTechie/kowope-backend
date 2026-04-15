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
        lga="Surulere",
        phone_number="08031112222",
        license_number="LIC12345",
        pin_hash="hashed",
        pin_set=True,
        is_phone_verified=True,
        verified=True,
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
