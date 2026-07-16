"""HRM 3.17 Payout & Reports — PaymentRegister URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("payout-batches/<int:pk>/register/", views.payment_register, name="payment_register"),
]
