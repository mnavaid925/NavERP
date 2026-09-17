"""Projects 7.13 Agile & Scrum Management — SprintImpediment [IMP-].

Realizes NavERP 7.13 bullet 2 Sprint Execution & Daily Standups:
Impediment tracking and blocker resolution workflows.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class SprintImpediment(TenantNumbered):
    NUMBER_PREFIX = "IMP"

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    sprint = models.ForeignKey(
        "projects.Sprint",
        on_delete=models.CASCADE,
        related_name="impediments",
        help_text="Sprint blocked by this impediment.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(
        help_text="Detailed description of the obstacle or blocker."
    )
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_impediments",
        help_text="Person assigned to resolve this impediment.",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolution_notes = models.TextField(
        blank=True,
        help_text="How this impediment was unblocked or resolved.",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "sprint"], name="imp_tnt_sprint_idx"),
            models.Index(fields=["tenant", "status"], name="imp_tnt_status_idx"),
            models.Index(fields=["tenant", "severity"], name="imp_tnt_severity_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_active(self):
        return self.status != "resolved"
