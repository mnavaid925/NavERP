"""SCM 4.8 Manufacturing — ProductionTimeLog, the shop-floor record [PRD-].

Realizes "Shop Floor Control" — the machine time, labour time and production progress the bullet
names. One log table covers all four entry types including downtime, rather than a second downtime
table: a stoppage is a booked interval at a work centre like any other, and splitting it would fork
every utilization query.

``quantity_completed`` here is ADVISORY progress. It does NOT roll up into
``WorkOrder.quantity_produced`` — that field has exactly one writer, the report-production action
that also posts the finished-goods StockMove. Two writers for one quantity is the bug 4.7 shipped
and had to fix (a second writer silently overwrote the computed column); the shop floor recording
"I finished 40" and the ledger recording "40 units were received into stock" are genuinely different
facts, and the run's output is the one backed by a stock move.

Entries are frozen once the work order is closed or cancelled — the audit-trail principle StockMove
sets, softened just enough while the run is live to satisfy the CRUD completeness rule.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class ProductionTimeLog(TenantNumbered):
    """One booked interval at a work centre against a work order [PRD-]."""

    NUMBER_PREFIX = "PRD"

    ENTRY_TYPE_CHOICES = [
        ("setup", "Setup"),
        ("labor", "Labour"),
        ("machine", "Machine"),
        ("downtime", "Downtime"),
    ]
    DOWNTIME_REASON_CHOICES = [
        ("breakdown", "Breakdown"),
        ("changeover", "Changeover"),
        ("material_shortage", "Material Shortage"),
        ("quality_hold", "Quality Hold"),
        ("no_operator", "No Operator"),
        ("other", "Other"),
    ]

    work_order = models.ForeignKey("scm.WorkOrder", on_delete=models.CASCADE,
                                   related_name="time_logs")
    work_center = models.ForeignKey("scm.WorkCenter", on_delete=models.PROTECT,
                                    related_name="time_logs")
    operation = models.CharField(
        max_length=120, blank=True,
        help_text="Free-text operation name — the stand-in until a routing master lands")
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES, default="labor")
    # The spine's Party + its 'employee' PartyRole — never a second employee table (L29).
    operator = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_production_time_logs")

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    # Computed from the interval on save — never typed, so the two can never disagree.
    duration_minutes = models.PositiveIntegerField(default=0, editable=False)

    quantity_completed = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                             validators=[MinValueValidator(ZERO)],
                                             help_text="Advisory progress — the run's output "
                                                       "quantity comes from reporting production")
    quantity_scrapped = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            validators=[MinValueValidator(ZERO)])
    downtime_reason = models.CharField(max_length=20, choices=DOWNTIME_REASON_CHOICES, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "work_order"], name="scm_prd_tnt_wo_idx"),
            models.Index(fields=["tenant", "work_center", "started_at"],
                         name="scm_prd_tnt_wc_start_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_entry_type_display()} {self.duration_minutes}m"

    def clean(self):
        super().clean()
        if self.ended_at and self.started_at and self.ended_at <= self.started_at:
            raise ValidationError({"ended_at": "End time must be after the start time."})
        if self.entry_type == "downtime" and not self.downtime_reason:
            raise ValidationError({"downtime_reason": "A downtime entry needs a reason."})
        if self.entry_type != "downtime" and self.downtime_reason:
            raise ValidationError({"downtime_reason": "Only a downtime entry carries a reason."})

    def save(self, *args, **kwargs):
        """Derive ``duration_minutes`` from the interval — the field's only writer."""
        if self.started_at and self.ended_at and self.ended_at > self.started_at:
            self.duration_minutes = int(
                (self.ended_at - self.started_at).total_seconds() // 60)
        else:
            self.duration_minutes = 0
        # A caller passing update_fields=["ended_at"] would otherwise persist the new interval and
        # leave the stale duration behind — the derived field must ride along with its inputs.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(dict.fromkeys(
                list(update_fields) + ["duration_minutes"]))
        return super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        return q2(Decimal(self.duration_minutes or 0) / Decimal("60"))

    @property
    def labor_cost(self):
        """Setup and labour both absorb at the centre's labour rate; downtime absorbs nothing."""
        if self.entry_type not in ("setup", "labor") or self.work_center_id is None:
            return ZERO
        return q4(self.duration_hours * (self.work_center.labor_cost_per_hour or ZERO))

    @property
    def machine_cost(self):
        if self.entry_type != "machine" or self.work_center_id is None:
            return ZERO
        return q4(self.duration_hours * (self.work_center.machine_cost_per_hour or ZERO))
