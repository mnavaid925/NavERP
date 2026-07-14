"""CRM 1.12 Inventory & Vendor Management — PurchaseOrders URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Purchase orders (1.12)
    path("purchase-orders/", views.crm_po_list, name="crm_po_list"),
    path("purchase-orders/add/", views.crm_po_create, name="crm_po_create"),
    path("purchase-orders/<int:pk>/", views.crm_po_detail, name="crm_po_detail"),
    path("purchase-orders/<int:pk>/edit/", views.crm_po_edit, name="crm_po_edit"),
    path("purchase-orders/<int:pk>/delete/", views.crm_po_delete, name="crm_po_delete"),
    path("purchase-orders/<int:pk>/add-line/", views.crm_po_add_line, name="crm_po_add_line"),
    path("purchase-orders/<int:pk>/remove-line/<int:line_pk>/", views.crm_po_remove_line, name="crm_po_remove_line"),
    path("purchase-orders/<int:pk>/receive/", views.crm_po_receive, name="crm_po_receive"),
]
