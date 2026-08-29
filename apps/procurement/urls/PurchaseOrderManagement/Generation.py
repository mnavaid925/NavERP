"""Procurement 6.10 Purchase Order Management — requisition -> PO generation URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("po-generation/", views.po_generation, name="po_generation"),
    path("po-generation/<int:requisition_pk>/", views.po_generate, name="po_generate"),
]
