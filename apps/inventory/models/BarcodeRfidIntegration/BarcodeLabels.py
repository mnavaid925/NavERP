"""Inventory 5.14 Barcode & RFID Integration — BarcodeLabel [LBL-].

**OWNERSHIP (L36/L29):**
SCM owns the Item / Location / LotSerial masters this register labels (L36) — Module 5 only
prints barcodes FOR them, pointing at the spine by string reference exactly like every other
model in this app. There is NO Pallet / LicensePlate master anywhere in NavERP, so ``pallet_ref``
is the documented L28 free-text stand-in pending a future pallet / HU master.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403


class BarcodeLabel(TenantNumbered):
    """A warehouse barcode label issued against an item SKU, bin, lot/serial or free-form code."""

    NUMBER_PREFIX = "LBL"

    TARGET_TYPE_CHOICES = [
        ("item", "Item SKU"),
        ("location", "Location / Bin"),
        ("lot", "Lot / Serial"),
        ("free", "Free-form"),
    ]

    LABEL_KIND_CHOICES = [
        ("product", "Product Label"),
        ("bin", "Bin Label"),
        ("pallet", "Pallet License Plate"),
        ("generic", "Generic"),
    ]

    SYMBOLOGY_CHOICES = [
        ("code39", "Code 39"),
        ("code128", "Code 128"),
        ("ean13", "EAN-13"),
        ("qr", "QR Code"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("printed", "Printed"),
        ("void", "Voided"),
    ]

    target_type = models.CharField(
        max_length=16,
        choices=TARGET_TYPE_CHOICES,
        default="item",
        help_text="Which L36 master this label points at",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="barcode_labels",
        help_text="The labelled item SKU (for target_type='item')",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="barcode_labels",
        help_text="The labelled location / bin (for target_type='location')",
    )
    lot_serial = models.ForeignKey(
        "scm.LotSerial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="barcode_labels",
        help_text="The labelled lot or serial number (for target_type='lot')",
    )
    target_ref = models.CharField(
        max_length=64,
        blank=True,
        help_text="Raw code for free-form targets",
    )
    pallet_ref = models.CharField(
        max_length=64,
        blank=True,
        help_text=(
            "License-plate / pallet reference — free-text stand-in: no pallet/HU master "
            "exists yet (L28)"
        ),
    )
    label_kind = models.CharField(
        max_length=16,
        choices=LABEL_KIND_CHOICES,
        default="product",
        help_text="Physical role this label plays on the floor",
    )
    symbology = models.CharField(
        max_length=12,
        choices=SYMBOLOGY_CHOICES,
        default="code128",
        help_text="Barcode symbology used to render the payload",
    )
    payload = models.CharField(
        max_length=120,
        help_text="Exact string encoded into the barcode",
    )
    copies = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        help_text="Number of physical labels one print run produces",
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Lifecycle of this label registration",
    )
    printed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="When the label was last printed (refreshed on reprint)",
    )
    printed_by = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="printed_barcode_labels",
        help_text="Stamped by print()/integrations — there is NO User→Party link in NavERP, never guess one",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Internal operator notes",
    )

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_lbl_tnt_stat_idx"),
            models.Index(fields=["tenant", "target_type"], name="inv_lbl_tnt_tgt_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_symbology_display()} → {self.payload})"

    def default_payload(self):
        """Derive the encoded string from the linked L36 master's own code."""
        if self.target_type == "item" and self.item_id:
            return self.item.sku
        if self.target_type == "location" and self.location_id:
            return self.location.code
        if self.target_type == "lot" and self.lot_serial_id:
            return self.lot_serial.number
        if self.target_type == "free":
            return self.target_ref.strip()
        return ""

    def save(self, *args, **kwargs):
        if not self.payload:
            self.payload = self.default_payload() or self.target_ref.strip()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return

        # Cross-tenant guards on the L36 masters pointed at by FK.
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "Item belongs to another workspace."})
        if self.location_id and getattr(self.location, "tenant_id", None) != tenant_id:
            raise ValidationError({"location": "Location belongs to another workspace."})
        if self.lot_serial_id and getattr(self.lot_serial, "tenant_id", None) != tenant_id:
            raise ValidationError({"lot_serial": "Lot/Serial belongs to another workspace."})

    def print(self, *, user=None, party=None):
        """Stamp + flip this label to ``printed`` inside one transaction.

        Printing a draft stamps ``printed_at`` and flips the status; REPRINTING an
        already-printed label is allowed and refreshes the stamp; only a voided label refuses.
        ``party`` (a ``core.Party``) stamps ``printed_by`` when given — there is NO User→Party
        link in NavERP, so callers holding only an authenticated user pass nothing rather than
        guessing one; the existing stamp is kept otherwise. ``user`` is accepted for caller
        convenience/logging symmetry and deliberately unused here.
        """
        if self.status == "void":
            raise ValidationError({"status": "Voided labels cannot be printed."})
        with transaction.atomic():
            self.status = "printed"
            self.printed_at = timezone.now()
            if party is not None:
                self.printed_by = party
            self.save(update_fields=["status", "printed_at", "printed_by", "updated_at"])

    def void(self):
        """Pull the label out of circulation; voiding twice refuses loudly."""
        if self.status == "void":
            raise ValidationError({"status": "Label has already been voided."})
        self.status = "void"
        self.save(update_fields=["status", "updated_at"])
