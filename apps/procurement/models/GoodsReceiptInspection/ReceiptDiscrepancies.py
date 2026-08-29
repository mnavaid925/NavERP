"""Procurement 6.12 Goods Receipt & Inspection — ReceiptDiscrepancy model.

**Discrepancy Reporting** bullet: the COMMERCIAL claim raised when what arrived does not match
what was ordered — short, over, damaged, wrong item, failed quality, missing paperwork, late.
One row per finding against one ``scm.GoodsReceiptNote`` (optionally pinned to one of its lines),
carrying the evidence, the remedy the buyer and the supplier agree on, and the trail of when the
vendor was told.

**Ownership (L36) — this is the CONSEQUENCE register, not a third quality register.** SCM 4.9
owns ``InspectionPlan -> QualityInspection -> NonConformance``; inventory 5.15 owns
``QcChecklist`` / ``QcRoutingRule`` / ``QuarantineOrder`` / ``DefectReport``; ``apps/quality``
does not exist. A discrepancy POINTS at those through nullable ``SET_NULL`` FKs and never raises
one, never re-declares one, and never adds a field to one. Likewise the physical facts stay where
they already live: booking a receipt is ``scm:goodsreceipt_receive``'s job.

**Posts NOTHING to stock and NOTHING to the ledger.** A discrepancy is a statement about a
receipt, not a movement of it. Dock-rejected quantity never entered stock in the first place
(``_post_grn_receipt`` posts only ``quantity_received``), accepted stock that later fails QC is
removed by ``inventory.QuarantineOrder.scrap()`` or ``scm:stockadjustment``, and the money side
travels on the linked ``ReturnToVendor``'s ``credit_note_ref`` free text because
``accounting.Bill`` has no vendor-credit ``kind`` (L29). One writer per effect.

**No item FK, deliberately.** ``core.Item`` does not exist and neither ``scm.PurchaseOrderLine``
nor ``scm.GoodsReceiptLine`` carries one — they are free text. This model therefore MIRRORS that
text (``item_description`` / ``sku_hint``, auto-copied from the receipt line's PO line when left
blank, the ``AsnLine.save()`` shape), and item resolution anywhere in 6.12 goes through the
best-effort ``resolve_line_item()`` helper in ``ReceiptTolerances.py``.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class ReceiptDiscrepancy(TenantNumbered):
    """One recorded receipt discrepancy [RDS-].

    Lifecycle: ``open`` -> ``vendor_notified`` -> ``resolved``, with ``cancelled`` reachable from
    either open state (the finding turned out to be a mis-count, or was folded into another
    claim). ``status`` is ``editable=False`` and moves ONLY through the verb methods, each of
    which re-checks its own guard INSIDE itself and returns a bool (the 6.9 C1 lesson): hiding a
    button in a template does not stop a direct POST, and a double-submitted notification must
    not re-stamp the date we told the supplier.

    A finding may be HEADER-level (``goods_receipt_line`` left blank) — "the paperwork never
    arrived" is a real discrepancy that belongs to no single line.
    """

    NUMBER_PREFIX = "RDS"

    KIND_CHOICES = [
        ("over_shipment", "Over-shipment"),
        ("short_shipment", "Short shipment"),
        ("damaged", "Damaged"),
        ("wrong_item", "Wrong item"),
        ("quality_failure", "Quality failure"),
        ("documentation", "Documentation"),
        ("late_delivery", "Late delivery"),
    ]
    #: Kinds that are ABOUT a quantity — for these a figure is mandatory, because "some of it was
    #: damaged" is not a claim a supplier can act on.
    QUANTITY_KINDS = ("over_shipment", "short_shipment", "damaged", "wrong_item")

    SEVERITY_CHOICES = [
        ("minor", "Minor"),
        ("major", "Major"),
        ("critical", "Critical"),
    ]
    REMEDY_CHOICES = [
        ("pending", "Pending decision"),
        ("replacement", "Replacement"),
        ("credit", "Credit"),
        ("rtv", "Return to vendor"),
        ("accept_as_is", "Accept as is"),
        ("scrap", "Scrap"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("vendor_notified", "Vendor notified"),
        ("resolved", "Resolved"),
        ("cancelled", "Cancelled"),
    ]
    #: Still live work — the window every verb except ``notify_vendor`` operates from.
    OPEN_STATUSES = ("open", "vendor_notified")

    # -- badge maps (L33) ---------------------------------------------------------------------
    # theme.css modifier classes are COLOUR-NAMED ONLY: badge-green / badge-red / badge-amber /
    # badge-info / badge-muted / badge-slate. A semantic ``badge-success`` / ``badge-danger``
    # renders COMPLETELY UNSTYLED — that bug has shipped four times; never invent one here.
    STATUS_CSS = {
        "open": "badge-amber",
        "vendor_notified": "badge-info",
        "resolved": "badge-green",
        "cancelled": "badge-muted",
    }
    SEVERITY_CSS = {
        "minor": "badge-muted",
        "major": "badge-amber",
        "critical": "badge-red",
    }
    KIND_CSS = {
        "over_shipment": "badge-amber",
        "short_shipment": "badge-amber",
        "damaged": "badge-red",
        "wrong_item": "badge-red",
        "quality_failure": "badge-red",
        "documentation": "badge-slate",
        "late_delivery": "badge-info",
    }
    REMEDY_CSS = {
        "pending": "badge-muted",
        "replacement": "badge-info",
        "credit": "badge-info",
        "rtv": "badge-amber",
        "accept_as_is": "badge-slate",
        "scrap": "badge-red",
    }

    #: Suffixes the detail page may render inline rather than as a download link.
    IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")

    goods_receipt = models.ForeignKey(
        "scm.GoodsReceiptNote", on_delete=models.PROTECT,
        related_name="procurement_discrepancies",
        help_text="The receipt this finding was raised against",
    )
    goods_receipt_line = models.ForeignKey(
        "scm.GoodsReceiptLine", on_delete=models.PROTECT, null=True, blank=True,
        related_name="procurement_discrepancies",
        help_text="Leave blank for a header-level finding (e.g. missing paperwork)",
    )

    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, default="minor")
    quantity_affected = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)])

    # Free-text item identity, MIRRORED from the receipt line's PO line — there is no item FK to
    # point at anywhere on the receiving spine.
    item_description = models.CharField(max_length=255, blank=True,
                                        help_text="Blank copies the receipt line's description")
    sku_hint = models.CharField(max_length=64, blank=True)
    lot_number = models.CharField(max_length=64, blank=True)
    serial_number = models.CharField(max_length=64, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    description = models.TextField(help_text="What was found, in the buyer's own words")
    evidence = models.FileField(upload_to="procurement/receipt_evidence/%Y/%m/", null=True,
                                blank=True)
    evidence_url = models.URLField(
        blank=True,
        help_text="Link to evidence held elsewhere (used when no file is uploaded)",
    )

    remedy = models.CharField(max_length=12, choices=REMEDY_CHOICES, default="pending")

    # Moves ONLY through notify_vendor() / resolve() / cancel(). On a form it would let a crafted
    # POST jump straight to resolved without ever recording a remedy (L22).
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open",
                              editable=False)

    # -- vendor notification block: written ONLY by notify_vendor() ---------------------------
    vendor_notified_on = models.DateField(null=True, blank=True, editable=False)
    vendor_reference = models.CharField(
        max_length=64, blank=True,
        help_text="The supplier's own claim / case number, once they give us one",
    )

    # -- closure block: written ONLY by resolve() / cancel() ------------------------------------
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False,
                                    related_name="procurement_discrepancies_resolved")
    resolution_notes = models.TextField(blank=True, editable=False)

    # -- pointers at the registers that OWN the quality/return effects (L36) -------------------
    nonconformance = models.ForeignKey(
        "scm.NonConformance", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_discrepancies",
        help_text="SCM 4.9 quality record this finding was escalated into",
    )
    quarantine_order = models.ForeignKey(
        "inventory.QuarantineOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_discrepancies",
        help_text="Inventory 5.15 segregation raised for the suspect stock",
    )
    return_to_vendor = models.ForeignKey(
        "procurement.ReturnToVendor", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="source_discrepancies",
        help_text="The RTV raised to send the goods back",
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="procurement_discrepancies_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # Every index below backs a filter the register actually issues: the ?status= and
            # ?kind= dropdowns plus the stat cards' status/kind buckets, and the ?grn= filter
            # plus the receipt detail's reverse lookup.
            models.Index(fields=["tenant", "status"], name="prc_rds_tnt_status_idx"),
            models.Index(fields=["tenant", "kind"], name="prc_rds_tnt_kind_idx"),
            models.Index(fields=["tenant", "goods_receipt"], name="prc_rds_tnt_grn_idx"),
        ]
        verbose_name = "receipt discrepancy"
        verbose_name_plural = "receipt discrepancies"

    def __str__(self):
        return f"{self.number or 'RDS'} · {self.goods_receipt.number}"

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.goods_receipt_id and self.tenant_id:
            if self.goods_receipt.tenant_id != self.tenant_id:
                errors["goods_receipt"] = "That receipt belongs to another workspace."

        if self.goods_receipt_line_id:
            # ``scm.GoodsReceiptLine`` carries NO tenant column — it is scoped through its
            # header — so a crafted POST carrying another workspace's line pk is stopped HERE, by
            # insisting the line belongs to the receipt this finding names.
            if self.goods_receipt_line.goods_receipt_id != self.goods_receipt_id:
                errors["goods_receipt_line"] = "That line belongs to a different receipt."

        for name in ("nonconformance", "quarantine_order", "return_to_vendor"):
            chosen = getattr(self, f"{name}_id", None)
            if chosen and self.tenant_id:
                if getattr(self, name).tenant_id != self.tenant_id:
                    errors[name] = "That record belongs to another workspace."

        if self.kind in self.QUANTITY_KINDS:
            if not self.quantity_affected or self.quantity_affected <= ZERO:
                errors["quantity_affected"] = (
                    "Give the quantity affected — a short/over/damaged/wrong-item claim without "
                    "a figure is not something a supplier can act on."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Mirror the receipt line's free text so the claim reads correctly even when the buyer
        # only typed a quantity (the AsnLine.save() shape). There is no item FK to copy.
        # Skipped on a targeted ``update_fields`` write (every verb): the mirrored columns are not
        # in that list, so computing them would cost a query to persist nothing.
        if self.goods_receipt_line_id and kwargs.get("update_fields") is None:
            source = getattr(self.goods_receipt_line, "po_line", None)
            if source is not None:
                if not (self.item_description or "").strip():
                    self.item_description = source.item_description or ""
                if not (self.sku_hint or "").strip():
                    self.sku_hint = source.sku_hint or ""
        super().save(*args, **kwargs)

    # -- verbs ---------------------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool. The view holds a row
    # lock around the call, so a double-submit finds the guard already closed and no-ops instead
    # of re-stamping a date or reassigning who resolved it.

    def notify_vendor(self, user, reference="", notified_on=None):
        """Record that the supplier has been told. Only from ``open``.

        L32: there is no vendor login in this pass, so this stamps that WE notified them —
        transport (portal / EDI / email) is integration work, deliberately deferred. ``user`` is
        accepted for symmetry with the other verbs; the actor is recorded by the caller's audit
        row (there is no notified-by column).
        """
        if self.status != "open":
            return False
        # A blank reference must not wipe one the buyer already typed on the form.
        self.vendor_reference = (reference or self.vendor_reference or "").strip()[:64]
        self.vendor_notified_on = notified_on or timezone.localdate()
        self.status = "vendor_notified"
        self.save(update_fields=["status", "vendor_reference", "vendor_notified_on",
                                 "updated_at"])
        return True

    def resolve(self, user, remedy, notes):
        """Close the finding with an agreed remedy. Only from an OPEN status.

        The remedy is REQUIRED by the form (Ariba's rule: rejecting goods means saying
        replace-or-credit), and re-validated here against the model's own vocabulary so a crafted
        POST cannot store a remedy that renders as a blank badge.
        """
        if self.status not in self.OPEN_STATUSES:
            return False
        valid_remedies = {value for value, _ in self.REMEDY_CHOICES}
        if remedy in valid_remedies:
            self.remedy = remedy
        self.resolution_notes = (notes or "").strip()[:2000]
        self.resolved_at = timezone.now()
        self.resolved_by = user if getattr(user, "pk", None) else None
        self.status = "resolved"
        self.save(update_fields=["status", "remedy", "resolution_notes", "resolved_at",
                                 "resolved_by", "updated_at"])
        return True

    def cancel(self, user, notes=""):
        """Withdraw the finding — a mis-count, or folded into another claim. Only from an OPEN
        status: a resolved discrepancy is a record of what was agreed, not a decision to take
        back."""
        if self.status not in self.OPEN_STATUSES:
            return False
        self.resolution_notes = (notes or "").strip()[:2000]
        self.resolved_at = timezone.now()
        self.resolved_by = user if getattr(user, "pk", None) else None
        self.status = "cancelled"
        self.save(update_fields=["status", "resolution_notes", "resolved_at", "resolved_by",
                                 "updated_at"])
        return True

    # -- derived (NEVER stored, L29) -----------------------------------------------------------

    @property
    def order(self):
        """The purchase order behind the receipt. Not a column — one hop, and every queryset in
        this entity ``select_related``s it."""
        return self.goods_receipt.purchase_order

    @property
    def vendor(self):
        """The supplier the claim is against — a ``core.Party`` reached through the order.

        Deliberately NOT duplicated as a column: a stored copy would drift the moment 6.10's
        change order re-points anything, and there is exactly one right answer already.
        """
        order = self.order
        return order.vendor if order is not None else None

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def has_evidence(self):
        return bool(self.evidence) or bool((self.evidence_url or "").strip())

    @property
    def evidence_is_image(self):
        if not self.evidence:
            return False
        return (self.evidence.name or "").lower().endswith(self.IMAGE_SUFFIXES)

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def severity_css(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def kind_css(self):
        return self.KIND_CSS.get(self.kind, "badge-slate")

    @property
    def remedy_css(self):
        return self.REMEDY_CSS.get(self.remedy, "badge-slate")
