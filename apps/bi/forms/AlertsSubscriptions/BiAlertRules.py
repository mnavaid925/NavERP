from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.StatisticalAnomalies import StatisticalAnomaly
from apps.core.forms import TenantModelForm


class BiAlertRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiAlertRule
        fields = [
            "name",
            "description",
            "alert_type",
            "kpi_definition",
            "anomaly_detection",
            "condition_operator",
            "threshold_value",
            "secondary_threshold_value",
            "severity",
            "evaluation_cadence",
            "trigger_frequency",
            "delivery_channel",
            "recipient_users",
            "notification_email_list",
            "webhook_url",
            "downstream_workflow",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Operating Margin Threshold Alert",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Trigger criteria and response protocol...",
                }
            ),
            "alert_type": forms.Select(attrs={"class": "form-select"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "anomaly_detection": forms.Select(attrs={"class": "form-select"}),
            "condition_operator": forms.Select(attrs={"class": "form-select"}),
            "threshold_value": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "secondary_threshold_value": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.0001"}
            ),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "evaluation_cadence": forms.Select(attrs={"class": "form-select"}),
            "trigger_frequency": forms.Select(attrs={"class": "form-select"}),
            "delivery_channel": forms.Select(attrs={"class": "form-select"}),
            "recipient_users": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 4}
            ),
            "notification_email_list": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "alerts@example.com, finance-leads@example.com",
                }
            ),
            "webhook_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://hooks.slack.com/services/...",
                }
            ),
            "downstream_workflow": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(
                tenant=self.tenant
            )
            self.fields["anomaly_detection"].queryset = (
                StatisticalAnomaly.objects.filter(tenant=self.tenant)
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["kpi_definition", "anomaly_detection"],
        )
        return cleaned
