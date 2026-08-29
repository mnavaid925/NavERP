"""Procurement 6.11 Order Fulfillment & Tracking — AdvancedShipmentNotice + AsnLine models.

**Advanced Shipping Notice (ASN)** bullet: the supplier's PRE-ARRIVAL declaration of what is on
its way against one ``scm.PurchaseOrder`` — what shipped, in how many packages, on whose truck,
under which tracking number, and when it is expected. Receiving reads it BEFORE the truck arrives
so the dock knows what to expect; the discrepancy fold (short / over / mixed) is what turns it
from a courtesy notification into a control.

**Ownership (L36) — 6.11 is READ-ONLY against the SCM spine.** ``scm.PurchaseOrder`` and
``scm.PurchaseOrderLine`` are owned by SCM 4.1 and mutated only by 6.10's
``PurchaseOrderChange.apply()``. Nothing in this module writes ``PurchaseOrderLine.quantity`` /
``unit_price`` / ``tax_rate_pct`` or ``PurchaseOrder.expected_date`` / ``status`` / ``version``.
Likewise ``scm.Shipment`` (SCM 4.6) OWNS freight milestones: an ASN SELECTS a shipment and READS
its projections (``current_status_text`` / ``last_known_location`` / ``eta``) — it never creates a
shipment and never appends a ``scm.TrackingEvent``. That is why there is no second tracking log
here.

**No item FK anywhere in 6.11, deliberately.** ``core.Item`` does not exist and
``scm.PurchaseOrderLine`` itself carries no item FK — it is free text
(``item_description`` / ``sku_hint`` / ``uom_hint``). ``AsnLine`` therefore MIRRORS that free
text, auto-copied from the PO line when left blank. Similarly ``scm.LotSerial`` exists but is NOT
FK'd: lot / serial / expiry / country-of-origin here are the supplier's DECLARATION as plain
text; the real ``LotSerial`` row is created at RECEIPT, which is 6.12's job. The only hand-off
6.12 needs is the data hook ``supplier_reference`` -> ``scm.GoodsReceiptNote.delivery_note_ref``.

**Carrier is a dual field on purpose**, not a stand-in: ``carrier`` FK is nullable AND
``carrier_name`` free text exists, because a supplier's own courier frequently has no
``scm.Carrier`` TMS profile. ``carrier_display`` folds the two for the templates.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class AdvancedShipmentNotice(TenantNumbered):
    """One supplier shipping notice against one purchase order [ASN-].

    Lifecycle: ``draft`` -> ``submitted`` -> ``in_transit`` -> ``delivered``, with ``cancelled``
    reachable from anything that has not already been delivered. Every transition is a VERB
    METHOD that re-checks its own guard inside itself (the 6.9 C1 lesson): hiding a button in a
    template does not stop a direct POST, and a double-submit must not re-stamp a delivery.

    One ASN per purchase order shipment — consolidated multi-PO ASNs are deliberately out of
    scope this pass.
    """

    NUMBER_PREFIX = "ASN"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    #: Still live work — anything not yet delivered or abandoned.
    OPEN_STATUSES = ("draft", "submitted", "in_transit")
    #: Declared to us and physically on its way — the window a delivery may be confirmed from.
    IN_FLIGHT_STATUSES = ("submitted", "in_transit")
    #: Header/lines may still be corrected; a delivered or cancelled ASN is a closed record.
    EDITABLE_STATUSES = ("draft", "submitted", "in_transit")

    #: How the notice reached us. ``edi`` records provenance for the deferred EDI 856 intake —
    #: ASNs are STAFF-recorded in this pass (L32: a staff sidebar bullet never points at a
    #: login-gated vendor page), so there is no supplier self-file screen.
    SOURCE_CHOICES = [
        ("portal", "Supplier Portal"),
        ("email", "Email"),
        ("edi", "EDI 856"),
        ("manual", "Manual Entry"),
    ]
    FREIGHT_TERMS_CHOICES = [
        ("prepaid", "Prepaid"),
        ("collect", "Collect"),
        ("third_party", "Third Party"),
        ("prepaid_and_charged", "Prepaid & Charged"),
    ]
    CONDITION_CHOICES = [
        ("good", "Good"),
        ("damaged", "Damaged"),
        ("partial", "Partial"),
        ("refused", "Refused"),
    ]

    # -- badge maps (L33) ----------------------------------------------------------------------
    # theme.css modifier classes are COLOUR-NAMED ONLY: badge-green / badge-red / badge-amber /
    # badge-info / badge-muted / badge-slate. A semantic ``badge-success`` / ``badge-danger``
    # renders COMPLETELY UNSTYLED — that bug has shipped four times; never invent one here.
    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "in_transit": "badge-amber",
        "delivered": "badge-green",
        "cancelled": "badge-muted",
    }
    CONDITION_CSS = {
        "good": "badge-green",
        "damaged": "badge-red",
        "partial": "badge-amber",
        "refused": "badge-red",
    }
    DISCREPANCY_CSS = {
        "ok": "badge-green",
        "short": "badge-amber",
        "over": "badge-info",
        "mixed": "badge-red",
    }
    SOURCE_CSS = {
        "portal": "badge-info",
        "email": "badge-slate",
        "edi": "badge-green",
        "manual": "badge-muted",
    }

    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder", on_delete=models.PROTECT, related_name="procurement_asns",
        help_text="The order this shipment is declared against",
    )
    supplier_reference = models.CharField(
        max_length=64, blank=True,
        help_text="Vendor's own ASN / delivery-note number",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft",
                              editable=False)
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default="manual")

    ship_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    # Stamped by confirm_delivery(), never typed — a system moment on a date widget silently
    # truncates to midnight (L22), so it stays off the form entirely.
    delivered_at = models.DateTimeField(null=True, blank=True, editable=False)

    carrier = models.ForeignKey(
        "scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_asns",
        help_text="TMS carrier profile, when the freight rides on one",
    )
    carrier_name = models.CharField(
        max_length=120, blank=True,
        help_text="Supplier's own courier when there is no TMS profile",
    )
    tracking_number = models.CharField(max_length=64, blank=True)
    shipment = models.ForeignKey(
        "scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_asns",
        help_text="Inbound SCM 4.6 shipment whose tracking projections this ASN reads",
    )
    bill_of_lading_ref = models.CharField("Bill of lading ref", max_length=64, blank=True)
    container_ref = models.CharField(max_length=64, blank=True)
    freight_terms = models.CharField(max_length=20, choices=FREIGHT_TERMS_CHOICES, blank=True)

    # The packing cube is deliberately FLAT: package/pallet counts, not a recursive
    # pallet -> carton handling-unit tree. Per-carton detail lives on the line's package_ref.
    package_count = models.PositiveIntegerField(null=True, blank=True)
    pallet_count = models.PositiveIntegerField(null=True, blank=True)
    gross_weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(ZERO)])
    volume_cbm = models.DecimalField("Volume (CBM)", max_digits=12, decimal_places=3, null=True,
                                     blank=True, validators=[MinValueValidator(ZERO)])

    # -- proof-of-delivery block: written ONLY by confirm_delivery() ----------------------------
    arrival_condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, blank=True,
                                         editable=False)
    pod_reference = models.CharField("POD reference", max_length=64, blank=True, editable=False)
    received_signature_name = models.CharField(max_length=120, blank=True, editable=False)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, editable=False,
                                     related_name="procurement_asns_confirmed")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="procurement_asns_created")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancellation_reason = models.TextField(blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # Every index below backs a filter the list/board pages actually issue: the ?status=
            # dropdown and both boards' status buckets, the late/ETA date arithmetic, and the
            # ?po= filter plus the PO detail's reverse lookup.
            models.Index(fields=["tenant", "status"], name="prc_asn_tnt_status_idx"),
            models.Index(fields=["tenant", "expected_delivery_date"],
                         name="prc_asn_tnt_expdate_idx"),
            models.Index(fields=["tenant", "purchase_order"], name="prc_asn_tnt_po_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # See line_rows(): the detail page folds the same rows three ways (count, quantity,
        # discrepancy verdict) and must not re-query — or re-aggregate each PO line's received
        # quantity — once per fold.
        self._line_rows_cache = None

    def __str__(self):
        return f"{self.number or 'ASN'} · {self.purchase_order.number}"

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.purchase_order_id and self.tenant_id:
            if self.purchase_order.tenant_id != self.tenant_id:
                errors["purchase_order"] = "That purchase order belongs to another workspace."

        reference = (self.supplier_reference or "").strip()
        if reference and self.tenant_id:
            # A supplier's own delivery-note number is the key receiving matches on, and 6.12
            # hands it to GoodsReceiptNote.delivery_note_ref — two live ASNs claiming one
            # reference would make that match ambiguous. Cancelled rows are exempt: a re-issued
            # notice after a cancellation legitimately reuses the supplier's number.
            duplicates = (type(self).objects
                          .filter(tenant_id=self.tenant_id, supplier_reference=reference)
                          .exclude(status="cancelled"))
            if self.pk:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                errors["supplier_reference"] = (
                    "Another live ASN in this workspace already carries that supplier reference."
                )

        if self.ship_date and self.expected_delivery_date:
            if self.expected_delivery_date < self.ship_date:
                errors["expected_delivery_date"] = "Delivery cannot be expected before it ships."

        if self.shipment_id:
            shipment = self.shipment
            if shipment.tenant_id != self.tenant_id:
                errors["shipment"] = "That shipment belongs to another workspace."
            elif shipment.direction != "inbound":
                errors["shipment"] = "An ASN tracks an INBOUND shipment from a supplier."

        if self.carrier_id and self.carrier.tenant_id != self.tenant_id:
            errors["carrier"] = "That carrier belongs to another workspace."

        if errors:
            raise ValidationError(errors)

    # -- verbs ---------------------------------------------------------------------------------
    # Each re-checks its own guard INSIDE the method and returns a bool. The view holds a row
    # lock around the call, so a double-submit finds the guard already closed and no-ops instead
    # of re-stamping.

    def submit(self):
        """Draft -> submitted: the notice is now a declaration we hold the supplier to."""
        if self.status != "draft":
            return False
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])
        return True

    def mark_in_transit(self):
        """Goods have left the supplier. Reachable straight from draft — a notice frequently
        arrives only once the truck has already rolled, and forcing a submit step first would
        make the trail lie about when we learned of it."""
        if self.status not in ("draft", "submitted"):
            return False
        self.status = "in_transit"
        fields = ["status", "updated_at"]
        if self.submitted_at is None:
            # Skipping submit must not leave the declaration moment blank.
            self.submitted_at = timezone.now()
            fields.append("submitted_at")
        self.save(update_fields=fields)
        return True

    def confirm_delivery(self, user, delivered_at=None, arrival_condition="good",
                         pod_reference="", received_signature_name=""):
        """Stamp arrival + the proof-of-delivery block. A second call is a NO-OP returning
        ``False`` so a double-submitted confirmation cannot re-stamp the delivery moment,
        overwrite the POD, or reassign who signed for it."""
        if self.status not in self.IN_FLIGHT_STATUSES:
            return False
        valid_conditions = {value for value, _ in self.CONDITION_CHOICES}
        self.status = "delivered"
        self.delivered_at = delivered_at or timezone.now()
        self.arrival_condition = (arrival_condition
                                  if arrival_condition in valid_conditions else "good")
        self.pod_reference = (pod_reference or "").strip()[:64]
        self.received_signature_name = (received_signature_name or "").strip()[:120]
        self.confirmed_by = user if getattr(user, "pk", None) else None
        self.save(update_fields=["status", "delivered_at", "arrival_condition", "pod_reference",
                                 "received_signature_name", "confirmed_by", "updated_at"])
        return True

    def cancel(self, user, reason):
        """Abandon the notice. Refused once delivered — arrival is a fact, not a decision to
        take back; a mis-booked delivery is corrected by 6.12's receipt, not by un-arriving.
        ``user`` is accepted for symmetry with the other verbs and is recorded by the caller's
        audit-log row (the cancellation itself names no actor column)."""
        if self.status in ("delivered", "cancelled"):
            return False
        self.status = "cancelled"
        self.cancelled_at = timezone.now()
        self.cancellation_reason = (reason or "").strip()[:2000]
        self.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
        return True

    # -- derived (NEVER stored, L29) -----------------------------------------------------------

    def line_rows(self):
        """This ASN's declared lines, fetched ONCE per instance.

        ``line_count``, ``total_quantity_shipped`` and ``discrepancy_verdict`` all fold the same
        rows, and every row's ``outstanding_at_declare`` costs one aggregate against the PO line.
        Sharing one fetch keeps the detail page at ``1 + lines`` queries instead of ``3 x`` that.
        The detail view hands this exact list to the template as ``lines`` so the template's own
        per-row reads hit the same memoized ``PurchaseOrderLine`` instances.
        """
        if self._line_rows_cache is None:
            self._line_rows_cache = list(
                self.lines.select_related("po_line", "po_line__purchase_order").order_by("id")
            )
        return self._line_rows_cache

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_in_flight(self):
        return self.status in self.IN_FLIGHT_STATUSES

    @property
    def is_late(self):
        return bool(self.expected_delivery_date
                    and self.status in self.IN_FLIGHT_STATUSES
                    and self.expected_delivery_date < timezone.localdate())

    @property
    def days_late(self):
        if not self.is_late:
            return 0
        return (timezone.localdate() - self.expected_delivery_date).days

    @property
    def tracking_status_text(self):
        """The freshest freight status available — SCM 4.6's projection when a shipment is
        linked, else our own lifecycle label."""
        if self.shipment_id and self.shipment.current_status_text:
            return self.shipment.current_status_text
        return self.get_status_display()

    @property
    def eta_display(self):
        if self.shipment_id and self.shipment.eta:
            return self.shipment.eta
        return self.expected_delivery_date

    @property
    def location_display(self):
        if self.shipment_id:
            return self.shipment.last_known_location or ""
        return ""

    @property
    def carrier_display(self):
        if self.carrier_id:
            return self.carrier.name
        return self.carrier_name

    @property
    def line_count(self):
        # The list page annotates ``line_total=Count("lines")``, so a row there answers this for
        # free instead of one query per row.
        annotated = getattr(self, "line_total", None)
        if annotated is not None:
            return annotated
        return len(self.line_rows())

    @property
    def total_quantity_shipped(self):
        return sum((row.quantity_shipped or ZERO) for row in self.line_rows())

    @property
    def discrepancy_verdict(self):
        """``ok`` / ``short`` / ``over`` / ``mixed`` folded from the lines.

        Over-shipping is a WARNING, never a hard block — the supplier has already loaded the
        truck by the time we read the notice, so refusing to record it would only make the
        system disagree with the dock.
        """
        over = short = False
        for row in self.line_rows():
            if row.is_over:
                over = True
            if row.is_short:
                short = True
        if over and short:
            return "mixed"
        if over:
            return "over"
        if short:
            return "short"
        return "ok"

    @property
    def discrepancy_css(self):
        return self.DISCREPANCY_CSS.get(self.discrepancy_verdict, "badge-slate")

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def condition_css(self):
        return self.CONDITION_CSS.get(self.arrival_condition, "badge-slate")

    @property
    def source_css(self):
        return self.SOURCE_CSS.get(self.source, "badge-slate")


class AsnLine(models.Model):
    """One declared line of an ASN — tenant-less, scoped through ``asn`` (the
    ``PurchaseOrderChangeLine`` precedent).

    The item identity MIRRORS the PO line's free text rather than pointing at an item master:
    ``scm.PurchaseOrderLine`` has no item FK, and ``core.Item`` does not exist. Blank text is
    auto-copied from the PO line on save so the declaration reads correctly even when the
    supplier only sent quantities.

    Lot / serial / expiry / country-of-origin are the supplier's PRE-ARRIVAL declaration as plain
    text. They are deliberately NOT ``scm.LotSerial`` rows: the real traceability record is
    created when goods are physically accepted, which is 6.12's receipt, and minting one here
    would put unreceived stock into the traceability chain.
    """

    #: over-shipped / short-shipped / exactly on the outstanding balance (L33: colours only).
    VARIANCE_CSS = {
        "over": "badge-info",
        "short": "badge-amber",
        "exact": "badge-green",
    }

    asn = models.ForeignKey("procurement.AdvancedShipmentNotice", on_delete=models.CASCADE,
                            related_name="lines")
    po_line = models.ForeignKey("scm.PurchaseOrderLine", on_delete=models.PROTECT,
                                related_name="asn_lines",
                                help_text="Which ordered line this declares against")
    item_description = models.CharField(max_length=255, blank=True,
                                        help_text="Blank copies the PO line's description")
    sku_hint = models.CharField(max_length=64, blank=True)
    uom_hint = models.CharField("UOM hint", max_length=32, blank=True)
    quantity_shipped = models.DecimalField(max_digits=14, decimal_places=4, default=1,
                                           validators=[MinValueValidator(Decimal("0.0001"))])
    package_ref = models.CharField(max_length=64, blank=True,
                                   help_text="Carton / pallet / LPN reference")
    lot_number = models.CharField(max_length=64, blank=True)
    serial_number = models.CharField(max_length=64, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    country_of_origin = models.CharField(max_length=64, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
        # One declaration per ordered line per notice — two rows against one line would make the
        # discrepancy fold ambiguous (and double-count the shipped quantity).
        unique_together = ("asn", "po_line")

    def __str__(self):
        return f"{self.item_description or self.po_line} ×{self.quantity_shipped}"

    def clean(self):
        errors = {}
        if self.asn_id and self.po_line_id:
            if self.po_line.purchase_order_id != self.asn.purchase_order_id:
                # A crafted POST must not staple another order's line onto this notice.
                errors["po_line"] = "That line belongs to a different purchase order."
        if self.quantity_shipped is not None and self.quantity_shipped <= ZERO:
            errors["quantity_shipped"] = "Declare a quantity greater than zero."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.po_line_id:
            source = self.po_line
            if not (self.item_description or "").strip():
                self.item_description = source.item_description
            if not (self.sku_hint or "").strip():
                self.sku_hint = source.sku_hint or ""
            if not (self.uom_hint or "").strip():
                self.uom_hint = source.uom_hint or ""
        super().save(*args, **kwargs)

    # -- derived (NEVER stored) ----------------------------------------------------------------

    @property
    def outstanding_at_declare(self):
        """What the PO line still expects — ordered minus already-received, read live off the
        spine. ``PurchaseOrderLine.received_quantity()`` memoizes per instance, so a template
        that reads this and ``variance`` and ``shortfall`` on one row costs ONE aggregate."""
        if not self.po_line_id:
            return ZERO
        return self.po_line.outstanding_quantity()

    @property
    def variance(self):
        return (self.quantity_shipped or ZERO) - self.outstanding_at_declare

    @property
    def shortfall(self):
        gap = self.outstanding_at_declare - (self.quantity_shipped or ZERO)
        return gap if gap > ZERO else ZERO

    @property
    def is_over(self):
        return self.variance > ZERO

    @property
    def is_short(self):
        return self.shortfall > ZERO

    @property
    def variance_css(self):
        if self.is_over:
            return self.VARIANCE_CSS["over"]
        if self.is_short:
            return self.VARIANCE_CSS["short"]
        return self.VARIANCE_CSS["exact"]
