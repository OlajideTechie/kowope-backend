from django.urls import path
from .views import (
    InitializePaymentView,
    PaystackWebhookView,
    VerifyPaymentView,
    PaymentCallbackView
)

app_name = 'payments'

urlpatterns = [
    path("initiate", InitializePaymentView.as_view(), name='initiate-payment'),
    path("webhook/paystack", PaystackWebhookView.as_view(), name='paystack-webhook'),
     path("callback", PaymentCallbackView.as_view(), name='payment-callback'),
    path("status/<str:reference>", VerifyPaymentView.as_view(), name='refence-status'),
]