"""tenants — UsageQuota form (0.19, the commercial ceiling)."""
from django.core.exceptions import ValidationError

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    UsageQuota,
)


class UsageQuotaForm(TenantModelForm):
    """`TenantModelForm`, never a plain `ModelForm` ([RULING] 9).

    **`breached_at` is EXCLUDED, and the exclusion is the model's own point.** It is an evidence
    stamp, `editable=False`, whose SOLE writer is the `usagequota_mark_breached` verb. A form that
    could set it would let a member declare their own quota breached without a single unit being
    consumed — and the breach is what an operator later reads as evidence, so it must be stamped by
    the act, not typed by hand (L22).

    Also excluded: `number` (`editable=False`, minted in `save()`) and `tenant` (set by the view).
    Both exclusions are belt-and-braces; `number` is off every ModelForm structurally.
    """

    class Meta:
        model = UsageQuota
        fields = ["subscription", "metric", "quota_limit", "warn_at_pct", "action_on_breach",
                  "is_fair_use", "period", "notes"]

    def clean(self):
        """The [RULING] 8 duplicate guard on `(tenant, subscription, metric, period)`.

        The tuple is fully non-nullable, so the database DOES enforce it — which is precisely why
        this guard is needed: without it a duplicate POST is an HTTP 500, not a form error. Keyed on
        `period`, a field this form actually has.
        """
        super().clean()
        subscription = self.cleaned_data.get("subscription")
        metric = self.cleaned_data.get("metric")
        period = self.cleaned_data.get("period")
        tenant = getattr(self, "tenant", None)
        if subscription is None or not metric or not period or tenant is None:
            return self.cleaned_data
        clash = UsageQuota.objects.filter(
            tenant=tenant, subscription=subscription, metric=metric, period=period,
        )
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError({
                "period": "That subscription already has a quota for this metric and period.",
            })
        return self.cleaned_data
