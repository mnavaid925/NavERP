"""Projects 7.13 Agile & Scrum Management — Sprint [SPT-].

Realizes NavERP 7.13 bullet 1 Sprint Planning & Backlog Grooming,
and bullet 2 Sprint Execution & Daily Standups.
"""
from django.utils import timezone

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class Sprint(TenantNumbered):
    NUMBER_PREFIX = "SPT"

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="sprints",
        help_text="Project this sprint belongs to.",
    )
    name = models.CharField(max_length=255)
    goal = models.TextField(blank=True, help_text="Sprint goal agreed by the team.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="planning")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    committed_points = models.PositiveIntegerField(
        default=0,
        help_text="Committed story points snapshot taken when sprint is activated.",
    )
    scrum_master = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scrum_master_sprints",
    )
    standup_notes = models.TextField(
        blank=True,
        help_text="Daily standup notes, impediments summary, and progress log.",
    )
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="spt_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="spt_tnt_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="spt_tnt_sdate_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def total_points(self):
        """Sum of story points assigned to this sprint."""
        pts = self.tasks.aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def completed_points(self):
        """Sum of story points for tasks marked done in this sprint."""
        pts = self.tasks.filter(status="done").aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def remaining_points(self):
        """Remaining uncompleted story points in this sprint."""
        return max(0, self.total_points - self.completed_points)

    @property
    def completion_rate(self):
        """Completion percentage based on story points."""
        tot = self.total_points
        if tot <= 0:
            return 0
        return round((self.completed_points / tot) * 100, 1)

    @property
    def task_count(self):
        """Total number of tasks in sprint."""
        return self.tasks.count()

    @property
    def completed_task_count(self):
        """Total number of completed tasks in sprint."""
        return self.tasks.filter(status="done").count()

    @property
    def is_overdue(self):
        """True if sprint end date has passed and sprint is still active."""
        if self.end_date and self.status == "active":
            return self.end_date < timezone.localdate()
        return False
