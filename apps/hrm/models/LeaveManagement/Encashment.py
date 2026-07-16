"""HRM 3.10 Leave Management — Encashment models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.LeaveManagement.Allocation import LeaveAllocation
from apps.hrm.models.LeaveManagement.Allocation import LeaveAllocation


class LeaveEncashment(TenantNumbered):
    """Convert unused, encashable leave into a cash payout (3.10 Leave Policy). Workflow
    ``draft → pending → approved → paid`` (+ ``rejected``/``cancelled``), mirroring ``LeaveRequest``.
    ``amount`` is recomputed in ``save()`` from ``days × rate_per_day`` (never hand-edited). On
    **approval** the matching ``LeaveAllocation.allocated_days`` is reduced by ``days`` — encashment
    consumes the balance (see ``views.leaveencashment_approve``)."""

    NUMBER_PREFIX = "ENC"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_encashments")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="encashments")
    year = models.PositiveSmallIntegerField()
    days = models.DecimalField(max_digits=6, decimal_places=2)
    rate_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_encashment_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-year", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_enc_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_enc_tenant_status_idx"),
            models.Index(fields=["tenant", "leave_type", "year"], name="hrm_enc_tenant_type_year_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.days or ZERO) <= ZERO:
            raise ValidationError({"days": "Days to encash must be greater than zero."})
        if self.leave_type_id and self.leave_type and not self.leave_type.encashable:
            raise ValidationError({"leave_type": "This leave type is not marked encashable."})
        # Cannot encash more than the current balance. ``employee`` is already tenant-scoped by the
        # form, so filtering by employee/leave_type/year (no tenant) is safe and avoids a tenant-None
        # gap (the view sets tenant only after form validation).
        if self.employee_id and self.leave_type_id and self.year:
            alloc = (LeaveAllocation.objects
                     .filter(employee_id=self.employee_id, leave_type_id=self.leave_type_id, year=self.year)
                     .first())
            available = alloc.balance if alloc else ZERO
            if self.days and self.days > available:
                raise ValidationError({"days": f"Only {available} day(s) available to encash for {self.year}."})

    def save(self, *args, **kwargs):
        self.amount = ((self.days or ZERO) * (self.rate_per_day or ZERO)).quantize(Decimal("0.01"))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.year}"
