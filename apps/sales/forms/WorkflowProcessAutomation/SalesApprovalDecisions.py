"""Sales 8.17 — SalesApprovalDecision forms (ledger entry, restricted edit, decide action)."""
from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import Role
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantActionForm, tenant_users
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.OrderManagement.OrderHolds import OrderHold
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule
from apps.sales.models.WorkflowProcessAutomation.SalesApprovalDecisions import (
    TARGET_KIND_CHOICES,
    SalesApprovalDecision,
)


class SalesApprovalDecisionForm(TenantModelForm):
    """Manual ledger entry — used by ``sales_approval_decision_create`` ONLY.

    The register is otherwise immutable, so this form exists to back-fill a sign-off
    that happened outside the system (email, phone, paper). System/derived fields are
    structurally unrenderable (L22): ``tenant``, auto ``number``, ``target_key``
    (computed in ``save()``), ``decided_at`` (auto_now_add), ``created_at`` and
    ``updated_at`` are all omitted from ``Meta.fields``.

    The exactly-one-target guard is repeated here because a ``Model.clean()`` guard
    keyed on tenant is a no-op on the form path (L49) — the form is the only place the
    tenant is known while the row is validated. Tenant membership of every target is
    guaranteed by the narrowed querysets below, so no ``_reject_foreign`` pass is needed.
    """

    class Meta:
        model = SalesApprovalDecision
        fields = [
            "approval_kind", "quote", "order_hold", "contract", "record_label",
            "approval_rule", "tier", "tier_count", "approver_role", "approver",
            "decision", "comment", "requested_by", "requested_at", "due_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["quote"].queryset = CPQQuote.objects.filter(tenant=self.tenant)
            self.fields["order_hold"].queryset = OrderHold.objects.filter(tenant=self.tenant)
            self.fields["contract"].queryset = CustomerContract.objects.filter(tenant=self.tenant)
            self.fields["approval_rule"].queryset = QuoteApprovalRule.objects.filter(tenant=self.tenant)
            # Role has NO is_active field — filter by tenant only.
            self.fields["approver_role"].queryset = Role.objects.filter(tenant=self.tenant)
            self.fields["approver"].queryset = tenant_users(self.tenant)
            self.fields["requested_by"].queryset = tenant_users(self.tenant)

    def clean(self):
        cleaned = super().clean()
        targets = sum(1 for field in ("quote", "order_hold", "contract") if cleaned.get(field))
        if targets != 1:
            raise ValidationError("Set exactly one approval target (quote, order hold, or contract).")
        tier = cleaned.get("tier")
        tier_count = cleaned.get("tier_count")
        if tier_count and tier and tier > tier_count:
            self.add_error("tier", "A tier cannot exceed the chain length.")
        return cleaned


class SalesApprovalDecisionEditForm(TenantModelForm):
    """Restricted edit — ``comment`` and ``due_at`` only (the register is otherwise immutable).

    Used by ``sales_approval_decision_edit`` ONLY. No clean methods: neither field can
    break the chain, and everything that decides WHO signed WHAT and at which tier is
    deliberately unrenderable here.
    """

    class Meta:
        model = SalesApprovalDecision
        fields = ["comment", "due_at"]


class SalesApprovalDecisionActionForm(TenantActionForm):
    """Approve / reject POST body for the deciding views.

    Target existence and tenancy are enforced in the deciding view via a tenant-scoped
    ``get_object_or_404(...).select_for_update()`` (IDOR-safe 404), so there are no clean
    methods here. There is deliberately NO ``tier_count`` field: the chain length is a
    security decision and must never be read from the request — the deciding view uses
    the recorded ``Max(tier_count)`` snapshot on the existing chain, else 1 for a brand
    -new chain (I1/S1; contract §10 deviation 8).
    """

    target_kind = forms.ChoiceField(choices=TARGET_KIND_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}))
    target_id = forms.IntegerField(min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-input"}))
    approval_kind = forms.ChoiceField(required=False,
        choices=[("", "Auto (from target)")] + list(SalesApprovalDecision.APPROVAL_KIND_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}))
    comment = forms.CharField(required=False, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}))
