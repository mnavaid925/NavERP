"""Projects 7.14 Client & External Collaboration — VendorHandoff [VHD-].

External vendor / subcontractor coordination: task assignments, deliverable handoffs,
acceptance/rejection workflows, and vendor scorecard ratings (1–5).
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.projects.models._base import TenantNumbered


class VendorHandoff(TenantNumbered):
    NUMBER_PREFIX = "VHD"

    STATUS_CHOICES = [
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("delivered", "Delivered"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="vendor_handoffs",
    )
    vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="project_vendor_handoffs",
    )
    task = models.ForeignKey(
        "projects.ProjectTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_handoffs",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    handoff_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="assigned")
    deliverable_link = models.URLField(blank=True, help_text="External repository, design file, or deliverable URL")
    scorecard_rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Vendor deliverable rating on a 1–5 scale",
    )
    performance_notes = models.TextField(blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    deficiency_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="vhd_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="vhd_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.vendor.name})"
