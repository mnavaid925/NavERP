"""Inventory 5.14 Barcode & RFID Integration — RfidTag [TAG-].

**OWNERSHIP (L36/L29):**
The EPC itself IS the identifier, so a tag carries no ``number`` prefix — this is ``TenantOwned``,
NOT ``TenantNumbered``. Module 5 owns only the tag register: ``scm.Item``, ``scm.Location`` and
``scm.LotSerial`` are pointed at, never re-declared (L36). No pallet / handling-unit master exists
anywhere in NavERP yet, so ``pallet_ref`` is a free-text stand-in (L28) until one lands.
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403


class RfidTag(TenantOwned):
    """A physical RFID tag [TAG-] tracked by its EPC across its unassigned → active → retired/lost life."""

    KIND_CHOICES = [
        ("passive", "Passive (UHF)"),
        ("active", "Active / Powered"),
    ]

    STATUS_CHOICES = [
        ("unassigned", "Unassigned"),
        ("active", "Active"),
        ("retired", "Retired"),
        ("lost", "Lost"),
    ]

    epc = models.CharField(
        max_length=64,
        validators=[RegexValidator(r"^[0-9A-F\-]{8,64}$", message="EPC must be 8-64 hex characters (hyphens allowed).")],
        help_text="Electronic Product Code — uppercase hex, hyphens allowed; unique per workspace",
    )
    kind = models.CharField(
        max_length=10,
        choices=KIND_CHOICES,
        default="passive",
        help_text="Passive UHF label or battery-powered active tag",
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="unassigned",
        help_text="Lifecycle state — moved only by the activate/retire/mark-lost actions",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfid_tags",
        help_text="Item this tag is attached to (optional)",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfid_tags",
        help_text="Bin/location the tag is assigned to (optional)",
    )
    lot_serial = models.ForeignKey(
        "scm.LotSerial",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfid_tags",
        help_text="Specific lot or serial the tag identifies (optional)",
    )
    target_ref = models.CharField(
        max_length=64,
        blank=True,
        help_text="Free-text reference for targets without a master record",
    )
    pallet_ref = models.CharField(
        max_length=64,
        blank=True,
        help_text="Pallet/HU reference — free text; no pallet master exists in NavERP yet",
    )
    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Timestamp of the most recent reader sweep that reported this EPC",
    )
    last_seen_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="rfid_last_seen_reads",
        help_text="Read point of the most recent reader sweep",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free-form notes",
    )

    class Meta:
        ordering = ["epc"]
        # (tenant, epc) lookups are already served by the unique_together index; adding an
        # identical non-unique inv_tag_tnt_epc_idx would only double MariaDB write cost.
        unique_together = [("tenant", "epc")]
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_tag_tnt_stat_idx"),
        ]

    def __str__(self):
        return f"{self.epc} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        self.epc = (self.epc or "").strip().upper()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.epc = (self.epc or "").strip().upper()

        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "Item belongs to another workspace."})
        if self.location_id and getattr(self.location, "tenant_id", None) != tenant_id:
            raise ValidationError({"location": "Location belongs to another workspace."})
        if self.lot_serial_id and getattr(self.lot_serial, "tenant_id", None) != tenant_id:
            raise ValidationError({"lot_serial": "Lot/Serial belongs to another workspace."})

    def has_target(self):
        """True when the tag points at anything — an item, bin, lot or free-text reference."""
        return bool(
            self.item_id
            or self.location_id
            or self.lot_serial_id
            or (self.target_ref or "").strip()
            or (self.pallet_ref or "").strip()
        )

    def activate(self):
        if self.status != "unassigned":
            raise ValidationError(f"A {self.get_status_display()} tag cannot be activated.")
        if not self.has_target():
            raise ValidationError("Attach the tag to an item, bin, lot or reference before activating.")
        self.status = "active"

    def retire(self):
        if self.status not in ("active", "unassigned"):
            raise ValidationError(f"A {self.get_status_display()} tag cannot be retired.")
        self.status = "retired"

    def mark_lost(self):
        if self.status != "active":
            raise ValidationError("Only an active tag can be marked lost.")
        self.status = "lost"

    @classmethod
    def bulk_read(cls, tenant, epcs, location=None, at=None):
        """Record a reader sweep over a batch of EPCs.

        Dedupes + normalizes the input (the caller caps the batch size), then updates every
        matching tag of ANY status within the tenant with one queryset ``update()``. Unknown EPCs
        are computed BEFORE the update and returned as a sorted list — pure service method, no
        exception is raised for unrecognized codes.
        """
        normalized = {str(e).strip().upper() for e in epcs}
        normalized.discard("")
        tags = cls.objects.filter(tenant=tenant, epc__in=normalized)
        unknown = sorted(set(normalized) - set(tags.values_list("epc", flat=True)))
        matched = tags.update(last_seen_at=at or timezone.now(), last_seen_location=location)
        return {"matched": matched, "unknown": unknown}
