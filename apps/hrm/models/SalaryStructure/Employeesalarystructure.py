"""HRM 3.13 Salary Structure — Employeesalarystructure models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class EmployeeSalaryStructure(TenantNumbered):
    """An effective-dated assignment of a salary structure / CTC to an employee (3.13) — ``ESS-#####``.
    At most one ``active`` assignment per employee (enforced in ``clean()``)."""

    NUMBER_PREFIX = "ESS"

    STATUS_CHOICES = [
        ("active", "Active"),
        ("superseded", "Superseded"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="salary_structures")
    template = models.ForeignKey("hrm.SalaryStructureTemplate", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employee_assignments")
    annual_ctc_amount = models.DecimalField(max_digits=14, decimal_places=2,
        help_text="The employee's actual assigned annual CTC (may differ from the template default).")
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_from"], name="hrm_ess_tenant_emp_efrom_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ess_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Effective-to date cannot be before the effective-from date."})
        # At most one active assignment per employee. Derive the tenant from the employee — the
        # instance's own tenant is unset during ModelForm validation on create (mirrors
        # FloatingHolidayElection.clean() from 3.12).
        if self.status == "active" and self.employee_id:
            clash = (EmployeeSalaryStructure.objects
                     .filter(tenant_id=self.employee.tenant_id, employee_id=self.employee_id, status="active")
                     .exclude(pk=self.pk))
            if clash.exists():
                raise ValidationError({"status": "This employee already has an active salary structure — "
                                       "mark the existing one superseded first."})

    def __str__(self):
        return f"{self.number} · {self.employee}"
