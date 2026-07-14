"""CRM 1.11 Customer Success & Retention — HealthScores forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    HealthScore,
    HealthScoreConfig,
)


class HealthScoreForm(TenantModelForm):
    """Manual score entry/override; breakdown + computed_at are system-set."""

    class Meta:
        model = HealthScore
        fields = ["account", "score", "tier"]

    def clean_account(self):
        # One score row per account (unique_together) — block a duplicate at the form
        # level so a manual create returns a friendly error instead of an IntegrityError 500.
        account = self.cleaned_data.get("account")
        if account is not None and self.tenant is not None:
            qs = HealthScore.objects.filter(tenant=self.tenant, account=account)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A health score already exists for this account — edit or recompute it instead.")
        return account


class HealthScoreConfigForm(TenantModelForm):
    class Meta:
        model = HealthScoreConfig
        fields = ["weight_tickets", "weight_nps", "weight_tasks", "weight_engagement",
                  "red_threshold", "yellow_threshold"]

    def clean(self):
        cleaned = super().clean()
        weights = [cleaned.get("weight_tickets"), cleaned.get("weight_nps"),
                   cleaned.get("weight_tasks"), cleaned.get("weight_engagement")]
        if all(w is not None for w in weights) and sum(weights) != 100:
            raise forms.ValidationError("Signal weights must add up to 100%.")
        red, yellow = cleaned.get("red_threshold"), cleaned.get("yellow_threshold")
        if red is not None and yellow is not None and red >= yellow:
            raise forms.ValidationError("The Red threshold must be below the Yellow threshold.")
        return cleaned
