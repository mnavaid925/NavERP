"""SCM 4.17 Third-Party Logistics (3PL) Management — ``ClientBillingRun`` + ``ClientBillingRunLine``.

**The billing run is the sub-module's engine.** A rate card says what a client is charged for; a run
is the act of going and *looking* — over one client, over one period, through one tariff — at what
the warehouse actually did, and turning it into money. Everything else in 4.17 exists so that this
can be done from evidence rather than from a spreadsheet.

FOLDER-NAME NOTE (do not "fix" it): the backend package is ``ThirdPartyLogistics/`` while the
templates live under ``templates/scm/3pl/``. That asymmetry is the house rule, not a defect — all
sixteen shipped scm template folders use a short slug while the Python package uses the NavERP.md
sub-module title in PascalCase. ``CustomerPortal/PortalAccounts.py`` carries the same note.

--------------------------------------------------------------------------------------------------
FOUR RULINGS THIS MODULE IS BUILT ON
--------------------------------------------------------------------------------------------------

**1. ``status`` is ``editable=False`` and moves ONLY along the verb ladder.**
``draft → calculated → approved → invoiced``, with ``void`` reachable from the first two. It is not
on any form — the ``SalesOrder.status`` / ``Shipment.status`` posture. A status a user can type is a
status that can be set to ``invoiced`` on a run that was never calculated, and the whole point of the
ladder is that ``approved`` means a human with the tenant-admin bit looked at the numbers.

**2. Money is DERIVED, never typed.** ``ClientBillingRunLine.save()`` is the ONE writer of
``amount``; ``recalc_amounts()`` is the one writer of ``subtotal`` / ``minimum_adjustment`` /
``total``. Both sum in **Python**, never with an ``F()`` expression — the SQLite integer-division
trap the rest of ``apps/scm`` avoids (``FreightInvoice.recalc_amounts`` says the same).

**3. SCM posts NO ``JournalEntry`` (L29).** ``apps.accounting`` owns the ledger. ``draft_invoice()``
stops at a **draft** ``accounting.Invoice``; AR aging, cash application, dunning, tax determination
and the journal posting are Module 2's, exactly as ``FreightInvoice`` stops at a draft ``Bill``.

**4. A quantity this app cannot MEASURE is never GUESSED.** Six of the fourteen charge bases
(``MANUAL_ONLY_BASES``) are priceable but not measurable today — ``Item`` carries no weight and no
dimensions, ``Location`` carries no area column, and per-client labour hours are 4.14's. Those lines
are still written, with ``quantity=0``, ``needs_manual_quantity=True`` and a description that NAMES
the missing measurement. An invented conversion factor is a number a client would be invoiced on and
nobody could defend; a zero with a visible "needs a quantity" chip is a number somebody fixes.

--------------------------------------------------------------------------------------------------
TWO STATED APPROXIMATIONS (stated, never hidden)
--------------------------------------------------------------------------------------------------

* ``per_pallet_position`` bills **one stock unit as one pallet position** until item dimensions
  exist. Every line it writes SAYS SO in its description — the ``YardVisit.carrier_name`` free-text
  posture. A units-per-pallet factor invented here would silently divide every storage bill.
* ``split_month`` and ``anniversary`` bill the stock that was **already there** at the start of the
  period at full weight, in addition to the in-period receipts the contract describes. Without the
  opening balance a steady-state client with no receipts in the month would be billed nothing for
  storage, which is not what either method means anywhere in the industry.

--------------------------------------------------------------------------------------------------
WHY THE INVOICE LINES LOOK "WRONG" (they are not — read this before changing them)
--------------------------------------------------------------------------------------------------
``accounting.InvoiceLine.unit_price`` is ``Decimal(14, **2**)`` and its ``save()`` recomputes
``line_total = quantity * unit_price``. A 4dp storage rate written there is silently re-rounded, and
the drafted invoice would then not equal the run it came from. So ``draft_invoice()`` writes
``quantity=Decimal("1")`` and ``unit_price=q2(line.amount)``, and carries the real *quantity × rate*
in the line **description**. Do NOT "improve" this into ``quantity=line.quantity`` /
``unit_price=line.rate``. The invariant that holds is ``invoice.subtotal == run.total``;
``invoice.total`` additionally carries tax, so the two are equal only when the client's
``default_tax_rate_pct`` is zero.

``__date`` LOOKUPS ARE BANNED IN THIS MODULE. Every datetime column (``StockMove.moved_at``,
``PickTask.picked_at``, ``Shipment.actual_pickup_at``) is filtered with an explicit **aware datetime
range**: ``__date`` compiles to ``CONVERT_TZ`` on MariaDB and returns NULL when the timezone tables
are not loaded, which on XAMPP they are not (the 4.12 carbon-report finding). A storage bill that
silently reads zero because of a driver-level NULL is the worst possible failure here.
"""
import calendar
import datetime

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.ThirdPartyLogistics._choices import (
    CHARGE_BASIS_CHOICES,
    CHARGE_CATEGORY_CHOICES,
    EDITABLE_RUN_STATUSES,
    MANUAL_ONLY_BASES,
    MAX_MEASUREMENT_ROWS,
    MAX_RUN_LINES,
    MAX_RUN_PERIOD_DAYS,
    RUN_STATUS_CHOICES,
)


