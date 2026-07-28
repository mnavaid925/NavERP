"""SCM 4.9 Quality Management — NonConformance, the ONE finding register [NCR-].

Realizes the "Non-Conformance Reports (NCR)" bullet entirely. Every detection source writes here:
an inspection that failed, units refused at the dock, a production defect, a supplier complaint, an
audit finding, or somebody walking past a pallet. There is deliberately no second findings table —
an audit finding is a row with ``source="audit"`` and the ``audit`` FK set.

**Three stock rulings, decided once, encoded here rather than described in a docstring:**

1. **Scrap posts an ``adjustment`` StockMove**, negative, ``reference="NCR-…"``. No new move type:
   ``adjustment`` already means "write-off / damage / cycle count / found / revaluation", it is
   already excluded from 4.7's demand series and already walks correctly in the FIFO/LIFO/WAC
   valuation. A `scrap` move_type would be a migration plus an audit of all three for no gain.
2. **Quarantine posts NOTHING.** It flips the existing ``LotSerial.status`` to ``quarantine``. The
   goods are physically still there, and on-hand is always ``Sum(quantity)`` over the ledger — a
   stored "blocked quantity" would be a second source of truth. Physical segregation, if wanted, is
   an ordinary 4.3 ``StockTransfer`` into a QC-hold location.
3. **Units rejected at the dock never entered stock**, so an NCR raised from a goods receipt posts
   nothing on any disposition. That is :attr:`NonConformance.posts_stock`, an executable rule the
   disposition action asks — not a comment somebody has to remember to honour.

**No JournalEntry (L29).** ``cost_of_quality`` is a recorded management figure with no GL effect;
accounting sees the scrap only through the 4.3 valuation report reading the StockMove.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class NonConformance(TenantNumbered):
    """A recorded quality failure, its MRB disposition and its cost [NCR-]."""

    NUMBER_PREFIX = "NCR"

    SOURCE_CHOICES = [
        ("inspection", "Quality inspection"),
        ("goods_receipt", "Goods receipt"),
        ("production", "Production"),
        ("supplier", "Supplier"),
        ("audit", "Audit finding"),
        ("internal", "Internal observation"),
    ]
    # No `customer_complaint` value on purpose: a complaint is a CRM Case, and duplicating it here
    # would give the same customer two records with two owners and two SLAs.
    DEFECT_CATEGORY_CHOICES = [
        ("dimensional", "Dimensional"),
        ("visual_cosmetic", "Visual / cosmetic"),
        ("functional", "Functional"),
        ("material", "Material"),
        ("packaging", "Packaging"),
        ("labelling", "Labelling"),
        ("documentation", "Documentation"),
        ("contamination", "Contamination"),
        ("quantity_shortage", "Quantity shortage"),
        ("late_delivery", "Late delivery"),
        ("process_deviation", "Process deviation"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("major", "Major"),
        ("minor", "Minor"),
        ("observation", "Observation"),
    ]
    DISPOSITION_CHOICES = [
        ("pending", "Pending"),
        ("use_as_is", "Use as is"),
        ("rework", "Rework"),
        ("repair", "Repair"),
        ("scrap", "Scrap"),
        ("return_to_vendor", "Return to vendor"),
        ("regrade", "Regrade"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("dispositioned", "Dispositioned"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    #: Statuses whose header the quality engineer may still edit.
    EDITABLE_STATUSES = ("open", "investigating")
    #: Statuses that still count as outstanding on a roll-up or an audit-close guard.
    OPEN_STATUSES = ("open", "investigating", "dispositioned")

    source = models.CharField(max_length=14, choices=SOURCE_CHOICES, default="internal")
    inspection = models.ForeignKey("scm.QualityInspection", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="nonconformances")
    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="nonconformances")
    work_order = models.ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="nonconformances")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="nonconformances")
    audit = models.ForeignKey("scm.QualityAudit", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="findings",
                              help_text="Set when this row IS an audit finding — there is no "
                                        "separate findings table")

    # Nullable because an audit finding ("training records incomplete") has no item; clean()
    # requires one for every other source.
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, null=True, blank=True,
                             related_name="nonconformances")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="nonconformances")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="nonconformances",
                                 help_text="Where the affected stock sits — a scrap posts from here")
    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_nonconformances")

    quantity_affected = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)])
    uom = models.ForeignKey("scm.UOM", on_delete=models.SET_NULL, null=True, blank=True,
                            related_name="+")
    defect_category = models.CharField(max_length=18, choices=DEFECT_CATEGORY_CHOICES,
                                       default="other")
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="minor")
    title = models.CharField(max_length=255)
    description = models.TextField()

    detected_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_nonconformances_detected")
    detected_on = models.DateField()
    containment_action = models.TextField(
        blank=True, help_text="What was done immediately — a correction, not the CAPA")
    # Mirrors LotSerial.status; written only by the quarantine / release actions.
    quarantine_applied = models.BooleanField(default=False, editable=False)

    # --- the MRB decision block: written ONLY by nonconformance_disposition ----------------------
    # Modelled as decision FIELDS, not as a review-board meeting entity — that is deferred.
    disposition = models.CharField(max_length=16, choices=DISPOSITION_CHOICES, default="pending",
                                   editable=False)
    disposition_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                               editable=False)
    disposition_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True,
                                       blank=True, editable=False,
                                       related_name="scm_nonconformance_dispositions")
    disposition_on = models.DateTimeField(null=True, blank=True, editable=False)
    disposition_notes = models.TextField(blank=True, editable=False)

    cost_of_quality = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(ZERO)],
        help_text="What this failure cost. USER-ENTERED — the form defaults it to quantity × "
                  "average cost and the human's figure then stands; nothing recomputes it. It "
                  "posts NO journal entry (SCM posts none)")

    owner = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_nonconformances_owned")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="open",
                              editable=False)
    closed_on = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-detected_on", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_ncr_tnt_status_idx"),
            models.Index(fields=["tenant", "severity", "status"], name="scm_ncr_tnt_sev_idx"),
            models.Index(fields=["tenant", "source"], name="scm_ncr_tnt_source_idx"),
            models.Index(fields=["tenant", "item"], name="scm_ncr_tnt_item_idx"),
            models.Index(fields=["tenant", "due_date"], name="scm_ncr_tnt_due_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'NCR'} · {self.title}"

    def clean(self):
        super().clean()
        if self.source != "audit" and self.item_id is None:
            raise ValidationError({"item": "Name the item this non-conformance is against — only "
                                           "an audit finding may have none."})
        if self.item_id and (self.quantity_affected or ZERO) <= ZERO:
            raise ValidationError({"quantity_affected": "Record how many units are affected."})
        if self.due_date and self.detected_on and self.due_date < self.detected_on:
            raise ValidationError({"due_date": "The due date cannot precede the detection date."})
        # Same reasoning as QualityInspection.clean(): a crafted POST pairing item A with item B's
        # lot would make the scrap adjustment draw A's units against B's batch in the append-only
        # ledger, where it can never be corrected in place.
        if self.lot_serial_id and self.item_id and self.lot_serial.item_id != self.item_id:
            raise ValidationError({"lot_serial": f"{self.lot_serial.number} belongs to "
                                                 f"{self.lot_serial.item.sku}, not {self.item.sku}."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_overdue(self):
        if not self.due_date or self.status in ("closed", "cancelled"):
            return False
        return self.due_date < timezone.localdate()

    @property
    def days_open(self):
        end = self.closed_on.date() if self.closed_on else timezone.localdate()
        return max((end - self.detected_on).days, 0) if self.detected_on else 0

    @property
    def posts_stock(self):
        """Whether a disposition on this NCR has a ledger effect. Ruling (c), made executable.

        Only a scrap moves stock, only from a known location, and NEVER for a goods receipt: the
        rejected units were refused at the dock, so ``_post_grn_receipt`` never posted them in and
        there is nothing to take out. Writing a negative move anyway would drive the receiving
        location negative for stock it never held.
        """
        return (self.disposition == "scrap" and self.location_id is not None
                and self.source != "goods_receipt")

    def lot_history(self, limit=50):
        """Where this lot went — the read-only ledger panel on the detail page.

        Every move for the lot, not just the ones this NCR wrote, so a quality engineer can see
        whether the affected batch has already been shipped or consumed. Recall EXECUTION is a
        later pass (4.10 / 12.18); this is the evidence it would be built on.
        """
        from apps.scm.models import StockMove
        if self.lot_serial_id is None:
            return StockMove.objects.none()
        return (StockMove.objects
                .filter(tenant_id=self.tenant_id, lot_serial_id=self.lot_serial_id)
                .select_related("item", "location")
                .order_by("-moved_at")[:limit])
