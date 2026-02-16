import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Payment
from .serializers import PaymentInitializeSerializer, TicketSerializer
from services import PaystackService
from payments.task import generate_ticket
from utils.paystack_signature import verify_paystack_signature



class InitializePaymentView(APIView):

    def post(self, request):

        serializer = PaymentInitializeSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        driver = request.user.driverprofile
        amount = serializer.validated_data["amount"]

        reference = str(uuid.uuid4())

        payment = Payment.objects.create(
            driver=driver,
            reference=reference,
            amount=amount,
            payment_date=timezone.now().date()
        )

        response = PaystackService.initialize_payment(
            email=request.user.email,
            amount=amount,
            reference=reference
        )

        return Response(response, status=status.HTTP_200_OK)
    


class verify_payment_view(APIView):

  def get(self, request, reference):

        payment = get_object_or_404(
            Payment,
            reference=reference,
            driver=request.user.driverprofile
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




class PaystackWebhookView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        if not verify_paystack_signature(request):
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        event = request.data

        if event["event"] != "charge.success":
            return Response(status=200)

        reference = event["data"]["reference"]

        payment = Payment.objects.filter(reference=reference).first()

        if not payment:
            return Response(status=200)

        if payment.status == Payment.Status.SUCCESS:
            return Response(status=200)

        verify = PaystackService.verify_payment(reference)

        if verify["data"]["status"] == "success":

            payment.status = Payment.Status.SUCCESS
            payment.provider_response = verify
            payment.save(update_fields=["status", "provider_response"])

            generate_ticket.delay(str(payment.id))

        else:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])

        return Response(status=200)