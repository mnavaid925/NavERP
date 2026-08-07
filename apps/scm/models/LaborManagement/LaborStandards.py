"""SCM 4.14 Labor Management — LaborStandard, the engineered standard [LST-].

Realizes the sub-module's **Performance Tracking** bullet, and it is the keystone of 4.14: without a
standard to measure against, a labor module is a timeclock. Every performance figure downstream is
*earned minutes over actual minutes*, and earned minutes is defined in exactly one place —
:meth:`LaborStandard.minutes_for`. Nothing else in this sub-module is allowed to re-derive it; a
second copy of that formula is a second definition of "productive", and the two would disagree the
first time an allowance changed.

**Three determinants, not one rate.** TZA publishes single- and multi-determinant standards, SAP EWM
computes a *normal time* that already includes travel, personal needs, fatigue and unavoidable
delay, and Blue Yonder derives physics-based times from travel distance and item weight. So a
standard here is ``setup_minutes`` (paid once for the task) + ``travel_minutes`` (getting to it) +
``quantity × minutes_per_unit`` (the work itself), the whole lot inflated by ``allowance_pct``
(PF&D). Distance-DERIVED travel is deliberately deferred: ``scm.Location`` carries ``pick_sequence``
but no coordinates, so a distance model is a 4.3/4.4 schema change, not something 4.14 may fake.

**Scope and effectivity, resolved by :func:`select_standard`.** A standard may be scoped to a
location, to an item category, to both, or to neither (the network-wide default), and it is dated.
That is what lets a site run a slower pick standard than the network without forking the library,
and what lets last quarter's numbers still reproduce after this quarter's re-time. Which row applies
is decided by one resolver so the list page, the booking form and the scorecard cannot each answer
differently.

**Why an ACTIVE standard is still editable.** Activating a standard does not freeze it, because
every ``LaborActivity`` SNAPSHOTS the standard's minutes at booking time — editing a live standard
therefore changes what future bookings earn and cannot rewrite a single figure already recorded.
``archived`` is the frozen one, and for a reason that is easy to miss: the overlap guard in
:meth:`clean` deliberately ignores archived rows, so editing an archived standard back into a live
date range would recreate exactly the ambiguity that guard exists to prevent.

**``labour_rate`` is a CHARGE-OUT rate, never a person's wage.** ``hrm`` owns compensation
(``SalaryStructureTemplate``) and SCM neither reads it nor duplicates it. ``apps/scm`` carries no
pointer into the HR app anywhere today and must keep none: the worker on a labor record is
``core.Party``, and the hand-off to payroll is a REPORT, not a foreign key.
"""
from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.LaborManagement._choices import (
    ACTIVITY_CHOICES,
    MAX_ALLOWANCE_PCT,
    MAX_STANDARD_RATE,
    MIN_PLAN_YEAR,
    STANDARD_BASIS_CHOICES,
    STANDARD_SOURCE_CHOICES,
)

ONE_HUNDRED = Decimal("100")
MINUTES_PER_HOUR = Decimal("60")


