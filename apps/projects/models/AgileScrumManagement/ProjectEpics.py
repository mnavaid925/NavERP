"""Projects 7.13 Agile & Scrum Management — ProjectEpic [EPC-].

Realizes NavERP 7.13 bullet 4 Epic & Feature Management:
Hierarchical story organization, cross-sprint feature tracking, and progress rollups.
"""
from django.core.validators import RegexValidator

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models

HEX_COLOR_VALIDATOR = RegexValidator(
    r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$",
    "Enter a valid hex color code (e.g. #3b82f6 or #fff).",
)


class ProjectEpic(TenantNumbered):
    NUMBER_PREFIX = "EPC"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="epics",
        help_text="Project this epic belongs to.",
    )
    name = models.CharField(max_length=255)
    summary = models.TextField(blank=True, help_text="High-level feature summary and scope.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_epics",
        help_text="Product owner / lead responsible for this epic.",
    )
    target_start = models.DateField(null=True, blank=True)
    target_end = models.DateField(null=True, blank=True)
    color_code = models.CharField(
        max_length=7,
        default="#3b82f6",
        validators=[HEX_COLOR_VALIDATOR],
        help_text="Hex color code for visual badges.",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="epc_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="epc_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def total_points(self):
        """Sum of story points across member tasks."""
        pts = self.tasks.aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def completed_points(self):
        """Sum of story points for completed tasks in this epic."""
        pts = self.tasks.filter(status="done").aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def progress_percent(self):
        """Dynamic completion rate based on points."""
        tot = self.total_points
        if tot <= 0:
            tc = self.task_count
            if tc == 0:
                return 0
            return round((self.done_task_count / tc) * 100, 1)
        return round((self.completed_points / tot) * 100, 1)

    @property
    def task_count(self):
        """Total number of tasks belonging to this epic."""
        return self.tasks.count()

    @property
    def done_task_count(self):
        """Number of done tasks belonging to this epic."""
        return self.tasks.filter(status="done").count()
