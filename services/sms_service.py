from django.conf import settings

TwilioClient = None  # Placeholder for actual Twilio client initialization

class SMSService:


    @staticmethod
    def send_otp(phone_number, code):
        if not settings.ENABLE_SMS_PROVIDER:
            return
      
        if settings.SMS_PROVIDER == "twilio":
            TwilioClient.send_sms(
                to=phone_number,
                message=f"Your verification code is {code}"
            )
