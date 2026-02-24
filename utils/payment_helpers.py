# payments/utils/helpers.py

import uuid

def generate_payment_reference(prefix="KPM"):
    """
    Generate a unique payment reference.
    Example: CPW-9F3A82BC12EF
    """
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def generate_driver_email(driver):
    """
    Generate synthetic email for Paystack
    since drivers do not provide real emails.
    """
    phone = driver.user.phone_number.replace("+", "").strip()
    return f"{phone}@kowope.app"