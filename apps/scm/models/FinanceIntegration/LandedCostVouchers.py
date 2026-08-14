"""SCM 4.18 Finance & Accounting Integration — ``LandedCostVoucher`` + its two children.

**The voucher is the sub-module's engine.** A goods receipt says what arrived and what the purchase
order agreed to pay for it. A landed cost voucher says what it cost to *get it here* — freight,
duty, brokerage, insurance, drayage, port fees — and pushes that cost down onto the units that
actually landed, so the inventory those units are valued at is the price of having them on the shelf
rather than the price printed on the vendor's order.

FOLDER-NAME NOTE (do not "fix" it): the backend package is ``FinanceIntegration/`` while the
templates live under ``templates/scm/finance/``. That asymmetry is the house rule, not a defect —
all seventeen shipped scm template folders use a short slug (``3pl/``, ``portal/``, ``coldchain/``,
``srm/`` …) while the Python package uses the NavERP.md sub-module title in PascalCase.
``ThirdPartyLogistics/ClientBillingRuns.py`` and ``CustomerPortal/PortalAccounts.py`` carry the same
note.

--------------------------------------------------------------------------------------------------
FIVE RULINGS THIS MODULE IS BUILT ON
--------------------------------------------------------------------------------------------------

**1. SCM POSTS NO JournalEntry. draft_bill() creates a DRAFT accounting.Bill and stops; accounting
posts the entry.** (L29 — repeated verbatim because it is the rule this sub-module is most likely to
be "improved" past.) AP approval, payment, tax determination and the GL effect are Module 2's, in
exactly the way ``FreightInvoice`` stops at a draft ``Bill`` and ``ClientBillingRun`` stops at a
draft ``Invoice``.

**2. THE ALLOCATION TARGET IS ``StockMove``, NOT ``GoodsReceiptLine``** — the documented L28
stand-in, and it is not negotiable. ``GoodsReceiptLine.po_line`` points at ``PurchaseOrderLine``,
which carries free-text ``item_description`` + ``sku_hint`` and **no ``item`` FK** (4.1 shipped
before the 4.3 item catalog). So ``goods_receipt_line → po_line → item`` DOES NOT EXIST and must
never be written. The thing that resolves a real ``Item`` is the inbound ``receipt`` StockMove that
``apps/scm/views/_helpers.py::_post_grn_receipt`` already posts — one per received GRN line, stamped
``reference=<GRN number>`` at the PO's agreed unit cost. :class:`LandedCostAllocation` therefore FKs
``stock_move`` + ``item`` and carries no ``goods_receipt_line``.

**3. Money is DERIVED, never typed.** ``recalc_totals()`` is the ONE writer of ``estimated_total`` /
``actual_total`` / ``variance_amount`` / ``variance_pct`` / ``allocated_total``; ``allocate()`` is
the ONE writer of every column on :class:`LandedCostAllocation`. Both sum in **Python**, never with
an ``F()`` expression — the SQLite integer-division trap the rest of ``apps/scm`` avoids
(``FreightInvoice.recalc_amounts`` says the same).

**4. ``status`` is ``editable=False`` and moves ONLY along the verb ladder.**
``draft → allocated → accrued → reconciled``, with ``cancelled`` reachable while no bill exists. It
is on no form. A status a user could type is a status that can be set to ``reconciled`` on a voucher
whose costs were never pushed into inventory.

**5. Allocation is REVERSIBLE, and reversing it is the FIRST thing a re-allocation does.**
``allocate()`` calls :meth:`LandedCostVoucher._unallocate` before it writes anything, in the same
transaction. Rolling a cost into ``Item.average_cost`` twice is the one mistake here that is
invisible on every page and permanently wrong in the ledger, so the button is built to be safe to
press twice rather than guarded against being pressed twice.

--------------------------------------------------------------------------------------------------
WHY THE BILL LINES LOOK "WRONG" (they are not — read this before changing them)
--------------------------------------------------------------------------------------------------
``accounting.BillLine.unit_price`` is ``Decimal(14, **2**)`` and its ``save()`` recomputes
``line_total = quantity * unit_price``. So :meth:`LandedCostVoucher.draft_bill` writes
``quantity=Decimal("1")`` and ``unit_price=q2(charge.allocatable_amount)``, carrying the charge's
identity in the line **description**. And ``BillLine.tax_rate_pct`` is ``DECIMAL(5, 2)`` while
``accounting.TaxCode.rate_pct`` is ``DECIMAL(6, 3)`` — an unclamped copy of a wide rate overflows to
``DataError``, so the copy is quantized to 2dp and clamped to ``999.99``.
"""
from apps.scm.models._base import *  # noqa: F401,F403


