"""Sales 8.14 — Forms for `DealRegistration`."""
from django import forms

from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.PartnerChannel.DealRegistrations import DealRegistration


class DealRegistrationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DealRegistration
        fields = [
            "partner",
            "customer_account",
            "deal_name",
            "estimated_value",
            "currency",
            "expected_close_date",
            "submission_date",
            "status",
            "rejection_reason",
            "protection_start_date",
            "protection_end_date",
            "exclusivity_status",
            "protected_margin_pct",
            "extension_count",
            "is_conflicted",
            "conflict_summary",
            "opportunity",
            "partner_rep_name",
            "partner_rep_email",
            "notes",
        ]
        widgets = {
            "partner": forms.Select(attrs={"class": "form-select"}),
            "customer_account": forms.Select(attrs={"class": "form-select"}),
            "deal_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Corp Cloud ERP Rollout"}),
            "estimated_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0.01}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "expected_close_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "submission_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "rejection_reason": forms.TextInput(attrs={"class": "form-input"}),
            "protection_start_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "protection_end_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "exclusivity_status": forms.Select(attrs={"class": "form-select"}),
            "protected_margin_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}),
            "extension_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "is_conflicted": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "conflict_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "partner_rep_name": forms.TextInput(attrs={"class": "form-input"}),
            "partner_rep_email": forms.EmailInput(attrs={"class": "form-input"}),
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
            if not self.fields["partner"].queryset.exists():
                self.fields["partner"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["customer_account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            if not self.fields["customer_account"].queryset.exists():
                self.fields["customer_account"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["opportunity"].queryset = (
                Opportunity.objects.filter(tenant=self.tenant).order_by("-created_at")
            )

        self.fields["currency"].queryset = Currency.objects.all().order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["partner", "customer_account", "opportunity"])
        return cleaned_data
