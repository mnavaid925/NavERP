"""Sales 8.14 — Forms for `ChannelConflict`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Opportunity, Territory
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.PartnerChannel.ChannelConflicts import ChannelConflict
from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration


class ChannelConflictForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ChannelConflict
        fields = [
            "conflict_type",
            "severity",
            "status",
            "deal_registration",
            "opportunity",
            "claimant_partner",
            "competing_partner",
            "direct_sales_rep",
            "client_account",
            "territory",
            "escalation_level",
            "escalated_to",
            "resolution_outcome",
            "split_percentage",
            "resolution_rationale",
            "resolved_by",
            "resolved_at",
            "description",
        ]
        widgets = {
            "conflict_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "deal_registration": forms.Select(attrs={"class": "form-select"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "claimant_partner": forms.Select(attrs={"class": "form-select"}),
            "competing_partner": forms.Select(attrs={"class": "form-select"}),
            "direct_sales_rep": forms.Select(attrs={"class": "form-select"}),
            "client_account": forms.Select(attrs={"class": "form-select"}),
            "territory": forms.Select(attrs={"class": "form-select"}),
            "escalation_level": forms.Select(attrs={"class": "form-select"}),
            "escalated_to": forms.Select(attrs={"class": "form-select"}),
            "resolution_outcome": forms.Select(attrs={"class": "form-select"}),
            "split_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}),
            "resolution_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "resolved_by": forms.Select(attrs={"class": "form-select"}),
            "resolved_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            partner_qs = (
                Party.objects.filter(tenant=self.tenant, roles__role="partner")
                .distinct()
                .order_by("name")
            )
            if not partner_qs.exists():
                partner_qs = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["claimant_partner"].queryset = partner_qs
            self.fields["competing_partner"].queryset = partner_qs

            client_qs = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            if not client_qs.exists():
                client_qs = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["client_account"].queryset = client_qs

            self.fields["deal_registration"].queryset = (
                DealRegistration.objects.filter(tenant=self.tenant).order_by("-submission_date")
            )
            self.fields["opportunity"].queryset = (
                Opportunity.objects.filter(tenant=self.tenant).order_by("-created_at")
            )
            self.fields["territory"].queryset = (
                Territory.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
            )

            users_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name")
            self.fields["direct_sales_rep"].queryset = users_qs
            self.fields["escalated_to"].queryset = users_qs
            self.fields["resolved_by"].queryset = users_qs

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            [
                "claimant_partner",
                "competing_partner",
                "client_account",
                "deal_registration",
                "opportunity",
                "territory",
                "direct_sales_rep",
                "escalated_to",
                "resolved_by",
            ],
        )
        return cleaned_data
