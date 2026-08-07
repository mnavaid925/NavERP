"""SCM 4.14 Labor Management — ``LaborPlan`` [LPL-] + ``LaborPlanLine``, the planned workload.

**What this is.** SAP EWM calls it the *planned workload document*, Made4net promises verbatim to
"forecast labor needs based on inbound/outbound volume", Blue Yonder and CognitOps sell the
rebalancing that hangs off it. One row per staffing question — *this warehouse, these dates, this
grain* — and one child row per (bucket x activity) carrying the volume the site expects, the minutes
that volume costs at standard, the headcount that implies, and the headcount the planner actually
intends to roster. The gap between the last two is the whole product.

**It is an ARTEFACT, not a screen.** ``draft -> planned -> approved -> archived``, generated once and
reviewed by a human, exactly the ``DemandForecast`` generate-then-review shape. That matters because
the volumes it was built from keep moving: a plan computed live would silently re-answer last week's
staffing question with this week's data, and nobody could ever say what the roster was decided on.
The lines are persisted; the *history* they were derived from never is (4.7's rule) — a regenerate
re-reads ``StockMove`` / ``PickTask`` / ``GoodsReceipt`` or an ``scm.DemandForecast`` at that moment
rather than trusting a stale copy.

**4.14 CONSUMES 4.7's forecast, it does not re-derive seasonality.** ``volume_source =
"demand_forecast"`` points at an existing ``scm.DemandForecast``, whose statistical machinery,
seasonality profiles and consensus adjustments already exist and are somebody else's job to be right
about. A second smoothing implementation here would be two answers to one question.

**There is deliberately NO activity-selector column.** The generator emits one line per
(bucket x every in-scope active ``LaborStandard`` whose activity is DIRECT), so the set of activities
a plan covers is a *consequence of the standards library* rather than a sixth table, a
comma-separated string, or a many-to-many nobody maintains. Three things fall out of that: an
activity the site has no standard for cannot be planned (correct — there is no minutes figure to
plan with), adding a standard automatically widens the next regenerate, and the ``MAX_PLAN_LINES``
guard is a single ``COUNT(*)`` against the standards library instead of a grid that has to be built
before it can be measured.

**Every day-count column is capped**, ``history_days`` above all: it is fed straight to
``timedelta(days=…)`` and a bare ``PositiveIntegerField`` accepts 4294967295 on MariaDB, which is an
uncaught ``OverflowError`` — a 500, not a validation error (the 4.10 finding).

**``LaborPlanLine`` carries no tenant.** It is a pure child of one plan, never listed on its own —
the ``MaintenancePlanTask`` / ``ComplianceCheck`` / ``TradeDocumentLine`` precedent. Its tenant is
``plan.tenant``, and every view MUST resolve it as
``get_object_or_404(LaborPlanLine, pk=pk, plan__tenant=request.tenant)``. A bare ``pk`` lookup is a
cross-tenant read, and it is the dangerous kind: nothing about the response would look wrong, so no
query anybody runs afterwards would ever reveal that it happened.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.LaborManagement._choices import (
    ACTIVITY_CHOICES,
    ACTIVITY_CSS,
    MAX_HORIZON_PERIODS,
    MAX_HOURS_PER_SHIFT,
    MAX_PLAN_LINES,
    MAX_PRODUCTIVITY_PCT,
    MIN_PLAN_YEAR,
    PLAN_BUCKET_CHOICES,
    PLAN_METHOD_CHOICES,
    PLAN_STATUS_CHOICES,
    PLAN_STATUS_CSS,
    VOLUME_SOURCE_CHOICES,
)


ONE_HUNDRED = Decimal("100")

#: Column ceilings for the two generated figures on the line, which are NARROWER than the (14, 4)
#: shape ``q4()`` clamps to. ``q2()`` would happily hand back 9999999999.99 for a
#: ``DecimalField(8, 2)``, and an over-range decimal raises ``DataError`` inside ``bulk_create`` —
#: which fails the WHOLE generated grid rather than the one absurd row (the ``q2()`` docstring's own
#: reasoning, applied to a column it does not know about). ``forecast_volume`` reaches 1e12 and a
#: standard reaches 1e8 minutes, so the product genuinely can exceed both of these.
MAX_REQUIRED_MINUTES = Decimal("999999999999.99")   # DecimalField(14, 2)
MAX_PLAN_HEADCOUNT = Decimal("999999.99")           # DecimalField(8, 2)


def _q2_within(value, ceiling):
    """Quantize to 2dp and clamp into ``[0, ceiling]`` — for columns narrower than ``q2()``'s.

    Both halves matter for the same reason they do in ``_base.q2()``: a long decimal fails to save
    and an over-range one poisons the entire batch it is written in. The low clamp is ``ZERO`` rather
    than ``-ceiling`` because every figure that passes through here is a quantity of minutes or of
    people, and neither is ever negative.
    """
    return min(max(Decimal(value or ZERO), ZERO), ceiling).quantize(Decimal("0.01"))


class LaborPlan(TenantNumbered):
    """A planned workload for one site over a bucketed period [LPL-]."""

    NUMBER_PREFIX = "LPL"

    #: ``draft`` and ``planned`` are still the planner's to change; ``approved`` is the roster the
    #: site is staffing to and ``archived`` is history, and neither may be edited in place. The
    #: generate verb is what moves ``draft -> planned``.
    EDITABLE_STATUSES = ("draft", "planned")

    #: Bounds, all lifted from ``_choices`` so the form, the seeder, the generate verb and any future
    #: revise action quote the same numbers back. See that module for why each one is a CONSTANT and
    #: not something computed from the data it is bounding.
    MAX_HORIZON_PERIODS = MAX_HORIZON_PERIODS
    MAX_PLAN_LINES = MAX_PLAN_LINES
    MIN_PLAN_YEAR = MIN_PLAN_YEAR

    #: Every outward FK whose target is tenant-scoped. ``clean()`` walks this list, so a pointer added
    #: later is covered by the cross-tenant guard the moment it is named here — the
    #: ``TradeLicense.TENANT_SCOPED_FKS`` idiom rather than another copy of the same if-block.
    TENANT_SCOPED_FKS = ("location", "demand_forecast")

    # --- what the plan IS -------------------------------------------------------------------------
    name = models.CharField(max_length=255)
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="labor_plans",
        help_text="The site being staffed — leave blank to plan the whole network")
    period_start = models.DateField()
    period_end = models.DateField()
    # `day` and `week` are the only two values the span arithmetic in period_count() and the walk in
    # period_starts() know how to step, so a third bucket is a change to both of those and not "a
    # one-line choices edit". max_length matches DemandForecast.bucket for that eventual day.
    bucket = models.CharField(max_length=8, choices=PLAN_BUCKET_CHOICES, default="day")

    # --- where the volume comes from --------------------------------------------------------------
    volume_source = models.CharField(
        max_length=16, choices=VOLUME_SOURCE_CHOICES, default="stock_moves",
        help_text="Which live ledger the generator derives expected volume from")
    method = models.CharField(
        max_length=24, choices=PLAN_METHOD_CHOICES, default="moving_average",
        help_text="How that derived history becomes a per-bucket volume")
    # Capped at two years, and the cap is not decoration: this number is handed straight to
    # timedelta(days=...) in history_window(), and PositiveIntegerField accepts 4294967295 on MariaDB
    # — an uncaught OverflowError, i.e. a 500, rather than a rejected form (the 4.10 DoS finding).
    # 730 against MIN_PLAN_YEAR=1900 also keeps the subtraction clear of date.min by ~two years.
    history_days = models.PositiveIntegerField(
        default=28, validators=[MinValueValidator(1), MaxValueValidator(730)],
        help_text="How far back the derived volume history reaches")
    demand_forecast = models.ForeignKey(
        "scm.DemandForecast", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="labor_plans",
        help_text="Required when the volume source is a demand forecast, and forbidden otherwise")

    # --- how volume becomes people ----------------------------------------------------------------
    hours_per_shift = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("8"),
        validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(MAX_HOURS_PER_SHIFT)],
        help_text="Paid hours in one shift — the divisor that turns required minutes into bodies")
    # MINIMUM 1, NOT 0 — this is a DIVISOR in required_headcount, so a zero here is not an aggressive
    # target, it is a ZeroDivisionError inside the generate verb (a 500) for every line in the grid.
    # The ceiling is generous headroom for a genuinely high-performing site; the floor is the one
    # that stops a 500.
    productivity_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=ONE_HUNDRED,
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(MAX_PRODUCTIVITY_PCT)],
        help_text="Expected achievement against standard — 90% means the site needs 111 minutes to "
                  "do 100 minutes of standard work")

    # --- lifecycle stamps (L22) — written by the verbs, never by a form ----------------------------
    status = models.CharField(max_length=8, choices=PLAN_STATUS_CHOICES, default="draft",
                              editable=False)
    generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="scm_labor_plans_approved")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_lpl_tnt_status_idx"),
            # The list page's date filter and the "which plan covers next Tuesday" lookup both
            # range-scan this one.
            models.Index(fields=["tenant", "period_start"], name="scm_lpl_tnt_start_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'LPL'} · {self.name}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The period contract, the volume-source pairing, and the cross-tenant guard.

        **Every bound below lives HERE rather than in the view**, so the form, the seeder and any
        future revise action all inherit it — ``DemandForecast.clean()`` says exactly this, and it is
        the reason the 4.7 horizon cap survived a generate verb it was written before.
        """
        super().clean()

        # THE GUARD. The form's querysets are tenant-scoped, but that is UX — a narrowed dropdown has
        # never held against a crafted POST (L39 §2). Skipped when the instance has no tenant yet: an
        # unsaved model has tenant_id None and ``self.tenant`` would raise RelatedObjectDoesNotExist
        # on a non-nullable FK rather than return None.
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

        errors = {}

        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                errors["period_end"] = "The plan cannot end before it starts."
            elif self.period_start.year < self.MIN_PLAN_YEAR:
                # Guards history_window()'s subtraction, which underflows date.min below year 1 —
                # an OverflowError, not a validation error.
                errors["period_start"] = f"The plan must start in {self.MIN_PLAN_YEAR} or later."
            else:
                # period_COUNT, not len(period_starts()). The grid is one row per
                # (bucket x in-scope standard), so an unbounded span is an unbounded bulk_create any
                # logged-in planner can fire by pressing Generate — and BUILDING the range in order
                # to discover the range is too big is precisely the allocation this check exists to
                # prevent (L40). Two dates and integer division answer it without allocating
                # anything. The computed span goes in the message so the planner is told how far past
                # the line they are, not merely that they are past it.
                span = self.period_count()
                if span > self.MAX_HORIZON_PERIODS:
                    errors["period_end"] = (
                        f"That period is {span} {self.get_bucket_display().lower()} buckets; the "
                        f"maximum is {self.MAX_HORIZON_PERIODS}. Use a weekly bucket or a shorter "
                        f"period.")

        # The volume-source pairing, BOTH ways. A forecast-sourced plan with no forecast attached
        # generates an empty grid and looks like a site with no work; a forecast attached to a plan
        # that reads stock moves is a pointer nothing consults, which is worse than none — the header
        # would name a forecast the numbers on the page were never derived from.
        if self.volume_source == "demand_forecast" and self.demand_forecast_id is None:
            errors["demand_forecast"] = (
                "A forecast-driven plan needs the demand forecast it reads volume from.")
        if self.volume_source != "demand_forecast" and self.demand_forecast_id is not None:
            errors["demand_forecast"] = (
                f"A '{self.get_volume_source_display()}' plan derives its own volume — clear the "
                f"forecast, or switch the volume source to the demand forecast.")

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # The period grid — measured by arithmetic, walked only under a cap
    # ---------------------------------------------------------------------------------------------
    def period_count(self):
        """How many buckets this plan spans, by INTEGER ARITHMETIC on the two dates.

        ``(period_end - period_start).days // step + 1`` where step is 1 day or 7. This never builds
        the range, and that is the entire point: it is called by :meth:`clean` to decide whether the
        range is small enough to build, so an implementation that allocated the range first would be
        the defect rather than the guard (L40 — ``DemandForecast.clean()`` reaches for
        ``period_count()`` and pointedly not ``len(period_range(...))``).

        ``0`` for an incomplete or inverted pair, so a half-filled form measures as no work rather
        than raising here — :meth:`clean` owns the message for that case.
        """
        if not (self.period_start and self.period_end) or self.period_end < self.period_start:
            return 0
        step = 1 if self.bucket == "day" else 7
        return (self.period_end - self.period_start).days // step + 1

    def period_starts(self, limit=None):
        """The first day of each bucket in the period, as a list, **capped**.

        The cap is on the walk itself and not applied afterwards, which is belt-and-braces behind
        :meth:`clean`: generate is also reachable on rows written before the cap existed, by a
        seeder, or by a data migration, and this is the call that turns a span into DB rows.

        Weekly buckets keep the ``period_start`` weekday rather than snapping to Monday — the plan's
        first day is a decision the planner made, and quietly moving it would mis-align every bucket
        against the volume history the generator reads for it.
        """
        if not (self.period_start and self.period_end) or self.period_end < self.period_start:
            return []
        limit = self.MAX_HORIZON_PERIODS if limit is None else limit
        step = timedelta(days=1 if self.bucket == "day" else 7)
        starts, cursor = [], self.period_start
        while cursor <= self.period_end and len(starts) < limit:
            starts.append(cursor)
            cursor += step
        return starts

    def bucket_end(self, start):
        """Last day covered by the bucket beginning on ``start``, clipped to ``period_end``.

        The clip matters on the trailing bucket: a weekly plan ending mid-week must read six days of
        volume for its last bucket and not seven, or the final line is staffed for work that falls
        outside the plan.
        """
        if start is None:
            return None
        span = timedelta(days=0 if self.bucket == "day" else 6)
        end = start + span
        return min(end, self.period_end) if self.period_end else end

    def history_window(self):
        """``(start, end)`` of the derived volume history the generator reads.

        Everything in the ``history_days`` immediately BEFORE the plan opens — the window never
        overlaps the period being planned, because a plan that read its own dates as history would
        forecast from whatever fragment of the future happened to be recorded already.

        ``history_days`` is capped at 730 and ``period_start`` at year 1900 precisely so this
        subtraction cannot underflow ``date.min``; see the field comments.
        """
        if not self.period_start:
            return None, None
        end = self.period_start - timedelta(days=1)
        return self.period_start - timedelta(days=int(self.history_days or 28)), end

    # ---------------------------------------------------------------------------------------------
    # Volume -> minutes -> people. The arithmetic lives HERE, once, so the generate verb, the seeder
    # and any future recompute cannot each carry a slightly different version of it.
    # ---------------------------------------------------------------------------------------------
    def required_minutes_for(self, standard_minutes):
        """Minutes at standard, inflated by the site's expected achievement against standard.

        ``standard_minutes x 100 / productivity_pct``. At 100% the two are equal; at 90% a bucket
        costing 1,000 standard minutes needs 1,111 real ones, which is the honest number to roster
        against — planning to the standard and hoping is how a site is understaffed every day and
        nobody can point at the assumption that did it.

        Falls back to the field default when ``productivity_pct`` arrives non-positive. That is
        unreachable through the form (``MinValueValidator(1)``) and through :meth:`clean`, so it can
        only be a caller that built the header in code and skipped both — and for that caller the
        right outcome is a plan built on the default assumption, not a ``ZeroDivisionError`` 500
        halfway through the grid. The validator remains the thing that stops the number being wrong.
        """
        pct = Decimal(self.productivity_pct or ZERO)
        if pct <= ZERO:
            pct = ONE_HUNDRED
        return _q2_within(Decimal(standard_minutes or ZERO) * ONE_HUNDRED / pct,
                          MAX_REQUIRED_MINUTES)

    def headcount_for(self, required_minutes):
        """Bodies needed for ``required_minutes`` of work — ``minutes / (hours_per_shift x 60)``.

        Deliberately fractional and NOT rounded up here: 2.3 and 3.0 are different staffing
        conversations, and rounding at the line would hide the fact that six activities each needing
        0.4 of a person share four bodies between them. Whoever adds up a bucket rounds once, at the
        top. Same non-positive fallback as :meth:`required_minutes_for`, for the same reason.
        """
        hours = Decimal(self.hours_per_shift or ZERO)
        if hours <= ZERO:
            hours = Decimal("8")
        return _q2_within(Decimal(required_minutes or ZERO) / (hours * Decimal("60")),
                          MAX_PLAN_HEADCOUNT)

    # ---------------------------------------------------------------------------------------------
    # Derived read-side figures — methods, never columns
    # ---------------------------------------------------------------------------------------------
    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """The badge class for :attr:`status`, decided in ``_choices`` and nowhere else, so the list
        page and the detail page cannot colour the same word differently."""
        return PLAN_STATUS_CSS.get(self.status, "badge-muted")

    def totals(self):
        """Plan-wide required vs planned effort in ONE aggregate.

        The detail header wants four of these figures at once; asking the child table separately for
        each would scan it four times per render and once per row on any list that shows them (the
        ``CycleCountTask.variance_count(lines=None)`` reason).

        **The unit is PERSON-SHIFTS, not headcount, and that is not pedantry.** Headcount does not
        add up across buckets — two people on Monday and two on Tuesday is two people, not four — so
        summing ``required_headcount`` and calling the answer a headcount would be a confidently
        wrong number on the most-read line of the page. Summed across (bucket x activity) the same
        arithmetic *is* meaningful as person-shifts of work, which is what a labour budget is
        denominated in anyway.

        ``coverage_pct`` is ``None``, never ``0``, when nothing is required: a plan whose grid has
        not been generated yet is unanswered, and a confident 0% would read as catastrophically
        understaffed (the 4.11 ``projected_stockout_count`` lesson).
        """
        agg = self.lines.aggregate(
            lines=models.Count("id"),
            minutes=Sum("required_minutes"),
            required=Sum("required_headcount"),
            planned=Sum("planned_headcount"),
        )
        required = q2(agg["required"] or ZERO)
        planned = q2(agg["planned"] or ZERO)
        return {
            "lines": agg["lines"] or 0,
            "required_minutes": q2(agg["minutes"] or ZERO),
            "required_shifts": required,
            "planned_shifts": planned,
            "shift_gap": q2(planned - required),
            "coverage_pct": (q2(planned * ONE_HUNDRED / required) if required > ZERO else None),
        }


