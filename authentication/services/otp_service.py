from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random

from authentication.models import OTP
from authentication.services.sms_service import SMSService


class OTPService:

    @staticmethod
    def normalize_phone(phone_number: str) -> str:
        return "".join(filter(str.isdigit, phone_number))

    @staticmethod
    def generate_otp():
        if settings.USE_STATIC_OTP:
            return settings.STATIC_OTP_CODE
        return str(random.randint(100000, 999999))

    @staticmethod
    def create_otp(phone_number, purpose):
        phone_number = OTPService.normalize_phone(phone_number)
        code = OTPService.generate_otp()

        otp = OTP.objects.create(
            phone_number=phone_number,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(
                seconds=settings.OTP_EXPIRY_SECONDS
            ),
            is_used=False
        )

        if settings.ENABLE_SMS_PROVIDER:
            SMSService.send_otp(phone_number, code)

        return otp

    @staticmethod
    def verify_otp(phone_number, code, purpose):
        phone_number = OTPService.normalize_phone(phone_number)

        otp = OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by("-created_at").first()

        if not otp:
            return {
                "success": False,
                "message": "OTP is invalid or expired"
            }

        if otp.code != code:
            return {
                "success": False,
                "message": "Incorrect OTP"
            }

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        return {
            "success": True,
            "message": "OTP verified successfully"
        }

    @staticmethod
    def resend_otp(phone_number, purpose):
        phone_number = OTPService.normalize_phone(phone_number)

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
            "otp": otp.code if settings.USE_STATIC_OTP else None
        }
