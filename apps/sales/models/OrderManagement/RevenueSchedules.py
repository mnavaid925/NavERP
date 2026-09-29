"""Sales 8.6 Order Management — ``RevenueSchedule`` + ``PerformanceObligation``.

This is the repo's ONLY ASC 606 / IFRS 15 representation, and it is built around one
architectural decision that everything else in this file follows from:

    **EVERY money balance on a revenue schedule is a ``@property``, never a column.**

``contract_amount``, ``allocated_amount``, ``recognized_amount``, ``deferred_amount``,
``contract_asset``, ``contract_liability``, ``recognition_progress_pct``, ``days_overdue``,
``is_unbalanced``, ``is_overdue``, ``is_editable`` and ``is_locked`` are all DERIVED on read
from the schedule's own obligations and from ``scm.SalesOrder.total``. The only two money
columns that exist are ``PerformanceObligation.allocated_amount`` and
``PerformanceObligation.recognized_amount``, and both are ``editable=False`` — off every form,
unreachable from any POST, and written by exactly one method: ``recompute()`` below.

Why derived rather than stored, stated once so a reader can tell a deliberate derivation from
an oversight:

* **A stored balance is a second source of truth that disagrees with its own inputs.** The
  moment an amendment re-prices an order, or a percentage is corrected, a stored
  ``recognized_amount`` is stale by definition and nothing in the schema notices. Derived, the
  figure cannot be stale, because there is nothing to fall out of date.
* **The order total is not ours.** ``contract_amount`` IS ``scm.SalesOrder.total``, which SCM
  4.5 owns and recomputes with its own logic. Copying it into a column would be 8.6 shadowing
  another module's arithmetic — the exact ownership error (L36/L37) this sub-module exists to
  avoid.
* **Time-dependent figures cannot be columns at all.** ``days_overdue`` is a comparison against
  ``recognize_on`` and today. A stored integer is correct when written and wrong the moment the
  clock ticks past midnight, and no refresh job makes that go away, because remembering to run
  the refresh job is the failure mode.

Every derived number is computed in **PYTHON** over an already-fetched set. Never an ``F()``
expression, never a database-side percentage, never ``aggregate("Sum")`` on a Decimal: the trap
is named in SCM 4.5's own ``SalesOrder.recalc_totals()``, where SQLite integer-divides and
silently drops fractional cents rather than raising. A schedule whose obligations sum to
``12345.67`` must not read back as ``12345`` because of a rounding that happened in the driver.

The register's arithmetic, in the order ASC 606 works in it::

    contract_amount    = the order's total                        (SCM 4.5 owns that figure)
    allocated_amount   = Σ obligation.allocated_amount
    recognized_amount  = Σ obligation.recognized_amount
    deferred_amount    = allocated - recognized, floored at zero
    contract_asset     = recognized - allocated, when positive
    contract_liability = allocated - recognized, when positive

**``recompute()`` is the single writer of the two stored money columns** and it refuses unless
``status == "active"`` — a draft schedule can never recognise revenue, so going active is a
deliberate human act and a schedule nobody looked at stays at zero. It walks the obligations
whose ``recognize_on`` has passed, oldest date first, spending a shared budget of
``contract_amount`` in Python, and writes each row back.

``PerformanceObligation`` is **tenant-less** — a plain ``models.Model`` with no ``tenant`` FK and
no number prefix, reached through ``schedule.tenant``. That is the convention
``scm.SalesOrderLine`` and ``OrderAmendmentLine`` already use: a child reachable only through a
tenant-owned parent has no business carrying its own tenant, and a second copy of the column is
a second thing to get wrong.

Two validation traps are handled explicitly, both the 0.20 close-out lesson:

* ``RevenueSchedule.clean()`` keys its tenant guards on the fields its form actually carries
  (``sales_order``, ``fiscal_period``) and on ``NON_FIELD_ERRORS`` for ``journal_entry`` — which
  is ``editable=False`` and off the form, so a message keyed on it would route through
  ``add_error(None, …)`` and 500 every create and edit.
* ``PerformanceObligation.clean()`` is keyed on ``NON_FIELD_ERRORS`` throughout: its form
  excludes ``schedule`` (set by the parent view), both money columns and the timestamps.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.forms.forms import NON_FIELD_ERRORS
from django.utils import timezone

from apps.sales.models._base import TenantNumbered


ZERO = Decimal("0")
CENT = Decimal("0.01")
ONE_HUNDRED = Decimal("100")

#: Sorts an obligation with no ``recognize_on`` BEHIND every dated one, so an undated row can
#: never consume the shared recognition budget ahead of a dated one. This must be a real
#: ``date``: the sort key pairs it with ``recognize_on`` itself, and Python compares the two
#: directly, so a tuple sentinel raises ``TypeError: '<' not supported between instances of
#: 'tuple' and 'datetime.date'`` the moment a schedule mixes dated and undated obligations —
#: which the form explicitly invites ("Leave blank only if the performance has no date yet").
#: ``date.max`` rather than ``date.min``: the undated rows sort last, and they are never
#: recognised anyway (the loop below skips them), so the ordering only matters for budget order.
UNSCHEDULED = date.max


class RevenueSchedule(TenantNumbered):
    """One ASC 606 / IFRS 15 revenue schedule over one SCM sales order [RVS-].

    The schedule owns NO money of its own. It is a frame: it names the order, the standard
    being applied, the method being applied, and the period revenue is recognised into — and
    every figure a reader wants is derived from the obligations hanging off it.
    """

    NUMBER_PREFIX = "RVS"

    #: The ONE authorable ``status`` in 8.6. A schedule is drafted and voided by a person, not
    #: by a workflow verb, which is why — unlike ``OrderAmendment.status`` — this one is on the
    #: form. The widget is narrowed to these exact values so nothing else is authorable.
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("complete", "Complete"),
        ("void", "Void"),
    ]
    METHOD_CHOICES = [
        ("point_in_time", "Point In Time"),
        ("over_time", "Over Time"),
        ("milestone", "Milestone"),
    ]
    COMPLIANCE_STANDARD_CHOICES = [
        ("asc606", "ASC 606"),
        ("ifrs15", "IFRS 15"),
        ("both", "ASC 606 & IFRS 15"),
    ]

    #: Statuses in which the schedule's own fields and obligations may still be worked. A
    #: complete or void schedule is a closed document.
    EDITABLE_STATUSES = ("draft", "active")

    # SCM 4.5 owns this row. CASCADE, because a revenue schedule without its order has no
    # contract to recognise against — and the order's lifecycle is 4.5's call, not ours.
    sales_order = models.ForeignKey("scm.SalesOrder", on_delete=models.CASCADE,
                                    related_name="revenue_schedules")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="over_time")
    compliance_standard = models.CharField(max_length=10, choices=COMPLIANCE_STANDARD_CHOICES,
                                           default="asc606")
    # SET_NULL: a period is closed and re-opened in Accounting, and retiring one must never
    # destroy the recognition history that was recognised into it.
    fiscal_period = models.ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="revenue_schedules")
    # REFERENCE-ONLY, ``editable=False``, absent from every form. 8.6 posts NOTHING (L29) —
    # matching SCM 4.5's and 4.10's explicit posture. The column exists so a schedule can
    # point at the journal entry a human or another module raised once the figures were
    # agreed; it is never written from here, and a form carrying it would let a clerk claim
    # revenue recognition happened that never did.
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="revenue_schedules",
                                      editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # NAMED, per MySQL's index-name ceiling: an auto-generated constraint name is long
            # and machine-derived, and a constraint nobody can name in a hand-written rollback
            # is a constraint nobody drops.
            models.UniqueConstraint(fields=["tenant", "number"],
                                    name="sales_rvs_tenant_number_uniq"),
        ]
        indexes = [
            # 22 characters each — under MySQL's 30-character identifier ceiling.
            models.Index(fields=["tenant", "status"], name="sales_rvs_tnt_status_idx"),
            models.Index(fields=["tenant", "sales_order"], name="sales_rvs_tnt_order_idx"),
        ]

    # ------------------------------------------------------------------ derived balances

    def obligation_rows(self):
        """This schedule's obligations as a LIST, fetched once, never raising.

        The same safety-wrapper discipline ``OrderHold.parsed_snapshot`` demonstrates, applied
        to the queries the derived properties sit on. Three things it protects:

        * an unsaved instance (``pk is None``) has no reverse relation to read, and the list
          view's stats are summed from instances that may never be saved;
        * a schedule whose order row has gone returns no obligations rather than exploding on
          the one page whose whole job is to explain a revenue position;
        * every balance below reads the SAME list, so a page showing five derived figures
          cannot show them derived from five different moments.
        """
        if self.pk is None:
            return []
        try:
            return list(self.obligations.all())
        except (ValueError, TypeError):
            return []

    @property
    def contract_amount(self):
        """The value of the contract — ``scm.SalesOrder.total``, read, never copied.

        DERIVED, not a column: SCM 4.5 recomputes that total from the order's own lines with
        its own logic, and an ``OrderAmendment.apply()`` moves it. A column here would be a
        snapshot of somebody else's arithmetic, and the two would disagree the first time an
        amendment was applied.
        """
        order = self.sales_order
        return (getattr(order, "total", None) or ZERO) if order is not None else ZERO

    @property
    def allocated_amount(self):
        """Σ ``allocated_amount`` across the obligations, summed in PYTHON.

        DERIVED: each obligation's ``allocated_amount`` is itself written only by
        ``recompute()``, so a schedule-level column would be a second copy that could only
        ever be a cache of the first. The sum is a Python loop over the fetched rows — never
        ``aggregate("Sum")``, which is the SQLite decimal trap.
        """
        total = ZERO
        for row in self.obligation_rows():
            total += (row.allocated_amount or ZERO)
        return total

    @property
    def recognized_amount(self):
        """Σ ``recognized_amount`` across the obligations, summed in PYTHON. See above."""
        total = ZERO
        for row in self.obligation_rows():
            total += (row.recognized_amount or ZERO)
        return total

    @property
    def deferred_amount(self):
        """``allocated - recognized``, floored at zero. DERIVED, never stored.

        ASC 606's liability side: payment taken ahead of performance is revenue you HOLD, not
        revenue you have earned. The floor at zero is the whole point — a schedule that has
        over-recognised holds a CONTRACT ASSET, and calling that excess "deferred" would
        report a liability where the standard says an asset. They are separate properties
        because only one of them is true at a time, and one signed number cannot say which.
        """
        gap = self.allocated_amount - self.recognized_amount
        return gap if gap > ZERO else ZERO

    @property
    def contract_asset(self):
        """``recognized - allocated`` when positive: performance ahead of payment.

        DERIVED, never stored, never negative. The mirror of ``contract_liability``; the
        excess is an asset because the customer owes for work already delivered, not because
        money is in the bank.
        """
        excess = self.recognized_amount - self.allocated_amount
        return excess if excess > ZERO else ZERO

    @property
    def contract_liability(self):
        """``allocated - recognized`` when positive: payment ahead of performance.

        DERIVED, never stored, never negative. Equal to ``deferred_amount`` by construction —
        kept under its own name because the standard calls this balance a contract liability,
        and a page labelled only "deferred" is answering a different question.
        """
        excess = self.allocated_amount - self.recognized_amount
        return excess if excess > ZERO else ZERO

    @property
    def recognition_progress_pct(self):
        """Recognised as a percentage of allocated, computed in PYTHON.

        DERIVED, and explicitly not an ``F()`` expression: ``F("recognized") * 100 /
        F("allocated")`` integer-divides on SQLite and returns a whole-number percent that
        silently drops the fractional part of every obligation. An unallocated schedule reads
        0 rather than dividing by zero.
        """
        allocated = self.allocated_amount
        if allocated <= ZERO:
            return ZERO
        pct = (self.recognized_amount / allocated) * ONE_HUNDRED
        return pct.quantize(CENT, rounding="ROUND_HALF_UP")


    @property
    def allocation_pct_total(self):
        """Σ ``allocation_pct`` across the obligations, in PYTHON. Feeds ``is_unbalanced``.

        DERIVED: the percentages are the AUTHORED input (they are on the obligation form) and
        their sum is arithmetic, not data. ASC 606 allocates the transaction price across the
        distinct obligations, so anything other than 100% means the schedule is missing an
        obligation or double-counting one.
        """
        total = ZERO
        for row in self.obligation_rows():
            total += (row.allocation_pct or ZERO)
        return total

    @property
    def is_unbalanced(self):
        """True when the obligations' percentages do not sum to 100% (within half a cent).

        DERIVED, never a stored flag: a flag would need a trigger to maintain it, and a
        schedule becomes balanced the moment an obligation's percentage is edited — with no
        trigger anywhere. The tolerance is a cent rather than an exact ``!= 100`` because three
        33.33% lines are a legitimate rounding of a third each, and calling that unbalanced
        would train people to ignore the warning.
        """
        return abs(self.allocation_pct_total - ONE_HUNDRED) > CENT

    @property
    def days_overdue(self):
        """Days since the EARLIEST passed, unrecognised ``recognize_on``. 0 when none.

        DERIVED, and the strongest argument in this file for derivation: this number depends on
        the wall clock, so a column is correct only at the instant it was written. Computed in
        Python over the fetched rows, with the obligation's own ``remaining_amount`` as the
        test — a passed date on a fully recognised obligation is history, not lateness, and
        reporting it as overdue would put every completed schedule permanently on the
        exception report.
        """
        today = timezone.localdate()
        worst = 0
        for row in self.obligation_rows():
            if not row.recognize_on or row.recognize_on >= today:
                continue
            if (row.remaining_amount or ZERO) <= ZERO:
                continue
            days = (today - row.recognize_on).days
            if days > worst:
                worst = days
        return worst

    @property
    def is_overdue(self):
        """True when at least one obligation is past its date with revenue still unrecognised."""
        return self.days_overdue > 0

    @property
    def is_editable(self):
        """True while the schedule is still a working document. Read from ``status``."""
        return self.status in self.EDITABLE_STATUSES

    @property
    def is_locked(self):
        """True once the schedule is complete. Read from ``status`` — never a stored flag.

        A ``locked`` column is the shape §2.5 rules out: a boolean that can disagree with the
        status it mirrors, and that nothing in the schema re-derives when the status moves.
        """
        return self.status == "complete"


    # ------------------------------------------------------------------ the single writer

    def recompute(self, as_of=None):
        """Write BOTH stored money columns on every obligation. THE ONLY WRITER.

        Two passes, both in Python over one fetched set:

        1. **Allocate.** Each obligation's share is ``contract_amount × allocation_pct / 100``,
           quantised to cents, and clamped so the running total can never exceed the contract.
           A schedule whose percentages exceed 100% therefore shows the truth on its face —
           the money does not exist — instead of inflating recognised revenue past the deal.
        2. **Recognise.** Obligations whose ``recognize_on`` has passed are walked OLDEST DATE
           FIRST against a shared budget of ``contract_amount``. Each takes at most its own
           allocation and at most what is left, and the budget is decremented as it goes. This
           is what stops the second obligation of a two-obligation schedule recognising more
           once the first has taken the whole contract.

        Undated obligations are allocated but NEVER recognised: without a date there is no
        evidence the performance happened, and a schedule that guessed would be the
        forgeable snapshot this sub-module refuses to build everywhere else.

        Refuses (and writes nothing) unless ``status == "active"``: revenue recognition on a
        draft schedule is the failure this whole sub-module is built to make impossible, so the
        refusal lives in the METHOD, not only in the view — a guard that exists in a view alone
        is a guard that can be bypassed by calling the method.

        Returns a summary dict for the caller to audit-log. Each row saves with
        ``update_fields``: this runs from a button and touches two columns per obligation, so
        it must not stamp a touch on rows whose figures did not move.
        """
        if self.status != "active":
            return {
                "refused": True,
                "reason": (
                    f"Revenue schedule {self.number or self.pk} is "
                    f"{self.get_status_display().lower()} — only an active schedule recognises "
                    "revenue."
                ),
                "contract_amount": self.contract_amount,
                "allocated": ZERO,
                "recognized": ZERO,
                "obligations_touched": 0,
            }

        today = as_of or timezone.localdate()
        rows = self.obligation_rows()
        contract = self.contract_amount

        # Pass 1 — allocation, clamped against the contract in Python.
        allocated_budget = contract
        for row in rows:
            share = (contract * (row.allocation_pct or ZERO) / ONE_HUNDRED).quantize(
                CENT, rounding="ROUND_HALF_UP"
            )
            if share > allocated_budget:
                share = allocated_budget if allocated_budget > ZERO else ZERO
            row.allocated_amount = share
            allocated_budget -= share

        # Pass 2 — recognition, oldest recognition date first, against a shared budget.
        ordered = sorted(rows, key=lambda r: (r.recognize_on or UNSCHEDULED, r.pk or 0))
        recognized_budget = contract
        touched = 0
        for row in ordered:
            if row.recognize_on is None or row.recognize_on > today:
                row.recognized_amount = ZERO
            else:
                want = row.allocated_amount or ZERO
                if want > recognized_budget:
                    want = recognized_budget if recognized_budget > ZERO else ZERO
                row.recognized_amount = want
                recognized_budget -= want
            row.save(update_fields=["allocated_amount", "recognized_amount"])
            touched += 1

        return {
            "refused": False,
            "contract_amount": contract,
            "allocated": self.allocated_amount,
            "recognized": self.recognized_amount,
            "deferred": self.deferred_amount,
            "obligations_touched": touched,
        }


    # ------------------------------------------------------------------ validation

    def _relation_belongs_to_tenant(self, field_name):
        """Does the FK on ``field_name`` point at a row in THIS schedule's tenant?

        The same helper shape ``OrderHold.clean()`` uses, for the same reason: a narrowed form
        queryset is a usability feature, not a security boundary, and the check must still
        hold when the row arrives from somewhere other than that form.
        """
        relation_id = getattr(self, f"{field_name}_id", None)
        if not self.tenant_id or not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id, tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        """Tenant guards, keyed so no message can 500 the form (0.20).

        ``RevenueScheduleForm.Meta.fields`` is ``[sales_order, status, method,
        compliance_standard, fiscal_period, notes]``. So:

        * ``sales_order`` and ``fiscal_period`` ARE on the form and may be keyed directly;
        * ``journal_entry`` is ``editable=False`` and off the form, and ``tenant`` / ``number``
          / the timestamps are set by the base class — a message keyed on any of them routes
          through ``add_error(None, …)``, which raises ``ValueError`` and 500s every create and
          edit. That check therefore goes on ``NON_FIELD_ERRORS``, which every form can carry.
        """
        super().clean()
        if not self.tenant_id:
            return
        if not self._relation_belongs_to_tenant("sales_order"):
            raise ValidationError(
                {"sales_order": "The sales order must belong to this workspace."}
            )
        if not self._relation_belongs_to_tenant("fiscal_period"):
            raise ValidationError(
                {"fiscal_period": "The fiscal period must belong to this workspace."}
            )
        if not self._relation_belongs_to_tenant("journal_entry"):
            raise ValidationError(
                {NON_FIELD_ERRORS: ["The journal entry must belong to this workspace."]}
            )

    def __str__(self):
        order_number = self.sales_order.number if self.sales_order_id else "—"
        return f"{self.number or 'RVS'} · {order_number} · {self.get_status_display()}"



class PerformanceObligation(models.Model):
    """One distinct promise inside the contract — the thing revenue is recognised against.

    **Tenant-less on purpose** (``models.Model``, no ``tenant`` FK, no number prefix). It is
    reachable only through ``schedule``, and the schedule's tenant IS its tenant. This is the
    convention ``scm.SalesOrderLine`` and ``OrderAmendmentLine`` already follow, and it means
    the form is never asked to narrow a tenant queryset that does not exist.

    The two money columns are ``editable=False`` and are written by
    ``RevenueSchedule.recompute()`` and nothing else — see that method for the allocation and
    recognition arithmetic, all of it in Python.
    """

    OBLIGATION_TYPE_CHOICES = [
        ("goods", "Goods"),
        ("services", "Services"),
        ("subscription", "Subscription"),
        ("milestone", "Milestone"),
        ("warranty", "Warranty"),
    ]
    RECOGNITION_METHOD_CHOICES = [
        ("point_in_time", "Point In Time"),
        ("over_time", "Over Time"),
        ("milestone", "Milestone"),
    ]

    # CASCADE: obligations have no meaning without the schedule that prices them. A schedule
    # is a working document, so deleting it takes its working papers with it.
    schedule = models.ForeignKey(RevenueSchedule, on_delete=models.CASCADE,
                                 related_name="obligations")
    # SET_NULL, not CASCADE: the order line is the TARGET of the promise, and deleting it (an
    # amendment removing that line) retires the target without rewriting what the schedule
    # promised. PROTECT on ``item`` below for the opposite reason — the item master is
    # catalogue, and a catalogue row must never be deletable out from under a revenue schedule.
    sales_order_line = models.ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name="performance_obligations")
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, null=True, blank=True,
                             related_name="performance_obligations")
    obligation_type = models.CharField(max_length=20, choices=OBLIGATION_TYPE_CHOICES,
                                       default="goods")
    description = models.CharField(max_length=255)
    allocation_pct = models.DecimalField(max_digits=6, decimal_places=2,
                                         validators=[MinValueValidator(Decimal("0.01")),
                                                    MaxValueValidator(Decimal("100"))])
    recognition_method = models.CharField(max_length=20, choices=RECOGNITION_METHOD_CHOICES,
                                          default="over_time")
    recognize_on = models.DateField(null=True, blank=True)
    # Authorable, and never overwritten: the document or tracking-event reference that proves
    # the milestone was actually met. A system that re-wrote this on each recompute would be
    # restating the evidence after the fact, which is the L22 forgeable-snapshot failure in
    # miniature.
    evidence_reference = models.CharField(max_length=255, blank=True)
    # THE ONLY TWO MONEY COLUMNS IN 8.6. Both ``editable=False``, both off every form, both
    # written exclusively by ``RevenueSchedule.recompute()``, in Python.
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0,
                                           editable=False)
    recognized_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0,
                                            editable=False)
    milestone_label = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def remaining_amount(self):
        """``allocated_amount - recognized_amount``. DERIVED, never a column.

        This is the figure ``RevenueSchedule.days_overdue`` tests: an obligation whose date has
        passed but whose remaining amount is already zero has nothing left to recognise, and
        calling it overdue would put every completed schedule permanently on the exception
        report.
        """
        return (self.allocated_amount or ZERO) - (self.recognized_amount or ZERO)

    @property
    def is_recognisable(self):
        """True when this obligation has a date in the past and money still to recognise."""
        if self.recognize_on is None or self.recognize_on > timezone.localdate():
            return False
        return self.remaining_amount > ZERO


    def clean(self):
        """Every message on ``NON_FIELD_ERRORS``, and that is not a style choice.

        ``PerformanceObligationForm.Meta.fields`` is ``[sales_order_line, item,
        obligation_type, description, allocation_pct, recognition_method, recognize_on,
        milestone_label, evidence_reference]``. It does **not** carry ``schedule`` (set by the
        parent view), nor ``allocated_amount`` / ``recognized_amount`` (``editable=False``),
        nor ``created_at`` / ``updated_at``. A ``ValidationError`` keyed on any of those routes
        through Django's ``add_error(None, …)``, which raises ``ValueError`` for a key the form
        does not have — a 500 on every create and edit, and a *data-dependent* one, so the same
        dropdown would 500 for one schedule and quietly save for another depending on invisible
        prior state. That is the 0.20 close-out finding, and it is why every message here is
        non-field.
        """
        super().clean()
        messages = []
        if self.schedule_id and self.sales_order_line_id:
            # The order line must be one of THE SCHEDULE'S ORDER's lines. This is the real
            # tenant-adjacency guard: ``SalesOrderLine`` is tenant-less, so nothing upstream
            # can filter it, and a line from another workspace's order would otherwise be a
            # way to attach this obligation to a contract it has nothing to do with.
            try:
                same_order = self.schedule.sales_order.lines.filter(
                    pk=self.sales_order_line_id
                ).exists()
            except (AttributeError, ValueError):
                same_order = False
            if not same_order:
                messages.append(
                    "That order line belongs to a different order. Only this schedule's own "
                    "order lines can be named here."
                )
        if messages:
            raise ValidationError({NON_FIELD_ERRORS: messages})

    def __str__(self):
        pct = self.allocation_pct if self.allocation_pct is not None else ZERO
        return f"{self.get_obligation_type_display()} · {self.description[:50]} · {pct}%"