#: The widest value ``LandedCostVoucher.variance_pct`` — ``DecimalField(8, 2)`` — can hold. A charge
#: estimated at 0.01 and actualised at 100,000 is a 999,999,900% variance, which does not fit the
#: column and raises ``DataError`` on save. The ratio is CLAMPED rather than left to break a page
#: nobody could then load; ``variance_amount`` beside it always carries the honest figure.
MAX_VARIANCE_PCT = Decimal("999999.99")

#: What ``accounting.BillLine.tax_rate_pct`` — ``DECIMAL(5, 2)`` — can hold. ``TaxCode.rate_pct`` is
#: ``DECIMAL(6, 3)`` and therefore WIDER on both sides, so a straight copy is an overflow waiting for
#: the first four-digit or three-decimal rate. See the module docstring.
MAX_BILL_TAX_RATE_PCT = Decimal("999.99")

#: The pinned fallback chain, per requested allocation basis.
#:
#: A basis that measures to NOTHING must neither divide by zero nor silently write an all-zero
#: allocation. Weight and volume fall back because ``Item.weight_kg`` / ``Item.volume_cbm`` are
#: nullable and a workspace that has not captured them yet is the normal case, not an error. ``value``
#: falls back for the same reason one step along: a receipt posted at a zero unit cost (an opening
#: balance, a free-of-charge replacement) sums to zero value and would otherwise be undividable.
#: ``quantity`` can only sum to zero when there are no moves, which :meth:`LandedCostVoucher.allocate`
#: has already refused, and ``equal`` cannot sum to zero at all — so the chain always terminates.
#:
#: The basis ACTUALLY used is stamped on every row it writes (``LandedCostAllocation.basis_used``),
#: because "this was allocated by weight" and "this was allocated by quantity because nobody has
#: weighed anything" are different facts and the second one is the one somebody needs to see.
_BASIS_FALLBACKS = {
    "value": ("value", "quantity", "equal"),
    "quantity": ("quantity", "equal"),
    "weight": ("weight", "quantity", "equal"),
    "volume": ("volume", "quantity", "equal"),
    "equal": ("equal",),
}


