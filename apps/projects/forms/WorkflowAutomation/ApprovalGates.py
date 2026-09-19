"""Projects 7.17 — ProjectApprovalGate forms."""
from django import forms
from django.contrib.auth import get_user_model

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.WorkflowAutomation.ApprovalGates import ProjectApprovalGate

User = get_user_model()


class ProjectApprovalGateForm(TenantModelForm):
    """Form for creating and updating ProjectApprovalGate instances."""

    class Meta:
        model = ProjectApprovalGate
        fields = [
            "project",
            "rule",
            "gate_type",
            "title",
            "description",
            "target_model",
            "target_id",
            "target_label",
            "requested_by",
            "approver",
            "delegate_approver",
            "escalate_to",
            "timeout_hours",
            "threshold_amount",
            "auto_approve_threshold",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "gate_type": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "rule"])
        return cleaned


class ApprovalDecisionForm(forms.Form):
    """Form for recording an approval or rejection decision."""

    decision = forms.ChoiceField(
        choices=[("approve", "Approve"), ("reject", "Reject")],
        widget=forms.RadioSelect(attrs={"class": "form-radio"}),
    )
    decision_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "Feedback or justification..."}),
        required=False,
    )


class ApprovalDelegateForm(forms.Form):
    """Form for delegating an approval gate to another user."""

    delegate_approver = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea", "placeholder": "Delegation reason..."}),
        required=False,
    )
