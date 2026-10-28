"""Sales 8.18 — SalesFieldMapping forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.FieldMappings import SalesFieldMapping


class SalesFieldMappingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SalesFieldMapping
        fields = [
            "connector",
            "target_entity",
            "local_field",
            "remote_field",
            "direction",
            "transform_rule",
            "value_map",
            "default_value",
            "is_key",
            "is_required",
            "is_active",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "target_entity": forms.Select(attrs={"class": "form-select"}),
            "local_field": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. order_number or email"}),
            "remote_field": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SAP_VBELN or hs_email"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "transform_rule": forms.Select(attrs={"class": "form-select"}),
            "value_map": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '{"draft": "D", "confirmed": "C"}'}),
            "default_value": forms.TextInput(attrs={"class": "form-input", "placeholder": "Fallback value if empty"}),
            "is_key": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["connector"].queryset = SalesIntegrationConnector.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["connector"])
        return cleaned
