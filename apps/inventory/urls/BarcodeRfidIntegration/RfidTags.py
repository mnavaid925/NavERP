"""Inventory 5.14 Barcode & RFID Integration — RfidTag URL patterns."""
from django.urls import path

from apps.inventory.views.BarcodeRfidIntegration.RfidTags import (
    rfidtag_activate,
    rfidtag_bulkread,
    rfidtag_create,
    rfidtag_delete,
    rfidtag_detail,
    rfidtag_edit,
    rfidtag_list,
    rfidtag_mark_lost,
    rfidtag_retire,
)

urlpatterns = [
    path("tags/", rfidtag_list, name="rfidtag_list"),
    path("tags/add/", rfidtag_create, name="rfidtag_create"),
    path("tags/bulk-read/", rfidtag_bulkread, name="rfidtag_bulkread"),
    path("tags/<int:pk>/", rfidtag_detail, name="rfidtag_detail"),
    path("tags/<int:pk>/edit/", rfidtag_edit, name="rfidtag_edit"),
    path("tags/<int:pk>/delete/", rfidtag_delete, name="rfidtag_delete"),
    path("tags/<int:pk>/activate/", rfidtag_activate, name="rfidtag_activate"),
    path("tags/<int:pk>/retire/", rfidtag_retire, name="rfidtag_retire"),
    path("tags/<int:pk>/mark-lost/", rfidtag_mark_lost, name="rfidtag_mark_lost"),
]