class LaborPlanLine(models.Model):
    """One planned bucket of one activity — volume, minutes at standard, bodies. Tenant-less child.

    Reached through ``plan__tenant`` (the ``MaintenancePlanTask`` / ``ComplianceCheck`` precedent), so
    every view MUST resolve it as
    ``get_object_or_404(LaborPlanLine, pk=pk, plan__tenant=request.tenant)`` and every queryset MUST
    filter ``plan__tenant=request.tenant``. Scoping on the child alone is a cross-tenant read that
    looks completely ordinary in the response and leaves no trace anybody would think to go looking
    for.

    **``planned_headcount`` is the only column a human may write.** Everything else is generated, and
    that asymmetry is the model: the machine says what the volume implies, the planner says what they
    are actually going to roster, and the difference between the two is the number the page exists to
    show. Letting a planner edit ``required_headcount`` would let them close the gap by editing the
    question.
    """

    #: The tenant-scoped FKs this row declares. ``plan`` is not in the list because it IS the tenant
    #: anchor — comparing it against the tenant derived from it is vacuous — and the loop in
    #: :meth:`clean` therefore reads the reference tenant off ``plan`` rather than off ``self``.
    TENANT_SCOPED_FKS = ("standard",)

    plan = models.ForeignKey("scm.LaborPlan", on_delete=models.CASCADE, related_name="lines")
    period_start = models.DateField(help_text="First day of the bucket this line plans")
    activity = models.CharField(max_length=18, choices=ACTIVITY_CHOICES)

    # --- generated by the plan's generate verb (L22) -----------------------------------------------
    forecast_volume = models.DecimalField(
        max_digits=16, decimal_places=4, default=0, editable=False,
        help_text="Units this bucket is expected to move, derived at generate time")
    standard = models.ForeignKey(
        "scm.LaborStandard", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="plan_lines",
        help_text="Which standard priced this line — traceability only")
    # THE GLASS BOX (4.7's "the decomposition IS the feature"). This is the total minutes at standard
    # for `forecast_volume`, taken from `standard.minutes_for(...)` at generate time and then frozen,
    # so `forecast_volume -> standard_minutes_snapshot -> required_minutes -> required_headcount`
    # multiplies out on the page and still reconciles months later. Frozen rather than recomputed for
    # the InspectionResult / MaintenanceWorkOrderTask reason: editing a LaborStandard next month must
    # not silently rewrite what last month's roster was decided on. The `standard` FK says WHICH
    # standard; this says what it said AT THE TIME, which is the half that survives an edit.
    standard_minutes_snapshot = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, editable=False,
        help_text="Minutes this volume costs at standard, frozen when the plan was generated")
    required_minutes = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, editable=False,
        help_text="Standard minutes adjusted for the plan's expected productivity")
    required_headcount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0, editable=False,
        help_text="Bodies the required minutes imply for one shift")

    # --- the planner's answer ---------------------------------------------------------------------
    planned_headcount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("9999"))],
        help_text="What you intend to roster — the only figure on this line you may change")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["period_start", "activity"]
        # One line per bucket per activity, enforced in the DATABASE and not merely in the generator:
        # a regenerate that raced itself, or a hand-written importer, would otherwise double the
        # required headcount for a bucket with nothing anywhere to say it had.
        unique_together = ("plan", "period_start", "activity")
        indexes = [
            models.Index(fields=["plan", "period_start"], name="scm_lpll_plan_idx"),
        ]

    def __str__(self):
        return f"{self.period_start} · {self.get_activity_display()} · {self.required_headcount}"

    def clean(self):
        """The cross-tenant guard, anchored on the PARENT's tenant.

        ``standard`` is ``editable=False`` and written only by the generate verb, so this is defence
        in depth rather than the front line — but the front line is one bug away, and a standard from
        another workspace here would price a whole plan against a rate nobody in this workspace has
        ever seen, silently and reproducibly. The same defaulted-``getattr`` care as the parent's
        loop: ``RelatedObjectDoesNotExist`` subclasses ``AttributeError``, so a pointer whose row went
        away degrades to ``None`` instead of 500-ing inside validation.
        """
        super().clean()
        tenant_id = getattr(self.plan, "tenant_id", None) if self.plan_id else None
        if tenant_id is None:
            return
        for name in self.TENANT_SCOPED_FKS:
            if getattr(self, f"{name}_id", None) is None:
                continue
            related = getattr(self, name, None)
            if related is not None and related.tenant_id != tenant_id:
                raise ValidationError({name: "That record belongs to another workspace."})

    # ---------------------------------------------------------------------------------------------
    # Derived — methods and properties, never columns
    # ---------------------------------------------------------------------------------------------
    @property
    def headcount_variance(self):
        """``planned - required``. Negative is a shortfall, positive is slack.

        Signed on purpose: a labour plan is read to find both, and an absolute "gap" column would
        make an overstaffed Tuesday and an understaffed Wednesday look like the same problem.
        """
        return q2(Decimal(self.planned_headcount or ZERO) - Decimal(self.required_headcount or ZERO))

    def coverage_pct(self):
        """Planned as a percentage of required. ``None``, never ``0``, when nothing is required.

        A bucket with no required headcount is a bucket with no forecast work in it — an unanswered
        question, not 0% coverage. Printing a confident zero would put a red chip on the emptiest day
        of the plan and send a supervisor to fix the one thing that is fine.
        """
        required = Decimal(self.required_headcount or ZERO)
        if required <= ZERO:
            return None
        return q2(Decimal(self.planned_headcount or ZERO) * ONE_HUNDRED / required)

    @property
    def is_short(self):
        """Understaffed — fewer bodies planned than the volume needs."""
        return self.headcount_variance < ZERO

    @property
    def is_over(self):
        """Overstaffed. Reported, not refused: a deliberate cushion before a peak is a legitimate
        plan, and the number is here so it is a decision somebody made rather than one nobody saw."""
        return self.headcount_variance > ZERO

    @property
    def activity_css(self):
        """The badge class for :attr:`activity`, from the one dict in ``_choices`` that decides it."""
        return ACTIVITY_CSS.get(self.activity, "badge-muted")
