"""Inventory 5.14 Barcode & RFID Integration — ScanSession form.

Status, operator and the timestamps are lifecycle/system-owned (never on the form): sessions
open at create and leave ``open`` only through the close verb. The form is deliberately tiny —
a device label, a capture mode and free-text context.
"""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.models.BarcodeRfidIntegration.ScanSessions import ScanSession


class ScanSessionForm(TenantUniqueMixin, TenantModelForm):
    """Open a scanning session on one device.

    TenantUniqueMixin stamps ``instance.tenant`` in ``__init__`` (same role it plays for
    every form whose model reads its own tenant), so a direct ``form.save()`` — not just
    the CRUD-helper path — mints a properly tenanted session.
    """

    class Meta:
        model = ScanSession
        fields = ["device_label", "mode", "notes"]
