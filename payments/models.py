import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Q

class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        REFUNDED = "REFUNDED"
        EXPIRED = "EXPIRED"
        REJECTED = "REJECTED"

    class Channel(models.TextChoices):
        CARD = "card"
        BANK = "bank"
        USSD = "ussd"
        TRANSFER = "transfer"
        QR = "qr"
        MOBILE_MONEY = "mobile_money"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    driver = models.ForeignKey(
        "authentication.DriverProfile",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    reference = models.CharField(
        max_length=100,
        unique=True,  # Paystack reference
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2) # Amount in Naira, e.g., 500.00 for ₦500.00

    currency = models.CharField(max_length=10, default='NGN')

    payment_date = models.DateField(default=timezone.now)  # Daily remittance target

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    provider = models.CharField(
        max_length=50,
        default="paystack"
    )

    gateway_response = models.JSONField(null=True, blank=True)

    channel = models.CharField(
        max_length=50,
        choices=Channel.choices,
        null=True,
        blank=True
    )

    authorization_url = models.URLField(null=True, blank=True)

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["driver", "payment_date"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["status"]),
        ]

        constraints = [
            # Prevent more than one SUCCESS payment per driver per day
            models.UniqueConstraint(
                fields=["driver", "payment_date"],
                condition=Q(status="SUCCESS"),
                name="unique_successful_daily_payment"
            )
        ]

    def __str__(self):
        return f"{self.driver} - {self.payment_date} - {self.status}"
