"""HRM 3.1 Employee Management — EmployeeLifecycleEvents models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeManagement.Lifecycle import LIFECYCLE_EVENT_TYPE_CHOICES
from apps.hrm.models.EmployeeManagement.Lifecycle import LIFECYCLE_EVENT_TYPE_CHOICES


class EmployeeLifecycleEvent(TenantNumbered):
    """An append-only, dated record of a single job-change event (3.1 Employee Lifecycle) — hire,
    confirmation, transfer, promotion, salary revision, separation, etc. Populate only the from→to
    fields relevant to the event type. v1 records the timeline; it does NOT auto-mutate
    ``core.Employment``/``EmployeeProfile`` (a deferred bidirectional-sync enhancement)."""

    NUMBER_PREFIX = "ELC"

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="lifecycle_events")
    event_type = models.CharField(max_length=30, choices=LIFECYCLE_EVENT_TYPE_CHOICES, default="other")
    effective_date = models.DateField()
    reason = models.TextField(blank=True)
    # From / To capture — all nullable/blank; fill only what the event changes.
    from_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_location = models.CharField(max_length=255, blank=True)
    to_location = models.CharField(max_length=255, blank=True)
    from_job_title = models.CharField(max_length=255, blank=True)
    to_job_title = models.CharField(max_length=255, blank=True)
    from_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    to_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    from_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_employee_type = models.CharField(max_length=20, blank=True)
    to_employee_type = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_initiated_lifecycle_events", editable=False)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_date"], name="hrm_elc_tenant_emp_date_idx"),
            models.Index(fields=["tenant", "event_type"], name="hrm_elc_tenant_type_idx"),
            models.Index(fields=["tenant", "employee", "event_type"], name="hrm_elc_tenant_emp_type_idx"),
            models.Index(fields=["tenant", "effective_date"], name="hrm_elc_tenant_effdate_idx"),
        ]

    def __str__(self):
        name = self.employee.name if self.employee_id else "—"
        return f"{self.number} · {name} — {self.get_event_type_display()} ({self.effective_date})"
