import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Payment
from authentication.models import DriverProfile
from .serializers import PaymentInitializeSerializer, PaymentInitializeSerializer
from ticket.serializers import TicketSerializer
from utils.task import generate_ticket
from utils.paystack_signature import verify_paystack_signature
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import OpenApiResponse
from datetime import time

from services.paystack import PaystackService
from rest_framework import status, permissions
from ticket.utils import expire_old_tickets_once_per_day

import json

import logging

logger = logging.getLogger(__name__)

TICKET_AMOUNT = 10


@extend_schema(tags=["Payments"],)
class InitializePaymentView(APIView):
    serializer_class = PaymentInitializeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        expire_old_tickets_once_per_day()

        if not self.is_before_cutoff():
            return Response(
                {"error": "Ticket purchase cutoff reached. Try again tomorrow."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentInitializeSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        driver = request.user.driver_profile
        amount = serializer.validated_data["amount"]

        reference = str(uuid.uuid4())

        payment = Payment.objects.create(
            driver=driver,
            reference=reference,
            amount=TICKET_AMOUNT,
            currency='NGN',
            payment_date=timezone.localtime()
        )
        

        response = PaystackService.initialize_payment(
            payment=payment,
            amount=amount,
            reference=reference
        )

        return Response(response, status=status.HTTP_200_OK)
    


@extend_schema(
    tags=["Payments"],
    responses={200: None},
    description="Verify a payment with Paystack"
    )
class verify_payment_view(APIView):

  def get(self, request, reference):

        payment = get_object_or_404(
            Payment,
            reference=reference,
            driver=request.user.driver_profile
        )

        data = {
            "status": payment.status
        }
        
        # If payment is successful and ticket already generated, include ticket info in response
        if payment.status == Payment.Status.SUCCESS and hasattr(payment, "ticket"):
            data["ticket"] = TicketSerializer(payment.ticket).data

        else:
            if payment.status == Payment.Status.SUCCESS:
                data["message"] = "Payment successful. Ticket generation in progress."

            if payment.status == Payment.Status.FAILED:
                data["message"] = "Payment failed. Please try again."

        return Response(data)


@extend_schema(tags=["Payments"],
        exclude=True        
    )
class PaystackWebhookView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            # Step 1: Verify signature
            try:
                if not verify_paystack_signature(request):
                    logger.warning("Invalid Paystack signature")
                    return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.exception(f"Signature verification failed: {e}")
                return Response({"error": "Signature verification failed"}, status=status.HTTP_400_BAD_REQUEST)

            # Step 2: Load JSON safely
            try:
                event = json.loads(request.body)
            except Exception as e:
                logger.exception(f"Failed to parse webhook payload: {e}")
                return Response(status=400)

            # Step 3: Only handle charge.success events
            if event.get("event") != "charge.success":
                logger.info(f"Ignored event: {event.get('event')}")
                return Response(status=200)

            reference = event["data"].get("reference")
            if not reference:
                logger.warning("No reference found in event")
                return Response(status=200)

            # Step 4: Fetch payment safely
            payment = Payment.objects.filter(reference=reference).first()
            if not payment:
                logger.warning(f"No payment found for reference {reference}")
                return Response(status=200)

            if payment.status == Payment.Status.SUCCESS:
                logger.info(f"Payment already marked success for reference {reference}")
                return Response(status=200)

            # Step 5: Verify payment with Paystack API
            try:
                verify = PaystackService.verify_payment(reference)
            except Exception as e:
                logger.exception(f"Paystack verification failed: {e}")
                return Response(status=200)  # Return 200 to prevent retries

            if verify.get("data", {}).get("status") == "success":
                payment.status = Payment.Status.SUCCESS
                payment.provider_response = verify
                payment.save(update_fields=["status", "provider_response"])
                # Queue ticket generation safely
                try:
                    generate_ticket(payment.id)
                except Exception as e:
                    logger.exception(f"Failed to enqueue ticket generation: {e}")
            else:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status"])

            return Response(status=200)

        except Exception as e:
            # Catch everything to prevent 502
            logger.exception(f"Unexpected webhook error: {e}")
            return Response(status=200)