#: Bases that are always written even when they price nothing this period — a flat recurring fee and
#: a dedicated-space commitment are owed whether or not a single carton moved.
_ALWAYS_BILLED_BASES = ("flat_recurring", "dedicated_space")

#: What is MISSING, per un-measurable basis. This text lands in the run line's description, so the
#: person who has to type the quantity is told what to go and measure rather than being handed a
#: blank. Keyed by ``charge_basis``; every member of ``MANUAL_ONLY_BASES`` must appear here.
_MANUAL_BASIS_NOTES = {
    "per_sqft": "needs a manual quantity — no item dimensions and no area column on a location, "
                "so occupied square footage cannot be derived",
    "per_cbm": "needs a manual quantity — items carry no volume or dimensions, so cubic metres "
               "cannot be derived",
    "per_kg": "needs a manual quantity — items carry no weight, so billable weight cannot be derived",
    "per_hour": "needs a manual quantity — labour is recorded per work centre (4.14), not per "
                "client, so client hours cannot be derived",
    "per_carton": "needs a manual quantity — items carry no case/carton pack, so cartons cannot be "
                  "derived from stock units",
    "pct_of_value": "needs a manual quantity — declared value is not recorded on a shipment, so a "
                    "percentage-of-value base cannot be derived",
}


def _day_start(day):
    """Midnight on ``day``, timezone-aware. See the module docstring for why every datetime filter
    in this module is an explicit aware range instead of a ``__date`` lookup."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def _day_end(day):
    """The last instant of ``day``, timezone-aware (inclusive upper bound)."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))


