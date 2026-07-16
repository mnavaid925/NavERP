"""HRM 3.11 Time Tracking — Timesheet models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.11 Time Tracking — Timesheet (+ TimesheetEntry lines) + OvertimeRequest
# ---------------------------------------------------------------------------
class Timesheet(TenantNumbered):
    """A weekly timesheet header per employee (3.11). ``total_hours``/``billable_hours`` are
    **derived** — recomputed by ``refresh_totals()`` from the child ``TimesheetEntry`` rows, never
    hand-typed (mirrors ``LeaveRequest.days``). Workflow ``draft → pending → approved/rejected``
    (+ ``cancelled``), mirroring ``LeaveRequest``; entries lock once the sheet is approved."""

    NUMBER_PREFIX = "TS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="timesheets")
    period_start = models.DateField()
    period_end = models.DateField()
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    billable_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_timesheet_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    rejected_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "period_start")]
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ts_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ts_tenant_status_idx"),
            models.Index(fields=["tenant", "period_start"], name="hrm_ts_tenant_period_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot be before period start."})
        # On edit, the (possibly narrowed) period must still cover every existing entry's date —
        # otherwise a header edit could strand entries outside the period the entry clean() enforces.
        if self.pk and self.period_start and self.period_end:
            if self.entries.exclude(date__gte=self.period_start, date__lte=self.period_end).exists():
                raise ValidationError({"period_start": "This period no longer covers existing time "
                                       "entries — adjust or remove those entries first."})

    def refresh_totals(self, save=True):
        """Recompute total/billable hours from the child entries in a single aggregate pass.
        Called after any entry add/edit/delete and on approval. No-op if the row isn't saved yet
        (a brand-new header has no pk and therefore no entries)."""
        if not self.pk:
            return
        agg = self.entries.aggregate(
            total=Sum("hours"),
            billable=Sum("hours", filter=Q(is_billable=True)))
        self.total_hours = agg["total"] or ZERO
        self.billable_hours = agg["billable"] or ZERO
        if save:
            super().save(update_fields=["total_hours", "billable_hours", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.period_start}…{self.period_end}"
