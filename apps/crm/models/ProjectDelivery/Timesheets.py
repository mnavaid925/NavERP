"""CRM 1.8 Project & Delivery Management — Timesheets models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Timesheet(TenantNumbered):
    """A billable/non-billable time entry against a project (1.8)."""

    NUMBER_PREFIX = "TS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="timesheets")
    milestone = models.ForeignKey("crm.CrmMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="timesheets")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_timesheets")
    client = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_timesheets")
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    is_billable = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approved_timesheets")

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project", "date"], name="crm_ts_tnt_prj_date_idx"),
            models.Index(fields=["tenant", "employee", "date"], name="crm_ts_tnt_emp_date_idx"),
            models.Index(fields=["tenant", "status"], name="crm_ts_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.hours}h"
