"""Procurement 6.3 Approval Workflow Engine — forms."""
from django import forms

from apps.procurement.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
)
from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
)


class ApprovalRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    """One routing rule. The mixin validates no unique here but DOES stamp
    instance.tenant before clean() — without it the model's foreign-FK guards
    would falsely reject every create."""

    class Meta:
        model = ApprovalRoutingRule
        fields = ["org_unit", "commodity", "min_total", "max_total",
                  "required_tiers", "escalation_hours", "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["org_unit"])
        return cleaned


class ApprovalDelegationForm(TenantUniqueMixin, TenantModelForm):
    """One DOA grant."""

    class Meta:
        model = ApprovalDelegation
        fields = ["delegator", "delegate", "scope_org_unit",
                  "valid_from", "valid_until", "reason", "is_active"]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["delegator", "delegate", "scope_org_unit"])
        return cleaned


class EscalationPolicyForm(TenantUniqueMixin, TenantModelForm):
    """The tenant's standing escalation knob (singleton row)."""

    class Meta:
        model = EscalationPolicy
        fields = ["idle_hours", "escalate_to", "is_active"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["escalate_to"])
        return cleaned


class ApprovalDecisionForm(forms.Form):
    """Comment captured when approving or rejecting a tier (optional on approve)."""

    comment = forms.CharField(required=False, max_length=2000,
                              widget=forms.Textarea(attrs={"class": "form-textarea",
                                                           "rows": 2}),
                              help_text="Recorded against the signature")