class LaborStandard(TenantNumbered):
    """How long one unit of one activity is expected to take, in one scope, over one date range."""

    NUMBER_PREFIX = "LST"

    #: Local to this model on purpose — the ``_choices.py`` rule is that a vocabulary read from two
    #: directions is shared and one read from a single direction stays where it is used. Nothing
    #: outside a standard has an opinion about ``draft``/``active``/``archived``.
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]
    #: ``active`` is editable, which looks wrong until you know that every ``LaborActivity``
    #: snapshots the standard it was measured against: a re-time changes what FUTURE work earns and
    #: cannot touch a minute already booked. ``archived`` is frozen because the overlap guard in
    #: :meth:`clean` ignores archived rows — an archived standard edited back into a live date range
    #: would slip past the one check that keeps :func:`select_standard` deterministic.
    EDITABLE_STATUSES = ("draft", "active")

    #: Colour per status, decided in ONE place so the list badge and the detail badge cannot drift.
    #: theme.css has badge-green / red / amber / info / muted / slate ONLY (L33).
    STATUS_CSS = {
        "draft": "badge-muted",
        "active": "badge-green",
        "archived": "badge-slate",
    }

    #: Ceiling on any single determinant — a week and a half of continuous work for ONE unit. It is
    #: a bound on the way in rather than a clamp on the way out: ``minutes_for()`` multiplies
    #: ``minutes_per_unit`` by a quantity, so an absurd determinant does not stay local — it lands
    #: in earned minutes, in ``cost_for()``, and in the required-headcount arithmetic of every plan
    #: built on this activity. It lives here rather than in ``_choices.py`` because this is the only
    #: model that reads it.
    MAX_DETERMINANT_MINUTES = Decimal("10000")

    #: The FKs :meth:`clean` tenant-checks. Table-driven so adding a pointer to this model means
    #: adding it here, not remembering to copy a third if-block.
    TENANT_SCOPED_FKS = ("location", "item_category")

    # --- identity ---------------------------------------------------------------------------------
    name = models.CharField(max_length=255)
    activity = models.CharField(
        max_length=18, choices=ACTIVITY_CHOICES,
        help_text="The work this standard measures. An INDIRECT activity may carry a standard, but "
                  "no performance figure is computed against it — break time is not earned time")
    basis = models.CharField(
        max_length=10, choices=STANDARD_BASIS_CHOICES, default="per_unit",
        help_text="What one 'unit' counts. 0.4 minutes is fast per pallet and absurd per case, so "
                  "the basis is what makes minutes per unit mean anything")
    source = models.CharField(
        max_length=12, choices=STANDARD_SOURCE_CHOICES, default="engineered",
        help_text="Where the number came from. A supervisor arguing with a standard is entitled to "
                  "know whether it was time-studied here or lifted from a benchmark library")

    # --- the three determinants -------------------------------------------------------------------
    # setup + travel + (quantity x per-unit) is the shape TZA and SAP EWM both publish. Splitting the
    # fixed part out of the variable part is the whole point: a per-task standard that is really
    # 12 minutes of setup, charged per unit, prices a one-line pick identically to a forty-line one.
    minutes_per_unit = models.DecimalField(
        max_digits=10, decimal_places=4, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_DETERMINANT_MINUTES)],
        help_text="Variable time per unit of the chosen basis")
    setup_minutes = models.DecimalField(
        max_digits=10, decimal_places=4, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_DETERMINANT_MINUTES)],
        help_text="Fixed time paid once per task, regardless of quantity")
    travel_minutes = models.DecimalField(
        max_digits=10, decimal_places=4, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_DETERMINANT_MINUTES)],
        help_text="Fixed travel to and from the work, once per task. Distance-derived travel needs "
                  "bin coordinates that scm.Location does not have — this is the typed stand-in")
    allowance_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_ALLOWANCE_PCT)],
        help_text="Personal, fatigue and delay allowance added on top of the measured time. Capped "
                  "at 100% — an allowance may at most double the standard")

    labour_rate = models.DecimalField(
        max_digits=14, decimal_places=4, default=ZERO,
        validators=[MinValueValidator(ZERO), MaxValueValidator(MAX_STANDARD_RATE)],
        help_text="CHARGE-OUT rate per hour used for cost per unit — never a person's wage. HRM "
                  "owns compensation and SCM does not read it. Leave at zero to skip costing")

    # --- lifecycle --------------------------------------------------------------------------------
    # editable=False and OFF the form: activating a standard changes what every FUTURE activity
    # snapshots and archiving one removes it from the resolver, so both are verbs a person presses,
    # with the consequence on the screen — not a dropdown somebody scrolls past on the edit page.
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="draft", editable=False)

    effective_from = models.DateField(
        help_text="First day this standard applies. Re-timing an activity means a NEW standard "
                  "starting today, not an edit — that is what keeps last month reproducible")
    effective_to = models.DateField(
        null=True, blank=True, help_text="Last day this standard applies. Blank = open-ended")
    notes = models.TextField(blank=True)

    # --- scope ------------------------------------------------------------------------------------
    # Both blank = the network-wide default. SET_NULL rather than CASCADE on purpose: deleting a
    # warehouse must not silently delete the standards that were measured there and the historic
    # activities that snapshot them — the standard widens to the network and stays readable.
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="labor_standards",
        help_text="Warehouse or zone this standard is measured for. Blank = the whole network")
    item_category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="labor_standards",
        help_text="Item class this standard is measured for. Blank = every item")

    class Meta:
        ordering = ["activity", "-effective_from", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # select_standard() opens on (tenant, activity) every single time it is called, and it
            # is called once per activity row on every scorecard and plan generation.
            models.Index(fields=["tenant", "activity"], name="scm_lst_tnt_act_idx"),
            models.Index(fields=["tenant", "status"], name="scm_lst_tnt_status_idx"),
            models.Index(fields=["tenant", "effective_from"], name="scm_lst_tnt_eff_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'LST'} · {self.name}"

    # ---------------------------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------------------------
    def clean(self):
        """The cross-tenant guard, the "this standard can actually be applied" contract, and the
        overlap refusal that makes :func:`select_standard` deterministic."""
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

        # (a) The date range. Both halves are read by the resolver, so a reversed pair produces a
        #     standard that is effective on no day at all — configured, listed, and silently never
        #     selected.
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "A standard cannot stop applying before it starts."
        if self.effective_from and self.effective_from.year < MIN_PLAN_YEAR:
            errors["effective_from"] = (
                f"The effective date must be in {MIN_PLAN_YEAR} or later — earlier dates break the "
                "history-window arithmetic the planner does against them.")

        setup = self.setup_minutes or ZERO
        travel = self.travel_minutes or ZERO
        per_unit = self.minutes_per_unit or ZERO

        # (b) A standard of zero minutes is not a lenient standard, it is a broken one: earned
        #     minutes come out zero for any quantity, so performance_pct() divides work into nothing
        #     and every worker measured against it reads as 0% forever. Refuse it at the door rather
        #     than explain the zeroes on the scorecard later.
        if setup + travel + per_unit <= ZERO:
            errors["minutes_per_unit"] = (
                "A standard needs some time in it — set a per-unit, setup or travel figure. A "
                "zero standard earns nothing for any quantity of work.")

        # (c) The paired basis rule, in both directions — the ProductionTimeLog downtime/reason
        #     shape. "Per task (fixed)" says the fixed time IS the standard, so a per-unit figure
        #     beside it is a contradiction the arithmetic would quietly honour: minutes_for() would
        #     scale a supposedly fixed task by quantity. Every other basis is the mirror image — a
        #     per-case standard with no per-unit time charges the same minutes for one case as for
        #     two hundred.
        elif self.basis == "per_task":
            if per_unit > ZERO:
                errors["minutes_per_unit"] = (
                    "A per-task standard is a FIXED time — put it in setup minutes and leave the "
                    "per-unit figure at zero, or change the basis.")
            if setup <= ZERO:
                errors["setup_minutes"] = (
                    "A per-task standard needs setup minutes — that fixed time is the standard.")
        elif per_unit <= ZERO:
            errors["minutes_per_unit"] = (
                f"A '{self.get_basis_display()}' standard needs a per-unit time, or it charges the "
                "same minutes for one unit as for a thousand. Use the 'Per task (fixed)' basis if "
                "the time really is fixed.")

        # (d) THE OVERLAP REFUSAL. Two live standards covering the same (activity, location,
        #     category) scope on the same day means select_standard() has no deterministic answer:
        #     which one applies would depend on row order, so the same job could earn different
        #     minutes on two page loads and last month's performance figure would stop reproducing.
        #     That is worse than a wrong standard — a wrong standard can be argued with.
        #
        #     Archived rows are excluded on BOTH sides: an archived standard is never selected, so it
        #     cannot create the ambiguity, and history has to stay parked under a superseding row.
        if (self.tenant_id is not None and self.effective_from and self.status != "archived"
                and not errors.keys() & {"effective_from", "effective_to"}):
            clash = (LaborStandard.objects
                     .filter(tenant_id=self.tenant_id,
                             activity=self.activity,
                             location_id=self.location_id,
                             item_category_id=self.item_category_id)
                     .exclude(status="archived")
                     # On create self.pk is None, which Django renders as NOT (id IS NULL) — it
                     # excludes nothing, which is exactly right for a row that does not exist yet.
                     .exclude(pk=self.pk))
            # Two ranges overlap when each starts on or before the other ends; an open-ended range
            # (effective_to null) never ends, so it overlaps everything that starts after it.
            if self.effective_to:
                clash = clash.filter(effective_from__lte=self.effective_to)
            clash = clash.filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from))
            other = clash.order_by("effective_from", "id").first()
            if other is not None:
                span = (f"from {other.effective_from:%d %b %Y} to {other.effective_to:%d %b %Y}"
                        if other.effective_to
                        else f"from {other.effective_from:%d %b %Y} onwards")
                errors["effective_from"] = (
                    f"{other.number or 'Another standard'} already covers this activity and scope "
                    f"{span}. Close that one off or archive it — two standards for one scope on "
                    "one day have no defined winner.")

        if errors:
            raise ValidationError(errors)

    # ---------------------------------------------------------------------------------------------
    # Derived — nothing below is stored
    # ---------------------------------------------------------------------------------------------
    def minutes_for(self, quantity):
        """**The earned-minutes definition.** How long this standard says ``quantity`` should take::

            (setup_minutes + travel_minutes + quantity × minutes_per_unit) × (1 + allowance_pct/100)

        This is the ONE place that formula exists. Session performance, the worker scorecard, the
        plan generator's required minutes and ``cost_for()`` all route through here, so re-timing
        the allowance moves every one of them together. A second copy of this arithmetic anywhere in
        4.14 is a second definition of productive work and should be deleted rather than kept in
        sync.

        The allowance is applied as ``× (100 + pct) / 100`` rather than ``× (1 + pct/100)`` — the
        same number, but the division happens once at the end instead of on a repeating decimal
        before the multiply. ``q4()`` clamps as well as quantizes, so a hostile quantity degrades to
        a capped figure on this row rather than a ``DataError`` that fails a whole batch.
        """
        qty = Decimal(quantity or ZERO)
        base = ((self.setup_minutes or ZERO) + (self.travel_minutes or ZERO)
                + qty * (self.minutes_per_unit or ZERO))
        return q4(base * (ONE_HUNDRED + (self.allowance_pct or ZERO)) / ONE_HUNDRED)

    def cost_for(self, quantity):
        """Standard labour cost of ``quantity`` — Easy Metrics' headline figure, cost per unit.

        Minutes at standard, converted to hours, at the CHARGE-OUT rate. A standard with no rate
        costs zero, which is the honest answer: it means nobody has priced this activity, and the
        cost column on the scorecard says so by staying empty rather than inventing a rate.
        """
        return q4(self.minutes_for(quantity) / MINUTES_PER_HOUR * (self.labour_rate or ZERO))

    def is_effective_on(self, day=None):
        """Whether this standard's date range covers ``day`` (default today).

        Says nothing about ``status`` — :func:`select_standard` checks that separately, because
        "was this standard in force then?" and "is this standard live now?" are different questions
        and the detail page asks the first one about archived rows.
        """
        day = day or timezone.localdate()
        if self.effective_from and day < self.effective_from:
            return False
        if self.effective_to and day > self.effective_to:
            return False
        return True

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def status_css(self):
        """theme.css badge class for :attr:`status` — one lookup, so no template invents a colour."""
        return self.STATUS_CSS.get(self.status, "badge-muted")


