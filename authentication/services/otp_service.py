from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random

from authentication.models import OTP
from authentication.services.sms_service import SMSService


class OTPService:

    @staticmethod
    def normalize_phone(phone_number: str) -> str:
        phone_number = "".join(filter(str.isdigit, phone_number))
        
        # Normalize Nigerian phone numbers by converting +234 to 0
        if phone_number.startswith("0"):
            phone_number = "234" + phone_number[1:]

        elif phone_number.startswith("234"):
            pass  # Already in correct format

        else :
            raise ValueError("Invalid phone number format. Must start with '0' or '234'.")

        return phone_number

    @staticmethod
    def generate_otp() -> str:
        if getattr(settings, "USE_STATIC_OTP", False):
            return getattr(settings, "STATIC_OTP_CODE", "123456")
        return str(random.randint(100000, 999999))

    @staticmethod
    def create_otp(phone_number: str, purpose: str) -> OTP:
        phone_number = OTPService.normalize_phone(phone_number)
        code = OTPService.generate_otp()

        expires_at = timezone.now() + timedelta(seconds=getattr(settings, "OTP_EXPIRY_SECONDS", 300))

        OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)

        otp = OTP.objects.create(
            phone_number=phone_number,
            code=code,
            purpose=purpose,
            expires_at=expires_at,
            is_used=False
        )
       
       # Send OTP via SMS if provider is enabled
        if getattr(settings, "ENABLE_SMS_PROVIDER", False):
            SMSService.send_otp(phone_number, code)

        return otp

    @staticmethod
    def verify_otp(phone_number: str, code: str, purpose: str) -> dict:
        phone_number = OTPService.normalize_phone(phone_number)

        OTP.objects.filter(
            phone_number=phone_number,
            purpose="signup",
            is_used=False,
            expires_at__lt=timezone.now()
        ).update(is_used=True)

        otp = OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False,
        ).order_by("-created_at").first()

        if not otp:
            return {
                "success": False,
                "message": "OTP not found"
            }
        
        if timezone.now() > otp.expires_at:
            return {
                "success": False,
                "message": "OTP has expired"
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
    def resend_otp(phone_number: str, purpose: str) -> dict:
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
            "otp_id": otp.purpose
        }
