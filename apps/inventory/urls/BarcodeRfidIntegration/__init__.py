"""Inventory BarcodeRfidIntegration URL patterns package (Sub-module 5.14)."""
from .BarcodeLabels import urlpatterns as _br_labels
from .RfidTags import urlpatterns as _br_tags
from .ScanSessions import urlpatterns as _br_sessions

urlpatterns = [
    *_br_sessions,
    *_br_tags,
    *_br_labels,
]

