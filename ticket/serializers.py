# tickets/serializers.py

from rest_framework import serializers
from .models import Ticket
from django.core import signing
from django.conf import settings



class TicketSerializer(serializers.ModelSerializer):
    driver_id = serializers.UUIDField(source="driver.id", read_only=True)

    driver_name = serializers.CharField(
        source="driver.full_name",
        read_only=True
    )

    amount = serializers.DecimalField(
        source="payment.amount",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    computed_status = serializers.SerializerMethodField()

    qr_code = serializers.UUIDField(read_only=True)

    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_number",
            "driver_id",
            "driver_name",
            "amount",
            "area",
            "valid_for_date",
            "created_at",
            "computed_status",
            "qr_code",
            "verification_url",
        ]
        read_only_fields = fields

    def get_computed_status(self, obj):
        return obj.computed_status

    def get_verification_url(self, obj):
        domain = getattr(settings, "FRONTEND_DOMAIN")
        return f"{domain}/api/v1/ticket/validate?qr_code={obj.qr_code}"
    


class TicketQRValidationSerializer(serializers.Serializer):
    qr_code = serializers.UUIDField()

    ticket = None 

    def validate_qr_code(self, value):
        try:
            ticket = Ticket.objects.get(qr_code=value)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Ticket not found")

        if ticket.computed_status != Ticket.Status.ACTIVE:
            raise serializers.ValidationError(f"Ticket is {ticket.computed_status}")

        self.ticket = ticket
        return value

    @property
    def validated_data(self):
        return {"ticket": self.ticket}