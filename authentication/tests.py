import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from services.otp_service import OTPService
from authentication.models import AdminProfile, AgentProfile, DriverProfile

User = get_user_model()

CLOUDINARY_MOCK = {
    "public_id": "test/doc",
    "version": 123,
    "format": "jpg",
    "type": "upload",
    "resource_type": "auto",
    "url": "http://res.cloudinary.com/test/doc.jpg",
    "secure_url": "https://res.cloudinary.com/test/doc.jpg",
}

# -------------------------------
# Fixtures
# -------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    """
    Creates a User + DriverProfile directly (bypasses the API).
    phone_number is stored raw (11 digits) on User so login/OTP lookups work.
    DriverProfile.save() normalises the phone to E164 internally.
    is_phone_verified=True by default so login works; pass False for OTP flow tests.
    """
    def _create_user(phone_number="08031234567", pin="2468", is_phone_verified=True):
        user = User.objects.create(
            phone_number=phone_number,
            role="driver",
            is_active=True,
        )
        driver = DriverProfile.objects.create(
            user=user,
            full_name="Test Driver",
            area="Lagos",
            lga="Ikeja",
            phone_number=phone_number,
            license_number="ABCDE12",
            is_phone_verified=is_phone_verified,
            verified=is_phone_verified,
        )
        driver.set_pin(pin)
        return user
    return _create_user


@pytest.fixture
def generate_otp():
    def _generate_otp(phone_number, purpose="signup"):
        return OTPService.create_otp(phone_number=phone_number, purpose=purpose)
    return _generate_otp


# -------------------------------
# Signup Tests
# -------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "phone_number, full_name, pin",
    [
        ("08031234567", "Test User", "2468"),
        ("08039876543", "Another User", "3579"),
    ],
)
def test_signup(api_client, phone_number, full_name, pin):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": phone_number,
        "full_name": full_name,
        "pin": pin,
        "confirm_pin": pin,
        "area": "Lagos",
        "lga": "Ikeja",
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    with patch("cloudinary.uploader.upload", return_value=CLOUDINARY_MOCK):
        response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 201
    assert response.json()["success"] is True


@pytest.mark.django_db
def test_signup_existing_phone(api_client, create_user):
    create_user(phone_number="08031234567")
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "2468",
        "confirm_pin": "2468",
        "area": "Lagos",
        "lga": "Ikeja",
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    with patch("cloudinary.uploader.upload", return_value=CLOUDINARY_MOCK):
        response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 400
    assert "Phone number already registered" in str(response.json())


@pytest.mark.django_db
def test_signup_weak_pin_rejected(api_client):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "1234",
        "confirm_pin": "1234",
        "area": "Lagos",
        "lga": "Ikeja",
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 400
    assert "weak" in str(response.json()).lower()


@pytest.mark.django_db
def test_signup_pin_mismatch_rejected(api_client):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "2468",
        "confirm_pin": "9999",
        "area": "Lagos",
        "lga": "Ikeja",
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 400
    assert "match" in str(response.json()).lower()


# -------------------------------
# OTP Verification Tests
# -------------------------------

@pytest.mark.django_db
def test_otp_verification_flow(api_client, create_user, generate_otp):
    # User must NOT be verified yet
    user = create_user("08031234567", is_phone_verified=False)
    otp = generate_otp(user.phone_number)

    data = {"phone_number": user.phone_number, "code": otp.code}
    response = api_client.post("/api/v1/auth/driver/verify-otp", data, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Reusing the same OTP must fail
    response = api_client.post("/api/v1/auth/driver/verify-otp", data, format="json")
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_otp_already_verified_rejected(api_client, create_user, generate_otp):
    user = create_user("08031234567", is_phone_verified=True)
    otp = generate_otp(user.phone_number)
    data = {"phone_number": user.phone_number, "code": otp.code}
    response = api_client.post("/api/v1/auth/driver/verify-otp", data, format="json")
    assert response.status_code == 400
    assert "already verified" in response.json()["message"]


# -------------------------------
# Login Tests
# -------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize(
    "pin, expected_success",
    [
        ("2468", True),   # correct pin
        ("0000", False),  # wrong pin
    ],
)
def test_login_flow(api_client, create_user, pin, expected_success):
    user = create_user("08031234567", pin="2468")
    data = {"phone_number": user.phone_number, "pin": pin}
    response = api_client.post("/api/v1/auth/driver/login", data, format="json")
    if expected_success:
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "access_token" in response.json()["result"]
        assert "refresh_token" in response.json()["result"]
    else:
        assert response.status_code == 400


@pytest.mark.django_db
def test_login_unverified_phone_rejected(api_client, create_user):
    user = create_user("08031234567", is_phone_verified=False)
    response = api_client.post(
        "/api/v1/auth/driver/login",
        {"phone_number": user.phone_number, "pin": "2468"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["success"] is False


# -------------------------------
# Reset PIN Tests
# -------------------------------

@pytest.mark.django_db
def test_reset_pin_flow(api_client, create_user, generate_otp):
    user = create_user("08031234567", pin="2468")

    # Phase 1: initiate — just phone number
    response = api_client.post(
        "/api/v1/auth/driver/reset-pin",
        {"phone_number": user.phone_number},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["message"] == "OTP has been sent to your phone."

    # Manually generate OTP to simulate delivery
    otp = generate_otp(user.phone_number, purpose="reset_pin")

    # Phase 2: verify OTP + set new PIN
    response = api_client.post(
        "/api/v1/auth/driver/reset-pin",
        {"phone_number": user.phone_number, "otp_code": otp.code, "new_pin": "5867"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Login with new PIN
    response = api_client.post(
        "/api/v1/auth/driver/login",
        {"phone_number": user.phone_number, "pin": "5867"},
        format="json",
    )
    assert response.json()["success"] is True


# ---------------------------------------------------------------------------
# Fixtures: Admin & Agent
# ---------------------------------------------------------------------------

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
def super_admin_user(db):
    user = User.objects.create(
        email="superadmin@kowope.com",
        role="super_admin",
        is_active=True,
        is_staff=True,
    )
    user.set_password("superpass123")
    user.save(update_fields=["password"])
    AdminProfile.objects.create(user=user, level="super_admin")
    return user


@pytest.fixture
def agent_user(db):
    user = User.objects.create(
        email="agent@kowope.com",
        role="agent",
        is_active=True,
    )
    user.set_password("agentpass123")
    user.save(update_fields=["password"])
    AgentProfile.objects.create(user=user, status="approved")
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


ADMIN_LOGIN_URL = "/api/v1/auth/admin/login"
AGENT_LOGIN_URL = "/api/v1/auth/agent/login"


# ---------------------------------------------------------------------------
# Unit Tests: StaffLoginSerializer
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffLoginSerializer:

    def test_valid_credentials_return_user(self, admin_user):
        from authentication.serializers import StaffLoginSerializer
        s = StaffLoginSerializer(data={"email": "admin@kowope.com", "password": "adminpass123"})
        assert s.is_valid(), s.errors
        assert s.validated_data == admin_user

    def test_wrong_password_rejected(self, admin_user):
        from authentication.serializers import StaffLoginSerializer
        s = StaffLoginSerializer(data={"email": "admin@kowope.com", "password": "wrongpassword"})
        assert not s.is_valid()

    def test_nonexistent_email_rejected(self):
        from authentication.serializers import StaffLoginSerializer
        s = StaffLoginSerializer(data={"email": "nobody@kowope.com", "password": "pass"})
        assert not s.is_valid()

    def test_missing_fields_rejected(self):
        from authentication.serializers import StaffLoginSerializer
        assert not StaffLoginSerializer(data={"email": "admin@kowope.com"}).is_valid()
        assert not StaffLoginSerializer(data={"password": "adminpass123"}).is_valid()
        assert not StaffLoginSerializer(data={}).is_valid()


# ---------------------------------------------------------------------------
# Integration Tests: AdminLoginView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminLoginView:

    def test_admin_login_returns_tokens(self, api_client, admin_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "adminpass123"},
            format="json",
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert "access_token" in result
        assert "refresh_token" in result
        assert "expires_in" in result

    def test_admin_login_returns_correct_level(self, api_client, admin_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "adminpass123"},
            format="json",
        )
        assert response.json()["result"]["level"] == "admin"

    def test_super_admin_can_login(self, api_client, super_admin_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "superadmin@kowope.com", "password": "superpass123"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["result"]["level"] == "super_admin"

    def test_wrong_password_rejected(self, api_client, admin_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "wrongpassword"},
            format="json",
        )
        assert response.status_code == 400

    def test_non_admin_role_denied(self, api_client, driver_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "driver@kowope.com", "password": "driverpass123"},
            format="json",
        )
        assert response.status_code == 403

    def test_agent_cannot_use_admin_login(self, api_client, agent_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "agentpass123"},
            format="json",
        )
        assert response.status_code == 403

    def test_missing_fields_rejected(self, api_client):
        response = api_client.post(ADMIN_LOGIN_URL, {}, format="json")
        assert response.status_code == 400

    def test_inactive_admin_denied(self, api_client, admin_user):
        admin_user.is_active = False
        admin_user.save(update_fields=["is_active"])
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "adminpass123"},
            format="json",
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Integration Tests: AgentLoginView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAgentLoginView:

    def test_agent_login_returns_tokens(self, api_client, agent_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "agentpass123"},
            format="json",
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert "access_token" in result
        assert "refresh_token" in result
        assert "expires_in" in result

    def test_agent_login_returns_profile_status(self, api_client, agent_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "agentpass123"},
            format="json",
        )
        assert response.json()["result"]["status"] == "approved"

    def test_wrong_password_rejected(self, api_client, agent_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "wrongpassword"},
            format="json",
        )
        assert response.status_code == 400

    def test_admin_cannot_use_agent_login(self, api_client, admin_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "adminpass123"},
            format="json",
        )
        assert response.status_code == 403

    def test_driver_cannot_use_agent_login(self, api_client, driver_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "driver@kowope.com", "password": "driverpass123"},
            format="json",
        )
        assert response.status_code == 403

    def test_agent_without_profile_denied(self, api_client, db):
        user = User.objects.create(email="noprofile@kowope.com", role="agent", is_active=True)
        user.set_password("pass1234")
        user.save(update_fields=["password"])
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "noprofile@kowope.com", "password": "pass1234"},
            format="json",
        )
        assert response.status_code == 403

    def test_missing_fields_rejected(self, api_client):
        response = api_client.post(AGENT_LOGIN_URL, {}, format="json")
        assert response.status_code == 400

    def test_inactive_agent_denied(self, api_client, agent_user):
        agent_user.is_active = False
        agent_user.save(update_fields=["is_active"])
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "agentpass123"},
            format="json",
        )
        assert response.status_code == 400
