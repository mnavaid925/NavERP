"""Sales 8.18 — SalesSyncJob forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import _reject_foreign
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.SyncJobs import SalesSyncJob


class SalesSyncJobForm(TenantModelForm):
    class Meta:
        model = SalesSyncJob
        fields = [
            "name",
            "connector",
            "entity_scope",
            "sync_direction",
            "conflict_policy",
            "cadence",
            "filter_expression",
            "batch_size",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Daily Order-to-Cash Sync"}),
            "connector": forms.Select(attrs={"class": "form-select"}),
            "entity_scope": forms.Select(attrs={"class": "form-select"}),
            "sync_direction": forms.Select(attrs={"class": "form-select"}),
            "conflict_policy": forms.Select(attrs={"class": "form-select"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "filter_expression": forms.TextInput(attrs={"class": "form-input", "placeholder": "status='confirmed' AND total_amount > 0"}),
            "batch_size": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 1000}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["connector"].queryset = SalesIntegrationConnector.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["connector"])
        return cleaned
