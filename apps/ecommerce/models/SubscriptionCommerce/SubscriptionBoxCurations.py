from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class SubscriptionBoxCuration(TenantNumbered):
    NUMBER_PREFIX = "ESBX"

    name = models.CharField(
        max_length=150,
        help_text="Curated box release title e.g. 'October Artisan Roast', 'Winter Hydration Box'",
    )
    code = models.SlugField(
        max_length=60,
        help_text="Machine identifier slug for curation cycle",
    )
    plan = models.ForeignKey(
        "ecommerce.SubscriptionPlan",
        on_delete=models.CASCADE,
        related_name="curations",
        help_text="Governing curated box subscription plan",
    )
    cycle_identifier = models.CharField(
        max_length=50,
        help_text="Cycle cadence tag e.g. '2026-11', 'Q4-2026', 'Box-Vol-12'",
    )
    theme_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Marketing headline or unboxing theme name",
    )
    curation_notes = models.TextField(
        blank=True,
        help_text="Detailed tasting notes, inclusion story, or unboxing guide",
    )
    primary_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="curation_primaries",
        help_text="Lead featured product or centerpiece SKU in this curation",
    )
    has_surprise_item = models.BooleanField(
        default=False,
        help_text="Flag indicating mystery / surprise bonus item is included in this cycle",
    )
    surprise_item_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret or internal description of bonus inclusion (e.g. 'Limited Edition Enamel Pin')",
    )
    preference_tag = models.CharField(
        max_length=100,
        blank=True,
        help_text="Subscriber preference filter match e.g. 'Dark Roast', 'Gluten Free', 'Sensitive Skin'",
    )
    start_date = models.DateField(
        help_text="Effective start date when this curation is actively shipped",
    )
    end_date = models.DateField(
        help_text="End date when this cycle rotates out to the next curation",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active curations are eligible for upcoming shipment allocation",
    )

    class Meta:
        ordering = ["-start_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esbx_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "plan", "cycle_identifier"],
                name="ecommerce_esbx_plan_cycle_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "start_date", "end_date"],
                name="idx_esbx_ten_act_dates",
            ),
        ]

    def clean(self):
        super().clean()
        if self.code:
            self.code = slugify(self.code)
        elif self.name and not self.code:
            self.code = slugify(self.name)

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date cannot be earlier than start date."})

        # Tenant cross-reference validation
        if self.plan_id and self.plan and self.plan.tenant_id != self.tenant_id:
            raise ValidationError({"plan": "Subscription plan belongs to another workspace."})
        if self.primary_product_id and self.primary_product and self.primary_product.tenant_id != self.tenant_id:
            raise ValidationError({"primary_product": "Primary product belongs to another workspace."})

    def __str__(self):
        return f"{self.name} ({self.cycle_identifier}) [{self.number}]"
