from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


class SMSService:

    @staticmethod
    def _get_twilio_client():
        return Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

    @staticmethod
    def send_otp(phone_number, code):
        """
        Sends OTP using configured SMS provider.
        """

        if not settings.ENABLE_SMS_PROVIDER:
            logger.info("SMS provider disabled. Skipping SMS send.")
            return
        
        message = f"Your verification code is {code}"

        if settings.SMS_PROVIDER == "twilio":
            SMSService._send_via_twilio(phone_number, message)

        else:
            logger.warning(f"Unsupported SMS provider: {settings.SMS_PROVIDER}")

    @staticmethod
    def _send_via_twilio(phone_number, message):

        try:
            client = SMSService._get_twilio_client()

            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )

            logger.info(f"OTP SMS sent to {phone_number}")

        except Exception as e:
            logger.exception(f"Failed to send SMS via Twilio: {e}")