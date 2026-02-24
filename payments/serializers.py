from rest_framework import serializers
from django.utils import timezone
from .models import Payment
from authentication.models import DriverProfile

class PaymentInitializeSerializer(serializers.Serializer):

    class Meta:
        model = Payment
        fields = ["amount"]

    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        driver = self.context["request"].user.driver_profile
        today = timezone.now().date()

        already_paid = Payment.objects.filter(
            driver=driver,
            payment_date=today,
            status=Payment.Status.SUCCESS
        ).exists()

        if already_paid:
            raise serializers.ValidationError(
                "You have already made payment for today."
            )

        return attrs
