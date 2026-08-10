"""SCM 4.14 Labor Management — ``LaborSession`` [LSN-], one worked shift at a warehouse.

**What this is, and just as importantly what it is not.** A session is the *warehouse-shift
EXECUTION* record: a worker, a facility, a clock-in and a clock-out, whose minutes are then broken
into booked :class:`~apps.scm.models.LaborActivity` intervals — direct work, indirect work, lost
time. That breakdown is the whole point, and it is the thing a one-row-per-day HR attendance record
structurally cannot hold.

**It is deliberately NOT a second attendance table.** ``hrm.AttendanceRecord`` is
``unique_together ("tenant", "employee", "date")`` — strictly one row per employee per day, with
``TimeField`` punches and a derived ``hours_worked`` — and HRM keeps geofencing, biometric punches,
regularisation, overtime approval, timesheets, skills and pay. This module reads none of it and
writes none of it: **``apps/scm`` carries ZERO ``hrm.*`` references and this file must not be the
one that introduces the first.** The payroll hand-off is a report and a CSV, never a FK and never a
write into ``hrm`` — the ``FreightInvoice`` -> ``accounting.Bill`` "hand off, don't be a second
writer" posture, thinner still because there is no target row at all.

Two fields are shaped so the two systems reconcile *without* a pointer between them.
``work_date`` is deliberately the same grain as ``hrm.AttendanceRecord.date``, and ``shift_label``
mirrors ``hrm.Shift.name`` by CONVENTION. A later reconciliation report joins on
``(worker, work_date)`` and a human eye; a FK would have been an architecture decision disguised as
a convenience.

**``worker`` is ``core.Party`` and the FK is ``PROTECT``.** Party + the ``employee`` ``PartyRole``
is how SCM has named a person since 4.8 (``WorkCenter.supervisor``, ``ProductionTimeLog.operator``,
``MaintenanceWorkOrder.reported_by``), and it is the right vocabulary here because warehouse
associates routinely have no ERP login at all. ``PROTECT`` rather than ``SET_NULL`` because the
worker is the **SUBJECT** of the row: a session with no worker is not a degraded record, it is
minutes belonging to nobody — unattributable in the payroll export, uncountable on the scorecard,
and silently dropped from every per-worker aggregate. Contrast ``MeterReading.recorded_by``, which
is ``SET_NULL`` precisely because the worker there is *not* the subject: the observation outlives
the observer, and a bearing temperature is still a fact once the technician who wrote it down has
left. Here there is no equivalent fact left over.

**Every productivity figure is DERIVED and none of them is a column.** Attended, booked, direct,
indirect, gap, over-booked, earned, performance %, utilisation %, units per hour and accuracy % are
all recomputed on read — the same house rule as 4.3's ``Item.on_hand()`` over the append-only
ledger and 4.13's ``Asset.mtbf_hours()``. It is what makes "two writers for one quantity"
structurally impossible here. **Each returns ``None``, never ``0``, on a zero denominator**, and
every template must render that as an em dash: a utilisation of 0% reads as "this worker did
nothing", which is the opposite of "this shift has not been measured yet".

**The provenance block is stamped by the verb, never typed.** ``source``, ``recorded_by``,
``login``, ``closed_at``, ``approved_at`` and ``approved_by`` are all ``editable=False`` and off
every form — this is the 4.13 ``MeterReading`` fix applied at the point of design rather than after
the fact. A ``source`` a user can choose is not a provenance: it would let a member file a session
claiming to have come from a badge reader that never saw them, on a record that ends in a payroll
export.

**There is no ``exported_at`` column, and that is a decision rather than an omission.**
``approved`` IS the export lock — the payroll export reads ``approved`` sessions and nothing else,
and ``approved`` freezes the session and its activities. A separate export stamp would have to be
written by the CSV page, which is a ``GET``; making a read perform a write means a refresh, a
prefetch or a crawler silently changes state, and the second download of the same period would then
be indistinguishable from a tampered one. If "exported twice" ever needs to be answerable, the
answer is an audit-log query, not a mutable column on the record being exported.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.LaborManagement._choices import (
    DIRECT_ACTIVITIES,
    INDIRECT_ACTIVITIES,
    MAX_SESSION_MINUTES,
    MIN_PLAN_YEAR,
    SESSION_SOURCE_CHOICES,
    SESSION_STATUS_CHOICES,
    SESSION_STATUS_CSS,
)


class LaborSession(TenantNumbered):
    """One worker's shift at one facility, and the minutes it is accountable for [LSN-]."""

    NUMBER_PREFIX = "LSN"

    #: ``open`` is the only writable state. ``closed`` and ``approved`` freeze the session **and its
    #: activities** (``LaborActivity.clean()`` refuses to write into a session that is not open), so
    #: a shift that has been signed off cannot quietly grow another twenty minutes after the pay
    #: period closed. ``cancelled`` is the escape hatch for a mis-filed session and is excluded from
    #: the overlap guard below — a cancelled shift occupies no time.
    EDITABLE_STATUSES = ("open",)

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer
    #: added later is covered by the cross-tenant guard the moment it is named here — the
    #: ``TradeLicense.TENANT_SCOPED_FKS`` idiom rather than another copy of the same if-block.
    #:
    #: The three ``AUTH_USER_MODEL`` pointers below are deliberately absent: they are stamped from
    #: ``request.user`` by the verbs and are ``editable=False``, so there is no request path that
    #: can carry a crafted pk into them. Listing them would be guarding against the framework.
    TENANT_SCOPED_FKS = ("worker", "location")

    # --- whose minutes these are ------------------------------------------------------------------
    # PROTECT, not SET_NULL: see the module docstring for the MeterReading.recorded_by contrast.
    # Never hrm.EmployeeProfile — apps/scm holds zero hrm references, HRM owns daily attendance, and
    # this is the shift EXECUTION layer rather than a second attendance table.
    worker = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="scm_labor_sessions",
        help_text="The person whose shift this is — a Party holding the 'employee' role")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="labor_sessions",
        help_text="The warehouse or zone worked")

    # --- when ------------------------------------------------------------------------------------
    # Same grain as hrm.AttendanceRecord.date ON PURPOSE and with no FK between them — the two
    # reconcile on (worker, work_date) in a later report. clean() pins this to the LOCAL date of
    # clock_in so the two can never disagree.
    work_date = models.DateField(
        help_text="The shift's calendar day — an overnight shift keeps the day it STARTED on")
    shift_label = models.CharField(
        max_length=60, blank=True,
        help_text="Free text, e.g. 'Nights' or 'Early' — mirrors hrm.Shift.name by convention, "
                  "not by foreign key")
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(
        null=True, blank=True,
        help_text="Null while the shift is still running — attended minutes are unknown until it "
                  "is set, and every figure derived from them answers 'not yet', not zero")

    # --- lifecycle --------------------------------------------------------------------------------
    # editable=False (L22): the status is moved by the clock-out / close / approve / reopen / cancel
    # verbs, each of which validates the transition it is making. A status dropdown would let a
    # member jump straight to 'approved' and skip the approval it is named after.
    status = models.CharField(
        max_length=10, choices=SESSION_STATUS_CHOICES, default="open", editable=False)

    # --- provenance: stamped by whichever code path files the session, never typed (L20/L22) -------
    # The 4.13 MeterReading fix, applied up front. A provenance a user can choose is not a
    # provenance — see the module docstring.
    source = models.CharField(
        max_length=12, choices=SESSION_SOURCE_CHOICES, default="web", editable=False,
        help_text="How the punch reached the system — stamped by the verb, never a form field")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="scm_labor_sessions_recorded",
        help_text="The login that FILED the session — a supervisor when filed on someone's behalf")
    # Set by the self-service clock-in verb only, and only when the acting user's own Party IS the
    # chosen worker. Left null when a supervisor files for somebody else, which is the common case,
    # and a null here is never an error: every report, filter, aggregate and export keys on
    # `worker`. `login` is read in exactly one place — the labor board's "this assignee's currently
    # open session" panel — which falls back to User.party -> worker and then to showing nothing.
    login = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="scm_labor_sessions_started",
        help_text="The login that clocked itself in, when the worker punched in for themselves")
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="scm_labor_sessions_approved")

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-work_date", "-clock_in", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # The list page and every period aggregate range-scan this one.
            models.Index(fields=["tenant", "work_date"], name="scm_lsn_tnt_wkdate_idx"),
            # The payroll export and the scorecard group by worker within a window; the overlap
            # guard in clean() reads it on every save.
            models.Index(fields=["tenant", "worker", "work_date"], name="scm_lsn_tnt_wkr_dt_idx"),
            models.Index(fields=["tenant", "status"], name="scm_lsn_tnt_status_idx"),
            models.Index(fields=["tenant", "location"], name="scm_lsn_tnt_loc_idx"),
        ]

    def __str__(self):
        who = self.worker.name if self.worker_id else "?"
        return f"{self.number or 'LSN'} · {who} · {self.work_date}"

    # ---------------------------------------------------------------------------------------------
    # Derived figures — none of these is a column, and none of them answers 0 when it means "unknown"
    # ---------------------------------------------------------------------------------------------
    #
    # Every method below takes an optional pre-fetched ``activities`` list. The
    # ``CycleCountTask.variance_count(lines=None)`` idiom: the session detail page renders six of
    # these figures at once, and without the parameter that is six independent scans of the child
    # table for one page. A caller that has already fetched the rows passes them in; a caller that
    # has not gets one query, because the composed figures resolve the rows ONCE and hand the same
    # object down (a QuerySet caches its result set after the first evaluation).

    def _activity_rows(self, activities=None):
        """The child rows, fetched once. See the block comment above for why this exists."""
        return self.activities.all() if activities is None else activities

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """``SESSION_STATUS_CSS`` lives in ``_choices.py`` (the export and the board read it too);
        the lookup lives here so no template decides a badge colour for itself."""
        return SESSION_STATUS_CSS.get(self.status, "badge-muted")

    @property
    def attended_minutes(self):
        """Clock-out minus clock-in, in whole minutes — the minutes the shift is PAID for.

        ``None``, never ``0``, while ``clock_out`` is null. A running shift has no attended figure
        yet, and answering zero would put every session currently on the floor at 0% utilisation
        with infinite gap time — the exception queue would fill up with people who are simply still
        working.

        Floored at zero for a row that predates the ordering guard in :meth:`clean`; a negative
        attended figure would make utilisation negative and the gap arithmetic meaningless.
        """
        if not self.clock_in or not self.clock_out:
            return None
        return max(int((self.clock_out - self.clock_in).total_seconds() // 60), 0)

    def booked_minutes(self, activities=None):
        """Σ of the activity durations — the minutes the shift can ACCOUNT for.

        Deliberately independent of ``attended_minutes``: booking more than was attended is a real
        and expected condition (two people on one badge, a forgotten stop) and is *reported* by
        :meth:`over_booked_minutes` rather than refused at the door.
        """
        return sum((row.duration_minutes or 0) for row in self._activity_rows(activities))

    def direct_minutes(self, activities=None):
        """Booked minutes spent on productive work — the denominator of performance.

        Branches on ``DIRECT_ACTIVITIES`` from ``_choices``, never a hand-typed tuple, so the
        definition of productive work exists once and moves once.
        """
        return sum((row.duration_minutes or 0) for row in self._activity_rows(activities)
                   if row.activity_type in DIRECT_ACTIVITIES)

    def indirect_minutes(self, activities=None):
        """Booked minutes on breaks, meetings, training and lost time.

        Computed by branching on ``INDIRECT_ACTIVITIES`` rather than as ``booked − direct``. The two
        frozensets partition the vocabulary by construction, so today they agree — but if an
        activity value ever escaped the partition, the subtraction would silently file it as
        indirect while this form leaves ``direct + indirect < booked``, which is a visible
        discrepancy somebody can chase.
        """
        return sum((row.duration_minutes or 0) for row in self._activity_rows(activities)
                   if row.activity_type in INDIRECT_ACTIVITIES)

    def unaccounted_minutes(self, activities=None):
        """GAP TIME — attended minutes the shift cannot account for, ``max(0, attended − booked)``.

        Easy Metrics sells this as a named product ("Missing/Gap Time Insights") and it is the
        single most actionable number on the page: paid minutes with no work booked against them.

        ``None`` while the session is open — there is no attended figure to subtract from yet, and
        a shift still running has not "gone missing".
        """
        attended = self.attended_minutes
        if attended is None:
            return None
        return max(attended - self.booked_minutes(activities), 0)

    def over_booked_minutes(self, activities=None):
        """The other half of the gap, ``max(0, booked − attended)``.

        Split out rather than letting :meth:`unaccounted_minutes` go negative, so the exception
        queue can NAME the condition — "48 minutes booked beyond the shift" is a badge scan or a
        forgotten stop and has a fix; "−48 minutes of gap time" is a number nobody can act on.

        ``None`` while the session is open, for the same reason as the gap.
        """
        attended = self.attended_minutes
        if attended is None:
            return None
        return max(self.booked_minutes(activities) - attended, 0)

    def _measured(self, activities=None):
        """``(earned minutes, direct minutes)`` over ONLY the activities that carried a standard.

        Both halves of the performance ratio come from here, and that is the point: an activity
        filed against work with no ``LaborStandard`` is excluded from the numerator AND the
        denominator. Leaving its minutes in the denominator while it contributes nothing to the
        numerator is the same thing as scoring unmeasured work as zero — which would mean every new
        activity type dragged the floor's performance down until somebody wrote a standard for it.

        "Carried a standard" means the row's earned figure is present, i.e. the SNAPSHOT taken when
        the activity was filed. The ``standard`` FK itself is ``SET_NULL`` and may have gone away
        since; deleting a standard must not retroactively unmeasure last month's work.

        Returns ``(None, 0)`` when nothing was measured at all, so the caller can tell "no standard
        anywhere on this shift" apart from "measured, and earned nothing".
        """
        earned = ZERO
        minutes = 0
        measured = False
        for row in self._activity_rows(activities):
            # Restricted to direct work: an indirect row has no units and clean() forbids it a
            # quantity, so a standard attached to one could only ever pollute the ratio.
            if row.activity_type not in DIRECT_ACTIVITIES:
                continue
            # A STILL-RUNNING row is skipped, and this is the load-bearing line. clean() requires a
            # direct row to carry quantity > 0 but deliberately allows ended_at=None, so a booked
            # interval that has not finished yet is ordinary use, not a corrupt row. Its
            # earned_minutes is already known (the snapshots times the quantity so far) while its
            # duration_minutes is still 0 — so counting it would add to the NUMERATOR and nothing to
            # the DENOMINATOR. A completed 60-minute pick of 100 units plus a running pick of 40
            # renders the shift at ~130% of standard instead of ~88%: the figure climbs the moment
            # work starts and drops when it finishes, which is precisely backwards.
            # The rule, stated once: a shift's measured figures describe COMPLETED work; work in
            # flight is counted when it lands. `_unit_totals()` skips the same rows for the same
            # reason, and Reports.py's GROUP BY twin carries the same `duration_minutes__gt=0`.
            if (row.duration_minutes or 0) <= 0:
                continue
            value = row.earned_minutes
            if value is None:
                continue
            measured = True
            earned += value
            minutes += row.duration_minutes or 0
        return (q4(earned), minutes) if measured else (None, 0)

    def earned_minutes(self, activities=None):
        """Σ of the standard minutes the booked work SHOULD have taken.

        ``None``, never ``0``, when no activity on the shift carried a standard — an unmeasured
        shift has not earned zero minutes, it has not been measured. See :meth:`_measured`.
        """
        return self._measured(activities)[0]

    def performance_pct(self, activities=None):
        """Earned minutes over MEASURED DIRECT minutes, as a percentage — the headline LMS figure.

        100% is working exactly to standard; above is faster, below is slower. The denominator is
        direct minutes restricted to the activities that carried a standard, for the reason spelled
        out in :meth:`_measured`.

        ``None`` when nothing was measured or the measured rows booked no minutes at all.
        """
        earned, minutes = self._measured(activities)
        if earned is None or minutes <= 0:
            return None
        return q2(earned / Decimal(minutes) * Decimal("100"))

    def utilisation_pct(self, activities=None):
        """Booked minutes over attended minutes — how much of a paid shift is accounted for.

        Not a productivity figure: a shift spent entirely in sanctioned meetings is 100% utilised
        and 0% direct. It answers "is the time explained", and its complement is the gap.

        ``None`` while the session is open, and ``None`` on a zero-length shift.
        """
        attended = self.attended_minutes
        if not attended:
            return None
        return q2(Decimal(self.booked_minutes(activities)) / Decimal(attended) * Decimal("100"))

    def _unit_totals(self, activities=None):
        """``(units, errors)`` over COMPLETED direct activities — the shift's recorded quantities.

        Still-running rows are skipped for the same reason :meth:`_measured` skips them: their
        units are known while their minutes are still 0, so including them would inflate
        :meth:`units_per_hour`, whose denominator is direct MINUTES. One rule across every measured
        figure on the shift — completed work is counted, work in flight is counted when it lands —
        which also keeps :meth:`accuracy_pct` describing the same set of rows as the rate figures
        rather than a quietly larger one.
        """
        units = ZERO
        errors = ZERO
        for row in self._activity_rows(activities):
            if row.activity_type not in DIRECT_ACTIVITIES:
                continue
            if (row.duration_minutes or 0) <= 0:
                continue
            units += row.quantity or ZERO
            errors += row.error_quantity or ZERO
        return units, errors

    def units_per_hour(self, activities=None):
        """Units completed per DIRECT hour worked.

        Direct minutes, not attended minutes, and deliberately the same denominator as
        :meth:`performance_pct` — the two then answer the same question in two units and cannot
        disagree about what they are dividing by. Dividing by attended hours would fold the
        staffing question (how much of the shift was productive) into the rate question; that
        question is :meth:`utilisation_pct` and it already has an answer.

        ``None`` when no direct minutes were booked.
        """
        minutes = self.direct_minutes(activities)
        if minutes <= 0:
            return None
        units, _errors = self._unit_totals(activities)
        return q2(units * Decimal("60") / Decimal(minutes))

    def accuracy_pct(self, activities=None):
        """``(units − errors) ÷ units × 100`` — the quality half of the scorecard.

        ``error_quantity`` is the one recorded number; accuracy is derived from it, so a shift's
        quality figure can never be typed to something the error count does not support.

        ``None`` when no units were completed. A shift of pure indirect time has no accuracy, and
        rendering 0% would put a worker who spent the day in training at the bottom of a quality
        ranking.
        """
        units, errors = self._unit_totals(activities)
        if units <= ZERO:
            return None
        return q2((units - errors) / units * Decimal("100"))

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The clock contract, the no-double-counting guard, and the cross-tenant guard.

        Everything here protects a number that ends up in a payroll export, which is why these are
        refusals rather than badges: a session that overlaps another one does not merely look odd on
        a report, it bills the same hour twice.
        """
        super().clean()

        # THE GUARD, first — every rule below reads through these pointers. The form's querysets are
        # tenant-scoped, but that is UX; a narrowed dropdown has never held against a crafted POST
        # (L39 §2). Skipped when the instance has no tenant yet: an unsaved model has tenant_id None
        # and ``self.tenant`` would raise RelatedObjectDoesNotExist on a non-nullable FK rather than
        # return None.
        if self.tenant_id is not None:
            for name in self.TENANT_SCOPED_FKS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a
                # pointer whose row went away degrades to None here instead of 500-ing inside
                # validation.
                related = getattr(self, name, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another workspace."})

        # (a) Order. A shift that ended before it started derives negative attended minutes, and
        #     every ratio built on them inverts.
        if self.clock_in and self.clock_out and self.clock_out <= self.clock_in:
            raise ValidationError({"clock_out": "Clock-out must be after clock-in."})

        # (b) LENGTH, not just order — the ProductionTimeLog.MAX_LOG_MINUTES reasoning. Attended
        #     minutes are derived rather than typed, so they never see form validation, and they
        #     feed utilisation, cost per unit, required headcount and the payroll export. A
        #     1000-01-01 -> 9999-12-31 clock pair derives ~4.7e9 minutes, past what the arithmetic
        #     downstream holds — a 500 rather than a rejection. A warehouse shift is at most a day;
        #     the bound allows two, which covers an overnight shift closed out late the next
        #     morning. Comparators in the message are ASCII deliberately: these strings are printed
        #     by management commands on a cp1252 Windows console.
        if self.clock_in and self.clock_out:
            minutes = (self.clock_out - self.clock_in).total_seconds() // 60
            if minutes > MAX_SESSION_MINUTES:
                raise ValidationError({
                    "clock_out": f"A single session cannot run longer than "
                                 f"{MAX_SESSION_MINUTES // (60 * 24)} days — clock out and start a "
                                 f"new session per shift."})

        # (c) The work date IS the local date the shift started on. An overnight shift keeps its
        #     START date (that is the grain hrm.AttendanceRecord uses and the grain a supervisor
        #     rosters by), and letting the two float apart is how a session dated last March ends up
        #     holding this week's clock times — poisoning every period aggregate, every scorecard
        #     window and the payroll export, all of which filter on work_date and none of which
        #     re-read the clock. localtime() is only meaningful on an aware value; a naive one is
        #     read as-is rather than crashing validation.
        if self.clock_in and self.work_date:
            started = (timezone.localtime(self.clock_in) if timezone.is_aware(self.clock_in)
                       else self.clock_in)
            if self.work_date != started.date():
                raise ValidationError({
                    "work_date": f"The work date must be the day the shift STARTED "
                                 f"({started.date()}) — an overnight shift keeps its start date."})

        # (d) Floor on the date, guarding the window arithmetic every report does against it: a
        #     work_date in year 1 minus a history window underflows datetime.date, which is an
        #     OverflowError (a 500), not a validation error. DemandForecast.MIN_HORIZON_YEAR exists
        #     for the same reason.
        if self.work_date and self.work_date.year < MIN_PLAN_YEAR:
            raise ValidationError({"work_date": f"The work date must be in {MIN_PLAN_YEAR} or later."})

        if self.tenant_id is not None and self.worker_id is not None:
            # (e) One open session per worker. Two open sessions have no defined clock-out target,
            #     so the clock-out verb would have to guess which one it is closing, and until then
            #     both sit on the board claiming the same person is on shift twice.
            if self.status == "open":
                clash = (LaborSession.objects
                         .filter(tenant_id=self.tenant_id, worker_id=self.worker_id, status="open")
                         .exclude(pk=self.pk))
                if clash.exists():
                    raise ValidationError({
                        "worker": "That worker already has an open session — clock the current one "
                                  "out before starting another."})

            # (f) No two sessions may occupy the same instant for one worker. Double-counted minutes
            #     are double-counted payroll hours, and nothing downstream can detect it: the export
            #     sums per worker per period and would simply report a longer day. Cancelled
            #     sessions are excluded from BOTH sides because a cancelled shift occupies no time —
            #     excluding them only from the query would make cancelling a mis-filed overlapping
            #     session impossible, which is exactly the row this rule most wants withdrawn.
            #
            #     Half-open intervals, so a shift ending at 14:00 and one starting at 14:00 do NOT
            #     overlap — that is a legitimate shift handover, not a clash. An open session
            #     (clock_out null) runs to infinity, so it clashes with anything that ends after it
            #     began; and while THIS session is open it has no end, which is why the second
            #     filter is applied only when clock_out is set.
            if self.clock_in and self.status != "cancelled":
                overlap = (LaborSession.objects
                           .filter(tenant_id=self.tenant_id, worker_id=self.worker_id)
                           .exclude(pk=self.pk)
                           .exclude(status="cancelled")
                           .filter(Q(clock_out__isnull=True) | Q(clock_out__gt=self.clock_in)))
                if self.clock_out:
                    overlap = overlap.filter(clock_in__lt=self.clock_out)
                other = overlap.first()
                if other is not None:
                    raise ValidationError({
                        "clock_in": f"That worker already has a session covering this time "
                                    f"({other.number or 'LSN'}) — overlapping sessions would count "
                                    f"the same minutes twice."})

        # (g) The worker must actually be an employee of this workspace. Party is the spine's
        #     one-table-for-every-person model, so without this a session could be filed against a
        #     customer or a haulier — the same posture as the seeder's refusal to invent an
        #     inspector, because a worker nobody hired is a person whose hours nobody owes.
        #     Reached through the reverse accessor so this file imports no sibling app.
        worker = getattr(self, "worker", None) if self.worker_id is not None else None
        if worker is not None and not worker.roles.filter(role="employee").exists():
            raise ValidationError({
                "worker": f"{worker} does not hold the 'employee' role — add it on the party "
                          f"record before booking a shift against them."})