class LandedCostVoucher(TenantNumbered):
    """One receipt's landed cost [LC-]: its charges, their allocation, and the AP hand-off."""

    NUMBER_PREFIX = "LC"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("allocated", "Allocated"),
        ("accrued", "Accrued"),
        ("reconciled", "Reconciled"),
        ("cancelled", "Cancelled"),
    ]
    #: Public so the templates, the views and the smoke sweep filter the same set the verbs do.
    #: A voucher stops being editable the moment its costs are inside somebody's inventory value.
    EDITABLE_STATUSES = ("draft",)

    #: FIVE bases, and there is deliberately no ``manual`` sixth. A hand-typed per-row split needs an
    #: editable grid over rows that are ``editable=False`` by construction (``allocate()`` is their
    #: only writer), which is a different feature with a different UI — deferred and named, rather
    #: than half-shipped as a choice that nothing implements.
    ALLOCATION_BASIS_CHOICES = [
        ("value", "By Value"),
        ("quantity", "By Quantity"),
        ("weight", "By Weight"),
        ("volume", "By Volume"),
        ("equal", "Equal"),
    ]

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer added
    #: later is covered by the cross-tenant guard the moment it is named here — the
    #: ``ClientBillingRun.TENANT_SCOPED_FKS`` idiom rather than another copy of the same if-block.
    #: ``party`` is deliberately absent: it is a soft ``core.Party`` pointer, and the FORM adds it to
    #: its own ``_reject_foreign`` tuple (that is the boundary where it can render as a field error).
    TENANT_SCOPED_FKS = ("goods_receipt", "shipment", "trade_document")

    # --- what this voucher costs out ---------------------------------------------------------------
    # PROTECT: the receipt is the EVIDENCE for every allocated figure. A GRN deleted out from under an
    # allocated voucher would leave inventory carrying a cost nobody can reconstruct.
    goods_receipt = models.ForeignKey("scm.GoodsReceiptNote", on_delete=models.PROTECT,
                                      related_name="landed_cost_vouchers",
                                      help_text="The receipt whose units these costs land on")
    # REQUIRED, and the requirement comes from downstream: `accounting.Bill.party` is PROTECT and
    # non-null, so a voucher with no payee could never draft the bill it exists to draft.
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT,
                              related_name="scm_landed_cost_vouchers",
                              help_text="Who is paid for these charges — the forwarder, broker or "
                                        "carrier the vendor bill is raised to")
    # The stand-in for D365's voyage and Oracle's trade operation: the grouping that says "these
    # costs and that receipt travelled together". An FK to the consignment we already track, NOT a
    # new Voyage/Container/Folio entity (deferred and named as such).
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="landed_cost_vouchers",
                                 help_text="The consignment these costs were incurred on")
    # The source of the declared value and the incoterm. There is deliberately no SECOND incoterm
    # column here — the term lives on the paperwork that states it (4.12 TradeDocument.incoterm).
    trade_document = models.ForeignKey("scm.TradeDocument", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="landed_cost_vouchers",
                                       help_text="Customs paperwork carrying the declared value and "
                                                 "the incoterm these charges follow from")
    # `accounting.Currency` is a GLOBAL model with NO tenant column, so TenantModelForm cannot scope
    # it — the form narrows it with `_active_currencies()` instead. Never filter this by tenant.
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="scm_landed_cost_vouchers")
    # THE ONLY ACCOUNTING WRITE IN 4.18, and it is a DRAFT (ruling 1). SET_NULL so voiding the bill in
    # accounting cannot cascade a landed cost voucher — and the inventory value it justifies — out of
    # existence. `editable=False`: `draft_bill()` is its only writer.
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True,
                             editable=False, related_name="scm_landed_cost_vouchers")

    # --- the three things a human types ------------------------------------------------------------
    cost_date = models.DateField(help_text="The date these charges were incurred")
    allocation_basis = models.CharField(max_length=10, choices=ALLOCATION_BASIS_CHOICES,
                                        default="value",
                                        help_text="Default basis for every charge that does not "
                                                  "override it")
    notes = models.TextField(blank=True)

    # --- derived, all editable=False (L22) ---------------------------------------------------------
    # NOT ON ANY FORM. Ruling 4 — the verb ladder is the only writer.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft", editable=False)
    # Ruling 3 — derived, never typed. `recalc_totals()` is the only writer of all five.
    estimated_total = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    actual_total = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    variance_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    variance_pct = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                       editable=False)
    allocated_total = models.DecimalField(max_digits=16, decimal_places=2, default=0, editable=False)
    accrued_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-cost_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # The list page's ?status= filter and the five status stat tiles.
            models.Index(fields=["tenant", "status"], name="scm_lcv_tnt_status_idx"),
            # The list ORDER BY and the landed-cost variance report's ?date_from/?date_to window.
            models.Index(fields=["tenant", "cost_date"], name="scm_lcv_tnt_date_idx"),
            # The GRN detail page's "what did this receipt cost to land" panel.
            models.Index(fields=["tenant", "goods_receipt"], name="scm_lcv_tnt_grn_idx"),
        ]

    def __str__(self):
        who = self.party.name if self.party_id else "?"
        return f"{self.number or 'LC'} · {who}"

    # ------------------------------------------------------------------ validation
    def clean(self):
        errors = {}

        # Cross-tenant guards first: every later rule reads THROUGH these FKs.
        #
        # SKIPPED WHEN THE INSTANCE HAS NO TENANT YET, and the skip is load-bearing rather than
        # defensive (the `Asset` / `TradeLicense` / `MaintenancePlan` pattern). `crud_create` stamps
        # `tenant` AFTER `is_valid()`, so on the CREATE path this runs against `tenant_id = None` —
        # without the guard every legitimately chosen receipt, shipment and document would compare
        # unequal to None and be flagged "belongs to another workspace", making the create page
        # impossible to submit. `LandedCostVoucherForm.clean()` carries the form-boundary copy of
        # this check, which does NOT depend on the stamp and is therefore live on create; this one is
        # the database-boundary copy and holds on every path that reaches `full_clean()` with a
        # tenant, including the admin and the seeder.
        #
        # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a pointer whose
        # row went away degrades to None here instead of 500-ing inside validation.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                target = getattr(self, name, None)
                if target is not None and getattr(target, "tenant_id", None) != self.tenant_id:
                    errors[name] = "That record belongs to another workspace."

        if not self.cost_date:
            errors["cost_date"] = "A landed cost voucher needs the date its charges were incurred."

        if self.goods_receipt_id and "goods_receipt" not in errors:
            # Defaulted getattr for the same reason as the loop above.
            grn = getattr(self, "goods_receipt", None)
            if grn is not None and grn.status == "cancelled":
                # A cancelled receipt has had its inbound moves compensated away, so there is nothing
                # left to land a cost on — allocate() would refuse later with a much vaguer sentence.
                errors["goods_receipt"] = (
                    f"{grn.number} has been cancelled — its receipt was reversed out of the stock "
                    "ledger, so there are no units left to land these costs on.")

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ derived reads
    @property
    def is_editable(self):
        """Draft AND not yet billed. Once a bill exists the figures are somebody else's evidence."""
        return self.status in self.EDITABLE_STATUSES and self.bill_id is None

    def receipt_moves(self):
        """The inbound stock moves this receipt posted — THE allocation base (ruling 2).

        ``quantity__gt=ZERO`` excludes the compensating negatives ``_reverse_grn_receipt`` posts when
        a receipt is cancelled: the ledger is append-only, so a cancellation leaves both the original
        and its mirror image, and allocating over the pair would land cost on quantities that are no
        longer there.

        Ordered by ``id`` rather than by the model's ``-moved_at`` default so the row that absorbs the
        rounding remainder in :meth:`allocate` is the same row every time the button is pressed.
        """
        from apps.scm.models import StockMove

        if not self.goods_receipt_id:
            return StockMove.objects.none()
        return (StockMove.objects
                .filter(tenant=self.tenant, reference=self.goods_receipt.number,
                        move_type="receipt", quantity__gt=ZERO)
                .select_related("item")
                .order_by("id"))

    def split_charges(self, charges=None):
        """``(billable, excluded)`` — what this voucher can bill to its OWN payee, and what it cannot.

        A charge naming a DIFFERENT vendor is excluded rather than silently billed to the voucher's
        payee: multi-vendor auto-split into several bills is deferred and named, and quietly invoicing
        the forwarder for the customs broker's fee is the failure that deferral must not become.

        ``charges`` lets a caller that has already fetched the rows (the detail view) hand them in
        rather than pay for the identical query twice. Both :meth:`draft_bill` and the detail page
        read this ONE method, so the count the page shows and the count the bill excludes can never
        disagree.
        """
        if charges is None:
            charges = list(self.charges.select_related("tax_code", "gl_account", "party").all())
        billable, excluded = [], []
        for charge in charges:
            if charge.party_id is None or charge.party_id == self.party_id:
                billable.append(charge)
            else:
                excluded.append(charge)
        return billable, excluded

    # ------------------------------------------------------------------ money
    def recalc_totals(self, save=True):
        """Sum the charges and the allocations in PYTHON. Never an ``F()`` (ruling 3)."""
        estimated, actual = ZERO, ZERO
        for charge in self.charges.all():
            estimated += charge.estimated_amount or ZERO
            actual += charge.actual_amount or ZERO

        self.estimated_total = q2(estimated)
        self.actual_total = q2(actual)
        self.variance_amount = q2(actual - estimated)
        if estimated > ZERO:
            ratio = (self.variance_amount * 100 / estimated).quantize(Decimal("0.01"))
            # Clamped, not just quantized — see MAX_VARIANCE_PCT.
            self.variance_pct = min(max(ratio, -MAX_VARIANCE_PCT), MAX_VARIANCE_PCT)
        else:
            # None, never 0: "nothing was estimated" and "the estimate was exactly right" are
            # different facts and the template renders them differently.
            self.variance_pct = None

        allocated = ZERO
        for allocation in self.allocations.all():
            allocated += allocation.allocated_amount or ZERO
        self.allocated_total = q2(allocated)

        if save and self.pk:
            self.save(update_fields=["estimated_total", "actual_total", "variance_amount",
                                     "variance_pct", "allocated_total", "updated_at"])
        return self.actual_total

    # ------------------------------------------------------------------ the engine
    def _unallocate(self):
        """Roll this voucher's uplift back OUT of every item it touched, then drop its rows.

        PRIVATE, and the ONLY remover of ``LandedCostAllocation`` rows anywhere. Two halves, and both
        are required: deleting the rows without reversing the weighted-average roll would leave every
        affected item permanently carrying a cost whose evidence has gone, and reversing without
        deleting would double-count on the next allocation.

        The roll-back is ONE call per item (never one per row), because ``apply_landed_cost`` walks
        the item's current on-hand and a per-row call would re-read it N times to reach the same
        place. A NEGATIVE amount is what makes it a reversal.
        """
        from apps.scm.models import Item

        rollback = {}
        for allocation in self.allocations.all():
            if not allocation.item_id:
                continue
            rollback[allocation.item_id] = (rollback.get(allocation.item_id, ZERO)
                                            + (allocation.allocated_amount or ZERO))

        if rollback:
            items = {item.pk: item for item in Item.objects.filter(pk__in=list(rollback))}
            for item_id, amount in rollback.items():
                item = items.get(item_id)
                if item is not None and amount:
                    item.apply_landed_cost(-amount)

        self.allocations.all().delete()

    @staticmethod
    def _basis_value(move, basis):
        """One move's share weight under ``basis``. Never negative — ``receipt_moves`` filters > 0."""
        quantity = move.quantity or ZERO
        if basis == "value":
            return quantity * (move.unit_cost or ZERO)
        if basis == "quantity":
            return quantity
        if basis == "weight":
            return quantity * ((move.item.weight_kg if move.item_id else None) or ZERO)
        if basis == "volume":
            return quantity * ((move.item.volume_cbm if move.item_id else None) or ZERO)
        # "equal" — every landed line takes the same share regardless of what is on it.
        return Decimal("1")

    def _resolve_basis(self, moves, basis):
        """``(basis_used, [(move, basis_value)], total_basis)`` after the pinned fallback chain.

        ``total_basis`` is guaranteed ``> 0``, which is what makes the division in :meth:`allocate`
        safe without a second guard there. See ``_BASIS_FALLBACKS`` for why each link exists.
        """
        for candidate in _BASIS_FALLBACKS.get(basis, _BASIS_FALLBACKS["value"]):
            pairs = [(move, self._basis_value(move, candidate)) for move in moves]
            total = sum((value for _move, value in pairs), ZERO)
            if total > ZERO:
                return candidate, pairs, total
        # Unreachable while `moves` is non-empty (allocate() refuses an empty base and "equal" gives
        # every move a weight of 1). Kept so this method can never return a zero divisor.
        pairs = [(move, Decimal("1")) for move in moves]
        return "equal", pairs, Decimal(len(moves) or 1)

    def allocate(self):
        """Push every capitalising charge down onto the receipt's units. Safe to press twice.

        Whole body inside ``transaction.atomic()``, and :meth:`_unallocate` runs FIRST inside it
        (ruling 5) — so a re-allocation after a corrected charge amount reverses the old roll and
        applies the new one as one indivisible step, and a failure half-way leaves the item costs
        exactly where they were.

        Returns ``{"rows", "amount", "charges", "fallbacks"}`` for the view's message and audit row.
        """
        if self.status == "cancelled":
            raise ValidationError("A cancelled landed cost voucher cannot be allocated.")
        if self.bill_id is not None:
            number = self.bill.number if self.bill else "a vendor bill"
            raise ValidationError(
                f"This voucher has been billed as {number}, so its allocation can no longer be "
                "changed. Void the bill in Accounting first.")

        moves = list(self.receipt_moves())
        if not moves:
            # The exact sentence the contract pins, because it names BOTH causes: a receipt still in
            # draft has posted nothing, and a receipt whose free-text SKUs matched no Item posted
            # nothing either (see `_post_grn_receipt`'s `unmatched` return).
            raise ValidationError(
                "This receipt has not been posted to the stock ledger — receive it first, or its "
                "lines' SKUs matched no item.")

        charges = [charge for charge in self.charges.all()
                   if charge.capitalises and charge.allocatable_amount > ZERO]
        if not charges:
            raise ValidationError(
                "No charge on this voucher capitalises into inventory — every charge is either "
                "recoverable, marked not to capitalise, or has no amount yet.")

        # `Item` deferred (the package __init__ is mid-import while this module loads);
        # `LandedCostAllocation` is a module-level global in THIS file, resolved at call time, so it
        # needs no import at all and does not depend on the package re-export block landing first.
        from apps.scm.models import Item

        rows, fallbacks = [], []
        with transaction.atomic():
            # FIRST, and inside the same transaction. See ruling 5.
            self._unallocate()

            for charge in charges:
                requested = charge.effective_basis
                basis_used, pairs, total_basis = self._resolve_basis(moves, requested)
                if basis_used != requested:
                    label = dict(self.ALLOCATION_BASIS_CHOICES)
                    fallbacks.append(f"{label.get(requested, requested)} → "
                                     f"{label.get(basis_used, basis_used)}")

                amount = q2(charge.allocatable_amount)
                running, last = ZERO, len(pairs) - 1
                for index, (move, basis_value) in enumerate(pairs):
                    if index == last:
                        # THE LAST ROW ABSORBS THE ROUNDING REMAINDER, so the rows sum to the charge
                        # EXACTLY. Without this a 100.00 charge over three equal moves allocates
                        # 99.99 and the inventory uplift quietly disagrees with the vendor bill.
                        allocated = q2(amount - running)
                    else:
                        allocated = q2(amount * basis_value / total_basis)
                        running += allocated
                    quantity = move.quantity or ZERO
                    rows.append(LandedCostAllocation(
                        tenant=self.tenant,
                        voucher=self,
                        charge=charge,
                        stock_move=move,
                        item=move.item,
                        quantity=q4(quantity),
                        basis_value=q4(basis_value),
                        basis_used=basis_used,
                        allocated_amount=allocated,
                        unit_cost_uplift=q4(allocated / quantity) if quantity else ZERO,
                    ))

            LandedCostAllocation.objects.bulk_create(rows)

            # ONE weighted-average roll per ITEM, not per row: `apply_landed_cost` spreads the amount
            # over that item's CURRENT on-hand, so N calls would re-read the same on-hand N times to
            # arrive at the same place while paying N queries for it.
            per_item = {}
            for row in rows:
                per_item[row.item_id] = per_item.get(row.item_id, ZERO) + row.allocated_amount
            items = {item.pk: item for item in Item.objects.filter(pk__in=list(per_item))}
            for item_id, amount in per_item.items():
                item = items.get(item_id)
                if item is not None and amount:
                    item.apply_landed_cost(amount)

            self.status = "allocated"
            self.save(update_fields=["status", "updated_at"])
            self.recalc_totals()

        return {
            "rows": len(rows),
            "amount": self.allocated_total,
            "charges": len(charges),
            # De-duplicated but ORDER-PRESERVING: the message reads best naming each distinct
            # fallback once, in the order the charges were processed.
            "fallbacks": list(dict.fromkeys(fallbacks)),
        }

    def accrue(self):
        """``allocated → accrued``. Records that the estimate is owed but the bill has not arrived.

        Posts NO ``JournalEntry`` (ruling 1). The accrual JOURNAL is Module 2's; what 4.18 records is
        that these costs are in inventory and not yet in accounts payable — which is exactly what the
        payables report reads to show a landed cost voucher with no bill behind it.
        """
        if self.status != "allocated":
            raise ValidationError(
                f"Only an allocated voucher can be accrued; this one is "
                f"{self.get_status_display().lower()}.")
        self.status = "accrued"
        self.accrued_at = timezone.now()
        self.save(update_fields=["status", "accrued_at", "updated_at"])
        return self

    def draft_bill(self):
        """Draft an ``accounting.Bill`` for the payee and link it — the AP hand-off (L29).

        A DRAFT only. **SCM POSTS NO JournalEntry. draft_bill() creates a DRAFT accounting.Bill and
        stops; accounting posts the entry.** Approval, payment and the GL effect are Module 2's.

        IDEMPOTENT: an already-billed voucher returns its existing bill rather than drafting a second
        one, because pressing the button twice is the ordinary mistake here and a duplicate vendor
        bill is the expensive one. See the module docstring for the two precision rules the lines obey.
        """
        if self.bill_id is not None:
            return self.bill
        if self.status not in ("allocated", "accrued"):
            raise ValidationError(
                "Allocate the landed costs before drafting a vendor bill — a bill drafted from "
                "un-allocated charges would not match what inventory is carrying.")

        billable, excluded = self.split_charges()
        if not billable:
            # Refusing beats drafting a 0.00 bill and marking the voucher `reconciled`: every charge
            # here names a DIFFERENT vendor, so there is a real bill to raise — just not to this
            # payee. Multi-vendor auto-split is deferred and named, so this says so out loud.
            raise ValidationError(
                f"Every charge on this voucher names a different vendor ({len(excluded)} of them), "
                "so there is nothing to bill to its own payee. Split them onto vouchers for each "
                "vendor, or clear the vendor on the charges this payee covers.")

        from apps.accounting.models import Bill, BillLine

        grn_number = self.goods_receipt.number if self.goods_receipt_id else "no receipt"
        with transaction.atomic():
            bill = Bill(
                tenant=self.tenant,
                party=self.party,
                bill_date=timezone.localdate(),
                status="draft",
                currency=self.currency,
                notes=f"Landed cost — {self.number} ({grn_number})",
            )
            bill.save()

            for charge in billable:
                rate = ZERO
                if charge.tax_code_id and charge.tax_code is not None:
                    rate = charge.tax_code.rate_pct or ZERO
                BillLine.objects.create(
                    bill=bill,
                    description=self._bill_line_description(charge),
                    # quantity=1 with the real figure in unit_price — BillLine.save() recomputes
                    # line_total = quantity * unit_price at 2dp, so the 2dp unit_price is what is
                    # authoritative and a 4dp rate written here would be silently re-rounded.
                    quantity=Decimal("1"),
                    unit_price=q2(charge.allocatable_amount),
                    # DECIMAL(5,2) here vs DECIMAL(6,3) on TaxCode — quantize AND clamp, or a wide
                    # rate overflows to DataError. See MAX_BILL_TAX_RATE_PCT.
                    tax_rate_pct=min(MAX_BILL_TAX_RATE_PCT, rate.quantize(Decimal("0.01"))),
                    gl_account=charge.gl_account,
                )

            bill.recalc_totals()
            self.bill = bill
            self.status = "reconciled"
            self.save(update_fields=["bill", "status", "updated_at"])

        return bill

    def _bill_line_description(self, charge):
        """The charge's identity, since the flattened bill line loses everything but a number."""
        text = charge.get_charge_type_display()
        if charge.description:
            text = f"{text} — {charge.description}"
        if self.goods_receipt_id:
            text = f"{text} · {self.goods_receipt.number}"
        return text[:255]

    def cancel(self):
        """Reverse the allocation and close the voucher. REFUSED once a bill exists.

        Cancelling un-does the inventory uplift, which is the whole point: a voucher raised in error
        that is merely marked cancelled would leave every affected item permanently over-valued.
        Once a draft bill exists the conversation has moved to accounting — void it there.
        """
        if self.bill_id is not None:
            number = self.bill.number if self.bill else "a vendor bill"
            raise ValidationError(
                f"This voucher has been billed as {number} and cannot be cancelled here — void the "
                "bill in Accounting instead.")
        if self.status == "cancelled":
            raise ValidationError("This voucher is already cancelled.")

        with transaction.atomic():
            self._unallocate()
            self.status = "cancelled"
            self.recalc_totals(save=False)
            self.save(update_fields=["status", "estimated_total", "actual_total", "variance_amount",
                                     "variance_pct", "allocated_total", "updated_at"])
        return self


