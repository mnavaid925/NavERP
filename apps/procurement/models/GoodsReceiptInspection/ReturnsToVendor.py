"""Procurement 6.12 Goods Receipt & Inspection — ReturnToVendor + ReturnToVendorLine models.

**Return to Vendor (RTV) Processing** bullet: the COMMERCIAL consequence of a bad receipt. Goods
were rejected on the dock, or accepted and then failed inspection; this register records what is
going back, to whom, under whose RMA, on whose truck, and what we expect in return (credit,
replacement, repair, or nothing).

**Ownership (L36) — 6.12 owns the commercial document, never a third quality register.**
``apps/quality`` does not exist and is not being invented here. SCM 4.9 owns
``InspectionPlan -> QualityInspection -> NonConformance``; inventory 5.15 owns
``QcChecklist / QcRoutingRule / QuarantineOrder / DefectReport``. An RTV POINTS at those through
the discrepancy it was raised from — it never re-declares them, and it never re-declares a vendor
master either: ``vendor`` is a ``core.Party`` carrying the supplier/vendor ``PartyRole``.

**DELIBERATE NON-POSTING — an RTV posts NO ``StockMove`` and NO ``JournalEntry``.** This is a
design decision, not an omission, and it is defended here AND on ``rtv/detail.html`` so nobody
"fixes" it into a double-posting:

* ``apps/scm/views/_helpers.py:299 _post_grn_receipt`` posts ONLY ``line.quantity_received``.
  Dock-REJECTED quantity therefore never entered stock or the ledger in the first place, so an
  RTV raised against it has nothing to remove — subtracting it would create negative stock out of
  goods we never booked.
* Stock that WAS accepted and later failed inspection is removed by the module that owns that
  movement: ``inventory.QuarantineOrder.scrap()`` or ``scm:stockadjustment``. One writer per
  effect (L36).
* The AP side is blocked on a spine gap, not on effort: ``accounting.Bill`` has no ``kind``
  discriminating a vendor credit note, and inventing a stored credit balance here would be
  exactly the derived-value-stored-editable mistake of L29. ``credit_note_ref`` is therefore FREE
  TEXT — the reference of a credit raised in AP, recorded so the two can be reconciled by eye.

``scm.NonConformance`` already takes the same posture for its own ``return_to_vendor``
disposition, so this is the module's existing convention rather than a new one.

**No item FK anywhere, deliberately.** ``core.Item`` does not exist, and ``scm.GoodsReceiptLine``
and ``scm.PurchaseOrderLine`` both carry free text rather than an item FK. ``ReturnToVendorLine``
MIRRORS that free text (auto-copied from its source line when left blank — the ``AsnLine.save()``
shape) instead of hard-FK'ing ``scm.Item``. Best-effort item resolution is the module-level
``resolve_line_item()`` helper in ``ReceiptTolerances.py``.

**Freight is free text this pass (L36).** SCM 4.6 owns ``Shipment`` / ``TrackingEvent`` for
inbound freight; an outbound return leg has no owner yet, so ``carrier_name`` /
``tracking_number`` are plain strings rather than a second tracking log.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class ReturnToVendor(TenantNumbered):
    """One return shipment back to a supplier [RTV-].

    Lifecycle: ``draft`` -> ``authorized`` -> ``shipped`` -> ``closed``, with ``cancelled``
    reachable from anything not yet shipped. Every transition is a VERB METHOD that re-checks its
    own guard INSIDE itself and returns a bool (the 6.9 C1 lesson): hiding a button in a template
    does not stop a direct POST, and a double-submitted authorize must not re-stamp who signed it.

    Header/lines are editable in ``draft`` only. Once the return is authorized the supplier has
    been told what is coming back, and silently re-writing the lines under an issued RMA is how a
    disputed credit starts.
    """

    NUMBER_PREFIX = "RTV"

    REASON_CHOICES = [
        ("damaged", "Damaged"),
        ("defective", "Defective"),
        ("wrong_item", "Wrong item"),
        ("over_shipment", "Over-shipment"),
        ("expired", "Expired"),
        ("not_to_spec", "Not to spec"),
        ("other", "Other"),
    ]
    REMEDY_CHOICES = [
        ("credit", "Credit"),
        ("replacement", "Replacement"),
        ("repair", "Repair"),
        ("none", "No remedy"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("authorized", "Authorized"),
        ("shipped", "Shipped"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: Header + lines may still be corrected.
    EDITABLE_STATUSES = ("draft",)
    #: Abandonable while the goods have not physically left — once shipped, the return is a fact.
    CANCELLABLE_STATUSES = ("draft", "authorized")

    # -- badge maps (L33) ----------------------------------------------------------------------
    # theme.css modifier classes are COLOUR-NAMED ONLY: badge-green / badge-red / badge-amber /
    # badge-info / badge-muted / badge-slate. A semantic ``badge-success`` / ``badge-danger``
    # renders COMPLETELY UNSTYLED — that bug has shipped four times; never invent one here.
    STATUS_CSS = {
        "draft": "badge-muted",
        "authorized": "badge-info",
        "shipped": "badge-amber",
        "closed": "badge-green",
        "cancelled": "badge-slate",
    }
    REASON_CSS = {
        "damaged": "badge-red",
        "defective": "badge-red",
        "expired": "badge-red",
        "wrong_item": "badge-amber",
        "over_shipment": "badge-amber",
        "not_to_spec": "badge-amber",
        "other": "badge-muted",
    }
    REMEDY_CSS = {
        "credit": "badge-info",
        "replacement": "badge-info",
        "repair": "badge-slate",
        "none": "badge-muted",
    }

    vendor = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="procurement_rtvs",
        help_text="The supplier the goods go back to",
    )
    # All three origins are nullable: a return is occasionally raised against a supplier before
    # anyone has worked out which receipt it came off, and refusing to record it until then just
    # means it is recorded nowhere.
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_rtvs",
    )
    goods_receipt = models.ForeignKey(
        "scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_rtvs",
        help_text="The receipt these goods arrived on",
    )
    discrepancy = models.ForeignKey(
        "procurement.ReceiptDiscrepancy", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rtvs",
        help_text="The receiving finding this return answers",
    )

    reason = models.CharField(max_length=14, choices=REASON_CHOICES)
    reason_note = models.CharField(
        max_length=255, blank=True,
        help_text="Required when the reason is 'Other'",
    )
    remedy = models.CharField(max_length=11, choices=REMEDY_CHOICES, default="credit")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft",
                              editable=False)

    supplier_rma_number = models.CharField(
        "Supplier RMA number", max_length=64, blank=True,
        help_text="The supplier's return authorization number",
    )
    # Freight is free text this pass — SCM 4.6 owns inbound Shipment/TrackingEvent and there is
    # no owner for the outbound return leg yet (L36). A second tracking log here would give the
    # workspace two answers about where a parcel is.
    carrier_name = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=64, blank=True)
    # Stamped by mark_shipped(), never typed.
    shipped_on = models.DateField(null=True, blank=True, editable=False)
    expected_return_date = models.DateField(
        null=True, blank=True,
        help_text="When the replacement / credit is expected back",
    )
    credit_note_ref = models.CharField(
        max_length=64, blank=True,
        help_text=("Reference only — the AP credit is blocked on the accounting.Bill.kind gap "
                   "(L29); this posts NOTHING to the ledger."),
    )

    authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, editable=False,
                                      related_name="procurement_rtvs_authorized")
    authorized_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancellation_reason = models.TextField(blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="procurement_rtvs_created")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # Each index backs a filter the register actually issues: the ?status= dropdown and
            # the four stat cards, the ?vendor= dropdown plus the vendor detail's reverse lookup,
            # and the ?reason= dropdown.
            models.Index(fields=["tenant", "status"], name="prc_rtv_tnt_status_idx"),
            models.Index(fields=["tenant", "vendor"], name="prc_rtv_tnt_vendor_idx"),
            models.Index(fields=["tenant", "reason"], name="prc_rtv_tnt_reason_idx"),
            # The duplicate-RMA badge is an Exists() correlated subquery keyed on exactly this
            # pair (see ReturnsToVendor._scoped), so without it the database re-scans the whole
            # RTV table once per row of every list page.
            models.Index(fields=["tenant", "supplier_rma_number"], name="prc_rtv_tnt_rma_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The detail page folds the same lines three ways (count, credit total, the rendered
        # table) and the list page reads the credit total per row — one fetch per instance.
        self._line_rows_cache = None
        # Seeded by the list view's Exists() annotation (see has_duplicate_rma) so a page of rows
        # costs zero extra queries instead of one apiece.
        self._duplicate_rma_cache = None

    def __str__(self):
        return f"{self.number or 'RTV'} · {self.vendor}"

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.vendor_id and self.tenant_id and self.vendor.tenant_id != self.tenant_id:
            errors["vendor"] = "That supplier belongs to another workspace."

        if self.purchase_order_id:
            order = self.purchase_order
            if self.tenant_id and order.tenant_id != self.tenant_id:
                errors["purchase_order"] = "That purchase order belongs to another workspace."
            elif self.vendor_id and order.vendor_id != self.vendor_id:
                # Returning goods to someone other than the supplier who sold them is either a
                # typo or a crafted POST; both must land as a field error, not as a saved row.
                errors["purchase_order"] = "That order was placed with a different supplier."

        if self.goods_receipt_id:
            receipt = self.goods_receipt
            if self.tenant_id and receipt.tenant_id != self.tenant_id:
                errors["goods_receipt"] = "That receipt belongs to another workspace."
            elif self.purchase_order_id and receipt.purchase_order_id != self.purchase_order_id:
                errors["goods_receipt"] = "That receipt is against a different purchase order."

        if self.discrepancy_id and self.tenant_id:
            if self.discrepancy.tenant_id != self.tenant_id:
                errors["discrepancy"] = "That record belongs to another workspace."

        if self.reason == "other" and not (self.reason_note or "").strip():
            errors["reason_note"] = "Say what the reason is when choosing 'Other'."

        if errors:
            raise ValidationError(errors)

    # -- verbs ---------------------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool. The view holds a row lock
    # around the call, so a double-submit finds the guard already closed and no-ops instead of
    # re-stamping.

    def authorize(self, user):
        """Draft -> authorized: the return is approved and the supplier can be told."""
        if self.status != "draft":
            return False
        self.status = "authorized"
        self.authorized_by = user if getattr(user, "pk", None) else None
        self.authorized_at = timezone.now()
        self.save(update_fields=["status", "authorized_by", "authorized_at", "updated_at"])
        return True

    def mark_shipped(self, user, carrier_name="", tracking_number="", shipped_on=None):
        """Authorized -> shipped: the goods have physically left us.

        Carrier and tracking are only OVERWRITTEN when the ship form supplies them — the header
        may already carry what was arranged when the RMA was issued, and a blank field in the
        ship dialog means "unchanged", never "erase it". ``user`` is accepted for symmetry with
        the other verbs; the shipping actor is recorded by the caller's audit-log row (this model
        deliberately carries no ``shipped_by`` column).
        """
        if self.status != "authorized":
            return False
        fields = ["status", "shipped_on", "updated_at"]
        self.status = "shipped"
        self.shipped_on = shipped_on or timezone.localdate()
        carrier_name = (carrier_name or "").strip()
        if carrier_name:
            self.carrier_name = carrier_name[:120]
            fields.append("carrier_name")
        tracking_number = (tracking_number or "").strip()
        if tracking_number:
            self.tracking_number = tracking_number[:64]
            fields.append("tracking_number")
        self.save(update_fields=fields)
        return True

    def close(self, user, credit_note_ref=""):
        """Shipped -> closed: the remedy landed (credit raised, replacement received, repair
        returned). ``credit_note_ref`` is a REFERENCE — closing an RTV posts nothing to the
        ledger; see the class docstring."""
        if self.status != "shipped":
            return False
        fields = ["status", "closed_at", "updated_at"]
        self.status = "closed"
        self.closed_at = timezone.now()
        credit_note_ref = (credit_note_ref or "").strip()
        if credit_note_ref:
            self.credit_note_ref = credit_note_ref[:64]
            fields.append("credit_note_ref")
        self.save(update_fields=fields)
        return True

    def cancel(self, user, reason):
        """Abandon the return. Refused once shipped — the goods are physically gone, and
        un-shipping them by editing a status would make the register lie. A return that went out
        and came back is closed, not cancelled."""
        if self.status not in self.CANCELLABLE_STATUSES:
            return False
        self.status = "cancelled"
        self.cancelled_at = timezone.now()
        self.cancellation_reason = (reason or "").strip()[:2000]
        self.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
        return True

    # -- derived (NEVER stored, L29) -----------------------------------------------------------

    def line_rows(self):
        """This return's lines, fetched ONCE per instance.

        Honours a caller's ``prefetch_related("lines", …)`` when there is one — the register
        prefetches so a page of rows costs a fixed number of queries rather than one credit fold
        per row.
        """
        if self._line_rows_cache is None:
            if "lines" in getattr(self, "_prefetched_objects_cache", {}):
                self._line_rows_cache = list(self.lines.all())
            else:
                self._line_rows_cache = list(
                    self.lines.select_related(
                        "po_line", "goods_receipt_line", "goods_receipt_line__po_line",
                    ).order_by("id")
                )
        return self._line_rows_cache

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def line_count(self):
        return len(self.line_rows())

    @property
    def expected_credit_value(self):
        """What we expect back, priced off the ordered lines — computed at read time, never a
        stored balance (L29). Clamped by ``q2`` to what a money column actually holds so a
        fat-fingered quantity is a wrong number rather than a driver ``DataError``."""
        total = ZERO
        for line in self.line_rows():
            total += line.expected_credit
        return q2(total)

    @property
    def has_duplicate_rma(self):
        """ADVISORY only — another live return in this workspace already quotes this RMA number.

        Warns, never blocks: suppliers legitimately issue one RMA covering several shipments, so
        refusing the second row would be wrong more often than it would be right. The register
        seeds ``rma_duplicate_flag`` from one ``Exists()`` annotation; the live query below is the
        fallback for a single instance (the detail page) that carries no annotation.
        """
        annotated = getattr(self, "rma_duplicate_flag", None)
        if annotated is not None:
            return bool(annotated)
        if self._duplicate_rma_cache is None:
            reference = (self.supplier_rma_number or "").strip()
            if not reference or not self.tenant_id:
                self._duplicate_rma_cache = False
            else:
                peers = (type(self).objects
                         .filter(tenant_id=self.tenant_id, supplier_rma_number=reference)
                         .exclude(status="cancelled"))
                if self.pk:
                    peers = peers.exclude(pk=self.pk)
                self._duplicate_rma_cache = peers.exists()
        return self._duplicate_rma_cache

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def reason_css(self):
        return self.REASON_CSS.get(self.reason, "badge-slate")

    @property
    def remedy_css(self):
        return self.REMEDY_CSS.get(self.remedy, "badge-slate")


class ReturnToVendorLine(models.Model):
    """One line of a return — tenant-less, scoped through ``return_to_vendor`` (the ``AsnLine`` /
    ``PurchaseOrderChangeLine`` precedent). It has no urls and no templates of its own; it is
    edited through the inline formset on the RTV form page.

    Both source pointers are optional and independent: a return raised straight off a receipt
    line carries ``goods_receipt_line``, while one raised against an order that was never
    formally received carries only ``po_line``. ``po_line`` is what SIZES the expected credit —
    it is the only place a unit price exists, because ``scm.GoodsReceiptLine`` carries quantities
    and no money.

    Item identity MIRRORS the source line's free text rather than pointing at an item master:
    ``scm.PurchaseOrderLine`` has no item FK and ``core.Item`` does not exist. Blank text is
    auto-copied on save so the return reads correctly even when only quantities were typed.
    """

    return_to_vendor = models.ForeignKey("procurement.ReturnToVendor", on_delete=models.CASCADE,
                                         related_name="lines")
    goods_receipt_line = models.ForeignKey(
        "scm.GoodsReceiptLine", on_delete=models.PROTECT, null=True, blank=True,
        related_name="procurement_rtv_lines",
        help_text="The received line these goods came in on",
    )
    po_line = models.ForeignKey(
        "scm.PurchaseOrderLine", on_delete=models.PROTECT, null=True, blank=True,
        related_name="procurement_rtv_lines",
        help_text="Sizes the expected credit through its unit price",
    )
    item_description = models.CharField(max_length=255, blank=True,
                                        help_text="Blank copies the source line's description")
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField("UOM hint", max_length=32, blank=True)
    quantity_returned = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                            validators=[MinValueValidator(Decimal("0.0001"))])
    lot_number = models.CharField(max_length=64, blank=True)
    serial_number = models.CharField(max_length=64, blank=True)
    condition_note = models.CharField(max_length=255, blank=True,
                                      help_text="What is wrong with this specific quantity")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.item_description or self.po_line} ×{self.quantity_returned}"

    def clean(self):
        errors = {}

        if self.quantity_returned is not None and self.quantity_returned <= ZERO:
            errors["quantity_returned"] = "Return a quantity greater than zero."

        # Guard on the *_id attributes throughout: inside an inline formset a NEW row's parent FK
        # is not assigned until save(), so touching ``self.return_to_vendor`` directly would raise
        # RelatedObjectDoesNotExist instead of validating.
        if self.goods_receipt_line_id and self.po_line_id:
            if self.goods_receipt_line.po_line_id != self.po_line_id:
                # A crafted POST must not staple an unrelated ordered line onto a received one —
                # that is how a return gets priced off somebody else's unit price.
                errors["po_line"] = "That ordered line is not the one this receipt line received."

        if self.goods_receipt_line_id and self.return_to_vendor_id:
            header_receipt_id = self.return_to_vendor.goods_receipt_id
            if header_receipt_id and self.goods_receipt_line.goods_receipt_id != header_receipt_id:
                errors["goods_receipt_line"] = "That line belongs to a different goods receipt."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        source = None
        if self.goods_receipt_line_id and self.goods_receipt_line.po_line_id:
            source = self.goods_receipt_line.po_line
        elif self.po_line_id:
            source = self.po_line
        if source is not None:
            if not (self.item_description or "").strip():
                self.item_description = source.item_description
            if not (self.sku_hint or "").strip():
                self.sku_hint = source.sku_hint or ""
            if not (self.uom_hint or "").strip():
                self.uom_hint = source.uom_hint or ""
        super().save(*args, **kwargs)

    # -- derived (NEVER stored) ----------------------------------------------------------------

    @property
    def unit_price(self):
        """Read live off the ordered line. Checked with explicit ``_id`` tests rather than
        ``a or b``, because a legitimately zero-priced line (a free replacement) must return zero
        rather than falling through to the other source."""
        if self.po_line_id:
            return self.po_line.unit_price or ZERO
        if self.goods_receipt_line_id and self.goods_receipt_line.po_line_id:
            return self.goods_receipt_line.po_line.unit_price or ZERO
        return ZERO

    @property
    def expected_credit(self):
        return q2((self.quantity_returned or ZERO) * self.unit_price)
