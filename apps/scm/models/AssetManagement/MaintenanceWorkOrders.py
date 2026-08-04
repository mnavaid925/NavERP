"""SCM 4.13 Asset Management — ``MaintenanceWorkOrder`` [MWO-] + its parts and task children.

Realizes the *Breakdown Maintenance* bullet, and is also the execution record every preventive job
lands on: a ``MaintenancePlan`` does not do work, it generates one of these.

**This is NOT ``scm.WorkOrder`` [WO-], and the two must never be merged.** 4.8's work order is a
PRODUCTION RUN: it carries ``item``, ``bom``, ``quantity_planned``, ``quantity_produced``,
``component_location`` / ``output_location`` (``Manufacturing/WorkOrders.py:59-100``), none of which
a repair has. The tempting move — one ``WorkOrder`` table with a ``work_type`` discriminator — breaks
three shipped features at once:

* **MRP netting** reads open work orders as supply for their ``item``. A repair has no output item,
  so every maintenance job would either need a fake one or would have to be filtered out of a query
  that currently does not filter at all.
* **The load board** schedules ``WorkOrder`` rows against work-centre capacity by
  ``planned_start`` / ``planned_end``; repairs booked there would consume production capacity that
  is in fact already unavailable *because* the machine is down — double counting the same outage.
* **OEE** divides good output by planned production time. Rows with no output quantity would drive
  the numerator to zero on the very shifts maintenance was working.

So: separate document, separate prefix (``MWO-`` vs ``WO-``), separate url prefix
(``maintenance-work-orders/`` vs ``work-orders/``), separate templates. The one place they touch is
``Asset.work_center`` — taking a machine down is a fact 4.8's board wants to *read*, not a row it
should own.

**Equally deliberate: this is ONE table covering requests, PM jobs and breakdowns.** A maintenance
*request* is ``status="requested"`` plus ``reported_by``; a manager approving it is a status verb,
not a conversion between two tables. SAP splits notification from order and Maximo splits service
request from work order, but both then spend enormous effort keeping the pair joined. The same call
4.9 made for audit findings vs NCRs (``navigation.py:859-868``) applies here with more force: MTTR,
mean time between failures, downtime totals and PM compliance are all "group the jobs on this asset
by what happened", and a split forks every one of those queries into a UNION over two grains.

**``status`` is verb-driven and is not on the form.** ``editable=False``, the 4.8
``WorkOrder.status`` posture (L22). It is excluded from ``Meta.fields`` in the form layer, so a
crafted ``status=completed`` in a POST body cannot land — not because a view checks for it, but
because there is no path from form data to the column at all. ``started_at`` / ``completed_at`` are
system stamps for the same reason. ``downtime_start`` / ``downtime_end`` are the exception and ARE
editable: a technician recording the outage window afterwards is the normal case, and forcing that
through a verb would mean the window could never be corrected.

**Downtime minutes are DERIVED, never typed.** :meth:`MaintenanceWorkOrder.save` computes them from
the pair and clamps the result — the ``ProductionTimeLog.duration_minutes`` precedent
(``Manufacturing/ProductionTimeLogs.py:102-115``). The clamp is not decoration: two
``DateTimeField`` values can be 9999 years apart, which derives ~5.3e9 minutes and does not fit a
``PositiveIntegerField`` — an uncaught ``OverflowError``, i.e. a 500, from a field no validator ever
sees because it is ``editable=False``.

**Tasks are a SNAPSHOT of the plan's checklist, with deliberately no FK back to it.** Same rule 4.9
applies to ``QualityInspection`` / ``InspectionResult`` and 4.8 applies to ``WorkOrderComponent``:
editing a plan next month must not rewrite what a job three weeks ago actually asked the technician
to check and sign off. A ``plan_task`` FK would make the record of completed work mutable by someone
who never touched it.

**What this module does NOT do.**

* It posts **no ``JournalEntry``** — the standing 4.9/4.10/4.11/4.12 rule (L29). The only ledger
  effect in 4.13 is the issue-parts verb writing a negative ``StockMove`` of the new ``maintenance``
  move type; a GL hand-off, if ever wanted, follows the 4.6 freight pattern of drafting an
  ``accounting.Bill``, which is why ``external_cost`` is a plain column here and not a posted charge.
* It adds **no RCA table**. ``non_conformance`` is a nullable link OUT to 4.9's existing engine, and
  4.13 does not touch ``NonConformance.source`` to add a reciprocal choice — refactoring a shipped
  sub-module for a convenience link is exactly what 4.11 declined to do.
* It stores **no meter value of its own**. ``meter_reading_at_work`` is a capture field: the
  **complete** verb turns it into a ``MeterReading`` row (``source="work_order"``,
  ``reference=<MWO number>``) and the reading history remains the single place a meter is read from.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.AssetManagement._choices import (
    CAUSE_CODE_CHOICES,
    MAX_LABOUR_RATE,
    PRIORITY_CHOICES,
    PRIORITY_CSS,
    PROBLEM_CODE_CHOICES,
    REMEDY_CODE_CHOICES,
    WORK_TYPE_CHOICES,
    WORK_TYPE_CSS,
)


class MaintenanceWorkOrder(TenantNumbered):
    """One maintenance job — requested, planned or reactive — against one asset [MWO-]."""

    NUMBER_PREFIX = "MWO"

    #: Where the job came from. ``plan`` is stamped by the generate action; ``request`` is the
    #: default because a human typing this form is, by definition, raising a request. ``condition``
    #: and ``inspection`` are the seams 11.7 (condition monitoring) and 4.9 (inspection findings)
    #: write through — declared now so those arrive as a new *value*, not a column widen.
    SOURCE_CHOICES = [
        ("plan", "Preventive plan"),
        ("request", "Maintenance request"),
        ("condition", "Condition trigger"),
        ("inspection", "Inspection finding"),
    ]

    #: ``requested`` is the intake state — see the module docstring for why there is no second
    #: request table. ``completed`` means the work is done; ``closed`` means it has been reviewed and
    #: costed and is now history. Keeping them apart is what lets a supervisor find "finished but not
    #: yet signed off" without a second flag.
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    #: The job is still live: it counts against the asset's open-job chip, it blocks a duplicate
    #: generate from the same plan, and its parts may still be issued. Declared ONCE here because
    #: three readers outside this file depend on it — ``Asset.open_job_count()``, the plan's generate
    #: refusal, and the work-order list filter. Three hand-written tuples would eventually disagree.
    OPEN_STATUSES = ("requested", "approved", "scheduled", "in_progress", "on_hold")
    #: Terminal states. Nothing may be issued, ticked or re-stamped once a job is here.
    CLOSED_STATUSES = ("completed", "closed", "cancelled")

    #: Colour per status, decided in one place (the ``TradeLicense.STATUS_CSS`` precedent). Only the
    #: six classes that exist in ``static/css/theme.css`` appear — there is no ``badge-success`` /
    #: ``badge-warning`` / ``badge-danger`` (L33). Red is spent on the ONE state that means work has
    #: stopped and a human must intervene; ``cancelled`` and ``closed`` are muted because neither is
    #: a problem, they are simply over.
    STATUS_CSS = {
        "requested": "badge-slate",
        "approved": "badge-info",
        "scheduled": "badge-info",
        "in_progress": "badge-amber",
        "on_hold": "badge-red",
        "completed": "badge-green",
        "closed": "badge-muted",
        "cancelled": "badge-muted",
    }

    #: Longest downtime window a single job may record, in minutes — one year. See
    #: :meth:`save` for why a ceiling exists at all rather than trusting the two datetimes.
    MAX_DOWNTIME_MINUTES = 60 * 24 * 365

    #: FKs :meth:`clean` tenant-checks. Table-driven so adding a pointer to another workspace-scoped
    #: model means adding it here, not remembering to copy a sixth if-block (the
    #: ``TradeLicense.TENANT_SCOPED_FKS`` precedent).
    TENANT_SCOPED_FKS = ("asset", "plan", "parts_location", "non_conformance")

    # --- what and how urgent ---------------------------------------------------------------------
    title = models.CharField(max_length=255)
    work_type = models.CharField(max_length=12, choices=WORK_TYPE_CHOICES, default="corrective")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="request")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="requested",
                              editable=False)
    description = models.TextField(blank=True, help_text="What was observed, or what the job covers")
    resolution_notes = models.TextField(blank=True, help_text="What was actually done")

    # --- who and what ------------------------------------------------------------------------------
    asset = models.ForeignKey("scm.Asset", on_delete=models.PROTECT, related_name="work_orders")
    # SET_NULL, not CASCADE: a retired PM schedule must never take the history of the jobs it
    # produced with it. The job keeps its snapshotted tasks and its costs either way — the link is a
    # provenance note, not a dependency.
    plan = models.ForeignKey("scm.MaintenancePlan", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="work_orders",
                             help_text="The preventive plan this job was generated from")
    reported_by = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_reported_maintenance_orders",
                                    help_text="Who raised the fault — this plus status='requested' "
                                              "IS the maintenance request")
    assigned_to = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="scm_assigned_maintenance_orders")
    service_vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="scm_vendor_maintenance_orders",
                                       help_text="External contractor, when the work is outsourced")
    parts_location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="maintenance_work_orders",
                                       help_text="Storeroom the parts are drawn from")
    # A link OUT to 4.9, one way. 4.13 owns no root-cause table and does not add a reciprocal choice
    # to NonConformance.source — see the module docstring.
    non_conformance = models.ForeignKey("scm.NonConformance", on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="maintenance_work_orders",
                                        help_text="The quality non-conformance this failure fed")

    # --- dates: two editable, two stamped ----------------------------------------------------------
    # Editable on purpose — an operator logs a fault that happened on the night shift.
    reported_at = models.DateTimeField(default=timezone.now)
    scheduled_start = models.DateTimeField(
        null=True, blank=True,
        help_text="When the job is committed to happen. For a generated PM job this is the plan's "
                  "due date at generate time, and it is what is_on_time measures against")
    # System stamps (L22): written by the start / complete verbs, never by a form.
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    # --- the outage --------------------------------------------------------------------------------
    # These two ARE editable while the stamps above are not: the window is frequently discovered
    # after the fact ("it actually went down at 02:10") and a verb-only field could never be
    # corrected. Correctness is protected by clean() ordering the pair and save() deriving the total.
    downtime_start = models.DateTimeField(null=True, blank=True)
    downtime_end = models.DateTimeField(null=True, blank=True)
    downtime_minutes = models.PositiveIntegerField(default=0, editable=False)
    is_unplanned_downtime = models.BooleanField(
        default=False,
        help_text="Unplanned outage — the figure availability and MTBF are actually about")

    # --- Maximo's failure hierarchy, bottom three levels -------------------------------------------
    # A CLOSED vocabulary is the entire reason "which cause costs us the most downtime?" is a GROUP
    # BY rather than a text-mining project. max_length=24 against current longest values of 17 / 19 /
    # 16 is deliberate headroom: a new failure code should be a choices edit, not a column widen.
    problem_code = models.CharField(max_length=24, choices=PROBLEM_CODE_CHOICES, blank=True,
                                    help_text="The symptom observed")
    cause_code = models.CharField(max_length=24, choices=CAUSE_CODE_CHOICES, blank=True,
                                  help_text="Why it happened")
    remedy_code = models.CharField(max_length=24, choices=REMEDY_CODE_CHOICES, blank=True,
                                   help_text="What was done about it")

    # --- cost inputs -------------------------------------------------------------------------------
    labour_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("9999.99"))])
    # Capped, for the reason WorkCenters.py:60-67 spells out: q4() CLAMPS rather than raising, and
    # editing a work order is only @login_required, so an absurd rate does not stay local — it flows
    # into total_cost(), the asset's maintenance-cost-to-date and the repair-vs-replace ratio on the
    # depreciation report. The ceiling belongs on the way in, not on the way out.
    labour_rate = models.DecimalField(
        max_digits=14, decimal_places=4, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_LABOUR_RATE)],
        help_text="Charge-out rate per labour hour")
    external_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q2)],
        help_text="The contractor's charge. Recorded here only — 4.13 drafts no accounting document")

    # Optional capture. The complete verb turns a value here into a MeterReading row; this column is
    # the form field, the reading log is the record. Nothing reads a meter from here.
    meter_reading_at_work = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)],
        help_text="Meter value at the moment of work — filed as a reading when the job completes")

    class Meta:
        ordering = ["-reported_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_mwo_tnt_status_idx"),
            # The asset detail page's job history, and every MTTR/MTBF roll-up.
            #
            # ``-reported_at`` is the third column and it is not decoration: Meta.ordering above is
            # ``["-reported_at", "-id"]``, so a two-column ``(tenant, asset)`` index could find the
            # asset's jobs and then had to FILESORT every one of them to answer "newest 25 first".
            # Measured on nav_erp by migrating 0023 back and forth over the SAME query and data:
            # two columns gave ``key: scm_mwo_tnt_asset_idx, key_len 16, Using where; Using
            # filesort``; three gave the same key with the filesort GONE.
            #
            # Declared DESCENDING to state the intent, though this database does not yet store it
            # that way — MariaDB gained descending indexes in 10.8 and XAMPP ships 10.4, where SHOW
            # CREATE TABLE reports a plain ascending ``(tenant_id, asset_id, reported_at)``. The
            # ordering is served anyway, by a BACKWARD index scan: with the first two columns pinned
            # to constants the third is already in order, and every ORDER BY term points the same
            # way, so reading the index in reverse IS the answer. The declaration costs nothing here
            # and starts paying the moment the server is newer.
            #
            # Still a valid prefix for the index's other users: anything filtering ``tenant`` alone
            # or ``(tenant, asset)`` reads it exactly as before, because a B-tree's leading prefix is
            # usable on its own. Widening it therefore cost nothing that was already working.
            models.Index(fields=["tenant", "asset", "-reported_at"], name="scm_mwo_tnt_asset_idx"),
            models.Index(fields=["tenant", "work_type"], name="scm_mwo_tnt_type_idx"),
            # Matches the default ordering, so the list page's first screen is an index scan.
            models.Index(fields=["tenant", "reported_at"], name="scm_mwo_tnt_rep_idx"),
            models.Index(fields=["tenant", "priority"], name="scm_mwo_tnt_prio_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'MWO'} · {self.title}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """Cross-tenant FK guard, the plan/asset agreement, and the downtime window ordering.

        ``status``, ``started_at``, ``completed_at`` and ``downtime_minutes`` are deliberately NOT
        validated here: none of them is on the form, and a rule guarding a column only the verbs and
        :meth:`save` write would be enforcing an invariant against code that already derives it.
        """
        super().clean()

        # THE GUARD. The form's querysets are tenant-scoped, but that is UX — a narrowed dropdown has
        # never held against a crafted POST (L39 §2). Skipped while the instance has no tenant: an
        # unsaved model has tenant_id None, and ``self.asset`` on a non-nullable FK would raise
        # RelatedObjectDoesNotExist rather than return None.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing in validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # The plan must be a plan for THIS asset — the WorkOrder.bom/item precedent
        # (WorkOrders.py:134-136). The create form offers every plan in the tenant because the asset
        # is not known until the form binds, so without this a mis-picked plan would file a job
        # against one machine under another machine's PM schedule, and both assets' compliance
        # percentages would be wrong in opposite directions.
        if self.plan_id and self.asset_id and self.plan.asset_id != self.asset_id:
            raise ValidationError({"plan": f"{self.plan.number} maintains {self.plan.asset}, not "
                                           f"{self.asset} — pick a plan for this asset."})

        if self.downtime_start and self.downtime_end and self.downtime_end < self.downtime_start:
            raise ValidationError({"downtime_end": "Downtime cannot end before it started."})

    def save(self, *args, **kwargs):
        """Derive ``downtime_minutes`` from the window — the field's only writer.

        ``minutes = (downtime_end - downtime_start) // 60``, clamped to
        :attr:`MAX_DOWNTIME_MINUTES` and floored at 0.

        The clamp is load-bearing, not tidiness. ``downtime_minutes`` is ``editable=False`` so it
        never sees form validation, and two ``DateTimeField`` values can legally be 9999 years apart
        — ~5.3e9 minutes, past what a ``PositiveIntegerField`` holds. That is an uncaught
        ``OverflowError`` (a 500) rather than a rejection, and it would arrive from an ordinary edit
        with a mistyped year. The same reasoning as ``ProductionTimeLog.save``
        (``ProductionTimeLogs.py:102-115``); the difference is that a repair outage is legitimately
        longer than a booked shift, so the ceiling is a year rather than 31 days.
        """
        if self.downtime_start and self.downtime_end and self.downtime_end > self.downtime_start:
            minutes = int((self.downtime_end - self.downtime_start).total_seconds() // 60)
            self.downtime_minutes = min(max(minutes, 0), self.MAX_DOWNTIME_MINUTES)
        else:
            self.downtime_minutes = 0
        # A caller passing update_fields=["downtime_end"] would otherwise persist the new window and
        # leave the stale total behind — the derived field must ride along with its inputs.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(dict.fromkeys(
                list(update_fields) + ["downtime_minutes"]))
        return super().save(*args, **kwargs)

    # ---------------------------------------------------------------------------------------------
    # State
    # ---------------------------------------------------------------------------------------------
    @property
    def is_open(self):
        """Still live — the asset counts it, and its parts may still be issued."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_editable(self):
        """A terminal job is history. Editing one would silently restate a cost already reported."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_down_now(self):
        """The outage is open: downtime started and never ended. Feeds the asset's "down" chip."""
        return bool(self.downtime_start) and self.downtime_end is None

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored. Each recomputes on read, and each answers None rather than
    # a confident zero where the question genuinely has no answer (the 4.11 lesson: a zero in a tile
    # reads as a measurement, a blank makes someone go and look).
    # ---------------------------------------------------------------------------------------------
    @property
    def parts_cost(self):
        """``sum(part.quantity × part.unit_cost)`` over the ISSUED lines, to 2dp.

        Unissued lines contribute nothing and that is arithmetic, not a filter: ``unit_cost`` is
        stamped at issue time and is still zero on a line that has only been planned. The explicit
        ``is_issued`` test is kept anyway so the intent survives someone later defaulting the cost.

        Iterates ``self.parts.all()`` rather than firing a ``Sum`` aggregate: the detail page has
        already prefetched the lines to render the parts table, and Django templates evaluate a
        property once per reference — an aggregate would issue a fresh query each time it is printed,
        while this reuses the cache the page already paid for.
        """
        total = ZERO
        for part in self.parts.all():
            if part.is_issued:
                total += (part.quantity or ZERO) * (part.unit_cost or ZERO)
        return q2(total)

    @property
    def labour_cost(self):
        """``labour_hours × labour_rate``, to 2dp. The rate is capped on the way in — see the field."""
        return q2((self.labour_hours or ZERO) * (self.labour_rate or ZERO))

    @property
    def total_cost(self):
        """``parts_cost + labour_cost + external_cost`` — what this job cost, all in.

        The three components are stored (or derived from stored) inputs; the total never is. A stored
        total would be a second copy of the same fact that could disagree with the first the moment a
        part is issued, and there is no event that reliably re-stamps it.
        """
        return q2(self.parts_cost + self.labour_cost + (self.external_cost or ZERO))

    @property
    def duration_hours(self):
        """``(completed_at - started_at)`` in hours, to 2dp. ``None`` while the job is unfinished.

        Deliberately NOT zero for a job in progress: zero is a completed job that took no time, and
        an in-flight repair averaged in as zero would flatter every MTTR figure that reads this.
        """
        if not self.started_at or not self.completed_at or self.completed_at <= self.started_at:
            return None
        return q2(Decimal((self.completed_at - self.started_at).total_seconds()) / Decimal("3600"))

    @property
    def is_on_time(self):
        """Was the job finished by the date it was committed to? ``None`` when unanswerable.

        ``completed_at.date() <= scheduled_start.date()``, compared in the workspace's local day
        because PM compliance is a question about days, not seconds — finishing at 16:00 on the due
        day is on time even if the job was scheduled to start at 09:00.

        The comparison is made against ``scheduled_start`` and explicitly NOT against
        ``self.plan.next_due_on``, even though the plan is where the due date came from: the generate
        action ADVANCES ``next_due_on`` to the next cycle inside the same transaction that creates
        this job. Reading it back afterwards would measure every generated job against a date that
        has not arrived yet and report 100% PM compliance forever. The due date is snapshotted onto
        the job at generate time for exactly the same reason the tasks are.

        ``None`` — never ``False`` — for an unfinished or never-scheduled job: the caller computing
        a compliance percentage must be able to leave an unanswered question out of the denominator
        rather than count it as a miss.
        """
        if not self.completed_at or not self.scheduled_start:
            return None
        return timezone.localtime(self.completed_at).date() <= \
            timezone.localtime(self.scheduled_start).date()

    @property
    def open_task_count(self):
        """Checklist steps not yet ticked. Counted from the prefetched rows — see :attr:`parts_cost`."""
        return sum(1 for task in self.tasks.all() if not task.is_done)

    # --- badge classes: one lookup each, so no template invents a colour -------------------------
    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def priority_css(self):
        return PRIORITY_CSS.get(self.priority, "badge-muted")

    @property
    def work_type_css(self):
        return WORK_TYPE_CSS.get(self.work_type, "badge-muted")


