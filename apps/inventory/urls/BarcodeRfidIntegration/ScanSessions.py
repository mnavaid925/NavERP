"""Inventory 5.14 Barcode & RFID Integration — routes (prefixes ``sessions/`` and
``console/``). Literals before ``<int:pk>`` per the house first-match rule — ``console/``
MUST sit above the pk patterns or ``/console/`` would be captured as a detail pk.

Imports the view module DIRECTLY rather than through the package-root re-export: this file
ships during the build wave, before ``apps/inventory/views/__init__.py`` gains its 5.14
lines (integrate phase), and attribute access through the not-yet-wired package would raise
at import time. After integration either spelling resolves to the same function objects.
"""
from django.urls import path

from apps.inventory.views.BarcodeRfidIntegration import ScanSessions as views

urlpatterns = [
    path("sessions/", views.scansession_list, name="scansession_list"),
    path("sessions/add/", views.scansession_create, name="scansession_create"),
    path("console/", views.scan_console, name="scan_console"),
    path("sessions/<int:pk>/", views.scansession_detail, name="scansession_detail"),
    path("<int:pk>/edit/", views.scansession_edit, name="scansession_edit"),
    path("<int:pk>/close/", views.scansession_close, name="scansession_close"),
    path("<int:pk>/delete/", views.scansession_delete, name="scansession_delete"),
]
