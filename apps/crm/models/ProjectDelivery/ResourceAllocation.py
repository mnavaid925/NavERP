"""CRM 1.8 Project & Delivery Management — ResourceAllocation models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ---- 1.8 Resource Allocation — planned capacity bookings + a workload board -------------
class ResourceAllocation(TenantNumbered):
    """A planned capacity booking (1.8 Resource Allocation): assigns a person to a project for
    ``hours_per_week`` over a date window. The workload board aggregates these (planned) against
    logged ``Timesheet`` hours (actual) per person to flag overbooked vs. free capacity. People are
    keyed on ``User`` (matching ``Timesheet.employee`` / ``CrmMilestone.assignee``) so both sides of
    the workload join share one key — a future pass could move to HRM ``EmployeeProfile``."""

    NUMBER_PREFIX = "RA"

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="allocations")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_allocations")
    role = models.CharField(max_length=80, blank=True, help_text="e.g. Developer, Project Manager, QA")
    hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for an ongoing assignment.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "assignee"], name="crm_ra_tnt_assignee_idx"),
            models.Index(fields=["tenant", "project"], name="crm_ra_tnt_project_idx"),
            # The workload board filters by status + a start/end date window (performance-review).
            models.Index(fields=["tenant", "status"], name="crm_ra_tnt_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="crm_ra_tnt_start_idx"),
            models.Index(fields=["tenant", "end_date"], name="crm_ra_tnt_end_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.role or 'Resource'}"

    def overlap_hours(self, win_start, win_end):
        """Planned hours for this booking within [win_start, win_end], prorated by overlapping days.
        A null ``end_date`` means ongoing → clamped to the window end. Cancelled bookings count 0."""
        if self.status == "cancelled":
            return Decimal("0")
        a_end = self.end_date or win_end  # null = ongoing
        ov_start = max(self.start_date, win_start)
        ov_end = min(a_end, win_end)
        if ov_end < ov_start:
            return Decimal("0")
        days = (ov_end - ov_start).days + 1
        return (Decimal(self.hours_per_week or 0) * Decimal(days) / Decimal(7)).quantize(Decimal("0.01"))
