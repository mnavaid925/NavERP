"""HRM 3.10 Leave Management — Allocation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.LeaveManagement.Request import LeaveRequest
from apps.hrm.models.LeaveManagement.Request import LeaveRequest


class LeaveAllocation(TenantNumbered):
    """Per-employee, per-year leave entitlement (3.10). The used/balance figures are **derived**
    from approved ``LeaveRequest`` rows — never stored editable."""

    NUMBER_PREFIX = "LA"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_allocations")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="allocations")
    year = models.PositiveSmallIntegerField()
    allocated_days = models.DecimalField(max_digits=5, decimal_places=2)
    # Days rolled in from the prior year by the carry-forward run (a subset of allocated_days). Kept
    # separate so a re-run replaces its own prior contribution instead of double-adding (idempotent).
    carried_forward = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    # Days consumed by APPROVED LeaveEncashment payouts. Tracked separately from allocated_days so the
    # accrual engine (which recomputes allocated_days = accrued + carried_forward) can't silently
    # restore cashed-out days on a re-run — balance nets this out instead.
    encashed_days = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        ordering = ["-year", "employee__party__name"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "leave_type", "year")]
        indexes = [
            models.Index(fields=["tenant", "employee", "year"], name="hrm_la_tenant_emp_year_idx"),
            models.Index(fields=["tenant", "leave_type", "year"], name="hrm_la_tenant_type_year_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_la_tenant_status_idx"),
        ]

    @property
    def used_days(self):
        # Calendar-year semantic: a request is charged to the year of its start_date. A request
        # straddling a year boundary is counted whole against the start year (acceptable for the
        # demo; exact split + year-end carry-forward is a deferred enhancement — see todo.md).
        # Cached on the instance so `balance` doesn't re-run the aggregate. List views should use
        # the `used_days_db`/`balance_db` annotations (see hrm.views._used_days_subquery) instead.
        if not hasattr(self, "_used_days_cache"):
            agg = LeaveRequest.objects.filter(
                tenant_id=self.tenant_id, employee_id=self.employee_id,
                leave_type_id=self.leave_type_id, status="approved",
                start_date__year=self.year,
            ).aggregate(s=Sum("days"))
            self._used_days_cache = agg["s"] or ZERO
        return self._used_days_cache

    @property
    def balance(self):
        return (self.allocated_days or ZERO) - self.used_days - (self.encashed_days or ZERO)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.year}"
