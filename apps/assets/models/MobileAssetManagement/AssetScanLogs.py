from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetScanLog(TenantNumbered):
    """
    Timestamped audit trail of barcode, QR code, and RFID scans executed on mobile devices
    in yards, warehouses, and client sites [ASCN-].
    """

    NUMBER_PREFIX = "ASCN"

    SCAN_CONTEXT_CHOICES = [
        ("field_audit", "Field Cycle Count / Physical Audit"),
        ("checkout_verification", "Tool & Equipment Custody Check-out"),
        ("work_order_init", "Work Order Asset Identification"),
        ("receiving", "Dock Receiving & Tag Ingestion"),
        ("location_reconciliation", "Location / Yard Move Verification"),
    ]

    SCAN_METHOD_CHOICES = [
        ("camera_barcode", "Device Camera 1D Barcode"),
        ("camera_qr", "Device Camera 2D QR Code"),
        ("bluetooth_rfid", "Bluetooth RFID / NFC Reader"),
        ("handheld_laser", "Rugged Handheld Laser Scanner"),
        ("manual_entry", "Manual Fallback Entry"),
    ]

    MATCH_STATUS_CHOICES = [
        ("matched", "Asset Verified & Matched"),
        ("not_found", "Tag Not In Registry"),
        ("mismatched", "Location / Serial Mismatch"),
        ("unassigned", "Blank Tag Ingested"),
    ]

    MATCH_STATUS_CSS = {
        "matched": "badge-green",
        "not_found": "badge-red",
        "mismatched": "badge-amber",
        "unassigned": "badge-slate",
    }

    SCAN_METHOD_CSS = {
        "camera_barcode": "badge-info",
        "camera_qr": "badge-green",
        "bluetooth_rfid": "badge-purple",
        "handheld_laser": "badge-slate",
        "manual_entry": "badge-muted",
    }

    SCAN_CONTEXT_CSS = {
        "field_audit": "badge-info",
        "checkout_verification": "badge-slate",
        "work_order_init": "badge-amber",
        "receiving": "badge-green",
        "location_reconciliation": "badge-purple",
    }

    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_scans",
    )
    scanned_at = models.DateTimeField(default=timezone.now)
    scan_context = models.CharField(max_length=32, choices=SCAN_CONTEXT_CHOICES, default="field_audit")
    scan_method = models.CharField(max_length=24, choices=SCAN_METHOD_CHOICES, default="camera_qr")
    raw_payload = models.CharField(max_length=255, help_text="Raw scanned barcode string, QR payload, or RFID EPC")
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_logs",
    )
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default="matched")
    gps_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_accuracy_m = models.FloatField(null=True, blank=True)
    device_info = models.CharField(max_length=150, blank=True, help_text="Mobile hardware & browser agent info")
    notes = models.CharField(max_length=255, blank=True)
    client_sync_id = models.CharField(max_length=64, blank=True)
    is_offline_captured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-scanned_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_ascn_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "match_status"], name="idx_ascn_ten_stat"),
            models.Index(fields=["tenant", "scan_context"], name="idx_ascn_ten_ctxt"),
            models.Index(fields=["tenant", "scan_method"], name="idx_ascn_ten_meth"),
            models.Index(fields=["tenant", "scanned_at"], name="idx_ascn_ten_date"),
        ]

    def __str__(self):
        return f"{self.number} - {self.raw_payload} ({self.get_match_status_display()})"

    @property
    def match_status_badge_class(self):
        return self.MATCH_STATUS_CSS.get(self.match_status, "badge-slate")

    @property
    def scan_method_badge_class(self):
        return self.SCAN_METHOD_CSS.get(self.scan_method, "badge-slate")

    @property
    def scan_context_badge_class(self):
        return self.SCAN_CONTEXT_CSS.get(self.scan_context, "badge-slate")
