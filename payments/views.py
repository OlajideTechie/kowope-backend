import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError

from .models import Payment
from authentication.models import DriverProfile
from .serializers import PurchaseTicketSerializer, PurchaseTicketResponseSerializer, PendingPaymentResponseSerializer
from ticket.serializers import TicketSerializer
from utils.task import generate_ticket
from utils.paystack_signature import verify_paystack_signature
from drf_spectacular.utils import extend_schema, OpenApiResponse
from datetime import time, timedelta

from services.paystack import PaystackService
from rest_framework import status, permissions
from ticket.utils import expire_old_tickets_once_per_day
from django.conf import settings

from middleware.permissions import IsDriver

import json

import logging

logger = logging.getLogger(__name__)

@extend_schema(
    tags=["Payments"],
    summary="Purchase a ticket",
    description="Initiates a Paystack payment to purchase a daily road-use ticket. Returns an authorization URL to redirect the driver to complete payment.",
    request=None,
    responses={
        200: OpenApiResponse(
            description="Payment initiated successfully.",
            response=PurchaseTicketResponseSerializer,
        ),
        202: OpenApiResponse(
            description="Driver already has a pending payment within the expiry window.",
            response=PendingPaymentResponseSerializer,
        ),
        400: OpenApiResponse(
            description="Validation error or payment window closed.",
        ),
    }
)
class PurchaseTicketView(APIView):
    serializer_class = PurchaseTicketSerializer
    permission_classes = [IsDriver]
    
    # PAYMENT_CUTOFF: no new payments can be initiated after this time each day, 
    # ensuring ticket generation completes before cutoff and preventing late attempts that may not be fulfilled.
    PAYMENT_CUTOFF = time(22, 0)

    # PENDING_EXPIRY: if a pending payment exists, it will be valid for this duration before expiring and allowing a new one
    # this prevents users from spamming payment attempts while ensuring they can retry after a reasonable time if something goes wrong.
    PENDING_EXPIRY = timedelta(minutes=settings.PENDING_TICKET_EXPIRY_MINUTES)

    def is_before_cutoff(self):
        """
        Returns True if current time is before payment cutoff.
        Example cutoff: 6PM
        """
        now = timezone.localtime().time()
        return now <= self.PAYMENT_CUTOFF

    def post(self, request):
        # Lazy ticket expiration when initiating payment, 
        # ensuring we don't run this expensive operation on every request but still keep the system clean.
        expire_old_tickets_once_per_day()

        if not self.is_before_cutoff():
            return Response(
                {"error": "Payment window has closed for today."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = PurchaseTicketSerializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)

        driver = request.user.driver_profile

        # Fixed ticket amount
        amount = settings.TICKET_AMOUNT
        
        # Check for existing pending payment and 
        # expire if too old, otherwise return existing pending payment
        # info to prevent multiple pending payments for same driver
        # as long as the payment is not expired.
        pending_payment = Payment.objects.filter(
            driver=driver,
            status=Payment.Status.PENDING
        ).order_by("-created_at").first() 

        if pending_payment:

            expiry_time = pending_payment.created_at + self.PENDING_EXPIRY

           # Expire old pending payment
            if timezone.now() > expiry_time:
                pending_payment.status = Payment.Status.EXPIRED
                pending_payment.save(update_fields=["status"])

            else: 
               return Response ({
                   "message": "you already have a pending payment",
                   "reference": pending_payment.reference,
                   "status": pending_payment.status,
                   "authorization_url": pending_payment.authorization_url,
               }, status=status.HTTP_200_OK,
            )
           
        # Create new payment
        reference = str(uuid.uuid4())

        # Create payment record after getting URL
        payment = Payment.objects.create(
            driver=driver,
            reference=reference,
            amount=amount,
            currency='NGN'
        )

        # Initialize Paystack payment
        paystack_response = PaystackService.initialize_payment(
            payment=payment,
            amount=amount,
            reference=reference
        )

        # Extract authorization URL
        authorization_url = paystack_response["data"]["authorization_url"]

        # Save URL to DB
        payment.authorization_url = authorization_url
        payment.save(update_fields=["authorization_url"])
        

        return Response(paystack_response, status=status.HTTP_200_OK)
    


@extend_schema(
    tags=["Payments"],
    responses={200: None},
    exclude=True, 
    description="Verify a payment with Paystack"
    )
class VerifyPaymentView(APIView):

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
        """
        Handles Paystack webhook events, especially 'charge.success'.
        Marks payment as SUCCESS or FAILED, stores channel info, and triggers ticket generation.
        """

        # --- Step 1: Verify Paystack signature ---
        try:
            if not verify_paystack_signature(request):
                logger.warning("Invalid Paystack signature")

                return Response(
                    {"error": "Invalid signature"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.exception(
                f"Signature verification failed: {e}"
            )

            return Response(
                {"error": "Signature verification failed"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Step 2: Parse JSON payload ---
        try:
            event = json.loads(request.body)

        except Exception as e:
            logger.exception(
                f"Failed to parse webhook payload: {e}"
            )

            return Response(
                {"error": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Step 3: Only handle charge.success events ---
        event_type = event.get("event")

        if event_type != "charge.success":
            logger.info(
                f"Ignored event type: {event_type}"
            )

            return Response(status=status.HTTP_200_OK)

        reference = event.get("data", {}).get("reference")

        if not reference:
            logger.warning(
                "Webhook event missing payment reference"
            )

            return Response(status=status.HTTP_200_OK)

        # ---------------------------------------------------
        # STEP 4: Verify payment with Paystack
        # ---------------------------------------------------
        try:
            verification = PaystackService.verify_payment(reference)

        except Exception as e:
            logger.exception(
                f"Paystack verification failed for {reference}: {e}"
            )

            # Return 200 to avoid unnecessary webhook retries
            return Response(status=status.HTTP_200_OK)

        payment_data = verification.get("data", {})

        if payment_data.get("status") != "success":
            logger.warning(
                f"Verification returned non-success for {reference}"
            )

            Payment.objects.filter(reference=reference).update(
                status=Payment.Status.FAILED
            )

            return Response(status=status.HTTP_200_OK)

         # ---------------------------------------------------
        # STEP 5: Atomic payment update + ticket generation
        # ---------------------------------------------------
        try:

            with transaction.atomic():

                payment = (
                    Payment.objects
                    .select_for_update()
                    .filter(reference=reference)
                    .first()
                )

                if not payment:
                    logger.warning(
                        f"No payment found for reference {reference}"
                    )

                    return Response(status=status.HTTP_200_OK)

                # -------------------------------------------
                # IDEMPOTENCY CHECK
                # -------------------------------------------
                if payment.status == Payment.Status.SUCCESS:
                    logger.info(
                        f"Payment already processed: {reference}"
                    )

                    return Response(status=status.HTTP_200_OK)

                # -------------------------------------------
                # PREVENT DUPLICATE SUCCESS PAYMENTS
                # -------------------------------------------
                existing_success = Payment.objects.filter(
                   payment=payment,
                ).first()
                
                # self healing ticket recovery: if we receive a duplicate success webhook for a payment that is already marked as SUCCESS, we can check if a ticket exists for that payment. If not, we can attempt to generate the ticket again. This helps recover from cases where the ticket generation may have failed or the webhook processing was interrupted after marking the payment as successful but before generating the ticket.
                if not existing_success:
                    logger.warning(
                         f"SUCCESS payment missing ticket. "
                         f"Regenerating ticket for {reference}"
                    )

                    try:
                        generate_ticket(payment.id)

                    except Exception as e:
                            logger.exception(
                                f"Failed regenerating ticket "
                                f"for {reference}: {e}"
                            )

                    return Response(status=status.HTTP_200_OK)

                # -------------------------------------------------
                # PREVENT DUPLICATE SUCCESS PAYMENTS
                # -------------------------------------------------
                existing_success = Payment.objects.filter(
                    driver=payment.driver,
                    payment_date=payment.payment_date,
                    status=Payment.Status.SUCCESS
                ).exclude(id=payment.id).exists()

                if existing_success:

                    logger.warning(
                        f"Duplicate successful payment attempt "
                        f"for driver={payment.driver_id}, "
                        f"date={payment.payment_date}"
                    )

                    payment.status = Payment.Status.REJECTED

                    payment.gateway_response = verification

                    payment.save(update_fields=[
                        "status",
                        "gateway_response",
                    ])

                    return Response(status=status.HTTP_200_OK)

                # -------------------------------------------------
                # MARK PAYMENT SUCCESS
                # -------------------------------------------------
                payment.status = Payment.Status.SUCCESS
                payment.channel = payment_data.get("channel")
                payment.gateway_response = verification
                payment.paid_at = payment_data.get("paid_at")

                payment.save(update_fields=[
                    "status",
                    "channel",
                    "gateway_response",
                    "paid_at",
                ])

        except IntegrityError as e:

            logger.exception(
                f"Integrity error processing payment "
                f"{reference}: {e}"
            )

            return Response(status=status.HTTP_200_OK)

        except Exception as e:

            logger.exception(
                f"Unexpected webhook processing error "
                f"for {reference}: {e}"
            )

            return Response(status=status.HTTP_200_OK)

        # =====================================================
        # STEP 6: GENERATE TICKET OUTSIDE PAYMENT TRANSACTION
        # =====================================================
        try:

            ticket = generate_ticket(payment.id)

            logger.info(
                f"Payment processed successfully: "
                f"reference={reference}, "
                f"ticket_id={getattr(ticket, 'id', None)}"
            )

        except Exception as e:

            logger.exception(
                f"Ticket generation failed "
                f"for payment {reference}: {e}"
            )

        return Response(status=status.HTTP_200_OK)

@extend_schema(tags=["Payments"],
        exclude=True        
    )
class PaymentCallbackView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        reference = request.GET.get("reference")

        return Response({
            "message": "Payment completed successfully",
            "reference": reference
        })