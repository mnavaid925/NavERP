"""Projects 7.13 Agile & Scrum Management — SprintRetrospective [RET-].

Realizes NavERP 7.13 bullet 5 Retrospectives & Team Health:
Sprint retrospective boards, action item tracking, and team sentiment surveys.
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class SprintRetrospective(TenantNumbered):
    NUMBER_PREFIX = "RET"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open / In Review"),
        ("closed", "Closed"),
    ]

    sprint = models.ForeignKey(
        "projects.Sprint",
        on_delete=models.CASCADE,
        related_name="retrospectives",
        help_text="Sprint being evaluated.",
    )
    conducted_date = models.DateField(default=timezone.localdate)
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_retrospectives",
        help_text="Facilitator / Scrum Master who ran the retro.",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    sentiment_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("3.0"),
        validators=[
            MinValueValidator(Decimal("1.0")),
            MaxValueValidator(Decimal("5.0")),
        ],
        help_text="Average team sentiment / health score (1.0 = Very Negative to 5.0 = Very Positive).",
    )
    what_went_well = models.TextField(
        blank=True, help_text="Positive highlights, victories, and good practices."
    )
    what_needs_improvement = models.TextField(
        blank=True, help_text="Areas to improve, friction points, and bottlenecks."
    )
    action_items = models.TextField(
        blank=True, help_text="Agreed improvement actions, owners, and commitments."
    )
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-conducted_date", "-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "sprint"], name="ret_tnt_sprint_idx"),
            models.Index(fields=["tenant", "status"], name="ret_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — Retro for {self.sprint.name}"
