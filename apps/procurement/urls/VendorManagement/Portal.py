"""Procurement 6.4 Vendor Management — vendor portal URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("vendor-portal/", views.vendor_portal_home, name="vendor_portal_home"),
    path("vendor-portal/invoices/new/", views.vendor_invoice_new, name="vendor_invoice_new"),
]
