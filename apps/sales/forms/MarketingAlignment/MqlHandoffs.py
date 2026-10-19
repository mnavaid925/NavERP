"""Sales 8.13 — Forms for `MqlHandoff`."""
from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Campaign, Lead, Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.MarketingAlignment.MqlHandoffs import MqlHandoff


class MqlHandoffForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MqlHandoff
        fields = [
            "lead",
            "campaign",
            "account",
            "owner",
            "assigned_to",
            "opportunity",
            "status",
            "source_kind",
            "handoff_at",
            "sla_due_at",
            "acceptance_reason",
            "rejection_reason",
            "lead_score",
            "estimated_value",
            "currency",
            "notes",
        ]
        widgets = {
            "lead": forms.Select(attrs={"class": "form-select"}),
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "source_kind": forms.Select(attrs={"class": "form-select"}),
            "acceptance_reason": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Strong fit for the enterprise tier"}
            ),
            "rejection_reason": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Budget already allocated elsewhere"}
            ),
            "lead_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "estimated_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["lead"].queryset = Lead.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["campaign"].queryset = Campaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
            self.fields["assigned_to"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
            self.fields["opportunity"].queryset = Opportunity.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["currency"].queryset = Currency.objects.filter(
                is_active=True
            ).order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        # `currency` is deliberately absent: `accounting.Currency` is a GLOBAL master with no
        # tenant FK, so the generic tenant check would reject every currency (L29).
        _reject_foreign(
            self,
            cleaned_data,
            [
                "lead",
                "campaign",
                "account",
                "owner",
                "assigned_to",
                "opportunity",
            ],
        )
        status = cleaned_data.get("status")
        if status == "rejected" and not (cleaned_data.get("rejection_reason") or "").strip():
            self.add_error(
                "rejection_reason",
                "A rejected handoff must record why sales rejected it.",
            )
        # The SLA ordering rule lives here as well as on the model: when either field already
        # carries a form-level error, Django excludes it from model validation and the model's
        # own check is silently skipped.
        sla_due_at = cleaned_data.get("sla_due_at")
        handoff_at = cleaned_data.get("handoff_at")
        if sla_due_at and handoff_at and sla_due_at < handoff_at:
            self.add_error(
                "sla_due_at",
                "The SLA deadline cannot be earlier than the handoff time.",
            )
        return cleaned_data
