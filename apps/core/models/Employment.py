"""core — Employment models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Employment(models.Model):
    """HR's view of a Party-with-an-employee-role: job, department, manager."""

    STATUS_CHOICES = [("active", "Active"), ("on_leave", "On Leave"), ("terminated", "Terminated")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="employments", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="employments")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="employments")
    manager = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_employments")
    job_title = models.CharField(max_length=255, blank=True)
    hired_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        ordering = ["party__name"]
        indexes = [
            # HRM employee_list filters by employment status (employment__status) per tenant.
            models.Index(fields=["tenant", "status"], name="core_emp_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.party} — {self.job_title}" if self.job_title else str(self.party)
