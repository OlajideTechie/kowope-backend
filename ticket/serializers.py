# tickets/serializers.py
from rest_framework import serializers
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    amount = serializers.DecimalField(
        source="payment.amount",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_number",
            "driver_id",
            "amount",
            "driver_name",
            "area",
            "valid_for_date",
            "created_at",
            "computed_status",
        ]
        read_only_fields = fields 

def get_status(self, obj):
    return obj.computed_status