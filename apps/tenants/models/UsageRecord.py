"""tenants — UsageRecord models (0.1 "Subscription & Billing — usage metering").

The subscription is a flat plan + seat count (`tenants.Subscription`), which cannot express
metered consumption. This is the missing metering half: one row per metered metric per billing
period, with the included allowance and the resulting overage **derived** rather than stored —
so a price-list change cannot rewrite what last month actually consumed.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

from apps.tenants.models._base import *  # noqa: F401,F403


#: Included allowance per plan, per metric. A missing metric (or an empty dict) means the metric
#: is UNMETERED on that plan, not zero — `included_allowance` returns ``None`` for it and no
#: overage is ever computed. Kept as a module-level policy constant rather than columns because
#: the allowance is a commercial decision that changes with the price list, not per-row data;
#: overages are derived from it and never snapshotted (the same posture 6.15 took for its
#: commitment vocabulary). "enterprise" is deliberately empty: unmetered.
PLAN_ALLOWANCES = {
    "free": {"api_calls": 1000, "storage_mb": 512, "active_users": 3, "transactions": 500},
    "starter": {"api_calls": 50000, "storage_mb": 5120, "active_users": 10, "transactions": 10000},
    "pro": {"api_calls": 500000, "storage_mb": 51200, "active_users": 50, "transactions": 100000},
    "enterprise": {},
}


class UsageRecord(models.Model):
    METRIC_CHOICES = [
        ("api_calls", "API Calls"),
        ("storage_mb", "Storage (MB)"),
        ("active_users", "Active Users"),
        ("transactions", "Transactions"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="usage_records", db_index=True)
    #: The subscription the usage bills against. Optional so a record can be filed before a
    #: subscription exists; with no subscription the metric is treated as unmetered.
    subscription = models.ForeignKey("tenants.Subscription", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="usage_records")
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"),
                                   validators=[MinValueValidator(Decimal("0.00"))])
    period_start = models.DateField()
    period_end = models.DateField()
    #: Evidence stamps: written only by `usagerecord_mark_billed`, never by the edit form.
    is_billed = models.BooleanField(default=False, editable=False)
    billed_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The invoice this usage was rolled into. Set BEFORE marking billed, because a billed row
    #: refuses further edits (it is the evidence the invoice stands on).
    subscription_invoice = models.ForeignKey("tenants.SubscriptionInvoice", on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name="usage_records")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start", "-id"]
        indexes = [
            models.Index(fields=["tenant", "metric", "-period_start"], name="usage_tenant_metric_idx"),
            models.Index(fields=["tenant", "is_billed"], name="usage_tenant_billed_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError({"period_end": "The period end cannot be before the period start."})

    # --------------------------------------------------------------- derived (never stored)
    @property
    def included_allowance(self):
        """Units the linked subscription's plan includes for this metric.

        ``None`` means UNMETERED (no subscription, unknown plan, or a metric the plan does not
        cap) — deliberately distinct from ``0``, which would make every unit an overage.
        """
        if not self.subscription_id:
            return None
        plan = self.subscription.plan
        return PLAN_ALLOWANCES.get(plan, {}).get(self.metric)

    @property
    def overage_quantity(self):
        allowance = self.included_allowance
        if allowance is None:
            return Decimal("0.00")
        return max(Decimal("0.00"), self.quantity - Decimal(allowance))

    @property
    def is_overage(self):
        return self.overage_quantity > Decimal("0.00")

    def __str__(self):
        return f"{self.get_metric_display()} {self.quantity} ({self.period_start}…{self.period_end})"
