"""HRM 3.9 Attendance Management — Shiftassignment models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ShiftAssignment(TenantOwned):
    """Assigns a ``Shift`` to an employee for an effective date range (3.9)."""

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="shift_assignments")
    shift = models.ForeignKey("hrm.Shift", on_delete=models.CASCADE, related_name="assignments")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("tenant", "employee", "effective_from")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_from"], name="hrm_sa_tenant_emp_from_idx"),
            models.Index(fields=["tenant", "shift"], name="hrm_sa_tenant_shift_idx"),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "End date cannot be before the start date."})

    def __str__(self):
        return f"{self.employee} → {self.shift} from {self.effective_from}"
