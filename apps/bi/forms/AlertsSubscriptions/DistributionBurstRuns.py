from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRun,
)
from apps.bi.models.AlertsSubscriptions.ReportSubscriptions import ReportSubscription
from apps.core.forms import TenantModelForm


class DistributionBurstRunForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DistributionBurstRun
        fields = [
            "subscription",
            "alert_rule",
            "run_trigger",
            "delivery_channel",
            "status",
            "recipient_count",
            "generated_file_name",
            "file_size_bytes",
            "error_summary",
        ]
        widgets = {
            "subscription": forms.Select(attrs={"class": "form-select"}),
            "alert_rule": forms.Select(attrs={"class": "form-select"}),
            "run_trigger": forms.Select(attrs={"class": "form-select"}),
            "delivery_channel": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "recipient_count": forms.NumberInput(attrs={"class": "form-input"}),
            "generated_file_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. SalesReport_Burst_20261107.pdf",
                }
            ),
            "file_size_bytes": forms.NumberInput(attrs={"class": "form-input"}),
            "error_summary": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Diagnostic notes or delivery warnings...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["subscription"].queryset = ReportSubscription.objects.filter(
                tenant=self.tenant
            )
            self.fields["alert_rule"].queryset = BiAlertRule.objects.filter(
                tenant=self.tenant
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["subscription", "alert_rule"],
        )
        return cleaned
