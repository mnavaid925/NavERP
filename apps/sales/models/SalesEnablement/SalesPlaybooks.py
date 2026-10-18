"""Sales 8.9 — `SalesPlaybook` (`SPB-`), step-by-step selling motions and tactical sales playbooks.

Supports new business, expansion, renewal, competitive displacement, and partner motions.
Includes verbatim talk tracks, discovery diagnostic questions, objection scripts, dos & don'ts,
and stage exit criteria aligned to 8.2 opportunity pipelines.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

SELLING_MOTION_CHOICES = [
    ("new_business", "New Business (Land)"),
    ("expansion", "Account Expansion (Upsell/Cross-sell)"),
    ("renewal", "Contract Renewal"),
    ("competitive_displacement", "Competitive Takeout / Displacement"),
    ("partner_co_selling", "Partner Co-Selling"),
]

PLAYBOOK_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("under_review", "Under Review"),
    ("archived", "Archived"),
]


class SalesPlaybook(TenantNumbered):
    NUMBER_PREFIX = "SPB"

    name = models.CharField(max_length=150, db_index=True)
    summary = models.TextField(blank=True)
    motion_type = models.CharField(
        max_length=30,
        choices=SELLING_MOTION_CHOICES,
        default="new_business",
        db_index=True,
    )
    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_playbooks",
    )
    status = models.CharField(
        max_length=20,
        choices=PLAYBOOK_STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    target_audience = models.CharField(max_length=200, blank=True)
    discovery_questions = models.TextField(
        blank=True,
        help_text="Key diagnostic discovery questions to qualify and probe customer pain.",
    )
    talk_tracks = models.TextField(
        blank=True,
        help_text="Recommended pitch phrasing, value messaging, and story anchors.",
    )
    objection_scripts = models.TextField(
        blank=True,
        help_text="Anticipated customer objections and battle-tested rebuttal scripts.",
    )
    dos_and_donts = models.TextField(
        blank=True,
        help_text="Best practices: what reps should do vs. avoid during this motion.",
    )
    exit_criteria = models.TextField(
        blank=True,
        help_text="Verifiable deal criteria required to advance or exit this stage.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_sales_playbooks",
    )
    version = models.CharField(max_length=20, default="1.0")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_spb_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "motion_type", "status"],
                name="sales_spb_motion_stat_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_motion_type_display()})"

    def clean(self):
        super().clean()
        if self.pipeline_id and self.tenant_id:
            if getattr(self.pipeline, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"pipeline": "Associated pipeline must belong to the same workspace."})
