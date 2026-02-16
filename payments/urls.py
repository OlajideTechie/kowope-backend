from django.urls import path
from .views import (
    InitializePaymentView,
    PaystackWebhookView,
    PaymentStatusView
)

urlpatterns = [
    path("initialize/", InitializePaymentView.as_view()),
    path("webhook/paystack/", PaystackWebhookView.as_view()),
    path("status/<str:reference>/", PaymentStatusView.as_view()),
]