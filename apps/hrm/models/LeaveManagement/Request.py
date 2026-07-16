"""HRM 3.10 Leave Management — Request models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.HolidayManagement.Publicholiday import PublicHoliday
from apps.hrm.models.HolidayManagement.Publicholiday import PublicHoliday


class LeaveRequest(TenantNumbered):
    """Apply / approve / reject leave (3.10). ``days`` is recomputed in ``save()`` from the date
    range, excluding non-optional public holidays in that range."""

    NUMBER_PREFIX = "LR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="leave_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    cancelled_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_lr_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_lr_tenant_status_idx"),
            models.Index(fields=["tenant", "leave_type", "start_date"], name="hrm_lr_tenant_type_start_idx"),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    def _recompute_days(self):
        if self.start_date and self.end_date and self.end_date >= self.start_date:
            total = (self.end_date - self.start_date).days + 1
            holidays = 0
            if self.tenant_id:
                holidays = PublicHoliday.objects.filter(
                    tenant_id=self.tenant_id, is_optional=False,
                    date__gte=self.start_date, date__lte=self.end_date,
                ).count()
            self.days = Decimal(max(0, total - holidays))
        else:
            self.days = ZERO

    def save(self, *args, **kwargs):
        self._recompute_days()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.start_date}"
