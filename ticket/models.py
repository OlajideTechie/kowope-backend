import uuid
from django.db import models
from django.utils import timezone
from payments.models import Payment
from django.core import signing
from authentication.models import DriverProfile

class Ticket(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"
        REVOKED = "REVOKED"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="payment_tickets"
    )

    driver = models.ForeignKey(
        "authentication.DriverProfile",
        on_delete=models.CASCADE,
        related_name="driver_tickets"
    )

    area = models.CharField(max_length=100)

    ticket_number = models.CharField(max_length=50, unique=True)

    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(default=timezone.now)

    valid_for_date = models.DateField() # Ticket valid date in Nigeria local date


    # ---------------------------
    # Computed Logic
    # ---------------------------

    # Dynamically check if ticket is expired
    @property
    def is_expired(self):
        return timezone.localdate() > self.valid_for_date
    
    @property
    def is_active(self):
        return (
        self.status == self.Status.ACTIVE
        and not self.is_expired
    )

    @property
    def computed_status(self):
        """
        Return INACTIVE if the ticket is past its valid date or revoked.
        Otherwise ACTIVE.
        """
        if self.status == self.Status.REVOKED:
            return "REVOKED"
        if self.valid_for_date < timezone.localdate():
            return "INACTIVE"
        return "ACTIVE"
    

    # ---------------------------
    # QR Token Generation
    # ---------------------------

    def generate_signed_token(self):
        return signing.dumps(
            {"ticket_id": str(self.id)}
        )

    def generate_qr_code(self):
        """Generate a signed QR code token for this ticket."""

        data = {"ticket_id": str(self.id)}
        token = signing.dumps(data)
        self.qr_code = token

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.generate_qr_code()
        super().save(*args, **kwargs)


    class Meta:
        indexes = [
            models.Index(fields=["ticket_number"]),
            models.Index(fields=["driver"]),
            models.Index(fields=["area"]),
            models.Index(fields=["status"]),
        ]

        constraints = [
            # One ticket per payment
            models.UniqueConstraint(
                fields=["payment"],
                name="unique_ticket_per_payment"
            ),

            # One active ticket per driver per day per area
            models.UniqueConstraint(
                fields=["driver", "valid_for_date", "area"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_ticket_per_driver_per_day_area"
            )
        ]

    def __str__(self):
        return self.ticket_number