class MaintenanceWorkOrderPart(models.Model):
    """One spare consumed by a job. Tenant-less child — reached through ``work_order__tenant``.

    The ``ComplianceCheck`` / ``TradeDocumentLine`` precedent: a line has no independent existence
    and no independent permission, so it carries no ``tenant`` column and **every view that touches
    one must scope on ``work_order__tenant``, never on the child alone** — a child filtered by pk
    only is a cross-tenant read with no query that would reveal it.

    A line is *planned* when it is added and *issued* when the issue verb posts the negative
    ``maintenance`` StockMove. Those are separate facts (MaintainX tracks "where every part stands
    from assigned to issued"), which is why the flag exists rather than the row's mere presence
    meaning consumption.
    """

    work_order = models.ForeignKey("scm.MaintenanceWorkOrder", on_delete=models.CASCADE,
                                   related_name="parts")
    # 4.3's ONE item master. There is no SparePart table — a bearing is an Item that happens to be
    # fitted to a machine, and a second master would fork valuation, reordering and on-hand.
    item = models.ForeignKey("scm.Item", on_delete=models.PROTECT, related_name="maintenance_parts")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="maintenance_parts")
    quantity = models.DecimalField(max_digits=14, decimal_places=4,
                                   validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_Q4)])
    # Stamped from item.average_cost AT ISSUE TIME by the issue verb, and never afterwards. The job's
    # cost has to be what the stock actually cost when it was drawn, not what the same part costs
    # today: average_cost moves with every receipt, so reading it live would quietly restate the cost
    # of a repair closed last quarter every time a new delivery landed. editable=False because the
    # only correct value is the one the ledger move was posted at.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    is_issued = models.BooleanField(default=False, editable=False)
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["work_order"], name="scm_mwop_wo_idx")]

    def __str__(self):
        return f"{self.item} × {self.quantity}"

    @property
    def line_cost(self):
        """``quantity × unit_cost``, to 2dp — zero until the line is issued and the cost is stamped."""
        return q2((self.quantity or ZERO) * (self.unit_cost or ZERO))


