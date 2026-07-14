"""Accounting 2.4 Accounts Receivable — RecurringInvoices URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.4 AR — Recurring invoices (subscription/cadence billing)
    path("recurring-invoices/", views.recurringinvoice_list, name="recurringinvoice_list"),
    path("recurring-invoices/add/", views.recurringinvoice_create, name="recurringinvoice_create"),
    path("recurring-invoices/<int:pk>/", views.recurringinvoice_detail, name="recurringinvoice_detail"),
    path("recurring-invoices/<int:pk>/edit/", views.recurringinvoice_edit, name="recurringinvoice_edit"),
    path("recurring-invoices/<int:pk>/delete/", views.recurringinvoice_delete, name="recurringinvoice_delete"),
    path("recurring-invoices/<int:pk>/generate/", views.recurringinvoice_generate, name="recurringinvoice_generate"),
]
