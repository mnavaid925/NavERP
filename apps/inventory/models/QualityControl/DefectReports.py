"""Inventory 5.15 Quality Control (QC) & Inspection — DefectReport [DEF-].

**Defect & Scrap Reporting** bullet: the floor's quick log of defective units found during
receiving, putaway, picking, packing or counting — with a photo and a one-click write-off.

Division of labour with SCM 4.9 (L36/L29): the ``NonConformance`` register is the quality
ENGINEERING finding (investigation, MRB board, CAPA linkage). This is the WAREHOUSE
capture that happens minutes after discovery; it may be *escalated* to an NCR via the
nullable ``ncr`` pointer when engineering must own it, but raising the NCR stays SCM's
flow. The write-off posts the SAME ledger shape NCR scrap does — a negative ``adjustment``
StockMove referenced ``DEF-…`` from the location where the units sit — so 4.3's valuation
and 5.17's reports read one consistent book. ``posts_stock`` keeps the executable-rule
discipline: only a written-off report has a leg, and only for stock that was actually IN
the location (units refused at the dock were never received).

The photo follows the 5.1 ProductFile pointer pattern (uploaded file OR external link,
this module's OWN image-only allowlist) — evidence belongs to the report, not to a
generic attachment queue nobody can find later.
"""
import os

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403


