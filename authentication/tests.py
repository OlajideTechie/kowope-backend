import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from authentication.services.otp_service import OTPService
from utils.phone import normalize_phone

User = get_user_model()

# -------------------------------
# Fixtures
# -------------------------------
@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user():
    def _create_user(phone_number="08031234567", password="1234"):
        user = User.objects.create_user(
            phone_number=normalize_phone(phone_number),
            password=password
        )
        # Make sure driver profile exists
        user.driver_profile.verified = True
        user.driver_profile.save()
        return user
    return _create_user

@pytest.fixture
def generate_otp():
    def _generate_otp(phone_number, purpose="signup"):
        return OTPService.create_otp(phone_number=normalize_phone(phone_number), purpose=purpose)
    return _generate_otp

# -------------------------------
# Signup Tests
# -------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize(
    "phone_number, full_name, pin, expected_status",
    [
        ("08031234567", "Test User", "1234", 201),
        ("08039876543", "Another User", "5678", 201),
    ]
)
def test_signup(api_client, phone_number, full_name, pin, expected_status):
    data = {"phone_number": phone_number, "full_name": full_name, "pin": pin}
    response = api_client.post("/api/v1/auth/driver/signup", data, format="json")
    assert response.status_code == expected_status
    assert response.json()["success"] is True

@pytest.mark.django_db
def test_signup_existing_user(api_client, create_user):
    create_user(phone_number="08031234567")
    data = {"phone_number": "08031234567", "full_name": "Test User", "pin": "1234"}
    response = api_client.post("/api/v1/auth/driver/signup", data, format="json")
    assert response.status_code == 400
    assert "already exists" in response.json()["message"]

# -------------------------------
# OTP Verification Tests
# -------------------------------
@pytest.mark.django_db
def test_otp_verification_flow(api_client, create_user, generate_otp):
    user = create_user("08031234567")
    otp = generate_otp(user.phone_number)

    # Correct OTP
    data = {"phone_number": user.phone_number, "code": otp.code}
    response = api_client.post("/api/v1/auth/driver/verify-otp", data, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Reusing OTP should fail
    response = api_client.post("/api/v1/auth/driver/verify-otp", data, format="json")
    assert response.status_code == 400
    assert response.json()["success"] is False

# -------------------------------
# Login Tests
# -------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize(
    "pin, expected_success",
    [
        ("1234", True),
        ("0000", False)
    ]
)
def test_login_flow(api_client, create_user, pin, expected_success):
    user = create_user("08031234567")
    data = {"phone_number": user.phone_number, "pin": pin}
    response = api_client.post("/api/v1/auth/driver/login", data, format="json")
    assert response.json()["success"] is expected_success
    if expected_success:
        assert "access_token" in response.json()["result"]
        assert "refresh_token" in response.json()["result"]

# -------------------------------
# Reset PIN Tests (Combined Endpoint)
# -------------------------------
@pytest.mark.django_db
def test_reset_pin_flow(api_client, create_user, generate_otp):
    user = create_user("08031234567")

    # Phase 1: Initiate OTP
    data = {"phone_number": user.phone_number}
    response = api_client.post("/api/v1/auth/driver/reset-pin", data, format="json")
    assert response.status_code == 200
    assert response.json()["message"] == "OTP sent to your phone."

    # Generate OTP manually to simulate delivery
    otp = generate_otp(user.phone_number, purpose="reset_pin")

    # Phase 2: Complete reset
    data = {
        "phone_number": user.phone_number,
        "otp_code": otp.code,
        "new_pin": "5678"
    }
    response = api_client.post("/api/v1/auth/driver/reset-pin", data, format="json")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Login with new PIN
    login_data = {"phone_number": user.phone_number, "pin": "5678"}
    response = api_client.post("/api/v1/auth/driver/login", login_data, format="json")
    assert response.json()["success"] is True
