from django import forms

from apps.sales.forms._common import TenantActionForm, TenantModelForm, TenantUniqueMixin, _reject_foreign, tenant_consent_purposes, tenant_drip_campaigns, tenant_leads, tenant_users
from apps.sales.models import LeadNurtureEnrollment


class LeadNurtureEnrollmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LeadNurtureEnrollment
        fields = ["lead", "email_campaign", "trigger_kind", "consent_purpose", "consent_evidence", "owner", "notes"]

    def __init__(self, *args, tenant=None, leads=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["lead"].queryset = leads if leads is not None else tenant_leads(tenant)
        self.fields["email_campaign"].queryset = tenant_drip_campaigns(tenant)
        self.fields["consent_purpose"].queryset = tenant_consent_purposes(tenant)
        self.fields["owner"].queryset = tenant_users(tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["lead", "email_campaign", "consent_purpose", "owner"])
        if self.instance.pk and self.instance.status != "pending":
            self.add_error(None, "Enrollment identity is editable only while it is pending.")
        return cleaned


class LeadNurtureActivationForm(TenantActionForm):
    next_touch_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}, format="%Y-%m-%dT%H:%M"), input_formats=["%Y-%m-%dT%H:%M"])


class LeadNurtureExitForm(TenantActionForm):
    exit_reason = forms.ChoiceField(choices=LeadNurtureEnrollment.EXIT_REASON_CHOICES)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}))

    def __init__(self, *args, target_status=None, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if target_status in LeadNurtureEnrollment.EXIT_REASON_TARGETS:
            self.fields["exit_reason"].choices = [
                (value, label)
                for value, label in LeadNurtureEnrollment.EXIT_REASON_CHOICES
                if value in LeadNurtureEnrollment.EXIT_REASON_TARGETS[target_status]
            ]
