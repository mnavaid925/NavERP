"""Projects 7.11 Time & Attendance Tracking — TimeActivityCode [TAC-].

Activity codes categorize time logs into structured work categories and drive the
overhead allocation analytics on the Time Reporting & Utilization dashboard.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class TimeActivityCode(TenantNumbered):
    """Activity code defining standard task types, overhead classification, and default billing status."""

    NUMBER_PREFIX = "TAC"

    CATEGORY_CHOICES = [
        ("direct_project", "Direct Project Work"),
        ("client_service", "Client Consulting & Support"),
        ("internal_overhead", "Internal Overhead"),
        ("general_admin", "General Administrative"),
        ("training", "Training & Professional Development"),
        ("research_dev", "Internal R&D"),
    ]

    code = models.CharField(
        max_length=30,
        help_text="Unique short code (e.g. DEV, QA, PM, MTG, ADMIN, TRN).")
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name of the activity.")
    category = models.CharField(
        max_length=24,
        choices=CATEGORY_CHOICES,
        default="direct_project",
        help_text="Overhead allocation category driving utilization reporting.")
    is_billable_default = models.BooleanField(
        default=True,
        help_text="Default billable flag when this code is selected in time entries.")
    is_active = models.BooleanField(
        default=True,
        help_text="Active codes appear in time logging dropdowns.")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("tenant", "number"), ("tenant", "code"))
        indexes = [
            models.Index(fields=["tenant", "category"], name="tac_tnt_category_idx"),
            models.Index(fields=["tenant", "is_active"], name="tac_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
