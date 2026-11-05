from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataCatalog.DataGovernancePolicies import DataGovernancePolicy
from apps.core.forms import TenantModelForm


class DataGovernancePolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataGovernancePolicy
        fields = [
            "name",
            "code",
            "policy_type",
            "regulatory_framework",
            "enforcement_level",
            "retention_period_days",
            "masking_algorithm",
            "policy_owner",
            "effective_date",
            "expiration_date",
            "review_frequency_days",
            "compliance_notes",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. GDPR Customer PII Erasure Policy"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. gdpr_pii_erasure"}),
            "policy_type": forms.Select(attrs={"class": "form-select"}),
            "regulatory_framework": forms.Select(attrs={"class": "form-select"}),
            "enforcement_level": forms.Select(attrs={"class": "form-select"}),
            "retention_period_days": forms.NumberInput(attrs={"class": "form-input", "placeholder": "2555"}),
            "masking_algorithm": forms.Select(attrs={"class": "form-select"}),
            "policy_owner": forms.Select(attrs={"class": "form-select"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "review_frequency_days": forms.NumberInput(attrs={"class": "form-input", "placeholder": "365"}),
            "compliance_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Statutory citations (e.g. GDPR Article 17 Right to Erasure)"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Comprehensive overview of policy guidelines"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "code" in self.fields:
            self.fields["code"].required = False
        if self.tenant is not None:
            self.fields["policy_owner"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant).order_by("first_name", "username")
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["policy_owner"])

        name = cleaned.get("name")
        code = cleaned.get("code")
        if name and not code:
            base_slug = slugify(name).replace("-", "_")[:80]
            cleaned["code"] = base_slug
            self.instance.code = base_slug

        return cleaned
