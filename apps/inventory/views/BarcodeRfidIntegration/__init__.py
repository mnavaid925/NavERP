"""Inventory BarcodeRfidIntegration views package (Sub-module 5.14)."""
from .BarcodeLabels import (
    barcodelabel_create,
    barcodelabel_delete,
    barcodelabel_detail,
    barcodelabel_edit,
    barcodelabel_list,
    barcodelabel_print,
    barcodelabel_render,
)
from .RfidTags import (
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
from .ScanSessions import (
    scan_console,
    scansession_close,
    scansession_create,
    scansession_delete,
    scansession_detail,
    scansession_edit,
    scansession_list,
)

__all__ = [
    "barcodelabel_list",
    "barcodelabel_detail",
    "barcodelabel_create",
    "barcodelabel_edit",
    "barcodelabel_delete",
    "barcodelabel_print",
    "barcodelabel_render",
    "scan_console",
    "scansession_list",
    "scansession_detail",
    "scansession_create",
    "scansession_edit",
    "scansession_close",
    "scansession_delete",
    "rfidtag_list",
    "rfidtag_detail",
    "rfidtag_create",
    "rfidtag_edit",
    "rfidtag_delete",
    "rfidtag_activate",
    "rfidtag_retire",
    "rfidtag_mark_lost",
    "rfidtag_bulkread",
]

