"""Form definitions for QuoteApprovalRule model."""
from django import forms
from apps.sales.forms._common import TenantModelForm
from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule


class QuoteApprovalRuleForm(TenantModelForm):
    """Form to create and edit CPQ pricing/discount approval rules."""

    class Meta:
        model = QuoteApprovalRule
        fields = [
            "name",
            "rule_type",
            "discount_threshold_pct",
            "min_margin_pct",
            "amount_threshold",
            "approver_role",
            "auto_reject",
            "priority",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Executive Discount Floor"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "discount_threshold_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "min_margin_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "amount_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional value ceiling"}),
            "approver_role": forms.Select(attrs={"class": "form-select"}),
            "auto_reject": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe conditions triggering this approval rule..."}),
        }
