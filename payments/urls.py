from django.urls import path
from .views import (
    InitializePaymentView,
    PaystackWebhookView,
    verify_payment_view
)

app_name = 'payments'

urlpatterns = [
    path("initiate", InitializePaymentView.as_view(), name='initiate-payment'),
    path("webhook/paystack", PaystackWebhookView.as_view(), name='paystack-webhook'),
    path("status/<str:reference>", verify_payment_view.as_view(), name='refence-status'),
]