"""Inventory 5.14 Barcode & RFID Integration — ScanSession [SSN-] and ScanEvent.

**OWNERSHIP (L36/L29):**
The scanned TARGETS stay owned by their home spines — ``scm.Item`` (SKU), ``scm.Location``
(bin code), ``scm.LotSerial`` (lot/serial number) and this sub-module's own ``RfidTag`` (EPC).
What 5.14 adds is the capture layer: a scan session groups the raw strings a device pushed,
and each event keeps WHAT was read, what it RESOLVED to at scan time (kind + pk + human label
snapshot) and whether it resolved at all — so re-labelling an item later can never rewrite
history.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403
from apps.scm.models import Item, Location, LotSerial


class ScanSession(TenantNumbered):
    """A scanning work period on one device [SSN-] — open while captures land, closed to freeze."""

    NUMBER_PREFIX = "SSN"

    MODE_CHOICES = [
        ("single", "Single Scan"),
        ("batch", "Batch / Paste-many"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    device_label = models.CharField(
        max_length=80,
        help_text="Rugged handheld or wedge scanner name (e.g. 'Zebra TC22 - Dock 3')",
    )
    mode = models.CharField(
        max_length=8,
        choices=MODE_CHOICES,
        default="single",
        help_text="Single Scan accepts one code per submit; Batch / Paste-many takes a pasted list",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="open",
        help_text="Open sessions accept scans; closing freezes the session for audit",
    )
    operator = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="scan_sessions",
        help_text="Operator party, stamped by seeding/integrations — NavERP has NO User→Party link",
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        help_text="When scanning began",
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="When the session was closed",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free-text context for this session (shift, dock, campaign…)",
    )

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_ssn_tnt_stat_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_mode_display()} on {self.device_label})"

    def clean(self):
        super().clean()

    def close(self):
        """Close the session exactly once — ended_at is stamped here, never edited later."""
        if self.status == "closed":
            raise ValidationError("This scan session is already closed.")
        self.status = "closed"
        self.ended_at = timezone.now()


def resolve_code(tenant, raw):
    """Resolve one raw scanned string against the tenant's spine:
    ``scm.Item.sku`` → ``scm.Location.code`` → ``scm.LotSerial.number`` → ``inventory.RfidTag.epc``.
    Returns ``(kind, obj|None)``. Tenant-scoped iexact everywhere; empty → ``("unknown", None)``.
    RfidTag comparison upper-cases.

    Duplicated numbers are possible on LotSerial (uniqueness is tenant+item+number), so every
    multi-row lookup is ordered by ``id`` — the OLDEST master wins deterministically."""
    code = (raw or "").strip()
    if not code:
        return ("unknown", None)

    item = Item.objects.filter(tenant=tenant, sku__iexact=code).order_by("id").first()
    if item is not None:
        return ("item", item)

    location = Location.objects.filter(tenant=tenant, code__iexact=code).order_by("id").first()
    if location is not None:
        return ("location", location)

    lot_serial = LotSerial.objects.filter(tenant=tenant, number__iexact=code).order_by("id").first()
    if lot_serial is not None:
        return ("lot", lot_serial)

    # Lazy sibling import: RfidTags lives in this package and imports back into it, so a
    # module-level import would be circular during the models package load.
    from .RfidTags import RfidTag

    tag = RfidTag.objects.filter(tenant=tenant, epc=code.upper()).order_by("id").first()
    if tag is not None:
        return ("rfid", tag)

    return ("unknown", None)


class ScanEvent(TenantOwned):
    """One immutable captured string inside a session, with its resolution snapshot."""

    RESOLVED_KIND_CHOICES = [
        ("item", "Item"),
        ("location", "Location"),
        ("lot", "Lot / Serial"),
        ("rfid", "RFID Tag"),
        ("unknown", "Unknown"),
    ]

    session = models.ForeignKey(
        ScanSession,
        on_delete=models.CASCADE,
        related_name="events",
        help_text="The parent scan session that captured this code",
    )
    raw_code = models.CharField(
        max_length=120,
        help_text="The raw scanned/pasted string exactly as the device delivered it",
    )
    resolved_kind = models.CharField(
        max_length=10,
        choices=RESOLVED_KIND_CHOICES,
        default="unknown",
        help_text="Which spine entity the code matched at scan time",
    )
    resolved_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Primary key of the matched row, snapshotted at scan time",
    )
    resolved_label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Human-readable snapshot of the match at scan time",
    )
    ok = models.BooleanField(
        default=False,
        help_text="Whether the code resolved to any known record",
    )
    scanned_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        help_text="Capture timestamp",
    )

    class Meta:
        # Append-only ledger: (-scanned_at, -id) is exact recency AND rides the
        # inv_scnev_tnt_scan_idx composite for the console's rolling-24h aggregate.
        ordering = ["-scanned_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "session"], name="inv_scnev_tnt_sess_idx"),
            models.Index(fields=["tenant", "resolved_kind"], name="inv_scnev_tnt_kind_idx"),
            models.Index(fields=["tenant", "scanned_at"], name="inv_scnev_tnt_scan_idx"),
        ]

    def __str__(self):
        return f"{self.raw_code} → {self.get_resolved_kind_display()}"

    @classmethod
    def record(cls, session, raw_code, kind=None, obj=None):
        """Append one capture row. Empty/whitespace codes are skipped silently (returns None);
        everything else saves directly (full_clean-exempt — the console validates its own input)
        with the resolution snapshot taken from ``obj`` when one matched."""
        code = (raw_code or "").strip()
        if not code:
            return None
        return cls.objects.create(
            tenant=session.tenant,
            session=session,
            raw_code=code[:120],
            resolved_kind=kind or "unknown",
            resolved_id=obj.pk if obj is not None else None,
            resolved_label=str(obj)[:120] if obj is not None else "",
            ok=obj is not None,
        )
