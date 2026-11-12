"""Form for Cloud Asset, SaaS Subscription & FinOps Tracking (11.18)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.accounting.models.GeneralLedger.GLAccounts import GLAccount
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.forms.ItAssetManagement._helpers import (
    normalize_json_dict_value,
    scope_tenant_querysets,
)
from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import CloudAssetSubscription
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party

User = get_user_model()


class CloudAssetSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Cloud Assets & SaaS Subscriptions [ITCL]."""

    _TENANT_FIELDS = {
        "org_unit": OrgUnit,
        "vendor_party": Party,
        "gl_expense_account": GLAccount,
        "business_owner": User,
        "technical_owner": User,
    }

    class Meta:
        model = CloudAssetSubscription
        fields = [
            "name",
            "asset_kind",
            "provider",
            "external_account_id",
            "cloud_resource_id",
            "cloud_region",
            "environment",
            "resource_tags",
            "billing_cadence",
            "commitment_term",
            "monthly_recurring_cost",
            "annual_contract_value",
            "currency",
            "provisioned_seats",
            "active_seats_30d",
            "sso_status",
            "approval_status",
            "renewal_date",
            "cancellation_notice_days",
            "auto_renew",
            "vendor_eol_date",
            "org_unit",
            "vendor_party",
            "gl_expense_account",
            "business_owner",
            "technical_owner",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. AWS Production EKS Cluster / Datadog APM"}),
            "external_account_id": forms.TextInput(attrs={"placeholder": "e.g. aws-acct-10482910"}),
            "cloud_resource_id": forms.TextInput(attrs={"placeholder": "e.g. arn:aws:eks:us-east-1:1048:cluster/prod"}),
            "cloud_region": forms.TextInput(attrs={"placeholder": "e.g. us-east-1 / global-saas"}),
            "resource_tags": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": '{"env": "prod", "cost_center": "CC-ENG", "owner": "devops"}',
                }
            ),
            "monthly_recurring_cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "annual_contract_value": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "provisioned_seats": forms.NumberInput(attrs={"min": "0"}),
            "active_seats_30d": forms.NumberInput(attrs={"min": "0"}),
            "cancellation_notice_days": forms.NumberInput(attrs={"min": "0"}),
            "renewal_date": forms.DateInput(attrs={"type": "date"}),
            "vendor_eol_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "FinOps right-sizing notes, reserved instance term, or Shadow IT investigation...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scope_tenant_querysets(self, self._TENANT_FIELDS)
        if "currency" in self.fields:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")

    def clean_resource_tags(self):
        return normalize_json_dict_value(self.cleaned_data.get("resource_tags"))

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, tuple(self._TENANT_FIELDS.keys()))
        mrc = cleaned.get("monthly_recurring_cost")
        acv = cleaned.get("annual_contract_value")
        if mrc is not None and mrc < 0:
            self.add_error("monthly_recurring_cost", "Monthly recurring cost cannot be negative.")
        if acv is not None and acv < 0:
            self.add_error("annual_contract_value", "Annual contract value cannot be negative.")
        provisioned = cleaned.get("provisioned_seats") or 0
        active = cleaned.get("active_seats_30d") or 0
        if provisioned > 0 and active > provisioned:
            self.add_error("active_seats_30d", "Active seats in last 30 days cannot exceed provisioned seats.")
        return cleaned
