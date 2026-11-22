from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Role
from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models import DocumentApprovalRequest, DocumentApprovalWorkflow

User = get_user_model()


class DocumentApprovalRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentApprovalRequest
        fields = [
            "workflow",
            "stage_number",
            "stage_name",
            "stage_type",
            "order",
            "approver",
            "approver_role",
            "due_date",
        ]
        widgets = {
            "workflow": forms.Select(attrs={"class": "form-select"}),
            "stage_number": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "stage_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Legal Counsel Review"}),
            "stage_type": forms.Select(attrs={"class": "form-select"}),
            "order": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "approver": forms.Select(attrs={"class": "form-select"}),
            "approver_role": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["workflow"].queryset = DocumentApprovalWorkflow.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["approver"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")
            self.fields["approver_role"].queryset = Role.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["approver_role"].required = False
        self.fields["due_date"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["workflow", "approver", "approver_role"])
        return cleaned


class ApprovalDecisionForm(forms.Form):
    DECISION_CHOICES = [
        ("approved", "Approve Document"),
        ("rejected", "Reject Document"),
    ]
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-radio"}),
        required=True,
    )
    decision_comments = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Enter mandatory approval remarks or reason for rejection..."}),
        required=True,
    )


class ApprovalDelegationForm(forms.Form):
    delegated_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    delegation_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Out-of-office, subject-matter reassignment reason..."}),
        required=True,
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["delegated_to"].queryset = User.objects.filter(tenant=tenant).order_by("username")


class ApprovalEscalationForm(forms.Form):
    escalated_to = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    escalation_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Turnaround timeout or deadlock escalation reason..."}),
        required=True,
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["escalated_to"].queryset = User.objects.filter(tenant=tenant).order_by("username")
