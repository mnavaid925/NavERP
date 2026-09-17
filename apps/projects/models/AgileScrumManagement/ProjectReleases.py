"""Projects 7.13 Agile & Scrum Management — ProjectRelease [REL-].

Realizes NavERP 7.13 bullet 3 Release & Version Planning:
Release trains, feature flags, and version roadmap visualization.
"""
from django.utils import timezone

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectRelease(TenantNumbered):
    NUMBER_PREFIX = "REL"

    STATUS_CHOICES = [
        ("unreleased", "Unreleased"),
        ("in_progress", "In Progress"),
        ("released", "Released"),
        ("archived", "Archived"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="releases",
        help_text="Project this release belongs to.",
    )
    name = models.CharField(max_length=255)
    version_tag = models.CharField(
        max_length=50, help_text="Version identifier (e.g. v1.0.0, 2026.3)."
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="unreleased"
    )
    release_date = models.DateField(null=True, blank=True)
    release_notes = models.TextField(blank=True, help_text="Release notes and changelog.")
    feature_flags = models.TextField(
        blank=True,
        help_text="Feature flags or toggles enabled in this release train.",
    )
    released_at = models.DateTimeField(null=True, blank=True, editable=False)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="published_releases",
    )

    class Meta:
        ordering = ["-release_date", "-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="rel_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="rel_tnt_status_idx"),
            models.Index(fields=["tenant", "version_tag"], name="rel_tnt_version_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.version_tag})"

    @property
    def total_stories(self):
        """Count of tasks mapped to this release."""
        return self.tasks.count()

    @property
    def completed_stories(self):
        """Count of done tasks mapped to this release."""
        return self.tasks.filter(status="done").count()

    @property
    def total_points(self):
        """Total points planned in this release."""
        pts = self.tasks.aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def completed_points(self):
        """Delivered points in this release."""
        pts = self.tasks.filter(status="done").aggregate(s=models.Sum("story_points"))["s"]
        return pts or 0

    @property
    def progress_percent(self):
        """Completion progress percentage."""
        tot = self.total_points
        if tot <= 0:
            ts = self.total_stories
            if ts == 0:
                return 0
            return round((self.completed_stories / ts) * 100, 1)
        return round((self.completed_points / tot) * 100, 1)

    @property
    def is_overdue(self):
        """True if planned release date has passed and release is not published."""
        if self.release_date and self.status in ("unreleased", "in_progress"):
            return self.release_date < timezone.localdate()
        return False
