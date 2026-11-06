from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class KpiDefinitionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = KpiDefinition
        fields = [
            "code",
            "name",
            "slug",
            "description",
            "category",
            "perspective",
            "target_direction",
            "unit_of_measure",
            "tracking_frequency",
            "calculation_type",
            "semantic_measure",
            "formula_expression",
            "target_value",
            "warning_threshold",
            "critical_threshold",
            "current_value",
            "previous_value",
            "industry_benchmark_value",
            "benchmark_source",
            "benchmark_percentile",
            "status",
            "is_active",
            "owner",
            "department",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FIN-KPI-001"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Operating Margin %"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "operating-margin-pct"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "category": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Profitability, Operations"}),
            "perspective": forms.Select(attrs={"class": "form-select"}),
            "target_direction": forms.Select(attrs={"class": "form-select"}),
            "unit_of_measure": forms.Select(attrs={"class": "form-select"}),
            "tracking_frequency": forms.Select(attrs={"class": "form-select"}),
            "calculation_type": forms.Select(attrs={"class": "form-select"}),
            "semantic_measure": forms.Select(attrs={"class": "form-select"}),
            "formula_expression": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. [ebit] / [total_revenue] * 100"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "warning_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "critical_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "current_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "previous_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "industry_benchmark_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "benchmark_source": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Gartner 2026 Benchmark"}),
            "benchmark_percentile": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["semantic_measure"].queryset = CalculatedMeasure.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["department"].queryset = OrgUnit.objects.filter(
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
        reject_foreign(self, cleaned, ["semantic_measure", "department"])
        return cleaned


class KpiDefinitionRefreshForm(forms.Form):
    new_value = forms.DecimalField(
        max_digits=14,
        decimal_places=4,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional measurement notes"}),
    )