class LandedCostCharge(models.Model):
    """One cost line on a voucher. **Tenant-less child**, reached via ``voucher.tenant``.

    The ``FreightInvoiceLine`` / ``BillLine`` / ``GoodsReceiptLine`` / ``ClientBillingRunLine``
    convention: a second ``tenant`` FK here would be a second answer to "whose row is this", and the
    two would eventually disagree. Every view scopes these rows through
    ``voucher__tenant=request.tenant``.

    ``duty_rate_pct``, ``hs_code`` and ``country_of_origin`` are **snapshots** taken from
    :class:`~apps.scm.models.DutyTariff` at the moment the charge is entered — never a live join. A
    tariff re-rated next quarter must not restate what a shipment cleared customs at.
    """

    #: Eleven, and wider than the 4.6 freight vocabulary on purpose: a landed cost sheet carries the
    #: customs and terminal side of the bill, which a carrier's own invoice never does.
    CHARGE_TYPE_CHOICES = [
        ("freight", "Freight"),
        ("duty", "Customs Duty"),
        ("brokerage", "Customs & Brokerage"),
        ("insurance", "Insurance"),
        ("handling", "Handling"),
        ("drayage", "Drayage / Inland"),
        ("port_fees", "Port & Terminal Fees"),
        ("fuel_surcharge", "Fuel Surcharge"),
        ("inspection", "Inspection / Fumigation"),
        ("storage", "Storage / Demurrage"),
        ("other", "Other"),
    ]

    voucher = models.ForeignKey("scm.LandedCostVoucher", on_delete=models.CASCADE,
                                related_name="charges")
    charge_type = models.CharField(max_length=16, choices=CHARGE_TYPE_CHOICES, default="freight")
    description = models.CharField(max_length=255, blank=True)
    # The vendor for THIS line, when it differs from the voucher's payee (the broker's fee on a
    # forwarder's voucher). Blank means "the voucher's payee". SET_NULL: a tidied-up party must not
    # take a cost line with it.
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_landed_cost_charges",
                              help_text="Blank bills to the voucher's payee; a different vendor here "
                                        "is excluded from the drafted bill")
    freight_invoice = models.ForeignKey("scm.FreightInvoice", on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="landed_cost_charges",
                                        help_text="The 4.6 audited carrier invoice this charge came "
                                                  "from, where there is one")
    estimated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                           validators=[MinValueValidator(ZERO)],
                                           help_text="What this was expected to cost")
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                        validators=[MinValueValidator(ZERO)],
                                        help_text="What it actually cost, once the invoice arrives")
    # BLANK INHERITS THE VOUCHER'S — see `effective_basis`. Not nullable: a CharField with both blank
    # and null has two spellings of "not set" and they never stay in step.
    allocation_basis = models.CharField(max_length=10,
                                        choices=LandedCostVoucher.ALLOCATION_BASIS_CHOICES,
                                        blank=True,
                                        help_text="Leave blank to use the voucher's basis")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="scm_landed_cost_charges",
                                   help_text="Expense account carried onto the drafted bill line")
    # Sales/VAT/GST stays `accounting.TaxCode` — 4.18 NEVER re-declares a sales-tax rate table.
    # `DutyTariff` exists only because TaxCode structurally cannot be a CUSTOMS master.
    tax_code = models.ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="scm_landed_cost_charges")
    is_recoverable = models.BooleanField(
        default=False,
        help_text="Recoverable import VAT/GST — reclaimed, so it never capitalises into stock")
    capitalise_to_inventory = models.BooleanField(
        default=True, help_text="Uncheck to expense this charge instead of landing it on the units")
    # Snapshots, not a FK to DutyTariff — see the class docstring.
    hs_code = models.CharField(max_length=20, blank=True)
    country_of_origin = models.CharField(max_length=64, blank=True)
    duty_rate_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0,
                                        validators=[MinValueValidator(ZERO),
                                                    MaxValueValidator(100)],
                                        help_text="Snapshotted from the duty tariff — a later rate "
                                                  "change never rewrites this shipment")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.get_charge_type_display()} · {self.allocatable_amount}"

    def clean(self):
        errors = {}
        if (self.duty_rate_pct or ZERO) > ZERO and self.charge_type != "duty":
            errors["duty_rate_pct"] = (
                "A duty rate belongs on a Customs Duty charge. Change the charge type, or clear the "
                "rate — it is a snapshot of what customs applied, not a general percentage.")
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ derived reads
    @property
    def variance_amount(self):
        return (self.actual_amount or ZERO) - (self.estimated_amount or ZERO)

    @property
    def allocatable_amount(self):
        """The ACTUAL once there is one, otherwise the estimate.

        Deliberately not "actual or estimate, whichever is greater", and not a sum: allocating an
        estimate is how a receipt gets a usable landed cost before the freight invoice arrives, and
        re-allocating once the actual lands replaces it (``allocate()`` reverses first, ruling 5).
        """
        actual = self.actual_amount or ZERO
        return actual if actual > ZERO else (self.estimated_amount or ZERO)

    @property
    def effective_basis(self):
        """This charge's basis, or the voucher's when it does not override."""
        if self.allocation_basis:
            return self.allocation_basis
        return self.voucher.allocation_basis if self.voucher_id else "value"

    @property
    def capitalises(self):
        """Recoverable tax NEVER lands on the units — it is reclaimed, not borne."""
        return bool(self.capitalise_to_inventory and not self.is_recoverable)


