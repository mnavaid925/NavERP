"""CRM 1.12 Inventory & Vendor Management — PartnerPortal URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Partner portal — partner-facing (1.12)
    path("portal/", views.portal_dashboard, name="portal_dashboard"),
    path("portal/orders/", views.portal_po_list, name="portal_po_list"),
    path("portal/stock/", views.portal_stock, name="portal_stock"),
]
