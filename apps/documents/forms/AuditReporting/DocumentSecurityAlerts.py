from django import forms
from django.contrib.auth import get_user_model

from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert

User = get_user_model()


class DocumentSecurityAlertTriageForm(forms.ModelForm):
    """Triage workbench form for adjusting severity, status, mitigation, and assigning investigator."""

    class Meta:
        model = DocumentSecurityAlert
        fields = [
            "status",
            "severity",
            "action_taken",
            "assigned_to",
            "triage_notes",
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "action_taken": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "triage_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Record triage findings, mitigation justifications, and next steps..."}),
        }

    def __init__(self, tenant=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["assigned_to"].queryset = User.objects.filter(tenant=tenant).order_by("first_name", "email")
        self.fields["assigned_to"].required = False


class DocumentSecurityAlertFilterForm(forms.Form):
    """Filter form for User Behavior Analytics security incident alerts."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Search alert headline, notes, or IP..."}),
    )
    severity = forms.ChoiceField(
        required=False,
        choices=[("", "All Severities")] + list(DocumentSecurityAlert.SEVERITY_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(DocumentSecurityAlert.STATUS_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    alert_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Alert Types")] + list(DocumentSecurityAlert.ALERT_TYPE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
