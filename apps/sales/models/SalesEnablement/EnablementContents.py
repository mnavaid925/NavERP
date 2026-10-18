"""Sales 8.9 — `EnablementContent` (`ECN-`), central sales collateral repository.

Supports battle cards, pitch decks, case studies, product sheets, whitepapers, demo scripts,
email templates, and proposal snippets. Files are anchored to `core.Document` or external cloud URLs
(Google Slides, Loom, Notion, etc.). Battlecards link to 8.2 `CompetitorProfile` by FK.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

CONTENT_TYPE_CHOICES = [
    ("battle_card", "Battle Card"),
    ("pitch_deck", "Pitch Deck"),
    ("case_study", "Case Study"),
    ("product_sheet", "Product One-Pager"),
    ("whitepaper", "Whitepaper / Research"),
    ("demo_script", "Demo Script / Flow"),
    ("email_template", "Outreach Email Template"),
    ("proposal_template", "Proposal Snippet"),
]

TARGET_STAGE_CHOICES = [
    ("all", "All Stages"),
    ("prospecting", "Prospecting / Discovery"),
    ("qualification", "Qualification"),
    ("demo_eval", "Demo & Solution Evaluation"),
    ("proposal_neg", "Proposal & Negotiation"),
    ("closing", "Closing"),
    ("post_sale", "Expansion & Retention"),
]

TARGET_PERSONA_CHOICES = [
    ("all", "All Personas"),
    ("c_level", "Executive / C-Suite"),
    ("vp_director", "VP / Director"),
    ("manager", "Functional Manager"),
    ("technical_buyer", "IT & Technical Buyer"),
    ("end_user", "End-User Specialist"),
    ("procurement", "Procurement / Legal"),
]


class EnablementContent(TenantNumbered):
    NUMBER_PREFIX = "ECN"

    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    content_type = models.CharField(
        max_length=30,
        choices=CONTENT_TYPE_CHOICES,
        default="battle_card",
        db_index=True,
    )
    document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_enablement_contents",
    )
    external_url = models.URLField(max_length=500, blank=True)
    competitor = models.ForeignKey(
        "sales.CompetitorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enablement_contents",
    )
    target_stage = models.CharField(
        max_length=30,
        choices=TARGET_STAGE_CHOICES,
        default="all",
    )
    target_persona = models.CharField(
        max_length=30,
        choices=TARGET_PERSONA_CHOICES,
        default="all",
    )
    pipeline_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enablement_contents",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_enablement_contents",
    )
    tags = models.CharField(max_length=255, blank=True)
    version = models.CharField(max_length=20, default="1.0")
    is_client_facing = models.BooleanField(
        default=False,
        help_text="True if safe to share directly with customer/prospect.",
    )
    is_active = models.BooleanField(default=True)
    expires_on = models.DateField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    share_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-updated_at", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_ecn_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "content_type", "is_active"],
                name="sales_ecn_type_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_content_type_display()})"

    def clean(self):
        super().clean()
        if not self.document_id and not self.external_url and not self.description:
            raise ValidationError(
                "Provide a document file attachment, an external cloud URL, or a text description/script."
            )
        if self.competitor_id and self.tenant_id:
            if getattr(self.competitor, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"competitor": "Competitor profile must belong to the same workspace."})
        if self.document_id and self.tenant_id:
            if getattr(self.document, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"document": "Document must belong to the same workspace."})
        if self.pipeline_stage_id and self.tenant_id:
            if getattr(self.pipeline_stage, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"pipeline_stage": "Pipeline stage must belong to the same workspace."})

    def record_view(self):
        type(self).objects.filter(pk=self.pk).update(view_count=models.F("view_count") + 1)

    def record_share(self):
        type(self).objects.filter(pk=self.pk).update(share_count=models.F("share_count") + 1)
