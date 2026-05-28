from rest_framework import serializers
from django.utils import timezone
from .models import Payment
from ticket.models import Ticket


class PurchaseTicketSerializer(serializers.Serializer):

    def validate(self, attrs):
        return attrs


class PaystackDataSerializer(serializers.Serializer):
    authorization_url = serializers.URLField()
    access_code = serializers.CharField()
    reference = serializers.CharField()


class PurchaseTicketResponseSerializer(serializers.Serializer):
    status = serializers.BooleanField()
    message = serializers.CharField()
    data = PaystackDataSerializer()


class PendingPaymentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    reference = serializers.CharField()
    status = serializers.CharField()
    authorization_url = serializers.URLField()
