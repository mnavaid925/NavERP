"""Inventory 5.5 Warehousing & Bin Management — Warehouse Map route."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("warehouse-map/", views.warehousemap, name="warehousemap"),
]