def _add_months(day, months):
    """``day`` shifted by whole months, with the day-of-month CLAMPED to the target month's length.

    Anniversary billing on the 31st has to survive February. ``calendar.monthrange`` is what makes
    31 Jan + 1 month land on 28/29 Feb instead of raising ``ValueError`` out of ``date()``.
    """
    total = (day.year * 12 + day.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    return datetime.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


class ClientBillingRun(TenantNumbered):
    """One client's charges for one period under one tariff [CBR-]. Amounts derived from its lines."""

    NUMBER_PREFIX = "CBR"

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list so a pointer added
    #: later is covered by the cross-tenant guard the moment it is named here — the
    #: ``ColdChainMonitor.TENANT_SCOPED_FKS`` idiom rather than another copy of the same if-block.
    TENANT_SCOPED_FKS = ("client", "rate_card")

    #: The smallest period that may attract the client's monthly minimum. A four-week run is a
    #: month for this purpose; a one-week catch-up run is not, and topping a partial period up to a
    #: full month's floor is how a client gets billed the minimum twice in one month.
    MINIMUM_CHARGE_MIN_DAYS = 28

    #: Public so the templates and the smoke sweep filter the same set the verbs do.
    EDITABLE_STATUSES = EDITABLE_RUN_STATUSES
    VOIDABLE_STATUSES = ("draft", "calculated")

    client = models.ForeignKey("scm.LogisticsClient", on_delete=models.PROTECT,
                               related_name="billing_runs")
    # PROTECT, deliberately: the tariff is the EVIDENCE for every figure on this run. A rate card
    # deleted out from under a billed period would leave an invoice nobody can reconstruct.
    rate_card = models.ForeignKey("scm.ClientRateCard", on_delete=models.PROTECT,
                                 related_name="billing_runs",
                                 help_text="The tariff these charges were priced from")
    period_start = models.DateField(help_text="First day billed (inclusive)")
    period_end = models.DateField(help_text="Last day billed (inclusive)")
    # NOT ON ANY FORM. Ruling 1 in the module docstring — the ladder is the only writer.
    status = models.CharField(max_length=12, choices=RUN_STATUS_CHOICES, default="draft",
                              editable=False)
    # Ruling 2 — derived, never typed. `recalc_amounts()` is the only writer of all three.
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    minimum_adjustment = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, editable=False,
        help_text="Top-up to the client's monthly minimum, when the period is a month and the "
                  "charges fell short of it")
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    calculated_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="+")
    # THE ONLY ACCOUNTING WRITE IN 4.17, and it is a DRAFT (ruling 3). SET_NULL so voiding the
    # invoice in accounting cannot cascade a billing run out of existence.
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True,
                                blank=True, editable=False, related_name="scm_billing_runs")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        unique_together = (("tenant", "number"),
                           ("tenant", "client", "period_start", "period_end"))
        indexes = [
            # The list page's ?status= filter and the five status stat tiles.
            models.Index(fields=["tenant", "status"], name="scm_cbr_tnt_status_idx"),
            # The ?client= filter, the client detail panel's "newest period_end first" and the SLA
            # credit basis lookup all walk (tenant, client, period_end) in exactly this order.
            models.Index(fields=["tenant", "client", "period_end"], name="scm_cbr_tnt_cli_end_idx"),
        ]

    def __str__(self):
        code = self.client.code if self.client_id else "?"
        return f"{self.number or 'CBR'} · {code} {self.period_start}–{self.period_end}"

    # ------------------------------------------------------------------ validation
    def clean(self):
        """Four refusals, one of which is the only mistake in this sub-module that quietly bills the
        wrong company."""
        errors = {}

        # Cross-tenant guards first: every later rule reads THROUGH these FKs.
        for name in self.TENANT_SCOPED_FKS:
            if getattr(self, f"{name}_id", None) is None:
                continue
            target = getattr(self, name, None)
            if target is not None and getattr(target, "tenant_id", None) != self.tenant_id:
                errors[name] = "That record belongs to another workspace."

        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                errors["period_end"] = "The period ends before it starts."
            else:
                days = (self.period_end - self.period_start).days + 1
                if days > MAX_RUN_PERIOD_DAYS:
                    errors["period_end"] = (
                        f"A billing run covers at most {MAX_RUN_PERIOD_DAYS} days; this one covers "
                        f"{days}. Split it into shorter periods.")

        rate_card = self.rate_card if self.rate_card_id else None
        if rate_card is not None and "rate_card" not in errors:
            # THE ONE THAT MATTERS: a tariff belonging to another client would bill Acme at
            # Contoso's rates, and every figure downstream of it would look perfectly plausible.
            if self.client_id and rate_card.client_id != self.client_id:
                errors["rate_card"] = "That tariff belongs to another client."
            elif self.period_start and self.period_end:
                starts_after = rate_card.effective_from and rate_card.effective_from > self.period_end
                ends_before = rate_card.effective_to and rate_card.effective_to < self.period_start
                if starts_after or ends_before:
                    window = (f"{rate_card.effective_from} – "
                              f"{rate_card.effective_to or 'open-ended'}")
                    errors["rate_card"] = (
                        f"{rate_card.number} is effective {window}, which does not overlap "
                        f"{self.period_start} – {self.period_end}.")

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ derived reads
    @property
    def period_days(self):
        """Inclusive day count. ``0`` when either bound is unset (an unsaved form instance)."""
        if not (self.period_start and self.period_end):
            return 0
        return (self.period_end - self.period_start).days + 1

    @property
    def is_editable(self):
        return self.status in EDITABLE_RUN_STATUSES

    def minimum_status(self):
        """``(applied, reason)`` — WHY the monthly minimum was or was not topped up.

        On the model rather than in the view so the totals block and ``recalc_amounts()`` can never
        disagree about a number the client is invoiced on.
        """
        client = self.client if self.client_id else None
        floor = (client.minimum_monthly_charge or ZERO) if client else ZERO
        if floor <= ZERO:
            return False, "not applied: this client has no monthly minimum"
        if client.billing_cycle != "monthly":
            return False, ("not applied: this client is billed "
                           f"{client.get_billing_cycle_display().lower()}, not monthly")
        if self.period_days < self.MINIMUM_CHARGE_MIN_DAYS:
            return False, (f"not applied: this run's period is shorter than "
                           f"{self.MINIMUM_CHARGE_MIN_DAYS} days")
        if (self.minimum_adjustment or ZERO) > ZERO:
            return True, (f"applied: charges of {self.subtotal} fell short of the "
                          f"{floor} monthly minimum")
        return False, f"not applied: charges already meet the {floor} monthly minimum"

    # ------------------------------------------------------------------ money
    def recalc_amounts(self, save=True):
        """Sum the lines in PYTHON, then apply the client's monthly minimum as a top-up.

        Never an ``F()`` and never a DB division (ruling 2). The minimum is applied ONLY to a
        monthly client on a period of at least ``MINIMUM_CHARGE_MIN_DAYS`` days — see
        :meth:`minimum_status` for every branch, in the words the detail page renders.
        """
        subtotal = sum((line.amount or ZERO for line in self.lines.all()), ZERO)
        self.subtotal = q2(subtotal)

        adjustment = ZERO
        client = self.client if self.client_id else None
        if (client is not None
                and client.billing_cycle == "monthly"
                and self.period_days >= self.MINIMUM_CHARGE_MIN_DAYS):
            adjustment = q2(max(ZERO, (client.minimum_monthly_charge or ZERO) - self.subtotal))
        self.minimum_adjustment = adjustment
        self.total = q2(self.subtotal + adjustment)

        if save and self.pk:
            self.save(update_fields=["subtotal", "minimum_adjustment", "total", "updated_at"])
        return self.total

    # ------------------------------------------------------------------ the engine
    def calculate(self, user=None):
        """Re-price the period from the tariff. Regenerates the DERIVED lines; manual lines survive.

        Deleting and re-deriving (rather than updating in place) is what makes the button safe to
        press twice: a run is a *statement of what the evidence says right now*, and the evidence —
        late-filed stock moves, a receipt posted yesterday for last week — genuinely changes.
        Manual lines are the human's, so they are never touched.

        ZERO matching lines is a VALID outcome: the run lands ``calculated`` with an empty line
        table and the detail page's empty state. It never raises and never 500s — "this tariff
        prices nothing that happened" is information, not an error.
        """
        if self.status not in EDITABLE_RUN_STATUSES:
            raise ValidationError(
                f"A {self.get_status_display().lower()} run can no longer be recalculated.")

        with transaction.atomic():
            self.lines.filter(is_manual=False).delete()
            manual_count = self.lines.count()
            budget = max(0, MAX_RUN_LINES - manual_count)

            rate_lines = list(
                self.rate_card.lines.filter(is_active=True)
                .select_related("applies_to_location", "applies_to_item_category", "gl_account"))

            written, truncated = 0, False
            for rate_line in rate_lines:
                if written >= budget:
                    truncated = True
                    break
                built = self._build_line(rate_line)
                if built is None:
                    continue
                built.save()
                written += 1

            self.status = "calculated"
            self.calculated_at = timezone.now()
            self.save(update_fields=["status", "calculated_at", "updated_at"])
            self.recalc_amounts()

        return {"lines_written": written, "manual_lines": manual_count, "truncated": truncated,
                "total": self.total}

    def _build_line(self, rate_line):
        """One unsaved :class:`ClientBillingRunLine` for ``rate_line``, or ``None`` to skip it."""
        quantity, reference, needs_manual, note = self._resolve_quantity(rate_line)
        basis = rate_line.charge_basis

        if not needs_manual:
            # The tier band is a statement about the MEASURED quantity, so it is only meaningful
            # once there is one. A band check against the placeholder 0 on an un-measurable basis
            # would silently drop exactly the lines somebody has to come back and fill in.
            if not rate_line.applies_to_quantity(quantity):
                return None

        included = rate_line.included_quantity or ZERO
        billable = max(ZERO, quantity - included)
        if not (needs_manual or billable > ZERO or basis in _ALWAYS_BILLED_BASES):
            return None

        description = rate_line.description or rate_line.get_charge_basis_display()
        if note:
            description = f"{description} — {note}"
        if included > ZERO and billable != quantity:
            description = f"{description} (first {included} included)"

        return ClientBillingRunLine(
            run=self,
            rate_card_line=rate_line,
            # SNAPSHOTS. The tariff can be superseded tomorrow; what this run billed must not move.
            charge_category=rate_line.charge_category,
            charge_basis=basis,
            description=description[:255],
            quantity=q4(billable),
            rate=q4(rate_line.rate or ZERO),
            source_reference=(reference or "")[:120],
            is_manual=False,
            needs_manual_quantity=needs_manual,
        )

    # ------------------------------------------------------------------ quantity resolvers
    def _resolve_quantity(self, rate_line):
        """``(quantity, source_reference, needs_manual_quantity, description_note)``.

        Every branch reads a column VERIFIED to exist as-built. There is deliberately no ``else:
        return some_guess`` — an unrecognised basis falls through to the manual path, which asks a
        human rather than inventing a figure.
        """
        basis = rate_line.charge_basis
        if basis in MANUAL_ONLY_BASES:
            return ZERO, "", True, _MANUAL_BASIS_NOTES.get(
                basis, "needs a manual quantity — this charge basis is not measurable from the "
                       "records this app keeps")

        handler = {
            "per_pallet_position": self._qty_pallet_positions,
            "per_receipt": self._qty_receipts,
            "per_order": self._qty_orders,
            "per_line": self._qty_order_lines,
            "per_unit": self._qty_units_picked,
            "per_shipment": self._qty_shipments,
            "flat_recurring": self._qty_recurring_periods,
            "dedicated_space": self._qty_dedicated_space,
        }.get(basis)
        if handler is None:
            return ZERO, "", True, ("needs a manual quantity — this charge basis has no automatic "
                                    "measurement in this release")
        return handler(rate_line)

    # -- storage ---------------------------------------------------------------
    def _storage_move_qs(self, rate_line):
        """The client's stock ledger, narrowed by whatever the rate line narrows.

        Attribution runs through ``item.owner_client`` and NEVER through a column on ``StockMove``:
        an owner column on an append-only ledger would be a second source of truth (L37).
        """
        from apps.scm.models import StockMove

        qs = StockMove.objects.filter(tenant=self.tenant, item__owner_client=self.client_id)
        if rate_line.applies_to_location_id:
            qs = qs.filter(location_id=rate_line.applies_to_location_id)
        if rate_line.applies_to_item_category_id:
            qs = qs.filter(item__category_id=rate_line.applies_to_item_category_id)
        return qs

    @staticmethod
    def _balance(qs):
        return qs.aggregate(s=Sum("quantity"))["s"] or ZERO

    def _qty_pallet_positions(self, rate_line):
        """Storage, per the client's ``storage_billing_method``.

        STATED APPROXIMATION (module docstring): one stock unit is billed as one pallet position,
        because items carry no dimensions. The note travels onto every line's description.
        """
        quantity, reference = self._storage_quantity(rate_line)
        return quantity, reference, False, ("1 stock unit billed as 1 pallet position — item "
                                            "dimensions are not recorded")

    def _storage_quantity(self, rate_line):
        """``(quantity, source_reference)`` for one of the five storage billing methods."""
        client = self.client
        method = client.storage_billing_method
        qs = self._storage_move_qs(rate_line)
        ps, pe, days = self.period_start, self.period_end, self.period_days

        if method == "snapshot":
            balance = self._balance(qs.filter(moved_at__lte=_day_end(pe)))
            return max(ZERO, q4(balance)), f"StockMove ledger · snapshot at {pe}"

        if method == "calendar_month":
            balance = self._balance(qs.filter(moved_at__lte=_day_end(ps)))
            return max(ZERO, q4(balance)), f"StockMove ledger · balance at {ps} · 1 period"

        if method == "average_daily":
            return self._storage_average_daily(qs, ps, pe, days)

        if method == "anniversary":
            return self._storage_anniversary(qs, ps, pe)

        if method == "split_month":
            return self._storage_split_month(qs, ps, pe)

        # A method the registry grew without a resolver: bill the snapshot and SAY which method
        # actually ran, rather than silently pricing something else under its name.
        balance = self._balance(qs.filter(moved_at__lte=_day_end(pe)))
        return max(ZERO, q4(balance)), f"StockMove ledger · snapshot at {pe} (no '{method}' resolver)"

    def _storage_average_daily(self, qs, ps, pe, days):
        """Opening balance, then the period's moves walked day by day in Python.

        Each day's balance is floored at zero before it enters the mean: a negative balance is a
        data fault (a ledger cannot hold less than nothing), and letting one cancel a real day of
        storage would UNDER-bill silently.
        """
        opening = self._balance(qs.filter(moved_at__lt=_day_start(ps)))
        rows = (qs.filter(moved_at__gte=_day_start(ps), moved_at__lte=_day_end(pe))
                .order_by("moved_at").values_list("moved_at", "quantity")[:MAX_MEASUREMENT_ROWS])

        daily = {}
        for moved_at, quantity in rows:
            day = timezone.localdate(moved_at)
            daily[day] = daily.get(day, ZERO) + (quantity or ZERO)

        balance, running, day = opening, ZERO, ps
        while day <= pe:
            balance += daily.get(day, ZERO)
            running += max(ZERO, balance)
            day += datetime.timedelta(days=1)

        average = (running / days) if days else ZERO
        return q4(average), f"StockMove ledger · {days} days · average daily balance"

    def _storage_anniversary(self, qs, ps, pe):
        """Each receipt's monthly anniversaries falling inside the period, times its quantity.

        Includes receipts filed BEFORE the period — their anniversaries are exactly what this method
        exists to bill (module docstring, stated approximation 2).
        """
        rows = (qs.filter(quantity__gt=0, moved_at__lte=_day_end(pe))
                .order_by("moved_at").values_list("moved_at", "quantity")[:MAX_MEASUREMENT_ROWS])

        total, counted = ZERO, 0
        for moved_at, quantity in rows:
            received = timezone.localdate(moved_at)
            # Jump straight to the month before the period rather than walking from the receipt
            # date: a two-year-old receipt would otherwise cost 24 wasted iterations each.
            step = max(0, (ps.year - received.year) * 12 + (ps.month - received.month) - 1)
            hits = 0
            while True:
                anniversary = _add_months(received, step)
                if anniversary > pe:
                    break
                if anniversary >= ps:
                    hits += 1
                step += 1
            if hits:
                total += (quantity or ZERO) * hits
                counted += 1

        return q4(total), f"StockMove ledger · {counted} receipts · monthly anniversaries in period"

    def _storage_split_month(self, qs, ps, pe):
        """Opening stock at full weight; in-period receipts full on days 1–15, half from the 16th."""
        opening = max(ZERO, self._balance(qs.filter(moved_at__lt=_day_start(ps))))
        rows = (qs.filter(quantity__gt=0, moved_at__gte=_day_start(ps), moved_at__lte=_day_end(pe))
                .order_by("moved_at").values_list("moved_at", "quantity")[:MAX_MEASUREMENT_ROWS])

        total, first_half, second_half = opening, 0, 0
        for moved_at, quantity in rows:
            received = timezone.localdate(moved_at)
            if received.day <= 15:
                total += (quantity or ZERO)
                first_half += 1
            else:
                total += (quantity or ZERO) * Decimal("0.5")
                second_half += 1

        return q4(total), (f"StockMove ledger · opening {opening} + {first_half} full-period and "
                           f"{second_half} half-period receipts")

    # -- activity --------------------------------------------------------------
    def _qty_receipts(self, rate_line):
        """Goods receipts attributable to this client.

        ``GoodsReceiptLine`` has NO ``item`` FK (``PurchaseOrderLine`` carries free-text
        ``item_description`` + ``sku_hint`` — the documented pre-catalog L28 stand-in), so
        attribution runs ONLY through the putaway task's item or the receiving location's owner.
        Do not "restore" a ``po_line → item`` path; it does not exist.

        ``rate_line`` is deliberately unused — a receipt count has nothing to narrow on — so the
        detail page's unbilled-activity panel calls this with ``None``. Same for
        :meth:`_qty_orders`, :meth:`_qty_order_lines`, :meth:`_qty_units_picked` and
        :meth:`_qty_shipments`; only the STORAGE resolvers read the rate line.
        """
        from apps.scm.models import GoodsReceiptNote

        qs = (GoodsReceiptNote.objects
              .filter(tenant=self.tenant,
                      receipt_date__gte=self.period_start, receipt_date__lte=self.period_end)
              .filter(Q(putaway_tasks__item__owner_client=self.client_id)
                      | Q(location__owner_client=self.client_id))
              .distinct())
        return self._count_with_evidence(qs, "number", "receipts")

    def _qty_orders(self, rate_line):
        from apps.scm.models import SalesOrder

        qs = (SalesOrder.objects
              .filter(tenant=self.tenant,
                      order_date__gte=self.period_start, order_date__lte=self.period_end,
                      lines__item__owner_client=self.client_id)
              .distinct())
        return self._count_with_evidence(qs, "number", "orders")

    def _qty_order_lines(self, rate_line):
        from apps.scm.models import SalesOrderLine

        qs = SalesOrderLine.objects.filter(
            sales_order__tenant=self.tenant,
            sales_order__order_date__gte=self.period_start,
            sales_order__order_date__lte=self.period_end,
            item__owner_client=self.client_id)
        count = qs.count()
        return Decimal(count), f"SalesOrderLine · {count} lines in period", False, ""

    def _qty_units_picked(self, rate_line):
        from apps.scm.models import PickTaskLine

        qs = PickTaskLine.objects.filter(
            pick_task__tenant=self.tenant,
            pick_task__picked_at__gte=_day_start(self.period_start),
            pick_task__picked_at__lte=_day_end(self.period_end),
            item__owner_client=self.client_id)
        picked = qs.aggregate(s=Sum("quantity_picked"))["s"] or ZERO
        return q4(picked), f"PickTaskLine · {qs.count()} picked lines in period", False, ""

    def _qty_shipments(self, rate_line):
        """Shipments carrying this client's stock, dated on the ACTUAL pickup where there is one.

        The fallback to ``planned_pickup_date`` is not laziness: a shipment that has left but whose
        actual timestamp was never captured is still a shipment the client owes for, and dropping it
        would under-bill in exactly the case where the warehouse's own data entry slipped.
        """
        from apps.scm.models import Shipment

        qs = (Shipment.objects
              .filter(tenant=self.tenant, sales_order__lines__item__owner_client=self.client_id)
              .filter(Q(actual_pickup_at__gte=_day_start(self.period_start),
                        actual_pickup_at__lte=_day_end(self.period_end))
                      | Q(actual_pickup_at__isnull=True,
                          planned_pickup_date__gte=self.period_start,
                          planned_pickup_date__lte=self.period_end))
              .distinct())
        return self._count_with_evidence(qs, "number", "shipments")

    @staticmethod
    def _count_with_evidence(qs, field, noun):
        """``(count, "GRN-00007, GRN-00011 …", False, "")`` — the count plus NAMED evidence.

        A bare count on an invoice line is unarguable-with. The first few document numbers are what
        turn "37 receipts" into something a client's ops manager can actually check.
        """
        count = qs.count()
        sample = list(qs.order_by(field).values_list(field, flat=True)[:4])
        reference = ", ".join(sample)
        if count > len(sample):
            reference = f"{reference} +{count - len(sample)} more" if reference else f"{count} {noun}"
        return Decimal(count), (reference or f"{count} {noun}"), False, ""

    # -- period / commitment ---------------------------------------------------
    def _qty_recurring_periods(self, rate_line):
        """How many ``day`` / ``week`` / ``month`` units the run period covers.

        A week is exactly 7 days. A MONTH is the summed FRACTION of each calendar month the period
        touches — exact, and free of the invented "30 days" or "30.44 days" constant that would
        make a full January bill 1.0323 months.
        """
        ps, pe, days = self.period_start, self.period_end, self.period_days
        period = rate_line.period or "month"

        if period == "day":
            return Decimal(days), f"{days} days in period", False, ""
        if period == "week":
            weeks = q4(Decimal(days) / 7)
            return weeks, f"{days} days = {weeks} weeks", False, ""

        months, cursor = ZERO, ps
        while cursor <= pe:
            length = calendar.monthrange(cursor.year, cursor.month)[1]
            month_end = datetime.date(cursor.year, cursor.month, length)
            covered = (min(pe, month_end) - cursor).days + 1
            months += Decimal(covered) / Decimal(length)
            cursor = month_end + datetime.timedelta(days=1)
        months = q4(months)
        return months, f"{days} days = {months} months", False, ""

    def _qty_dedicated_space(self, rate_line):
        """The contracted commitment — pallet positions where there are any, else square feet.

        On a ``hybrid`` client the greater of the commitment and the derived occupancy is billed,
        which is what "hybrid" means: a floor you pay for whether you use it or not, and the overflow
        on top. ``occupied_pallet_positions`` is deliberately NOT a stored column anywhere in 4.17.
        """
        client = self.client
        if client.committed_pallet_positions:
            quantity = Decimal(client.committed_pallet_positions)
            unit, reference = "pallet positions", f"{quantity} committed pallet positions"
        else:
            quantity = client.committed_sqft or ZERO
            unit, reference = "sq ft", f"{quantity} committed sq ft"

        note = ""
        if client.space_model == "hybrid":
            occupied, _ = self._storage_quantity(rate_line)
            if occupied > quantity:
                reference = f"{reference}; billed {occupied} occupied ({unit})"
                note = ("hybrid space — billed the greater of the commitment and the derived "
                        "occupancy")
                quantity = occupied
        return q4(quantity), reference, False, note

    # ------------------------------------------------------------------ the verb ladder
    def approve(self, user=None):
        """``calculated → approved``. The human signature on the numbers."""
        if self.status != "calculated":
            raise ValidationError(
                f"Only a calculated run can be approved; this one is {self.get_status_display().lower()}.")
        self.status = "approved"
        self.approved_by = user if getattr(user, "is_authenticated", False) else None
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return self

    def draft_invoice(self, user=None):
        """Draft an ``accounting.Invoice`` for the client and link it — the AR hand-off (L29).

        A DRAFT only. SCM posts no ``JournalEntry`` and opens no second AR ledger; the finance team
        sends, ages, taxes and applies cash against the invoice in ``apps/accounting``, which is
        where the GL effect lives. See the module docstring for why every line is written
        ``quantity=1`` with the real quantity × rate in the description.
        """
        if self.status != "approved":
            raise ValidationError("Approve the billing run before drafting an invoice.")
        if self.invoice_id is not None:
            raise ValidationError(f"This run is already invoiced as {self.invoice.number}.")

        from apps.accounting.models import Invoice, InvoiceLine

        client = self.client
        tax_rate = client.default_tax_rate_pct or ZERO
        default_account = client.default_revenue_account

        with transaction.atomic():
            invoice = Invoice(
                tenant=self.tenant,
                kind="invoice",
                status="draft",
                party=client.party,
                issue_date=timezone.localdate(),
                currency=(self.rate_card.currency if self.rate_card_id else None) or client.currency,
                payment_terms=client.payment_terms,
                notes=(f"3PL billing run {self.number} · {client.code} · "
                       f"{self.period_start} – {self.period_end}"),
            )
            invoice.save()

            for line in self.lines.select_related("rate_card_line").all():
                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=self._invoice_line_description(line),
                    quantity=Decimal("1"),
                    unit_price=q2(line.amount),
                    tax_rate_pct=tax_rate,
                    gl_account=((line.rate_card_line.gl_account if line.rate_card_line_id else None)
                                or default_account),
                )

            if (self.minimum_adjustment or ZERO) > ZERO:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=(f"Monthly minimum top-up — charges of {self.subtotal} against a "
                                 f"{client.minimum_monthly_charge} minimum")[:255],
                    quantity=Decimal("1"),
                    unit_price=q2(self.minimum_adjustment),
                    tax_rate_pct=tax_rate,
                    gl_account=default_account,
                )

            invoice.recalc_totals()
            self.invoice = invoice
            self.status = "invoiced"
            self.save(update_fields=["invoice", "status", "updated_at"])

        return invoice

    @staticmethod
    def _invoice_line_description(line):
        """The run line's description PLUS the quantity × rate the flattened invoice line loses."""
        text = line.description or line.get_charge_basis_display()
        if (line.quantity or ZERO) and (line.rate or ZERO):
            text = f"{text} ({line.quantity} × {line.rate})"
        if line.source_reference:
            text = f"{text} · {line.source_reference}"
        return text[:255]

    def void(self, user=None):
        """``draft`` / ``calculated`` → ``void``. An INVOICED run cannot be voided from SCM.

        Once a draft invoice exists, the money conversation has moved to accounting: voiding the run
        here would leave an AR document with no explanation behind it. Void the invoice there.
        """
        if self.status not in self.VOIDABLE_STATUSES:
            raise ValidationError(
                f"A {self.get_status_display().lower()} run cannot be voided here"
                + (" — void the linked invoice in accounting." if self.invoice_id else "."))
        self.status = "void"
        self.save(update_fields=["status", "updated_at"])
        return self


