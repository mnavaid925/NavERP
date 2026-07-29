"""SCM 4.10 Returns Management — ReturnDisposition: the receiving bench and 4.10's ONLY ledger writer.

**OWNERSHIP (L36):** SCM ships first, so SCM owns this table. NavERP ``### 5.10 Returns Management
(RMA) → Disposition Routing`` and ``### 9.5 OMS → restocking logic`` EXTEND this row by FK; neither
builds a second disposition table. ``### 5.10 Return Inspection`` is PARTIALLY PRE-EMPTED here by
:attr:`ReturnDisposition.condition_grade` — grading is inseparable from the disposition decision.
Deep inspection criteria remain 4.9's ``InspectionPlan``; 5.10 may extend this row, not replace it.

One row per *(line, decision, quantity)*: three units back can be 2 restock + 1 scrap. Receiving and
deciding are **two separately stamped acts on the same row** — intake writes quantity, grade, date
and bench location at ``disposition="received_pending"``; the decision follows.

============================================================================================
INTAKE POSTS NOTHING. This is deliberate and it is also the answer to the missing blocked-stock
concept.
============================================================================================

``Location.LOCATION_TYPES`` is warehouse / zone / bin / staging / transit — there is no "blocked"
type — and ``Item.on_hand()`` is ``Sum(quantity)`` across ALL locations. So anything posted at
intake would inflate on-hand, ``Item.total_value()``, the 4.3 valuation report and 4.7's reorder and
safety-stock inputs, tenant-wide and indistinguishable from sellable stock. Keeping the bench
OFF-LEDGER **is** the blocked-stock stand-in, and it keeps exactly one ledger write per row, which
is what makes ``stock_posted`` trustworthy.

Cost of that choice, stated honestly: goods physically on the bench are absent from inventory value
until they are dispositioned. Mitigated by the ``scm:returns_awaiting_disposition`` report — NOT by
a ledger row.

============================================================================================
PER-DISPOSITION LEDGER EFFECT
============================================================================================

===================  ============  ====  ==================  ====================
Disposition          Move          Sign  Location            unit_cost
===================  ============  ====  ==================  ====================
received_pending     none          —     —                   —
restock              ``receipt``   +     ``restock_location``  ``restock_unit_cost``
refurbish            none at the decision; stamps ``refurbished_on``, which unlocks the SAME
                     restock action on that row
scrap/donate/        ``adjustment``  −   ``restock_location``  ``restock_unit_cost``
recycle/liquidate    …but ONLY IF ``stock_posted`` is already True (it was restocked and is being
                     re-decided). Straight off the bench it posts nothing.
return_to_vendor     none — our stock never re-entered; the value chased is a ``WarrantyClaim``
repair_return        none — it was never our stock (D365 lists this branch explicitly)
quarantine           none — flips ``LotSerial.status`` to ``quarantine``
credit_only          none — there is no physical unit
===================  ============  ====  ==================  ====================

**Why ``receipt`` and why no new move type.** Checked against all five ``move_type`` consumers:
``demand_series``/``demand_series_map`` filter ``move_type="issue"`` ONLY and NEGATE the signed sum,
so a positive ``issue`` would SUBTRACT from a historical demand bucket and silently deflate every
4.7 forecast — ``issue`` is categorically banned for an inbound return, and ``receipt`` is invisible
to it. ``_item_valuation`` excludes only ``"transfer"``, so a restock correctly becomes a real
inbound FIFO/LIFO cost layer at ``restock_unit_cost``. ``_reverse_grn_receipt`` is keyed on
``move_type="receipt"`` **and** ``reference=grn.number``; our reference is ``RMA-…``, so a return
can never be swept up by a GRN reversal. ``WorkOrder._move_totals`` filters consumption/production
AND ``reference=self.number`` — unreachable. And the ledger filter UI ends every badge chain in an
``{% else %}``. ``adjustment`` for the write-offs follows 4.9's stated ruling verbatim; note
``move_type`` is ``CharField(max_length=12)``, so ``customer_return`` (15 chars) would need a column
widen anyway.

**DOCUMENTED CONSEQUENCE: demand history stays GROSS.** Returns are not netted out of the 4.7
demand series. Netting them is a change to ``models/DemandPlanning/_history.py`` and belongs to
4.11 — it is said here and on the forecast page rather than discovered.

**DOCUMENTED CONSEQUENCE: FIFO/LIFO and the quick value DIVERGE after a written-down restock.**
``_item_valuation`` walks cost layers and ignores ``average_cost``; ``Item.total_value()``
multiplies ``on_hand × average_cost``. That is pre-existing dual-figure design, but 4.10 is the
first module to make the two disagree routinely, because a grade-C restock adds a layer at 40% of
cost while the weighted average rolls only part-way down. **This is expected. Do not "fix" it** —
there is a test pinning the divergence so the next reviewer does not.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.ReturnsManagement.ReturnReasons import (
    DECIDED_DISPOSITION_CHOICES, DISPOSITION_CHOICES,
)


class ReturnDisposition(TenantOwned):
    """What we did with one quantity of one returned line. No NUMBER_PREFIX — the
    ``SalesOrderAllocation`` precedent: this is a row on a bench, not a document."""

    GRADE_CHOICES = [
        ("a", "A — as new, sellable"),
        ("b", "B — light wear, refurbishable"),
        ("c", "C — heavy wear, secondary channel"),
        ("d", "D — unsellable"),
    ]
    #: Re-exported for the forms and views so nothing re-lists the ladder by hand.
    DISPOSITION_CHOICES = DISPOSITION_CHOICES
    DECIDED_DISPOSITION_CHOICES = DECIDED_DISPOSITION_CHOICES

    #: Decisions that write the unit OUT of stock — and only when it had already been written IN.
    WRITE_OFF_DISPOSITIONS = ("scrap", "donate", "recycle", "liquidate")
    #: Decisions that flip a serialised unit to consumed (it is gone, whatever the ledger says).
    CONSUMING_DISPOSITIONS = WRITE_OFF_DISPOSITIONS

    return_line = models.ForeignKey("scm.ReturnLine", on_delete=models.CASCADE,
                                    related_name="dispositions")
    quantity = models.DecimalField(max_digits=14, decimal_places=4,
                                   validators=[MinValueValidator(Decimal("0.0001"))])
    received_on = models.DateField(editable=False)
    received_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name="scm_returns_received")
    location = models.ForeignKey("scm.Location", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="scm_return_dispositions",
                                 help_text="The returns bench the goods physically landed on. "
                                           "Nothing is posted here — see the module docstring")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="scm_return_dispositions")
    condition_grade = models.CharField(
        max_length=1, choices=GRADE_CHOICES, default="a",
        help_text="What the grader FOUND — the input. The disposition is the output; the two are "
                  "never collapsed into one field")
    disposition = models.CharField(max_length=16, choices=DISPOSITION_CHOICES,
                                   default="received_pending")

    restock_location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="scm_return_restocks",
                                         help_text="Where a restocked unit is posted IN — must "
                                                   "differ from the bench")
    restock_unit_cost = models.DecimalField(
        max_digits=14, decimal_places=4, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="Seeded once from policy.grade_X_cost_pct × item.average_cost, then HUMAN-OWNED "
                  "and never recomputed (the NonConformance.cost_of_quality posture)")
    recovery_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)],
        help_text="What a liquidation or donation actually recovered. A management figure with NO "
                  "GL effect (L29)")
    refurbished_on = models.DateField(null=True, blank=True, editable=False)

    stock_posted = models.BooleanField(default=False, editable=False,
                                       help_text="The idempotency latch — re-read INSIDE the lock")
    stock_move = models.ForeignKey("scm.StockMove", on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name="+")
    decided_on = models.DateField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                   editable=False, related_name="scm_return_decisions")
    nonconformance = models.ForeignKey("scm.NonConformance", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="scm_return_dispositions",
                                       help_text="The quality finding raised from this unit. 4.9's "
                                                 "NonConformance.source stays 'inspection' — see "
                                                 "the note below")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-received_on", "-id"]
        indexes = [
            models.Index(fields=["tenant", "disposition"], name="scm_rmadisp_tnt_disp_idx"),
            models.Index(fields=["tenant", "received_on"], name="scm_rmadisp_tnt_recv_idx"),
            models.Index(fields=["tenant", "condition_grade"], name="scm_rmadisp_tnt_grade_idx"),
            models.Index(fields=["tenant", "stock_posted"], name="scm_rmadisp_tnt_post_idx"),
        ]

    # NOTE on the 4.9 link: ``NonConformance.source`` is ``CharField(max_length=14)`` and
    # ``customer_return`` is 15 characters, so adding it to SOURCE_CHOICES is a COLUMN WIDEN plus a
    # choices change plus a reversal of 4.9's own documented reasoning. **4.10 does not carry a
    # migration against a 4.9 model.** An NCR raised from here uses ``source="inspection"`` with the
    # RMA number in the description, and this FK is the hard link. Deferred, priced, not hand-waved.

    def __str__(self):
        return (f"{self.get_disposition_display()} ×{self.quantity}"
                f" (grade {self.condition_grade.upper()})")

    def save(self, *args, **kwargs):
        # received_on is editable=False, so nothing on a form can set it; stamping it here means a
        # row created by the seeder, the receive-all action or the split action all agree.
        if self.received_on is None:
            self.received_on = timezone.localdate()
        return super().save(*args, **kwargs)

    def clean(self):
        """Four rules, each guarding something the append-only ledger cannot undo.

        1. A lot/serial is REQUIRED when the item is tracked. Returned serialised goods that land in
           the ledger with no lot are untraceable and defeat the ``lot_history`` panel entirely.
        2. The lot must belong to THIS line's item. A crafted POST pairing item A with item B's lot
           corrupts an append-only ledger that cannot be corrected in place — the
           ``NonConformance.clean()`` cross-check, for the identical reason.
        3. A restock needs somewhere to go, and it must not be the bench it is standing on.
        4. The reason may forbid restocking outright. Re-checked inside the posting transaction
           too — a form is a convenience, not a control.
        """
        super().clean()
        if self.return_line_id is None:
            return
        line = self.return_line
        item = line.item if line.item_id else None

        if item is not None and item.tracking != "none" and self.lot_serial_id is None:
            raise ValidationError(
                {"lot_serial": f"{item.sku} is {item.get_tracking_display().lower()}-tracked — "
                               "record which lot or serial came back, or the movement is "
                               "untraceable."})
        if self.lot_serial_id and item is not None and self.lot_serial.item_id != item.pk:
            raise ValidationError(
                {"lot_serial": f"{self.lot_serial.number} belongs to {self.lot_serial.item.sku}, "
                               f"not {item.sku}."})
        if self.disposition == "restock":
            if self.restock_location_id is None:
                raise ValidationError(
                    {"restock_location": "Choose where the unit goes back into sellable stock."})
            if self.restock_location_id == self.location_id:
                raise ValidationError(
                    {"restock_location": "That is the returns bench — a restock has to move the "
                                         "unit into sellable stock, not leave it where it is."})
            if line.reason_id and line.reason.blocks_restock:
                raise ValidationError(
                    {"disposition": f"Reason '{line.reason.code}' blocks restocking — this unit "
                                    "can never go back into sellable stock."})
            if self.lot_serial_id and self.lot_serial.status == "expired":
                raise ValidationError(
                    {"disposition": f"Lot {self.lot_serial.number} is expired — scrap or "
                                    "quarantine it instead of restocking it."})
        if self.disposition in self.WRITE_OFF_DISPOSITIONS and self.stock_posted \
                and self.restock_location_id is None:
            raise ValidationError(
                {"restock_location": "This unit was restocked, so writing it off has to take it "
                                     "out of the location it was put into."})
        # The authorised-quantity cap lives HERE, on the model, so every writer inherits it. It used
        # to exist only in the formset's clean(), which left the single-row edit path free to raise a
        # bench row's quantity to anything DecimalField(14,4) holds — and because the credit note is
        # deliberately computed FROM the disposition rows, that flowed straight into a real
        # accounting.Invoice for more than was ever returned. The rows are the ceiling, so the
        # ceiling has to be enforced on every path that writes a row.
        if self.return_line_id is not None and self.quantity is not None:
            line = self.return_line
            approved = line.quantity_approved or line.quantity_requested or ZERO
            if approved > ZERO:
                siblings = (line.dispositions.exclude(pk=self.pk)
                            .aggregate(s=Sum("quantity"))["s"] or ZERO)
                if siblings + self.quantity > approved:
                    raise ValidationError({
                        "quantity": f"That would receive {siblings + self.quantity} against "
                                    f"{approved} authorised on this line "
                                    f"({siblings} already recorded on other rows)."})

    # --- derived (nothing below is stored) -------------------------------------------------------
    @property
    def posts_stock(self):
        """Whether ``returndisposition_post`` has a ledger effect on this row RIGHT NOW.

        An EXECUTABLE rule in the shape of ``NonConformance.posts_stock``, not a comment somebody
        has to remember to honour. Asked by the view before it opens a transaction and by the
        template before it draws a button — one answer, two callers, no drift.

        ``item_id``/``location`` are part of the test rather than an assumption: a write-off with no
        restock location would otherwise hand ``None`` to ``_insufficient_stock``, which is an
        uncaught ``AttributeError`` (the caller only catches ``ValidationError``), not a refusal.
        """
        if self.return_line_id is None or self.return_line.item_id is None:
            return False
        if self.disposition == "restock":
            return not self.stock_posted and self.restock_location_id is not None
        if self.disposition in self.WRITE_OFF_DISPOSITIONS:
            # Only reverses a unit that ACTUALLY went into stock. Straight off the bench there is
            # nothing to take out — the goods were never posted in (see the module docstring).
            return self.stock_posted and self.restock_location_id is not None
        return False

    @property
    def is_decided(self):
        return self.disposition != "received_pending"

    @property
    def is_splittable(self):
        """Split is permitted ONLY while undecided and unposted.

        This is the single thing that makes disposition-as-a-row survive the real
        receive-then-grade sequence — the 2-restock/1-scrap case that justifies the row grain at
        all. Once stock has moved the row is an audit record and its quantity is history.
        """
        # `stock_move_id`, not the latch — see the edit/delete guards: after a restock-then-write-off
        # the latch is False again but the row has written two real movements, and its quantity is
        # history either way.
        return self.disposition == "received_pending" and self.stock_move_id is None

    @property
    def can_restock_after_refurbish(self):
        """A refurbished row unlocks the same restock action it was refused at the decision.

        The ``restock_location_id`` test is NOT optional and is the same one :attr:`posts_stock`
        carries: nothing forces a location onto a refurbish row (``clean()`` requires one only for
        ``restock``), so without it a refurbished row with nowhere to go draws the Post button on
        both the bench list and the detail page, and pressing it hands ``location=None`` to
        ``_post_stock_move`` — an IntegrityError on a non-null FK inside the atomic block, which the
        caller's ``except ValidationError`` does not catch. A 500 on the sub-module's only
        ledger-writing action. One rule, one definition, three consumers (this property, the two
        templates, and the bench filter's SQL).
        """
        return (self.disposition == "refurbish" and self.refurbished_on is not None
                and not self.stock_posted and self.restock_location_id is not None)

    @property
    def recovery_variance(self):
        """What we got back versus what the write-down said it was worth. Management figure only."""
        return q2((self.recovery_value or ZERO)
                  - (self.quantity or ZERO) * (self.restock_unit_cost or ZERO))
