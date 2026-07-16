"""HRM 3.11 Time Tracking — Overtimerequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OvertimeRequest(TenantNumbered):
    """An overtime claim (3.11) — daily OT hours at a configurable multiplier, paid out or converted
    to comp-leave. Approval workflow ``draft → pending → approved/rejected`` (+ ``cancelled``),
    mirroring ``LeaveEncashment``. No stored currency ``amount`` — there is no stable employee
    pay-rate source yet (3.13 Salary Structure); ``overtime_pay_equivalent_hours`` is derived."""

    NUMBER_PREFIX = "OT"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    PAYOUT_CHOICES = [
        ("pay", "Pay"),
        ("comp_leave", "Compensatory Leave"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="overtime_requests")
    timesheet = models.ForeignKey("hrm.Timesheet", on_delete=models.SET_NULL, null=True, blank=True, related_name="overtime_requests")
    date = models.DateField()
    hours_claimed = models.DecimalField(max_digits=5, decimal_places=2)
    multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"),
                                     validators=[MinValueValidator(Decimal("1"))])
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default="pay")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_overtime_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ot_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ot_tenant_status_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_ot_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.hours_claimed or ZERO) <= ZERO:
            raise ValidationError({"hours_claimed": "Overtime hours must be greater than zero."})
        # A linked timesheet must belong to the same employee (both are tenant-scoped independently).
        if self.timesheet_id and self.employee_id and self.timesheet.employee_id != self.employee_id:
            raise ValidationError({"timesheet": "The linked timesheet belongs to a different employee."})

    @property
    def overtime_pay_equivalent_hours(self):
        """Derived: the multiplier-weighted OT hours (e.g. 4h at 1.5× = 6.0 pay-equivalent hours).
        The currency payout is deferred until a stable pay-rate source (3.13) exists."""
        return (self.hours_claimed or ZERO) * (self.multiplier or ZERO)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.hours_claimed}h"
