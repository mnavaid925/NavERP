from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.AlertsSubscriptions.BiNotificationItems import (
    BiNotificationItem,
)
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRun,
)
from apps.core.forms import TenantModelForm

User = get_user_model()


class BiNotificationItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiNotificationItem
        fields = [
            "recipient",
            "title",
            "message",
            "severity",
            "category",
            "status",
            "alert_rule",
            "burst_run",
            "action_url",
            "acknowledgment_notes",
            "snoozed_until",
        ]
        widgets = {
            "recipient": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Critical Threshold Exceeded: Operating Margin",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Notification details and recommended operational action...",
                }
            ),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "alert_rule": forms.Select(attrs={"class": "form-select"}),
            "burst_run": forms.Select(attrs={"class": "form-select"}),
            "action_url": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "/bi/kpis/5/",
                }
            ),
            "acknowledgment_notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Reason or resolution notes upon acknowledgment...",
                }
            ),
            "snoozed_until": forms.DateTimeInput(
                attrs={
                    "class": "form-input",
                    "type": "datetime-local",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["alert_rule"].queryset = BiAlertRule.objects.filter(
                tenant=self.tenant
            )
            self.fields["burst_run"].queryset = DistributionBurstRun.objects.filter(
                tenant=self.tenant
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["alert_rule", "burst_run"],
        )
        return cleaned
