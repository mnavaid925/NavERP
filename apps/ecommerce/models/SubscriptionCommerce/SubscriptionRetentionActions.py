from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class SubscriptionRetentionAction(TenantNumbered):
    NUMBER_PREFIX = "ESRT"

    TRIGGER_TYPE_CHOICES = [
        ("cancel_intent", "Cancellation Intent Intercept"),
        ("pause_request", "Pause Request"),
        ("dunning_involuntary", "Involuntary Dunning Decline"),
        ("predicted_risk", "High Churn Risk Trigger"),
    ]

    REASON_CHOICES = [
        ("too_expensive", "Too Expensive / Cost"),
        ("too_much_product", "Too Much Backlog / Product"),
        ("poor_quality", "Product Did Not Meet Expectations"),
        ("temporary_break", "Temporary Break / Traveling"),
        ("switching_competitor", "Switching to Competitor"),
        ("other", "Other Reason"),
    ]

    OFFER_CHOICES = [
        ("discount_cycle", "Discount Next N Cycles"),
        ("free_skip", "Free Skip Next Cycle"),
        ("pause_duration", "Pause for 30/60 Days"),
        ("product_swap", "Swap to Alternate Item"),
        ("bonus_perk", "Free Gift / Bonus Item"),
        ("none", "No Offer Presented"),
    ]

    OUTCOME_CHOICES = [
        ("deflected", "Deflected / Retained"),
        ("cancelled", "Cancelled Anyway"),
        ("paused", "Paused Instead"),
        ("accepted_swap", "Accepted Product Swap"),
        ("pending", "Pending / In Progress"),
    ]

    subscription = models.ForeignKey(
        "ecommerce.CustomerSubscription",
        on_delete=models.CASCADE,
        related_name="retention_actions",
        help_text="Target customer subscription under churn deflection evaluation",
    )
    customer_profile = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.CASCADE,
        related_name="retention_actions",
        help_text="Customer profile anchor",
    )
    trigger_type = models.CharField(
        max_length=30,
        choices=TRIGGER_TYPE_CHOICES,
        default="cancel_intent",
        help_text="Deflection trigger initiation source",
    )
    cancellation_reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="too_much_product",
        help_text="Reported customer cancellation or dissatisfaction reason",
    )
    churn_risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Algorithmic or rule-based predicted churn risk score (0.00 - 100.00)",
    )
    offered_action = models.CharField(
        max_length=30,
        choices=OFFER_CHOICES,
        default="discount_cycle",
        help_text="Defensive retention incentive presented to the customer",
    )
    offer_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage offered (e.g. 15.00 for 15% off next orders)",
    )
    outcome = models.CharField(
        max_length=30,
        choices=OUTCOME_CHOICES,
        default="pending",
        help_text="Final result of deflection attempt",
    )
    notes = models.TextField(
        blank=True,
        help_text="Staff or customer-provided notes and feedback",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esrt_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "outcome", "trigger_type"],
                name="idx_esrt_ten_outc_trig",
            ),
            models.Index(
                fields=["tenant", "subscription", "created_at"],
                name="idx_esrt_ten_sub_created",
            ),
        ]

    def clean(self):
        super().clean()
        if self.churn_risk_score < Decimal("0.00") or self.churn_risk_score > Decimal("100.00"):
            raise ValidationError({"churn_risk_score": "Churn risk score must be between 0.00 and 100.00."})
        if self.offer_discount_pct < Decimal("0.00") or self.offer_discount_pct > Decimal("100.00"):
            raise ValidationError({"offer_discount_pct": "Discount percentage must be between 0.00 and 100.00."})

        # Tenant cross-reference validation
        if self.subscription_id and self.subscription and self.subscription.tenant_id != self.tenant_id:
            raise ValidationError({"subscription": "Subscription belongs to another workspace."})
        if self.customer_profile_id and self.customer_profile and self.customer_profile.tenant_id != self.tenant_id:
            raise ValidationError({"customer_profile": "Customer profile belongs to another workspace."})
        if self.subscription_id and self.customer_profile_id and self.subscription:
            if self.subscription.customer_profile_id != self.customer_profile_id:
                raise ValidationError({"customer_profile": "Customer profile does not match the subscription owner."})

    def __str__(self):
        return f"{self.number} - {self.get_trigger_type_display()} [{self.get_outcome_display()}]"
