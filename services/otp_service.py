from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from rest_framework.exceptions import ValidationError
import random

from authentication.models import OTP
from services.sms_service import SMSService
from utils.phone import normalize_phone


class OTPService:

    @staticmethod
    def generate_otp() -> str:
        """
        Generates OTP code.
        Uses static OTP in non-production environments if configured.
        """
        if getattr(settings, "USE_STATIC_OTP", False):
            return getattr(settings, "STATIC_OTP_CODE", "123456")

        return str(random.randint(100000, 999999))

    @staticmethod
    def create_otp(phone_number: str, purpose: str):
        """
        Creates a new OTP and sends it via SMS.
        """

        phone_number = normalize_phone(phone_number)

        # Invalidate previous unused OTPs
        OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)

        code = OTPService.generate_otp()

        otp_obj = OTP.objects.create(
            phone_number=phone_number,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(
                seconds=getattr(settings, "OTP_EXPIRY_SECONDS", 300)
            ),
            is_used=False
        )

        # Send OTP via SMS
        SMSService.send_otp(phone_number, code)

        return otp_obj

    @staticmethod
    def verify_otp(phone_number: str, code: str, purpose: str):
        """
        Verifies OTP validity.
        """

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

        return {"success": True, "message": "OTP verified successfully"}

    @staticmethod
    def resend_otp(phone_number: str, purpose: str):
        """
        Invalidates old OTPs and sends a new one.
        """

        phone_number = normalize_phone(phone_number)

       # Check cooldown BEFORE generating new OTP
        cooldown_time = timezone.now() - timedelta(seconds=120)

        recent_otp = OTP.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        created_at__gte=cooldown_time,
        is_used=False
    ).exists()

        if recent_otp:
            raise ValidationError("Please wait before requesting another OTP")

        # Invalidate previous OTPs
        OTP.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)
        
        # Create new OTP
        otp_obj = OTPService.create_otp(phone_number, purpose)

        return {
        "message": "A new OTP has been sent",
        "otp_code": otp_obj.code
    }