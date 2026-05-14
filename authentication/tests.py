import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from services.otp_service import OTPService
from authentication.models import AdminProfile, AgentProfile, DriverProfile
from common.models import Area
from utils.phone import normalize_phone

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
def lagos_area(db):
    return Area.objects.create(name="Ikeja", lga="Ikeja", state="Lagos")


@pytest.fixture
def create_user(lagos_area):
    """
    Creates a User + DriverProfile directly (bypasses the API).
    Stores phone_number in E164 format on both models, matching real signup behavior.
    Pass is_phone_verified=False to test OTP flow.
    """
    def _create_user(phone_number="08031234567", pin="2468", is_phone_verified=True):
        normalized = normalize_phone(phone_number)
        user = User.objects.create(
            phone_number=normalized,
            role="driver",
            is_active=True,
        )
        driver = DriverProfile.objects.create(
            user=user,
            full_name="Test Driver",
            area=lagos_area,
            phone_number=normalized,
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
        with patch("services.sms_service.SMSService.send_otp"):
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
def test_signup(api_client, lagos_area, phone_number, full_name, pin):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": phone_number,
        "full_name": full_name,
        "pin": pin,
        "confirm_pin": pin,
        "area": str(lagos_area.id),
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    with patch("cloudinary.uploader.upload", return_value=CLOUDINARY_MOCK), \
         patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 201
    assert response.json()["success"] is True


@pytest.mark.django_db
def test_signup_existing_phone(api_client, lagos_area, create_user):
    create_user(phone_number="08031234567")
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "2468",
        "confirm_pin": "2468",
        "area": str(lagos_area.id),
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    with patch("cloudinary.uploader.upload", return_value=CLOUDINARY_MOCK), \
         patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 400
    assert "Phone number already registered" in str(response.json())


@pytest.mark.django_db
def test_signup_weak_pin_rejected(api_client, lagos_area):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "1234",
        "confirm_pin": "1234",
        "area": str(lagos_area.id),
        "license_number": "ABCDE12",
        "document_type": "nin",
        "document_file": doc,
    }
    response = api_client.post("/api/v1/auth/driver/signup", data, format="multipart")
    assert response.status_code == 400
    assert "weak" in str(response.json()).lower()


