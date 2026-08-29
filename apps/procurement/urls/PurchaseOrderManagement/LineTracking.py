"""Procurement 6.10 Purchase Order Management — per-line delivery tracking URL pattern."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("po-tracking/", views.po_line_tracking, name="po_line_tracking"),
]
