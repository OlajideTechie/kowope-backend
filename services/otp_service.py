from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random

from authentication.models import OTP
from services.sms_service import SMSService
from utils.phone import normalize_phone


class OTPService:

    @staticmethod
    def generate_otp() -> str:
        if getattr(settings, "USE_STATIC_OTP", False):
            return getattr(settings, "STATIC_OTP_CODE", "123456")
        return str(random.randint(100000, 999999))

    @staticmethod
    def create_otp(phone_number: str, purpose: str):
        phone_number = normalize_phone(phone_number)

        OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)

        code = settings.STATIC_OTP_CODE if getattr(settings, "USE_STATIC_OTP", False) else OTPService.generate_otp()

        otp = OTP.objects.create(
            phone_number=phone_number,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(seconds=getattr(settings, "OTP_EXPIRY_SECONDS", 300)),
            is_used=False
        )

        return otp

    @staticmethod
    def verify_otp(phone_number: str, code: str, purpose: str):
        phone_number = normalize_phone(phone_number)

        otp = OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by("-created_at").first()

        if not otp:
            return {"success": False, "message": "Invalid or expired OTP"}
        
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        return {"success": True, "message": "OTP verified successfully" }

    @staticmethod
    def resend_otp(phone_number: str, purpose: str) -> dict:
        phone_number = normalize_phone(phone_number)

        # Invalidate all previous unused OTPs
        OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)

        # Create & send new OTP
        otp = OTPService.create_otp(phone_number, purpose)


        return {
            "success": True,
            "message": "A new OTP has been sent",
            "otp_id": otp.purpose
        }
