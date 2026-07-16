"""HRM 3.12 Holiday Management — Floatingholidayelection models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.HolidayManagement.Holidaypolicy import HolidayPolicy
from apps.hrm.models.HolidayManagement.Holidaypolicy import HolidayPolicy


class FloatingHolidayElection(TenantOwned):
    """An employee's election of one optional (floating) holiday (3.12 — "Floating Holidays"
    bullet). Only ``is_optional=True`` holidays are electable; the governing ``HolidayPolicy``'s
    ``floating_holiday_quota`` caps how many an employee may take per year (the "restriction
    rules"). Approvals mirror the ``LeaveRequest`` workflow: pending → approved/rejected via the
    privileged view actions (``status``/``approved_by``/``approved_at`` are never form fields)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="floating_holiday_elections")
    holiday = models.ForeignKey(
        "hrm.PublicHoliday", on_delete=models.CASCADE, related_name="floating_elections")
    policy = models.ForeignKey(
        "hrm.HolidayPolicy", on_delete=models.SET_NULL, null=True, blank=True, related_name="elections",
        help_text="The governing policy (auto-resolved from the employee if left blank).")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_on = models.DateField(default=timezone.localdate)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_floating_holiday_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_on"]
        unique_together = ("tenant", "employee", "holiday")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_fhe_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_fhe_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.holiday_id and not self.holiday.is_optional:
            raise ValidationError({"holiday": "Only optional (floating) holidays can be elected."})
        if self.employee_id and self.holiday_id:
            # ``tenant`` isn't set on the instance during ModelForm validation on create
            # (the view assigns it after ``is_valid()``), so derive it from the employee — an
            # election always shares its employee's tenant. Without this the quota count below
            # would filter on ``tenant_id=None`` and silently pass.
            tenant_id = self.tenant_id or self.employee.tenant_id
            # Resolve + STORE the governing policy here so save() doesn't re-scan for it — the normal
            # ModelForm flow runs clean() before save(), so save()'s auto-resolve becomes a no-op.
            # (A direct .save() that bypasses clean(), e.g. the seeder, still auto-resolves in save().)
            if self.policy_id is None:
                self.policy = HolidayPolicy.for_employee(self.employee)
            policy = self.policy
            if policy is not None and policy.floating_holiday_quota:
                year = self.holiday.date.year
                taken = (FloatingHolidayElection.objects
                         .filter(tenant_id=tenant_id, employee_id=self.employee_id,
                                 status__in=("pending", "approved"), holiday__date__year=year)
                         .exclude(pk=self.pk).count())
                if taken + 1 > policy.floating_holiday_quota:
                    raise ValidationError({"holiday":
                        f"Quota exceeded — {policy.name} allows {policy.floating_holiday_quota} "
                        f"floating holiday(s) in {year}."})

    def save(self, *args, **kwargs):
        # Auto-resolve the governing policy from the employee when not explicitly chosen.
        if self.policy_id is None and self.employee_id:
            self.policy = HolidayPolicy.for_employee(self.employee)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} · {self.holiday} · {self.get_status_display()}"
