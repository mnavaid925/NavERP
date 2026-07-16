"""HRM 3.17 Payout & Reports — Payoutpayments URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Per-payment actions (mark paid/failed/retry)
    path("payout-payments/<int:pk>/mark-paid/", views.payoutpayment_mark_paid, name="payoutpayment_mark_paid"),
    path("payout-payments/<int:pk>/mark-failed/", views.payoutpayment_mark_failed, name="payoutpayment_mark_failed"),
    path("payout-payments/<int:pk>/retry/", views.payoutpayment_retry, name="payoutpayment_retry"),
]
