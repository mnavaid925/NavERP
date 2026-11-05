from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardFilters import BiDashboardFilter
from apps.core.forms import TenantModelForm


class BiDashboardFilterForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiDashboardFilter
        fields = [
            "dashboard",
            "filter_label",
            "filter_key",
            "filter_type",
            "target_field",
            "default_value",
            "options_source",
            "order",
            "is_required",
            "is_active",
        ]
        widgets = {
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "filter_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Fiscal Year"}),
            "filter_key": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. fiscal_year"}),
            "filter_type": forms.Select(attrs={"class": "form-select"}),
            "target_field": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. fiscal_year, region, order_date"}),
            "default_value": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. current_year, north, all"}),
            "options_source": forms.Select(attrs={"class": "form-select"}),
            "order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["dashboard"])
        label = cleaned_data.get("filter_label")
        key = cleaned_data.get("filter_key")
        if not key and label:
            cleaned_data["filter_key"] = slugify(label)[:60].replace("-", "_")
        return cleaned_data
