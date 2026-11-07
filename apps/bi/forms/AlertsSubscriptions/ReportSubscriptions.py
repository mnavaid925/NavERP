from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AlertsSubscriptions.ReportSubscriptions import ReportSubscription
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


class ReportSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    """
    Form for ReportSubscription instances.

    Note: `filter_overrides` (JSONField) is intentionally excluded from this standard CRUD form;
    runtime parameter overrides are configured and evaluated dynamically by execution engines.
    """

    class Meta:
        model = ReportSubscription
        fields = [
            "name",
            "target_asset_type",
            "dashboard",
            "report",
            "export_format",
            "cadence",
            "scheduled_time",
            "cron_expression",
            "burst_mode",
            "subscriber_users",
            "subscriber_org_units",
            "external_recipient_emails",
            "include_cover_page",
            "skip_if_empty",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Weekly Executive Performance Digest",
                }
            ),
            "target_asset_type": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "export_format": forms.Select(attrs={"class": "form-select"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "scheduled_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
            "cron_expression": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "0 8 * * 1"}
            ),
            "burst_mode": forms.Select(attrs={"class": "form-select"}),
            "subscriber_users": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 4}
            ),
            "subscriber_org_units": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 4}
            ),
            "external_recipient_emails": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "board@example.com, execs@example.com",
                }
            ),
            "include_cover_page": forms.CheckboxInput(
                attrs={"class": "form-checkbox"}
            ),
            "skip_if_empty": forms.CheckboxInput(
                attrs={"class": "form-checkbox"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(
                tenant=self.tenant
            )
            self.fields["report"].queryset = ReportDefinition.objects.filter(
                tenant=self.tenant
            )
            self.fields["subscriber_org_units"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            )
            self.fields["subscriber_users"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["dashboard", "report", "subscriber_org_units", "subscriber_users"],
        )
        return cleaned
