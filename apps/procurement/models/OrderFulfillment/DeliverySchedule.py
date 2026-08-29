"""Procurement 6.11 Order Fulfillment & Tracking — DeliverySchedule model + split helper.

**Split Delivery Management** bullet: one ordered PO line delivered in several instalments. A
schedule row is one promised instalment — *how much* arrives, *when it is needed*, *what the
supplier promised instead*, *where it goes*, and (once an ASN declares it) *which shipment
covers it*.

**Why ``status`` is a form-editable field here, unlike the ASN's.**
``AdvancedShipmentNotice.status`` is ``editable=False`` and moves only through verb methods
because each transition STAMPS irreversible state off the row itself — ``submitted_at``,
``delivered_at``, the POD block, ``confirmed_by``, ``cancelled_at``. A form-editable status
there would let a hand-crafted POST claim "delivered" without ever stamping who confirmed it or
when. This ladder hangs NO timestamps and NO who-stamps off its own status: ``planned ->
confirmed -> shipped -> received`` is a buyer's plan annotation, the real evidence lives on the
ASN (arrival) and the GRN (6.12, receipt). With nothing to stamp there is nothing for a verb to
protect, so the field stays an honest ``<select>`` on the form and this model needs neither
verb methods nor ``editable=False``.

**Spine discipline (L36).** 6.11 is READ-ONLY against ``scm.PurchaseOrder*``: this model FKs
``scm.PurchaseOrderLine`` by string and never writes ``quantity`` / ``unit_price`` /
``expected_date`` / ``status`` on it. Coverage is DERIVED by aggregate over sibling rows, never
stored (L29) — a stored "scheduled so far" column would drift the moment a row is cancelled.

There is no ``core.Item``, and ``scm.PurchaseOrderLine`` carries no item FK, so this model
identifies what is coming purely through ``po_line`` — no item FK is invented here.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP

from apps.procurement.models._base import *  # noqa: F401,F403


class DeliverySchedule(TenantNumbered):
    """One promised instalment of a purchase order line [DSC-]."""

    NUMBER_PREFIX = "DSC"

    #: Ceiling on how many instalments one ``split_po_line()`` call may create. Lives on the
    #: MODEL (not module level) so the form can read it as ``DeliverySchedule.MAX_SPLIT_
    #: INSTALMENTS`` without the package __init__ having to re-export a second name — the UI cap
    #: and the helper's own defence can then never drift apart.
    MAX_SPLIT_INSTALMENTS = 12

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    ]
    #: Still live — counts toward coverage and can run late.
    OPEN_STATUSES = ("planned", "confirmed", "shipped")

    #: LOCAL to this model — deliberately NOT scm's transport MODE_CHOICES. That one describes a
    #: freight leg's carrier mode; this one is the buyer's instruction for how the instalment
    #: should reach them, including non-freight options (collection, dropship).
    MODE_CHOICES = [
        ("standard", "Standard"),
        ("express", "Express"),
        ("courier", "Courier"),
        ("freight", "Freight"),
        ("collection", "Collection"),
        ("dropship", "Dropship"),
    ]

    #: L33 — theme.css modifier classes are COLOUR-NAMED only. A semantic ``badge-success`` /
    #: ``badge-danger`` renders completely unstyled.
    STATUS_CSS = {
        "planned": "badge-slate",
        "confirmed": "badge-info",
        "shipped": "badge-amber",
        "received": "badge-green",
        "cancelled": "badge-muted",
    }
    MODE_CSS = {
        "standard": "badge-slate",
        "express": "badge-amber",
        "courier": "badge-info",
        "freight": "badge-info",
        "collection": "badge-muted",
        "dropship": "badge-green",
    }

    po_line = models.ForeignKey("scm.PurchaseOrderLine", on_delete=models.PROTECT,
                                related_name="procurement_delivery_schedules",
                                help_text="The ordered line this instalment delivers part of")
    sequence = models.PositiveIntegerField(default=1,
                                           help_text="Instalment number within the line (1, 2, 3 …)")
    scheduled_quantity = models.DecimalField(max_digits=14, decimal_places=4,
                                             validators=[MinValueValidator(Decimal("0.0001"))],
                                             help_text="How much of the line arrives in this instalment")
    need_by_date = models.DateField(help_text="When the business needs this instalment")

    # What the SUPPLIER came back with. Blank = no counter-promise yet; the slip is derived, not
    # stored, so correcting either date immediately corrects the slip.
    promised_quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True,
                                            validators=[MinValueValidator(ZERO)],
                                            help_text="Supplier's counter-offer quantity, if different")
    promised_date = models.DateField(null=True, blank=True,
                                     help_text="Supplier's committed date, if different from need-by")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")

    ship_to = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="procurement_delivery_schedules",
                                help_text="Site / unit this instalment is delivered to")
    delivery_mode = models.CharField(max_length=16, choices=MODE_CHOICES, blank=True)
    asn = models.ForeignKey("procurement.AdvancedShipmentNotice", on_delete=models.SET_NULL,
                            null=True, blank=True, related_name="delivery_schedules",
                            help_text="The advance shipping notice covering this instalment")
    change_reason = models.CharField(max_length=255, blank=True,
                                     help_text="Why this instalment's quantity or date moved")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="procurement_delivery_schedules_created")

    class Meta:
        # The ladder reads in instalment order within a line; ``po_line_id`` orders on the local
        # column so the default ordering never joins.
        ordering = ["po_line_id", "sequence", "id"]
        unique_together = (("tenant", "number"), ("tenant", "po_line", "sequence"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_dsc_tnt_status_idx"),
            models.Index(fields=["tenant", "need_by_date"], name="prc_dsc_tnt_needby_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Memoizes the sibling-coverage aggregate: the detail page and its template both ask, and
        # a template loop would otherwise re-issue the query on every render. The list view skips
        # it entirely by annotating ``sched_total_annot`` (one correlated subquery for the page).
        self._sched_total_cache = None

    def __str__(self):
        return f"{self.number or 'DSC'} · seq {self.sequence}"

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.po_line_id:
            line = self.po_line
            order = line.purchase_order
            if self.tenant_id and order.tenant_id != self.tenant_id:
                errors["po_line"] = "That purchase order line belongs to another workspace."
            else:
                # HARD BLOCK: instalments may not promise more than the line actually orders.
                # A SHORT total is never an error — under-coverage is a derived amber warning on
                # the board, because a buyer legitimately schedules part of a line first.
                # A cancelled instalment commits nothing, so it is exempt.
                if self.status != "cancelled":
                    ordered = line.quantity or ZERO
                    others = (DeliverySchedule.objects
                              .filter(tenant_id=self.tenant_id, po_line_id=self.po_line_id)
                              .exclude(status="cancelled"))
                    if self.pk:
                        others = others.exclude(pk=self.pk)
                    committed = others.aggregate(s=Sum("scheduled_quantity"))["s"] or ZERO
                    proposed = committed + (self.scheduled_quantity or ZERO)
                    if proposed > ordered:
                        errors["scheduled_quantity"] = (
                            f"Instalments would over-commit the PO line "
                            f"({proposed} of {ordered})."
                        )

            if self.asn_id:
                asn = self.asn
                if (self.tenant_id and asn.tenant_id != self.tenant_id) or \
                        asn.purchase_order_id != order.pk:
                    errors["asn"] = "That ASN belongs to another workspace or another order."

        if self.ship_to_id and self.tenant_id and self.ship_to.tenant_id != self.tenant_id:
            errors["ship_to"] = "That org unit belongs to another workspace."

        if self.promised_quantity is not None and self.promised_quantity <= ZERO:
            errors["promised_quantity"] = "A promised quantity must be greater than zero."

        if errors:
            raise ValidationError(errors)

    # -- derived values (NEVER stored — L29) ---------------------------------------------------

    @property
    def slip_days(self):
        """Days the supplier's promise slips past the need-by date (0 when there is no promise,
        negative when the supplier beat the need-by date)."""
        if not (self.promised_date and self.need_by_date):
            return 0
        return (self.promised_date - self.need_by_date).days

    @property
    def has_slip(self):
        return self.slip_days > 0

    @property
    def is_late(self):
        """Still open and the need-by date has already passed."""
        return bool(self.need_by_date and self.status in self.OPEN_STATUSES
                    and self.need_by_date < timezone.localdate())

    @property
    def days_late(self):
        if not self.is_late:
            return 0
        return (timezone.localdate() - self.need_by_date).days

    @property
    def line_scheduled_total(self):
        """Total scheduled across every non-cancelled instalment of this line, INCLUDING self.

        Prefers ``sched_total_annot`` when the caller annotated it (the list view does, so the
        whole page costs one correlated subquery instead of one query per row).
        """
        annotated = getattr(self, "sched_total_annot", None)
        if annotated is not None:
            return annotated
        if self._sched_total_cache is None:
            if not self.po_line_id:
                self._sched_total_cache = ZERO
            else:
                siblings = (DeliverySchedule.objects
                            .filter(tenant_id=self.tenant_id, po_line_id=self.po_line_id)
                            .exclude(status="cancelled"))
                total = siblings.aggregate(s=Sum("scheduled_quantity"))["s"] or ZERO
                if self.pk is None and self.status != "cancelled":
                    # Unsaved row: it is not in the query yet but it is part of the picture.
                    total += self.scheduled_quantity or ZERO
                self._sched_total_cache = total
        return self._sched_total_cache

    @property
    def remaining_quantity(self):
        """Ordered quantity not yet covered by any live instalment (negative is impossible —
        clean() blocks over-commitment)."""
        if not self.po_line_id:
            return ZERO
        return (self.po_line.quantity or ZERO) - self.line_scheduled_total

    @property
    def coverage_pct(self):
        """How much of the ordered line the live instalments cover, 0-100."""
        if not self.po_line_id:
            return 0
        ordered = self.po_line.quantity or ZERO
        if ordered <= ZERO:
            return 0
        pct = (self.line_scheduled_total / ordered * 100).quantize(Decimal("1"),
                                                                   rounding=ROUND_HALF_UP)
        return max(0, min(100, int(pct)))

    @property
    def is_under_covered(self):
        """The line still has unscheduled quantity — an amber warning, never an error."""
        return self.coverage_pct < 100

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def mode_css(self):
        return self.MODE_CSS.get(self.delivery_mode, "badge-muted")


def split_po_line(tenant, po_line, instalments, first_date, interval_days, user=None):
    """Split ONE purchase order line into evenly-spaced delivery instalments.

    Returns the list of created :class:`DeliverySchedule` rows. Raises ``ValidationError`` when
    the request is not splittable — the caller renders that as a non-field form error.

    Caller contract (enforced in ``deliveryschedule_split``): run inside ``transaction.atomic()``
    holding ``select_for_update()`` over the line's existing schedule rows, so two buyers hitting
    Split simultaneously cannot each read the same "already scheduled" total and together
    over-commit the line.

    **What is split is the UNCOMMITTED remainder, not the whole ordered quantity.** On a line
    with no schedule rows yet — the normal case — the remainder IS ``po_line.quantity`` and the
    arithmetic is exactly ``quantity / K``. On a partially scheduled line, splitting the full
    ordered quantity again would produce rows that instantly violate this model's own
    over-commitment block, so the remainder is what gets divided. The LAST row absorbs the
    rounding remainder, so the instalments always sum to the remainder exactly.
    """
    instalments = int(instalments or 0)
    interval_days = int(interval_days or 0)

    if instalments < 2:
        raise ValidationError("Split into at least two instalments.")
    if instalments > DeliverySchedule.MAX_SPLIT_INSTALMENTS:
        raise ValidationError(
            f"Split into at most {DeliverySchedule.MAX_SPLIT_INSTALMENTS} instalments."
        )
    if interval_days < 1:
        raise ValidationError("The interval between instalments must be at least one day.")
    if first_date is None:
        raise ValidationError("Give the first instalment's need-by date.")

    existing = DeliverySchedule.objects.filter(tenant=tenant, po_line=po_line)
    committed = (existing.exclude(status="cancelled")
                 .aggregate(s=Sum("scheduled_quantity"))["s"] or ZERO)
    # Cancelled rows still hold their sequence number (the unique_together spans every row), so
    # the next sequence is taken over ALL of them, not just the live ones.
    last_sequence = existing.aggregate(m=models.Max("sequence"))["m"] or 0

    ordered = po_line.quantity or ZERO
    remaining = ordered - committed
    if remaining <= ZERO:
        raise ValidationError(
            f"This line is already fully covered by delivery schedules ({committed} of {ordered})."
        )

    per = (remaining / instalments).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    final = remaining - (per * (instalments - 1))
    if per <= ZERO or final <= ZERO:
        raise ValidationError(
            f"{remaining} is too small to divide into {instalments} instalments."
        )

    created = []
    for index in range(instalments):
        row = DeliverySchedule(
            tenant=tenant,
            po_line=po_line,
            sequence=last_sequence + index + 1,
            scheduled_quantity=final if index == instalments - 1 else per,
            need_by_date=first_date + timedelta(days=index * interval_days),
            ship_to=po_line.purchase_order.ship_to,
            change_reason=f"Auto-split into {instalments} instalments",
            created_by=user,
        )
        # ``number`` is assigned inside save(); excluding it keeps full_clean() from rejecting the
        # not-yet-generated blank (and from running the tenant+number unique check on "").
        row.full_clean(exclude=["number"])
        row.save()
        created.append(row)
    return created
