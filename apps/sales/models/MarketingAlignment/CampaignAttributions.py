"""Sales 8.13 — `CampaignAttribution` (`ATR-`), the conversion-credit assignment.

A campaign attribution is the credit a given MODEL gives a given touchpoint. The models are the
rule-based set every commercial platform ships -- first touch, last touch, linear, time decay and
position-based (U-shaped) -- plus a `custom` escape hatch for a hand-agreed percentage.

The separation from `AttributionTouchpoint` is the whole point: the touch ledger is DATA (what
happened), the credit is a COMPUTATION over that data (what a model says it was worth). Keeping
them in different tables is what lets a team run first-touch and last-touch side by side over the
same journey, and what lets a custom credit be applied without re-typing the journey.

One credit per (touchpoint, model) is enforced by a database constraint, so the two models can
never silently overwrite each other.

OWNERSHIP (L36/L37): the campaign, lead and opportunity behind a credit are reached through the
touchpoint -- no campaign, lead or opportunity table is declared here.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

ATTRIBUTION_MODEL_CHOICES = [
    ("first_touch", "First Touch"),
    ("last_touch", "Last Touch"),
    ("linear", "Linear (Multi-Touch)"),
    ("time_decay", "Time Decay (Multi-Touch)"),
    ("position_based", "Position-Based / U-Shaped"),
    ("custom", "Custom Model"),
]

ATTRIBUTION_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("computed", "Computed"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class CampaignAttribution(TenantNumbered):
    """Conversion credit assigned to one touchpoint under one attribution model (8.13)."""

    NUMBER_PREFIX = "ATR"

    touchpoint = models.ForeignKey(
        "sales.AttributionTouchpoint",
        on_delete=models.CASCADE,
        related_name="attributions",
    )
    attribution_model = models.CharField(
        max_length=30,
        choices=ATTRIBUTION_MODEL_CHOICES,
        default="first_touch",
        db_index=True,
    )
    credit_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Share of conversion credit, 0-100. A custom model sets this by hand.",
    )
    attributed_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    attributed_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        max_length=15,
        choices=ATTRIBUTION_STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    computed_on = models.DateField(default=timezone.localdate)
    computed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_campaign_attributions",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-computed_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_atr_tenant_number_uniq",
            ),
            # One credit per touch per model. This is what makes two models comparable
            # side by side: without it a second model would overwrite the first.
            models.UniqueConstraint(
                fields=["tenant", "touchpoint", "attribution_model"],
                name="sales_atr_tp_model_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status"],
                name="sales_atr_tnt_status_idx",
            ),
            models.Index(
                fields=["tenant", "attribution_model"],
                name="sales_atr_tnt_model_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_attribution_model_display()} · {self.credit_pct}%"

    @property
    def campaign(self):
        """The source campaign, reached through the touchpoint."""
        return self.touchpoint.campaign if self.touchpoint_id else None

    @property
    def lead(self):
        return self.touchpoint.lead if self.touchpoint_id else None

    @property
    def opportunity(self):
        return self.touchpoint.opportunity if self.touchpoint_id else None

    @property
    def roi_pct(self):
        """Return on investment on the credited revenue, or None when no cost is recorded."""
        cost = Decimal(self.attributed_cost or 0)
        if not cost:
            return None
        return (Decimal(self.attributed_revenue or 0) - cost) / cost * 100

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id and self.touchpoint_id:
            if getattr(self.touchpoint, "tenant_id", None) != tenant_id:
                raise ValidationError(
                    {"touchpoint": "Touchpoint must belong to the same workspace."}
                )
        if tenant_id and self.computed_by_id:
            if getattr(self.computed_by, "tenant_id", None) != tenant_id:
                raise ValidationError(
                    {"computed_by": "Computed by must belong to the same workspace."}
                )
        if self.credit_pct is not None and self.credit_pct > Decimal("100"):
            raise ValidationError({"credit_pct": "Credit cannot exceed 100%."})