class LandedCostAllocation(TenantOwned):
    """One charge's share of one receipt move. Carries its OWN tenant, unlike its sibling child.

    The exception to the tenant-less-child convention is deliberate and load-bearing: the 4.3 stock
    valuation report and the 4.18 landed-cost variance report query these rows DIRECTLY, grouped by
    ``stock_move_id`` and by ``item``, without ever touching the voucher. Reaching the tenant through
    ``voucher__tenant`` on those queries would turn an indexed lookup into a join on every report
    page — and the indexes below exist precisely to serve them.

    **Every column is ``editable=False`` and** :meth:`LandedCostVoucher.allocate` **is their only
    writer.** There is no form, no create/edit/delete view, no list page and no url; the rows render
    inside the voucher detail page and the variance report, and admin registration is READ-ONLY (the
    ``StockMoveAdmin`` precedent).
    """

    voucher = models.ForeignKey("scm.LandedCostVoucher", on_delete=models.CASCADE,
                                related_name="allocations")
    charge = models.ForeignKey("scm.LandedCostCharge", on_delete=models.CASCADE,
                               related_name="allocations")
    # PROTECT and REQUIRED: the move IS the row this cost was landed on (ruling 2). The ledger is
    # append-only and never deleted anyway, so this can only ever fire on a data-repair attempt —
    # which is exactly when losing the link would strand an inventory uplift with no evidence.
    stock_move = models.ForeignKey("scm.StockMove", on_delete=models.PROTECT,
                                   related_name="landed_cost_allocations")
    # Denormalised from `stock_move.item` on purpose: the valuation and variance reports group by
    # item, and carrying it here is what lets them do that without joining through the ledger.
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT,
                             related_name="landed_cost_allocations")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    basis_value = models.DecimalField(max_digits=16, decimal_places=4, default=0, editable=False)
    # The basis ACTUALLY used, which is not always the basis requested — see `_BASIS_FALLBACKS`.
    basis_used = models.CharField(max_length=10, choices=LandedCostVoucher.ALLOCATION_BASIS_CHOICES,
                                  default="value", editable=False)
    allocated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                           editable=False)
    unit_cost_uplift = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                           editable=False)

    class Meta:
        ordering = ["id"]
        indexes = [
            # The FIFO/LIFO uplift map on the 4.3 valuation report, and the ?group=item variance report.
            models.Index(fields=["tenant", "item"], name="scm_lca_tnt_item_idx"),
            # `LandedCostAllocation.objects.filter(tenant=...).values("stock_move_id").annotate(...)`
            # — the ONE grouped query the valuation report builds its uplift map from.
            models.Index(fields=["tenant", "stock_move"], name="scm_lca_tnt_move_idx"),
            # The voucher detail page's allocation panel and `_unallocate()`'s roll-back sweep.
            models.Index(fields=["tenant", "voucher"], name="scm_lca_tnt_vch_idx"),
        ]

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{sku} · {self.allocated_amount} ({self.unit_cost_uplift}/unit)"
