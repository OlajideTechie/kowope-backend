import requests
from django.conf import settings


class PaystackService:

    base_url = "https://api.paystack.co"

    @staticmethod
    def initialize_payment(email, amount, reference):

        url = f"{PaystackService.base_url}/transaction/initialize"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }

        data = {
            "email": email,
            "amount": int(amount * 100),
            "reference": reference
        }

        response = requests.post(url, json=data, headers=headers)
        return response.json()

    @staticmethod
    def verify_payment(reference):

        url = f"{PaystackService.base_url}/transaction/verify/{reference}"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }

        response = requests.get(url, headers=headers)
        return response.json()