class MaintenanceWorkOrderTask(models.Model):
    """One checklist step on a job — a SNAPSHOT of a ``MaintenancePlanTask``. Tenant-less child.

    **There is deliberately no FK back to the plan task.** The first five columns are plain copies
    taken by the generate action, and once copied they are this job's own record. The 4.9
    ``InspectionResult`` precedent: editing a plan must never rewrite what a completed job asked a
    technician to check and what they signed off against it. A reference would make a finished
    record mutable by someone editing an unrelated schedule months later — and the reason to keep
    the record at all is that it is evidence.

    An ad-hoc corrective job simply has no tasks, which is why the columns carry the plan's defaults
    rather than being nullable: a step typed straight onto a breakdown job is as valid as a copied
    one.
    """

    work_order = models.ForeignKey("scm.MaintenanceWorkOrder", on_delete=models.CASCADE,
                                   related_name="tasks")
    # --- copied from the plan task ---------------------------------------------------------------
    sequence = models.PositiveIntegerField(default=10, validators=[MaxValueValidator(9999)])
    description = models.CharField(max_length=255)
    expected_result = models.CharField(max_length=255, blank=True,
                                       help_text="What a pass looks like — the tolerance or reading")
    is_mandatory = models.BooleanField(default=True)
    # Maximo embeds safety plans / permits / LOTO in its job plans. Until 11.11 exists those ride as
    # flagged steps rather than as a permit table nothing else can use.
    is_safety_step = models.BooleanField(default=False)

    # --- what actually happened -------------------------------------------------------------------
    is_done = models.BooleanField(default=False)
    actual_result = models.CharField(max_length=255, blank=True)
    # Stamped by the tick route, never typed (L22) — the tick is the event, so the time of the tick
    # is not something a user should be able to disagree with.
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [models.Index(fields=["work_order", "sequence"], name="scm_mwot_wo_seq_idx")]

    def __str__(self):
        return f"{self.sequence}. {self.description}"
