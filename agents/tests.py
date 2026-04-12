import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.models import AdminProfile, AgentProfile
from common.models import Area

User = get_user_model()

INVITE_URL = "/api/v1/invite-agent"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


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
def auth_admin_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
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
