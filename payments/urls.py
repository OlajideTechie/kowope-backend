from django.urls import path
from .views import (
    PurchaseTicketView,
    PaystackWebhookView,
    VerifyPaymentView,
    PaymentCallbackView
)

app_name = 'payments'

urlpatterns = [
    path("purchase", PurchaseTicketView.as_view(), name='purchase-ticket'),
    path("webhook/paystack", PaystackWebhookView.as_view(), name='paystack-webhook'),
     path("callback", PaymentCallbackView.as_view(), name='payment-callback'),
    path("status/<str:reference>", VerifyPaymentView.as_view(), name='refence-status'),
]