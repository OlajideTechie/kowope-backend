import hmac
import hashlib
from django.conf import settings


def verify_paystack_signature(request):

    signature = request.headers.get("x-paystack-signature")

    if not signature:
        return False

    computed_hash = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        request.body,
        hashlib.sha512
    ).hexdigest()

    """
    Here we use hmac.compare_digest for a secure comparison to prevent timing attacks. 
    This function compares the computed hash with the signature provided
    in the request headers and returns True if they match, indicating that the request is authentic, or False otherwise.
    """
    return hmac.compare_digest(computed_hash, signature)

    # return True
