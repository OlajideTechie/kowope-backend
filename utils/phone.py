import phonenumbers


def normalize_phone(phone: str) -> str:
    try:
        parsed = phonenumbers.parse(phone, "NG")
    except phonenumbers.NumberParseException:
        raise ValueError("Invalid phone number")

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Invalid phone number")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)