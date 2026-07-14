"""CRM 1.12 Inventory & Vendor Management — ProductStock URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Product stock (1.12)
    path("stock/", views.productstock_list, name="productstock_list"),
    path("stock/add/", views.productstock_create, name="productstock_create"),
    path("stock/<int:pk>/", views.productstock_detail, name="productstock_detail"),
    path("stock/<int:pk>/edit/", views.productstock_edit, name="productstock_edit"),
    path("stock/<int:pk>/delete/", views.productstock_delete, name="productstock_delete"),
]
