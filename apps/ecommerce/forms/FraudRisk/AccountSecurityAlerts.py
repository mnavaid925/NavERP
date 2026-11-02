from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.FraudRisk.AccountSecurityAlerts import AccountSecurityAlert


class AccountSecurityAlertForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AccountSecurityAlert
        exclude = ["tenant", "number", "created_at", "updated_at", "resolved_at"]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "alert_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "automated_action_taken": forms.Select(attrs={"class": "form-select"}),
            "ip_address": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "203.0.113.195"}),
            "location_info": forms.TextInput(attrs={"class": "form-input", "placeholder": "Kyiv, Ukraine"}),
            "user_agent": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "Mozilla/5.0..."}),
            "incident_details": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "15 failed password attempts in 60s, matched known botnet IP..."}),
            "assigned_investigator": forms.Select(attrs={"class": "form-select"}),
            "investigation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Investigator case notes, user contact log..."}),
            "resolved_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant)
        if "user" in self.fields:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(is_active=True)
        if "assigned_investigator" in self.fields:
            self.fields["assigned_investigator"].queryset = self.fields["assigned_investigator"].queryset.filter(is_active=True)
        if "resolved_by" in self.fields:
            self.fields["resolved_by"].queryset = self.fields["resolved_by"].queryset.filter(is_active=True)
