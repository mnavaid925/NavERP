"""CRM 1.2 Sales Force Automation — SalesQuotas forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    SalesQuota,
)


class SalesQuotaForm(TenantModelForm):
    class Meta:
        model = SalesQuota
        fields = ["owner", "territory", "period_type", "period_year", "period_number",
                  "target_amount", "notes"]

    def clean(self):
        # Block a duplicate quota at the form level so the user gets a friendly error instead of
        # an IntegrityError 500 — also covers the null-territory case the DB constraint won't catch.
        cleaned = super().clean()
        if self.tenant is None:
            return cleaned
        qs = SalesQuota.objects.filter(
            tenant=self.tenant, owner=cleaned.get("owner"), territory=cleaned.get("territory"),
            period_type=cleaned.get("period_type"), period_year=cleaned.get("period_year"),
            period_number=cleaned.get("period_number"))
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "A quota already exists for this rep, territory and period — edit that one instead.")
        return cleaned
