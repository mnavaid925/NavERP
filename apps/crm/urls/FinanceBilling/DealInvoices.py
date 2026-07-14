"""CRM 1.7 Finance & Billing Management — DealInvoices URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Invoicing (1.7) — DealInvoice wrappers over the accounting ledger + quote→invoice conversion
    path("deal-invoices/", views.dealinvoice_list, name="dealinvoice_list"),
    path("deal-invoices/add/", views.dealinvoice_create, name="dealinvoice_create"),
    path("deal-invoices/from-quote/<int:quote_pk>/", views.dealinvoice_from_quote, name="dealinvoice_from_quote"),
    path("deal-invoices/<int:pk>/", views.dealinvoice_detail, name="dealinvoice_detail"),
    path("deal-invoices/<int:pk>/edit/", views.dealinvoice_edit, name="dealinvoice_edit"),
    path("deal-invoices/<int:pk>/delete/", views.dealinvoice_delete, name="dealinvoice_delete"),
]
