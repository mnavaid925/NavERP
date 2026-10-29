from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class AudienceSegment(TenantNumbered):
    NUMBER_PREFIX = "ESEG"

    LIFECYCLE_STAGE_CHOICES = [
        ("all", "All Lifecycle Stages"),
        ("new_visitor", "New Visitor"),
        ("first_time_buyer", "First-Time Buyer"),
        ("active_repeat", "Active Repeat Customer"),
        ("high_value_vip", "High-Value VIP"),
        ("at_risk", "At-Risk Customer"),
        ("churned_lapsed", "Churned / Lapsed Shopper"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Administrative label for this segment, e.g. 'VIP Champions', 'Lapsed Buyers'",
    )
    code = models.CharField(
        max_length=60,
        help_text="Machine identifier slug, e.g. 'vip-champions', 'footwear-enthusiasts'",
    )
    lifecycle_stage = models.CharField(
        max_length=30,
        choices=LIFECYCLE_STAGE_CHOICES,
        default="all",
        help_text="Target customer lifecycle tier",
    )
    recency_days_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max days since last purchase (e.g. <= 30 for active)",
    )
    min_order_count = models.PositiveIntegerField(
        default=0,
        help_text="Minimum lifetime order count required",
    )
    min_lifetime_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Minimum lifetime monetary spend",
    )
    target_category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affinity_segments",
        help_text="Optional category affinity filter",
    )
    cached_member_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of matching shopper profiles",
    )
    last_evaluated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last member evaluation",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active segments participate in personalization evaluation",
    )
    description = models.TextField(
        blank=True,
        help_text="Operational description of audience cohort and strategic goals",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eseg_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="ecommerce_eseg_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "lifecycle_stage"],
                name="idx_eseg_ten_act_stage",
            ),
        ]

    def clean(self):
        super().clean()
        if self.code:
            self.code = slugify(self.code)
        if self.name and not self.code:
            self.code = slugify(self.name)
        if self.min_lifetime_spend < Decimal("0.00"):
            raise ValidationError({"min_lifetime_spend": "Minimum spend cannot be negative."})

        # C3: Model-level tenant foreign key validation
        if self.target_category_id and self.target_category and self.target_category.tenant_id != self.tenant_id:
            raise ValidationError({"target_category": "Target category belongs to another workspace."})

    def __str__(self):
        return f"{self.name} ({self.number})"
