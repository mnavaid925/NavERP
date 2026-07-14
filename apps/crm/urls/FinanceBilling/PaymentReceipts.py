"""CRM 1.7 Finance & Billing Management — PaymentReceipts URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Payment Tracking (1.7) — receipts over ledger payments, with a printable receipt
    path("payment-receipts/", views.paymentreceipt_list, name="paymentreceipt_list"),
    path("payment-receipts/add/", views.paymentreceipt_create, name="paymentreceipt_create"),
    path("payment-receipts/<int:pk>/", views.paymentreceipt_detail, name="paymentreceipt_detail"),
    path("payment-receipts/<int:pk>/edit/", views.paymentreceipt_edit, name="paymentreceipt_edit"),
    path("payment-receipts/<int:pk>/delete/", views.paymentreceipt_delete, name="paymentreceipt_delete"),
    path("payment-receipts/<int:pk>/print/", views.paymentreceipt_print, name="paymentreceipt_print"),
]
