"""Sales 8.18 — SalesSyncRun forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import _reject_foreign
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.SyncJobs import SalesSyncJob
from apps.sales.models.IntegrationApiHub.SyncRuns import SalesSyncRun


class SalesSyncRunForm(TenantModelForm):
    class Meta:
        model = SalesSyncRun
        fields = [
            "connector",
            "job",
            "run_type",
            "status",
            "records_read",
            "records_written",
            "records_failed",
            "records_skipped",
            "error_log",
        ]
        widgets = {
            "connector": forms.Select(attrs={"class": "form-select"}),
            "job": forms.Select(attrs={"class": "form-select"}),
            "run_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "records_read": forms.NumberInput(attrs={"class": "form-input"}),
            "records_written": forms.NumberInput(attrs={"class": "form-input"}),
            "records_failed": forms.NumberInput(attrs={"class": "form-input"}),
            "records_skipped": forms.NumberInput(attrs={"class": "form-input"}),
            "error_log": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["connector"].queryset = SalesIntegrationConnector.objects.filter(tenant=self.tenant)
            self.fields["job"].queryset = SalesSyncJob.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["connector", "job"])
        return cleaned
