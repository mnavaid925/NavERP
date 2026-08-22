"""Inventory 5.3 Purchase Order (PO) Management — reorder-draft route (prefix
``po/reorder-draft/``). One page, GET = suggestions, POST = draft spine orders."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("po/reorder-draft/", views.reorderdraft, name="reorderdraft"),
]
