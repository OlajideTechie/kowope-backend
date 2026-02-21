# tickets/serializers.py
from rest_framework import serializers
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'driver', 'area', 'payment', 'ticket_date', 'is_active', 'created_at']
        read_only_fields = ['id', 'driver', 'payment', 'ticket_date', 'created_at']