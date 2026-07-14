"""CRM 1.8 Project & Delivery Management — Milestones models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class CrmMilestone(TenantNumbered):
    """A milestone/task within a project (1.8). ``completed_at`` is system-set on done."""

    NUMBER_PREFIX = "MS"

    KIND_CHOICES = [("milestone", "Milestone"), ("task", "Task")]
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("blocked", "Blocked"),
    ]

    project = models.ForeignKey("crm.CrmProject", on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="task")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="not_started")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_milestones")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set
    order = models.PositiveSmallIntegerField(default=0)
    parent = models.ForeignKey("crm.CrmMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="subtasks")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "due_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project", "status"], name="crm_ms_tnt_prj_status_idx"),
            models.Index(fields=["tenant", "due_date"], name="crm_ms_tnt_due_idx"),
        ]

    def save(self, *args, **kwargs):
        # System-set completed_at: stamp on first completion, clear if re-opened.
        if self.status == "completed":
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"
