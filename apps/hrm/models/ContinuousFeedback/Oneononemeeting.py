"""HRM 3.20 Continuous Feedback — Oneononemeeting models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class OneOnOneMeeting(TenantNumbered):
    """A manager↔employee 1:1 meeting shell (3.20) — scheduling + a shared agenda/notes + a
    manager-only private-notes field. ``manager_private_notes`` is a direct clone of
    ``PerformanceReview.private_notes``: never rendered on the employee-facing detail. Meeting
    history is just the ordered queryset (no extra table — mirrors how ``GoalCheckIn`` rows ARE a
    KeyResult's history)."""

    NUMBER_PREFIX = "O2O"

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                related_name="oneonones_as_manager")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="oneonones_as_employee")
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="scheduled")
    agenda = models.TextField(blank=True, help_text="Shared talking points — editable by either party pre-meeting.")
    shared_notes = models.TextField(blank=True, help_text="Visible to both the manager and the employee.")
    manager_private_notes = models.TextField(
        blank=True, help_text="Manager-only — NEVER rendered on the employee-facing view.")
    related_objective = models.ForeignKey("hrm.Objective", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="oneonones",
                                          help_text="Optional 3.18 goal this 1:1 is anchored to.")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-scheduled_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "manager"], name="hrm_o2o_tenant_mgr_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_o2o_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_o2o_tenant_status_idx"),
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_o2o_tenant_sched_idx"),
        ]

    def clean(self):
        if self.manager_id and self.employee_id and self.manager_id == self.employee_id:
            raise ValidationError({"employee": "A 1:1 needs two distinct people."})

    @property
    def open_action_item_count(self):
        return self.action_items.filter(status="open").count()

    def __str__(self):
        m = self.manager.party.name if self.manager_id else "?"
        e = self.employee.party.name if self.employee_id else "?"
        stamp = f" ({self.scheduled_at:%Y-%m-%d})" if self.scheduled_at else ""
        return f"{self.number} · {m} & {e}{stamp}"
