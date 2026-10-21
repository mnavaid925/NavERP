"""Sales 8.14 — Forms for `PartnerProfile`."""
from django import forms

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Document, Party
from apps.crm.models import Territory
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.PartnerChannel.PartnerProfiles import PartnerProfile


class PartnerProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PartnerProfile
        fields = [
            "partner",
            "partner_type",
            "onboarding_status",
            "tier",
            "tier_effective_date",
            "tier_review_date",
            "application_date",
            "agreement_signed_at",
            "agreement_document",
            "channel_manager",
            "authorized_territory",
            "currency",
            "annual_revenue_target",
            "actual_revenue_ytd",
            "required_certifications_count",
            "active_certifications_count",
            "base_discount_pct",
            "deal_reg_margin_pct",
            "portal_access_enabled",
            "notes",
        ]
        widgets = {
            "partner": forms.Select(attrs={"class": "form-select"}),
            "partner_type": forms.Select(attrs={"class": "form-select"}),
            "onboarding_status": forms.Select(attrs={"class": "form-select"}),
            "tier": forms.Select(attrs={"class": "form-select"}),
            "tier_effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "tier_review_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "application_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "agreement_signed_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "agreement_document": forms.Select(attrs={"class": "form-select"}),
            "channel_manager": forms.Select(attrs={"class": "form-select"}),
            "authorized_territory": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "annual_revenue_target": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "actual_revenue_ytd": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "required_certifications_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "active_certifications_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "base_discount_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}),
            "deal_reg_margin_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}),
            "portal_access_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["partner"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="partner")
                .distinct()
                .order_by("name")
            )
            # Fallback if no specific partner role rows exist yet
            if not self.fields["partner"].queryset.exists():
                self.fields["partner"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["channel_manager"].queryset = (
                User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name")
            )
            self.fields["authorized_territory"].queryset = (
                Territory.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
            )
            self.fields["agreement_document"].queryset = (
                Document.objects.filter(tenant=self.tenant).order_by("-created_at")
            )

        self.fields["currency"].queryset = Currency.objects.all().order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["partner", "authorized_territory", "agreement_document", "channel_manager"])
        return cleaned_data
