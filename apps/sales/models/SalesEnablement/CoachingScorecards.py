"""Sales 8.9 — `CoachingScorecard` (`CSC-`), rubric-based manager coaching and conversation intelligence evaluations.

Anchors to `crm.CommunicationLog` (CRM 1.5) and optionally `sales.ActivityLog` (Sales 8.8).
Evaluates 4 core competencies (Discovery, Value Proposition, Objection Handling, Next Steps),
captures CI talk/listen ratios, call sentiment, transcript highlights, and structured manager critique.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

SCORECARD_STATUS_CHOICES = [
    ("draft", "Draft Evaluation"),
    ("shared", "Shared with Rep"),
    ("acknowledged", "Acknowledged by Rep"),
]

CALL_SENTIMENT_CHOICES = [
    ("positive", "Positive / Enthusiastic"),
    ("neutral", "Neutral / Professional"),
    ("skeptical", "Skeptical / Challenging"),
    ("negative", "Negative / Frustrated"),
]


class CoachingScorecard(TenantNumbered):
    NUMBER_PREFIX = "CSC"

    communication_log = models.ForeignKey(
        "crm.CommunicationLog",
        on_delete=models.CASCADE,
        related_name="coaching_scorecards",
        help_text="The evaluated call, meeting, or email interaction.",
    )
    activity_log = models.ForeignKey(
        "sales.ActivityLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coaching_scorecards",
        help_text="Optional Sales 8.8 activity attribution record.",
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="given_coaching_scorecards",
    )
    coachee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_coaching_scorecards",
    )
    recording_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Link to call recording video/audio (Zoom, Teams, Loom, Gong).",
    )
    discovery_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Discovery & Pain Diagnosis (1=Poor, 5=Exceptional).",
    )
    value_prop_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Value Proposition & Business Case Articulation (1-5).",
    )
    objection_handling_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Objection Handling & Empathy (1-5).",
    )
    next_steps_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Deal Momentum, Mutual Action Plan & Next Steps (1-5).",
    )
    overall_score = models.PositiveSmallIntegerField(
        default=60,
        editable=False,
        help_text="Composite competency percentage score (0-100%).",
    )
    talk_listen_ratio_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Conversation Intelligence: Rep talk time % (benchmark 40-55%).",
    )
    call_sentiment = models.CharField(
        max_length=20,
        choices=CALL_SENTIMENT_CHOICES,
        default="neutral",
    )
    transcript_summary = models.TextField(
        blank=True,
        help_text="Key conversation moments, customer quotes, and discussed themes.",
    )
    key_strengths = models.TextField(
        blank=True,
        help_text="What the rep executed effectively.",
    )
    areas_for_improvement = models.TextField(
        blank=True,
        help_text="Constructive coaching critique and missed opportunities.",
    )
    action_items = models.TextField(
        blank=True,
        help_text="Agreed coaching goals, roleplay drills, or follow-ups.",
    )
    review_status = models.CharField(
        max_length=20,
        choices=SCORECARD_STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    evaluated_on = models.DateField(default=timezone.now)

    class Meta:
        ordering = ["-evaluated_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_csc_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "coachee", "review_status"],
                name="sales_csc_coachee_stat_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.coachee} ({self.overall_score}%) [{self.get_review_status_display()}]"

    def clean(self):
        super().clean()
        for score_name, score_val in [
            ("discovery_score", self.discovery_score),
            ("value_prop_score", self.value_prop_score),
            ("objection_handling_score", self.objection_handling_score),
            ("next_steps_score", self.next_steps_score),
        ]:
            if score_val < 1 or score_val > 5:
                raise ValidationError({score_name: "Rubric score must be between 1 and 5."})

        if self.talk_listen_ratio_percent is not None:
            if self.talk_listen_ratio_percent < 0 or self.talk_listen_ratio_percent > 100:
                raise ValidationError({"talk_listen_ratio_percent": "Talk ratio percentage must be between 0% and 100%."})

        if self.communication_log_id and self.tenant_id:
            if getattr(self.communication_log, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"communication_log": "Communication log must belong to the same workspace."})

        if self.activity_log_id and self.tenant_id:
            if getattr(self.activity_log, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"activity_log": "Activity log must belong to the same workspace."})

    def save(self, *args, **kwargs):
        rubric_sum = (
            self.discovery_score
            + self.value_prop_score
            + self.objection_handling_score
            + self.next_steps_score
        )
        self.overall_score = int(round((rubric_sum / 20.0) * 100))
        return super().save(*args, **kwargs)
