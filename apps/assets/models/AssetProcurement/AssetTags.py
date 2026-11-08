from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetTag(TenantNumbered):
    """Machine-readable tag registry, physical affixation tracking, and scanner verification [ATAG-]."""

    NUMBER_PREFIX = "ATAG"

    TAG_FORMAT_CHOICES = [
        ("qr_code", "QR Code (2D Data Matrix)"),
        ("barcode_128", "Code 128 Linear Barcode"),
        ("rfid_uhf", "UHF Gen2 RFID EPC Tag"),
        ("nfc", "NFC HF Tag (13.56 MHz)"),
        ("metal_plate", "Anodized Aluminum Asset Nameplate"),
    ]

    STATUS_CHOICES = [
        ("pending_print", "Pending Print"),
        ("printed", "Printed / Awaiting Affixation"),
        ("affixed", "Affixed to Physical Asset"),
        ("verified", "Scanner Verified"),
        ("damaged_reissued", "Damaged / Reissued"),
        ("retired", "Decommissioned / Retired"),
    ]

    STATUS_CSS = {
        "pending_print": "badge-slate",
        "printed": "badge-info",
        "affixed": "badge-amber",
        "verified": "badge-green",
        "damaged_reissued": "badge-red",
        "retired": "badge-muted",
    }

    # Tag identifier
    tag_code = models.CharField(
        max_length=64,
        help_text="Machine-readable barcode, QR payload, or RFID EPC UID. Must be unique in this workspace.",
    )
    tag_format = models.CharField(max_length=30, choices=TAG_FORMAT_CHOICES, default="qr_code")

    # Associated asset records
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_tags",
        help_text="Operational asset record in plant register",
    )
    capitalization = models.ForeignKey(
        "assets.AssetCapitalization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_tags",
        help_text="Capitalization event that prompted tag issuance",
    )

    # Physical affixation details
    physical_placement = models.CharField(
        max_length=255,
        blank=True,
        help_text="Physical location on machine/chassis (e.g. Front upper-left bezel near power input)",
    )
    affixed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affixed_asset_tags",
    )
    affixed_at = models.DateTimeField(null=True, blank=True)

    # Field scanner audit & verification
    is_verified = models.BooleanField(default=False, help_text="Certified verified by field barcode/RFID scanner")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_asset_tags",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    scanner_device_id = models.CharField(max_length=64, blank=True, help_text="Handheld terminal, Zebra, or RFID reader ID")

    # Lifecycle & notes
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending_print")
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "assets_tag"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_atag_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "tag_code"], name="assets_atag_ten_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_atag_ten_stat"),
            models.Index(fields=["tenant", "is_verified"], name="idx_atag_ten_ver"),
            models.Index(fields=["tenant", "tag_format"], name="idx_atag_ten_fmt"),
            models.Index(fields=["tenant", "created_at"], name="idx_atag_ten_created"),
        ]

    def __str__(self):
        return f"{self.tag_code} ({self.number})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    def can_mark_printed(self):
        return self.status == "pending_print"

    def can_affix(self):
        return self.status in ("pending_print", "printed")

    def can_verify(self):
        return self.status == "affixed" and not self.is_verified

    def can_affix_tag(self):
        return self.can_affix()

    def can_verify_tag(self):
        return self.can_verify()
