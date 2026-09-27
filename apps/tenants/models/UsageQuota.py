"""tenants — UsageQuota (0.19 "License & Subscription Administration", bullet 3, the ceiling half).

THE COMMERCIAL CEILING SOMEBODY WROTE DOWN.

`UsageRecord` (0.1) is the consumption half; this is the ceiling half, and the two are joined on the
SAME `subscription`, because joining on anything else would let a quota be measured against a
different subscription's consumption — a "98% of quota" that is 98% of last year's subscription is
exactly the kind of confident lie this project refuses to ship.

A row here is a commercial term somebody wrote down, not a control that ran. `action_on_breach`
(`alert` / `charge` / `block`) is a RECORDED POLICY WITH NO INTERCEPTOR: marking a quota breached
writes a timestamp and an audit row, and nothing else happens — no alert is raised, no charge is
computed, no request is blocked. `breached_at` is therefore stamped by the `usagequota_mark_breached`
verb and is `editable=False` and off every form, because a form that could set it would let a member
declare their own quota breached without a single unit being consumed.

**`quota_limit == 0` MEANS UNMETERED, NOT "zero allowed".** This is the one rule a reader gets
wrong. `UsageRecord.included_allowance` returns `None` for an unmetered plan and its docstring says
so explicitly: *None means UNMETERED, deliberately distinct from 0, which would make every unit an
overage.* The same distinction applies here — a quota of 0 renders "Unmetered" with no percentage and
no breach state, and is EXCLUDED from the `warned` / `breached` counts on the quota board.

**Ownership:** 0.19 owns the COMMERCIAL limit. This is NOT an anti-abuse control and must never be
presented as one — the abuse bound belongs to `core.IpAccessRule` (0.18) and operational thresholds
to `core.AlertRule` (0.17); neither is re-declared here.

**The same TEN declines as the rest of 0.19:** entitlement enforcement · quota enforcement/throttling
(the one this file is most tempted by) · seat auto-deprovisioning · metered event ingestion ·
proration · prepaid credit grants · rate cards / tiered / multi-currency pricing · plan versioning &
grandfathering · automatic renewal execution · expiry email delivery.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator

from apps.tenants.models._base import *  # noqa: F401,F403
from apps.tenants.models.UsageRecord import UsageRecord


#: BY REFERENCE, not a pasted copy — the same object as `UsageRecord.METRIC_CHOICES`, exactly as
#: 0.18's `AlertRule` re-exposes `SEVERITY_CHOICES`. A rebuilt copy is the defect (it would be a
#: FIFTH metric list, the duplication the research rejects); the tests assert `is` identity.
METRIC_CHOICES = UsageRecord.METRIC_CHOICES

#: A recorded policy with no interceptor — see the module docstring.
ACTION_CHOICES = [
    ("alert", "Alert"),
    ("charge", "Charge"),
    ("block", "Block"),
]

#: The same two values as `Subscription.BILLING_CHOICES`, pinned as a LOCAL LITERAL rather than an
#: alias: a quota's reset window need not equal the subscription's billing cycle, and aliasing them
#: would make that unexpressible.
PERIOD_CHOICES = [
    ("monthly", "Monthly"),
    ("yearly", "Yearly"),
]


class UsageQuota(models.Model):
    #: Re-exposed by reference, the 0.18 `SEVERITY_CHOICES` pattern exactly.
    METRIC_CHOICES = METRIC_CHOICES
    ACTION_CHOICES = ACTION_CHOICES
    PERIOD_CHOICES = PERIOD_CHOICES

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="usage_quotas", db_index=True)
    #: UQ-##### — minted in save(); see `settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    #: NOT nullable, unlike `UsageRecord.subscription`: a ceiling with no subscription has nothing to
    #: bound, and a usage row can pre-date a subscription whereas a quota is authored FOR one.
    subscription = models.ForeignKey("tenants.Subscription", on_delete=models.CASCADE,
                                     related_name="usage_quotas")
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    #: REMEMBER: 0 means UNMETERED, not "zero permitted". See the module docstring.
    quota_limit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"),
                                      validators=[MinValueValidator(Decimal("0.00"))])
    warn_at_pct = models.PositiveIntegerField(default=80, validators=[MinValueValidator(1),
                                                                       MaxValueValidator(100)])
    action_on_breach = models.CharField(max_length=10, choices=ACTION_CHOICES, default="alert")
    is_fair_use = models.BooleanField(default=False)
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="monthly")
    #: Evidence stamp. `editable=False`, off every form, and the SOLE writer is the
    #: `usagequota_mark_breached` verb (the `UsageRecord.is_billed` / `billed_at` precedent, L22).
    breached_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subscription", "metric", "period"]
        unique_together = (("tenant", "subscription", "metric", "period"),)
        indexes = [
            models.Index(fields=["tenant", "subscription"], name="uquota_tenant_sub_idx"),
            models.Index(fields=["subscription", "metric"], name="uquota_sub_metric_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Assign UQ-#####; retry on the rare concurrent-collision (unique_together).
        for _ in range(5):
            self.number = next_number(UsageQuota, self.tenant, "UQ")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        """One rule: the [RULING] 8 duplicate guard on the unique tuple.

        No cross-field rule: `quota_limit` and `warn_at_pct` are independent, and in particular a
        limit of 0 is a legitimate UNMETERED quota, not a missing value.
        """
        super().clean()
        if self.tenant_id and self.subscription_id and self.metric and self.period:
            clash = UsageQuota.objects.filter(
                tenant_id=self.tenant_id, subscription_id=self.subscription_id,
                metric=self.metric, period=self.period,
            ).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError({
                    "period": "That subscription already has a quota for this metric and period.",
                })

    def __str__(self):
        return f"{self.get_metric_display()} quota for {self.subscription}"