@pytest.mark.django_db
def test_signup_pin_mismatch_rejected(api_client, lagos_area):
    doc = SimpleUploadedFile("doc.jpg", b"fake content", content_type="image/jpeg")
    data = {
        "phone_number": "08031234567",
        "full_name": "Test User",
        "pin": "2468",
        "confirm_pin": "9999",
        "area": str(lagos_area.id),
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

LOCAL_PHONE = "08031234567"
VERIFY_OTP_URL = "/api/v1/auth/driver/verify-otp"


@pytest.mark.django_db
def test_otp_verification_flow(api_client, create_user, generate_otp):
    user = create_user(LOCAL_PHONE, is_phone_verified=False)
    otp = generate_otp(user.phone_number)

    data = {"phone_number": LOCAL_PHONE, "code": otp.code}
    response = api_client.post(VERIFY_OTP_URL, data, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Reusing the same OTP must fail
    response = api_client.post(VERIFY_OTP_URL, data, format="json")
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_otp_already_verified_rejected(api_client, create_user, generate_otp):
    create_user(LOCAL_PHONE, is_phone_verified=True)
    otp = generate_otp(normalize_phone(LOCAL_PHONE))
    data = {"phone_number": LOCAL_PHONE, "code": otp.code}
    response = api_client.post(VERIFY_OTP_URL, data, format="json")
    assert response.status_code == 400
    assert "already verified" in response.json()["message"]


@pytest.mark.django_db
def test_otp_verify_unknown_phone_returns_404(api_client, generate_otp):
    """No user registered → 404 instead of 500."""
    otp = generate_otp(normalize_phone(LOCAL_PHONE))
    data = {"phone_number": LOCAL_PHONE, "code": otp.code}
    response = api_client.post(VERIFY_OTP_URL, data, format="json")
    assert response.status_code == 404
    assert response.json()["success"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("phone,code", [
    ("0803123456", "123456"),    # too short — not a valid NG number
    ("080312345678", "123456"),  # too long — not a valid NG number
    ("not-a-phone", "123456"),   # garbage
    (LOCAL_PHONE, "12345"),      # 5-digit code
    (LOCAL_PHONE, "ABCDEF"),     # non-numeric code
])
def test_otp_verify_invalid_input_rejected(api_client, phone, code):
    response = api_client.post(VERIFY_OTP_URL, {"phone_number": phone, "code": code}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_otp_verify_accepts_e164_format(api_client, create_user, generate_otp):
    """Users sending +2348031234567 instead of 08031234567 must be accepted."""
    user = create_user(LOCAL_PHONE, is_phone_verified=False)
    otp = generate_otp(user.phone_number)
    data = {"phone_number": "+2348031234567", "code": otp.code}
    response = api_client.post(VERIFY_OTP_URL, data, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True


# -------------------------------
# Resend OTP Tests
# -------------------------------

RESEND_OTP_URL = "/api/v1/auth/driver/resend-otp"


@pytest.mark.django_db
def test_resend_otp_success(api_client, create_user):
    create_user(LOCAL_PHONE, is_phone_verified=False)
    with patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post(RESEND_OTP_URL, {"phone_number": LOCAL_PHONE}, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.django_db
def test_resend_otp_unknown_phone_rejected(api_client):
    response = api_client.post(RESEND_OTP_URL, {"phone_number": LOCAL_PHONE}, format="json")
    assert response.status_code == 400
    assert "No driver profile found" in str(response.json())


@pytest.mark.django_db
def test_resend_otp_already_verified_rejected(api_client, create_user):
    create_user(LOCAL_PHONE, is_phone_verified=True)
    response = api_client.post(RESEND_OTP_URL, {"phone_number": LOCAL_PHONE}, format="json")
    assert response.status_code == 400
    assert "already verified" in str(response.json()).lower()


@pytest.mark.django_db
def test_resend_otp_no_auth_required(api_client, create_user):
    """AllowAny — unauthenticated requests must succeed."""
    create_user(LOCAL_PHONE, is_phone_verified=False)
    with patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post(RESEND_OTP_URL, {"phone_number": LOCAL_PHONE}, format="json")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("phone", [
    "0803123456",    # too short — not a valid NG number
    "080312345678",  # too long — not a valid NG number
    "not-a-phone",   # garbage
])
def test_resend_otp_invalid_phone_rejected(api_client, phone):
    response = api_client.post(RESEND_OTP_URL, {"phone_number": phone}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_resend_otp_accepts_e164_format(api_client, create_user):
    """Users sending +2348031234567 instead of 08031234567 must be accepted."""
    create_user(LOCAL_PHONE, is_phone_verified=False)
    with patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post(RESEND_OTP_URL, {"phone_number": "+2348031234567"}, format="json")
    assert response.status_code == 200


# -------------------------------
# Token Refresh Tests
# -------------------------------

REFRESH_URL = "/api/v1/auth/token/refresh"


@pytest.mark.django_db
def test_cookie_token_refresh_rotates_cookie(api_client, create_user):
    user = create_user(LOCAL_PHONE, pin="2468")
    login_resp = api_client.post(
        "/api/v1/auth/driver/login",
        {"phone_number": user.phone_number, "pin": "2468"},
        format="json",
    )
    original_refresh = login_resp.cookies["refresh_token"].value
    api_client.cookies["refresh_token"] = original_refresh

    refresh_resp = api_client.post(REFRESH_URL)
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    assert "refresh_token" in refresh_resp.cookies
    assert refresh_resp.cookies["refresh_token"].value != original_refresh


@pytest.mark.django_db
def test_cookie_token_refresh_no_cookie_returns_401(api_client):
    response = api_client.post(REFRESH_URL)
    assert response.status_code == 401


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
    user = create_user(LOCAL_PHONE, pin="2468")
    data = {"phone_number": user.phone_number, "pin": pin}
    response = api_client.post("/api/v1/auth/driver/login", data, format="json")
    if expected_success:
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "refresh_token" in response.cookies
        assert response.cookies["refresh_token"]["httponly"]
        assert "access_token" in response.json()["result"]
        assert "refresh_token" not in response.json()["result"]
        assert "expires_in" in response.json()["result"]
    else:
        assert response.status_code == 400


@pytest.mark.django_db
def test_driver_profile_accessible_via_cookie(api_client, create_user):
    """Login returns access_token in response; follow-up authenticated request via header succeeds."""
    user = create_user(LOCAL_PHONE, pin="2468")
    login_resp = api_client.post(
        "/api/v1/auth/driver/login",
        {"phone_number": user.phone_number, "pin": "2468"},
        format="json",
    )
    assert login_resp.status_code == 200
    # Client can use the access_token from response for authenticated requests
    access_token = login_resp.json()["result"]["access_token"]
    # Set it in Authorization header for subsequent requests
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    profile_resp = api_client.get("/api/v1/auth/driver/me")
    assert profile_resp.status_code == 200


@pytest.mark.django_db
def test_logout_clears_cookies(api_client, create_user):
    user = create_user(LOCAL_PHONE, pin="2468")
    login_resp = api_client.post(
        "/api/v1/auth/driver/login",
        {"phone_number": user.phone_number, "pin": "2468"},
        format="json",
    )
    api_client.cookies["refresh_token"] = login_resp.cookies["refresh_token"].value

    logout_resp = api_client.post("/api/v1/auth/driver/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.cookies["refresh_token"].value == ""


@pytest.mark.django_db
def test_logout_without_cookie_returns_200(api_client):
    """AllowAny + no cookie → graceful 200, not 401."""
    response = api_client.post("/api/v1/auth/driver/logout")
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.django_db
def test_login_unverified_phone_rejected(api_client, create_user):
    user = create_user(LOCAL_PHONE, is_phone_verified=False)
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
    user = create_user(LOCAL_PHONE, pin="2468")

    # Phase 1: initiate — just phone number
    with patch("services.sms_service.SMSService.send_otp"):
        response = api_client.post(
            "/api/v1/auth/driver/forgot-pin",
            {"phone_number": LOCAL_PHONE},
            format="json",
        )
    assert response.status_code == 200
    assert response.json()["message"] == "OTP has been sent to your phone."

    otp = generate_otp(user.phone_number, purpose="reset_pin")

    # Phase 2: verify OTP + set new PIN
    response = api_client.post(
        "/api/v1/auth/driver/forgot-pin",
        {"phone_number": LOCAL_PHONE, "otp_code": otp.code, "new_pin": "5867", "confirm_pin": "5867"},
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

    def test_admin_login_sets_cookies(self, api_client, admin_user):
        response = api_client.post(
            ADMIN_LOGIN_URL,
            {"email": "admin@kowope.com", "password": "adminpass123"},
            format="json",
        )
        assert response.status_code == 200
        assert "refresh_token" in response.cookies
        assert response.cookies["refresh_token"]["httponly"]
        assert "access_token" in response.json()["result"]
        assert "expires_in" in response.json()["result"]

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

    def test_agent_login_sets_cookies(self, api_client, agent_user):
        response = api_client.post(
            AGENT_LOGIN_URL,
            {"email": "agent@kowope.com", "password": "agentpass123"},
            format="json",
        )
        assert response.status_code == 200
        assert "refresh_token" in response.cookies
        assert response.cookies["refresh_token"]["httponly"]
        assert "access_token" in response.json()["result"]
        assert "expires_in" in response.json()["result"]

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