class ClientBillingRunLine(models.Model):
    """One charge on a billing run. **Tenant-less child**, reached via ``run.tenant``.

    The ``CarrierRateCardLine`` / ``FreightInvoiceLine`` / ``SalesOrderLine`` convention: a second
    ``tenant`` FK here would be a second answer to "whose row is this", and the two would eventually
    disagree. Every view scopes these rows through ``run__tenant=request.tenant``.

    ``charge_category``, ``charge_basis`` and ``rate`` are **snapshots**, not joins. The tariff can
    be superseded, re-priced or re-categorised tomorrow; what this run billed must not move under
    the invoice that was drafted from it.

    A NULL ``rate_card_line`` means a MANUAL line — a human's charge, which :meth:`ClientBillingRun.calculate`
    never deletes and never overwrites.
    """

    run = models.ForeignKey("scm.ClientBillingRun", on_delete=models.CASCADE, related_name="lines")
    # SET_NULL, not PROTECT: the tariff line is provenance, and a run that outlives a tidied-up rate
    # card must still render. The snapshot columns below are why nothing is lost when it goes.
    rate_card_line = models.ForeignKey("scm.ClientRateCardLine", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+",
                                       help_text="Blank on a manually added charge")
    charge_category = models.CharField(max_length=16, choices=CHARGE_CATEGORY_CHOICES)
    charge_basis = models.CharField(max_length=20, choices=CHARGE_BASIS_CHOICES)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    rate = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    # THE ONE COLUMN NOBODY TYPES. save() below is its only writer.
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)
    source_reference = models.CharField(
        max_length=120, blank=True,
        help_text="The evidence this figure came from, e.g. 'GRN-00007, GRN-00011' or "
                  "'StockMove ledger · 31 days · average daily balance'")
    is_manual = models.BooleanField(
        default=False, help_text="A human's charge — never regenerated by a recalculation")
    needs_manual_quantity = models.BooleanField(
        default=False, editable=False,
        help_text="Priced but not measurable — somebody has to enter the quantity")

    class Meta:
        ordering = ["charge_category", "id"]

    def __str__(self):
        return f"{self.description} · {self.amount}"

    def save(self, *args, **kwargs):
        """THE single writer of ``amount``.

        The rate line's ``minimum_charge`` is a FLOOR, not an addition: a per-order fee with a
        250.00 minimum bills 250.00 on a slow month and the real figure on a busy one. Reading it
        through ``rate_card_line`` costs no query on the calculate path, where the object is already
        assigned in memory.
        """
        minimum = ZERO
        if self.rate_card_line_id:
            minimum = self.rate_card_line.minimum_charge or ZERO
        self.amount = q2(max((self.quantity or ZERO) * (self.rate or ZERO), minimum))
        # `amount` is derived, so it must ride along on any partial save or the row would keep a
        # stale figure while its quantity moved.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "amount" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["amount"]
        super().save(*args, **kwargs)
