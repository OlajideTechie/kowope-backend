import requests
from django.conf import settings
from utils.payment_helpers import generate_driver_email, generate_payment_reference
from payments.models import Payment


class PaystackService:
    base_url = "https://api.paystack.co"

    @staticmethod
    def initialize_payment(payment: Payment, amount: float, reference: str = None):
        """
        Initialize a Paystack payment for a given Payment instance.
        """

        if reference is None:
            reference = generate_payment_reference()

        email = generate_driver_email(payment.driver)

        url = f"{PaystackService.base_url}/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "email": email,
            "amount": int(amount * 100),  # Paystack expects kobo
            "reference": reference,
            "callback_url": settings.PAYSTACK_REDIRECT_URL
        }

        response = requests.post(url, json=data, headers=headers)
        return response.json()

    @staticmethod
    def verify_payment(reference: str):
        """
        Verify a Paystack payment by its reference.
        """
        url = f"{PaystackService.base_url}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }

        response = requests.get(url, headers=headers)
        return response.json()