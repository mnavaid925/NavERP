"""SCM 4.8 Manufacturing — WorkCenter, the capacity + cost-rate master [WC-].

Realizes the capacity half of the "Production Scheduling" bullet and supplies the two hourly rates
that "Shop Floor Control" costs a run with.

Everything schedule-shaped here is DERIVED, never stored: scheduled hours come from the work orders
planned against the centre, actual hours from the ProductionTimeLog entries booked to it. There is
no stored load/utilization column to drift from the rows that produce it — the same rule 4.3 applies
to on-hand and 4.7 applies to forecast roll-ups.

The centre points at a ``scm.Location`` rather than owning one: "where this centre's WIP sits" is a
stock location like any other. Deliberately NOT a new ``wip`` ``location_type`` — that would be a
migration on a model 4.3/4.4/4.5 all share, and ``Location.is_pickable`` defaults True, which would
leak work-in-progress into 4.5's available-to-promise.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class WorkCenter(TenantNumbered):
    """A machine, cell or manual station that work orders are scheduled against [WC-]."""

    NUMBER_PREFIX = "WC"

    CENTER_TYPE_CHOICES = [
        ("machine", "Machine"),
        ("assembly", "Assembly"),
        ("manual", "Manual"),
        ("inspection", "Inspection"),
        ("outsourced", "Outsourced"),
    ]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    center_type = models.CharField(max_length=12, choices=CENTER_TYPE_CHOICES, default="machine")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="work_centers",
                                 help_text="Stock location this centre draws from and reports into")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_work_centers", help_text="Owning department")
    # The spine's Party + its 'employee' PartyRole — never a second employee table (L29).
    supervisor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="scm_supervised_work_centers")

    capacity_hours_per_day = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("8"),
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("24"))],
        help_text="Nominal available hours per working day")
    efficiency_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("100"),
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("200"))],
        help_text="Realised output as a % of nominal capacity")
    setup_minutes = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(10080)],
        help_text="Changeover time consumed before a run starts")

    machine_cost_per_hour = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                                validators=[MinValueValidator(ZERO)])
    labor_cost_per_hour = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                              validators=[MinValueValidator(ZERO)])

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("tenant", "code"), ("tenant", "number"))
        indexes = [models.Index(fields=["tenant", "is_active"], name="scm_wc_tnt_active_idx")]

    def __str__(self):
        return f"{self.code} · {self.name}"

    # --- rates -----------------------------------------------------------------------------------
    @property
    def cost_per_hour(self):
        """Fully-loaded hourly rate — machine + labour."""
        return (self.machine_cost_per_hour or ZERO) + (self.labor_cost_per_hour or ZERO)

    # --- capacity --------------------------------------------------------------------------------
    def effective_capacity_hours(self, days=1):
        """Nominal capacity scaled by efficiency, over ``days`` working days."""
        return q2((self.capacity_hours_per_day or ZERO) * (self.efficiency_pct or ZERO)
                  / Decimal("100") * Decimal(days or 0))

    def scheduled_hours(self, start, end):
        """Planned hours from work orders whose planned window OVERLAPS [start, end].

        Overlap, not containment: a run that straddles the window edge still consumes this centre's
        capacity inside it, and dropping it would under-report load exactly when the board matters.
        One aggregate, not a per-order loop.
        """
        if not start or not end:
            return ZERO
        rows = self.work_orders.filter(
            planned_start__isnull=False, planned_end__isnull=False,
            planned_start__lt=end, planned_end__gt=start,
        ).exclude(status__in=("cancelled", "closed"))
        total = ZERO
        for planned_start, planned_end in rows.values_list("planned_start", "planned_end"):
            total += Decimal((planned_end - planned_start).total_seconds()) / Decimal("3600")
        return q2(total)

    @classmethod
    def scheduled_hours_map(cls, tenant, start, end):
        """``{work_center_id: hours}`` for EVERY centre in one grouped query.

        The batched form of :meth:`scheduled_hours`, for the load board — calling the per-instance
        version there is one query per centre. Served by ``scm_wo_tnt_wc_start_idx``.
        """
        from apps.scm.models import WorkOrder
        if tenant is None or not start or not end:
            return {}
        rows = (WorkOrder.objects
                .filter(tenant=tenant, work_center__isnull=False,
                        planned_start__isnull=False, planned_end__isnull=False,
                        planned_start__lt=end, planned_end__gt=start)
                .exclude(status__in=("cancelled", "closed"))
                .values_list("work_center_id", "planned_start", "planned_end"))
        totals = {}
        for centre_id, planned_start, planned_end in rows:
            hours = Decimal((planned_end - planned_start).total_seconds()) / Decimal("3600")
            totals[centre_id] = totals.get(centre_id, ZERO) + hours
        return {centre_id: q2(hours) for centre_id, hours in totals.items()}

    def actual_hours(self, start, end):
        """Booked hours from ProductionTimeLog — one Sum, not a row walk."""
        if not start or not end:
            return ZERO
        minutes = self.time_logs.filter(started_at__gte=start, started_at__lt=end).aggregate(
            m=Sum("duration_minutes"))["m"] or 0
        return q2(Decimal(minutes) / Decimal("60"))

    def utilization_pct(self, start, end, days=None, actual=None):
        """Actual booked hours as a % of effective capacity over the window.

        Pass ``actual`` when the caller already has the figure — the detail page reads it out of
        ``oee_chip()``, which aggregates the same rows over the same window. Without it this method
        re-runs an identical ``Sum("duration_minutes")`` scan of the module's fastest-growing table.
        """
        if days is None:
            days = max((end - start).days, 1) if (start and end) else 1
        capacity = self.effective_capacity_hours(days)
        if capacity <= ZERO:
            return ZERO
        if actual is None:
            actual = self.actual_hours(start, end)
        return q2(actual / capacity * Decimal("100"))

    def oee_chip(self, start, end):
        """Runtime vs downtime vs scrap for the window — the shop-floor health chip.

        A deliberately small derived summary, NOT an OEE analytics engine: availability/performance/
        quality decomposition and its trend belong to 4.11 Supply Chain Analytics.
        """
        rows = self.time_logs.filter(started_at__gte=start, started_at__lt=end)
        agg = rows.aggregate(
            run=Sum("duration_minutes", filter=~Q(entry_type="downtime")),
            down=Sum("duration_minutes", filter=Q(entry_type="downtime")),
            good=Sum("quantity_completed"), scrap=Sum("quantity_scrapped"))
        run = Decimal(agg["run"] or 0)
        down = Decimal(agg["down"] or 0)
        good = agg["good"] or ZERO
        scrap = agg["scrap"] or ZERO
        booked = run + down
        produced = good + scrap
        return {
            "run_hours": q2(run / Decimal("60")),
            "downtime_hours": q2(down / Decimal("60")),
            # Total booked = run + downtime. Exposed so the detail page reads it from here instead
            # of calling actual_hours(), which is the identical aggregate over the same rows.
            "booked_hours": q2(booked / Decimal("60")),
            "availability_pct": q2(run / booked * Decimal("100")) if booked > ZERO else ZERO,
            "quantity_good": q4(good),
            "quantity_scrapped": q4(scrap),
            "quality_pct": q2(good / produced * Decimal("100")) if produced > ZERO else ZERO,
        }
