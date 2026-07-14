"""Accounting 2.3 Accounts Payable — PaymentTerms URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.3 AP — Payment terms
    path("payment-terms/", views.payment_term_list, name="payment_term_list"),
    path("payment-terms/add/", views.payment_term_create, name="payment_term_create"),
    path("payment-terms/<int:pk>/", views.payment_term_detail, name="payment_term_detail"),
    path("payment-terms/<int:pk>/edit/", views.payment_term_edit, name="payment_term_edit"),
    path("payment-terms/<int:pk>/delete/", views.payment_term_delete, name="payment_term_delete"),
]