def select_standard(tenant, activity, location=None, item_category=None, on_date=None):
    """The standard that governs ``activity`` in a scope on a date — most specific wins.

    The ladder, narrowest first: **location + category** → **category only** → **location only** →
    **network-wide**. Each rung matches standards scoped to exactly that shape: the "category only"
    rung requires ``location`` to be blank on the STANDARD, so a standard measured at warehouse B
    can never be selected for work done at warehouse A — the alternative (matching on category and
    ignoring the location column) would quietly apply another site's times.

    Only ``status="active"`` rows whose date range covers ``on_date`` (default today) are considered.
    Ties are broken by the latest ``effective_from``, then by id so the answer is deterministic even
    for rows that predate :meth:`LaborStandard.clean`'s overlap guard or were written around it.

    ``location`` and ``item_category`` accept a model instance or a raw pk — callers reach this from
    a saved row (``activity.location``) and from a form's cleaned ids alike, and a resolver that
    silently returned the network default because it was handed an int is the worst kind of wrong.

    **Returns ``None`` when nothing matches, and every caller must handle that.** An activity with no
    standard has ``earned_minutes = None`` and ``performance_pct() = None`` — never ``0``. The
    distinction is the whole point: zero earned minutes says the worker achieved nothing, ``None``
    says nobody has measured this work. Collapsing the two makes an UNMEASURED job read as a failing
    one on the scorecard, and the person it names has no way to argue with it.
    """
    if tenant is None or not activity:
        return None
    on_date = on_date or timezone.localdate()

    # A model instance yields its pk; an int is already one. Falsy (None / 0) means "unscoped", which
    # skips that rung of the ladder rather than matching rows whose column is NULL by accident.
    location_id = getattr(location, "pk", location)
    category_id = getattr(item_category, "pk", item_category)

    qs = (LaborStandard.objects
          .filter(tenant=tenant, activity=activity, status="active",
                  effective_from__lte=on_date)
          .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)))
    order = ("-effective_from", "-id")

    if location_id and category_id:
        match = qs.filter(location_id=location_id,
                          item_category_id=category_id).order_by(*order).first()
        if match is not None:
            return match
    if category_id:
        match = qs.filter(location__isnull=True,
                          item_category_id=category_id).order_by(*order).first()
        if match is not None:
            return match
    if location_id:
        match = qs.filter(location_id=location_id,
                          item_category__isnull=True).order_by(*order).first()
        if match is not None:
            return match
    return qs.filter(location__isnull=True,
                     item_category__isnull=True).order_by(*order).first()
