from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class PerformanceScorecardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PerformanceScorecard
        fields = [
            "name",
            "slug",
            "description",
            "scorecard_type",
            "review_period",
            "fiscal_year",
            "financial_weight",
            "customer_weight",
            "internal_process_weight",
            "learning_growth_weight",
            "status",
            "is_default",
            "is_published",
            "owner",
            "org_unit",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2026 Corporate Balanced Scorecard"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "2026-corporate-scorecard"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "scorecard_type": forms.Select(attrs={"class": "form-select"}),
            "review_period": forms.Select(attrs={"class": "form-select"}),
            "fiscal_year": forms.NumberInput(attrs={"class": "form-input", "min": 2020, "max": 2035}),
            "financial_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "customer_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "internal_process_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "learning_growth_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["owner"].queryset = User.objects.filter(
                is_active=True
            ).order_by("username")
        self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        name = self.cleaned_data.get("name")
        if not slug and name:
            slug = slugify(name)[:120]
        return slug

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["org_unit"])

        # Check total weights sum to 100%
        fw = cleaned.get("financial_weight") or Decimal("0.00")
        cw = cleaned.get("customer_weight") or Decimal("0.00")
        pw = cleaned.get("internal_process_weight") or Decimal("0.00")
        lw = cleaned.get("learning_growth_weight") or Decimal("0.00")
        total_weight = fw + cw + pw + lw
        if total_weight != Decimal("100.00"):
            self.add_error(None, f"The 4 BSC perspective weights must sum to 100.00% (current sum: {total_weight}%).")

        return cleaned


class PerformanceScorecardRecalculateForm(forms.Form):
    pass
