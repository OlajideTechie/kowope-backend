import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def disable_throttling(settings):
    # Clear any throttle counters left by previous tests in the session.
    cache.clear()

    # Setting DEFAULT_THROTTLE_CLASSES=[] disables throttles on views that don't
    # override throttle_classes. Views that DO set throttle_classes=[ScopedRateThrottle]
    # explicitly still run ScopedRateThrottle, which reads from DEFAULT_THROTTLE_RATES.
    # Provide very high rates so it never blocks and never raises ImproperlyConfigured.
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {
            "user": "9999/minute",
            "anon": "9999/minute",
            "signup": "9999/minute",
            "otp_request": "9999/minute",
            "otp_verify": "9999/minute",
            "login": "9999/minute",
            "reset_pin": "9999/minute",
        },
    }
