import json
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.MasterData.MdmSurvivorshipRules import MdmSurvivorshipRule
from apps.core.forms import TenantModelForm


class MdmSurvivorshipRuleForm(TenantUniqueMixin, TenantModelForm):
    source_priority_list_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-xs",
                "rows": 3,
                "placeholder": '["erp_core", "crm_sales", "billing_service", "web_portal"]',
            }
        ),
        required=False,
        label="Source System Priority Ranking (JSON array or comma-separated)",
        help_text="Ordered list of trusted systems from highest authority to lowest.",
    )

    class Meta:
        model = MdmSurvivorshipRule
        fields = [
            "name",
            "code",
            "domain",
            "target_field",
            "survivorship_strategy",
            "match_algorithm",
            "match_threshold_pct",
            "auto_merge_threshold_pct",
            "priority_order",
            "steward",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Legal Name ERP Precedence"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. legal_name_erp_priority"}),
            "domain": forms.Select(attrs={"class": "form-select"}),
            "target_field": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. name or *"}),
            "survivorship_strategy": forms.Select(attrs={"class": "form-select"}),
            "match_algorithm": forms.Select(attrs={"class": "form-select"}),
            "match_threshold_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "80.00"}),
            "auto_merge_threshold_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "95.00"}),
            "priority_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Business rationale for survivorship logic"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.source_priority_list_json:
                self.fields["source_priority_list_text"].initial = json.dumps(
                    self.instance.source_priority_list_json, indent=2
                )
        if self.tenant is not None:
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.steward_id:
                steward_filter |= Q(pk=self.instance.steward_id)
            self.fields["steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean_source_priority_list_text(self):
        data = self.cleaned_data.get("source_priority_list_text", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            return [str(parsed).strip()]
        except json.JSONDecodeError:
            items = [x.strip() for x in data.split(",") if x.strip()]
            return items

    def clean(self):
        cleaned = super().clean()
        match_pct = cleaned.get("match_threshold_pct")
        auto_merge_pct = cleaned.get("auto_merge_threshold_pct")
        if match_pct is not None and auto_merge_pct is not None:
            if auto_merge_pct < match_pct:
                raise forms.ValidationError(
                    {"auto_merge_threshold_pct": "Auto-merge threshold must be greater than or equal to candidate match threshold."}
                )
        reject_foreign(self, cleaned, ["steward"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.source_priority_list_json = self.cleaned_data.get("source_priority_list_text", [])
        if commit:
            instance.save()
        return instance
