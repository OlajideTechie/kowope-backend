import uuid
from django.db import models
from django.utils import timezone
from payments.models import Payment
from authentication.models import DriverProfile

class Ticket(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        EXPIRED = "EXPIRED",
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

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(default=timezone.now)

    valid_for_date = models.DateField()  # The date for which the ticket is valid, e.g., the date of payment

    

    class Meta:
        indexes = [
            models.Index(fields=["ticket_number"]),
            models.Index(fields=["driver"]),
            models.Index(fields=["area"]),
            models.Index(fields=["status"]),
        ]

# constraints to ensure one ticket per successful payment
    constraints = [
        models.UniqueConstraint(
            fields=["payment"],
            name="unique_ticket_per_payment"
        )
    ]   

def __str__(self):
        return self.ticket_number