class DefectReport(TenantNumbered):
    """One floor-level defect capture, optionally written off [DEF-]."""

    NUMBER_PREFIX = "DEF"

    # Aligned with scm.NonConformance.DEFECT_CATEGORY_CHOICES so floor counts roll up
    # into engineering's defect taxonomy without a translation table.
    DEFECT_TYPE_CHOICES = [
        ("dimensional", "Dimensional"),
        ("visual_cosmetic", "Visual / Cosmetic"),
        ("functional", "Functional"),
        ("material", "Material"),
        ("packaging", "Packaging"),
        ("labelling", "Labelling"),
        ("contamination", "Contamination"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("minor", "Minor"),
        ("major", "Major"),
        ("critical", "Critical"),
    ]
    DISCOVERED_DURING_CHOICES = [
        ("receiving", "Receiving"),
        ("putaway", "Putaway"),
        ("picking", "Picking"),
        ("packing", "Packing"),
        ("cycle_count", "Cycle Count"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("written_off", "Written Off"),
        ("closed", "Closed — No Write-off"),
    ]
    EDITABLE_STATUSES = ("open",)

    STATUS_CSS = {
        "open": "badge-amber",
        "written_off": "badge-red",
        "closed": "badge-muted",
    }

    #: Uploads accepted for the evidence photo. Deliberately images-only — this is a
    #: camera-phone capture, not a document store (ProductFile already owns documents).
    ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, related_name="inventory_defect_reports")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="inventory_defect_reports",
        help_text="Where the defective units sit — the write-off draws from here")
    lot_serial = models.ForeignKey(
        "scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_defect_reports",
        help_text="Optional lot/serial for tracked items")
    quantity = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="How many units are affected")
    defect_type = models.CharField(max_length=18, choices=DEFECT_TYPE_CHOICES, default="other")
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, default="minor")
    discovered_during = models.CharField(
        max_length=11, choices=DISCOVERED_DURING_CHOICES, default="receiving")
    description = models.TextField(blank=True)
    photo = models.FileField(upload_to="inventory/defects/%Y/%m/", blank=True, null=True)
    photo_url = models.URLField(blank=True, help_text="External link — used when no file is uploaded")
    reported_by = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_defect_reports",
        help_text="An employee party — who found it")
    reported_on = models.DateField(default=timezone.localdate)
    ncr = models.ForeignKey(
        "scm.NonConformance", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_defect_reports",
        help_text="Set when escalated to the quality-engineering register (SCM owns that flow)")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open",
                              editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-reported_on", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_def_tnt_status_idx"),
            models.Index(fields=["tenant", "item"], name="inv_def_tnt_item_idx"),
            models.Index(fields=["tenant", "reported_on"], name="inv_def_tnt_date_idx"),
        ]

    # -- state ---------------------------------------------------------------------------------

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """Badge class for this row's status — see :attr:`STATUS_CSS`."""
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def photo_href(self):
        """Where the evidence lives — the uploaded file when there is one, else the link."""
        return self.photo.url if self.photo else (self.photo_url or "")

    @property
    def posts_stock(self):
        """Whether resolving this report has a ledger effect (NCR's executable-rule discipline).

        Only a WRITE-OFF moves stock, only from a known location. Units refused at the
        dock were never received (scm never posted them in), so their report closes as
        paper — writing a negative move would drive the location negative.
        """
        return self.status == "written_off" and self.item_id is not None and self.location_id is not None

    def ledger_moves(self):
        """This report's StockMove legs, newest first."""
        from apps.scm.models import StockMove
        return (StockMove.objects.filter(tenant_id=self.tenant_id, reference=self.number)
                .select_related("item", "location").order_by("-moved_at", "-id"))

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        errors = {}
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if self.location_id and getattr(self.location, "tenant_id", None) != tenant_id:
            errors["location"] = "That location belongs to another workspace."
        if self.lot_serial_id:
            if getattr(self.lot_serial, "tenant_id", None) != tenant_id:
                errors["lot_serial"] = "That lot/serial belongs to another workspace."
            elif self.item_id and self.lot_serial.item_id != self.item_id:
                errors["lot_serial"] = f"{self.lot_serial.number} belongs to a different item."
        if self.ncr_id and getattr(self.ncr, "tenant_id", None) != tenant_id:
            errors["ncr"] = "That non-conformance belongs to another workspace."
        if self.photo:
            ext = os.path.splitext(self.photo.name)[1].lower()
            if ext not in self.ALLOWED_IMAGE_EXTENSIONS:
                errors["photo"] = f"Files of type '{ext or '(none)'}' are not allowed — attach an image."
        if errors:
            raise ValidationError(errors)

    # -- actions (called by the views, which flash around them; audit inside the txn) -----------

    def _locked(self):
        """Re-read this row FOR UPDATE inside the caller's atomic block."""
        return type(self).objects.select_for_update().get(pk=self.pk)

    def writeoff(self, user):
        """Scrap the reported units where they sit: one guarded negative adjustment leg."""
        from apps.scm.models import Item
        with transaction.atomic():
            obj = self._locked()
            _item_lock = Item.objects.select_for_update().get(pk=obj.item_id)
            if obj.status != "open":
                raise ValidationError(
                    f"{obj.number} cannot be written off — it is "
                    f"{obj.get_status_display().lower()}.")
            qs = obj.item.stock_moves.filter(location=obj.location)
            if obj.lot_serial_id:
                qs = qs.filter(lot_serial=obj.lot_serial)
            available = qs.aggregate(q=Sum("quantity"))["q"] or ZERO
            if obj.quantity > available:
                raise ValidationError(
                    f"{obj.item.sku}: only {available} available at {obj.location.code}, "
                    f"cannot write off {obj.quantity}.")
            from apps.scm.models import StockMove
            StockMove.objects.create(
                tenant_id=obj.tenant_id, item=obj.item, location=obj.location,
                lot_serial=obj.lot_serial, quantity=-obj.quantity,
                unit_cost=obj.item.average_cost or ZERO, move_type="adjustment",
                reference=obj.number, reason=f"Defect write-off ({obj.get_defect_type_display()})",
                moved_at=timezone.now(),
            )
            obj.status = "written_off"
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, "writeoff", {"status": "written_off"})
        return obj

    def close(self, user):
        """Resolve without a write-off — cosmetic acceptance, vendor credit, RTV in flight.
        No ledger effect by construction (:attr:`posts_stock`)."""
        with transaction.atomic():
            obj = self._locked()
            if obj.status != "open":
                raise ValidationError(
                    f"{obj.number} cannot be closed — it is "
                    f"{obj.get_status_display().lower()}.")
            obj.status = "closed"
            obj.resolved_at = timezone.now()
            obj.save(update_fields=["status", "resolved_at", "updated_at"])
            write_audit_log(user, obj, "close", {"status": "closed"})
        return obj

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{self.number or 'DEF'} · {sku} ×{self.quantity} ({self.get_defect_type_display()})"
