"""Sales 8.14 — Forms for `JointAccountPlan`."""
from django import forms

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Document, Party
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.PartnerChannel.JointAccountPlans import JointAccountPlan


class JointAccountPlanForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = JointAccountPlan
        fields = [
            "partner",
            "client_account",
            "plan_name",
            "plan_year",
            "period_start",
            "period_end",
            "status",
            "target_revenue",
            "actual_revenue",
            "currency",
            "vendor_lead",
            "partner_lead_name",
            "partner_lead_email",
            "co_sell_motion",
            "strategic_objectives",
            "joint_value_proposition",
            "collateral_document",
            "notes",
        ]
        widgets = {
            "partner": forms.Select(attrs={"class": "form-select"}),
            "client_account": forms.Select(attrs={"class": "form-select"}),
            "plan_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2026 Enterprise FinTech Expansion"}),
            "plan_year": forms.NumberInput(attrs={"class": "form-input", "min": 2020, "max": 2040}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "actual_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "vendor_lead": forms.Select(attrs={"class": "form-select"}),
            "partner_lead_name": forms.TextInput(attrs={"class": "form-input"}),
            "partner_lead_email": forms.EmailInput(attrs={"class": "form-input"}),
            "co_sell_motion": forms.Select(attrs={"class": "form-select"}),
            "strategic_objectives": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "joint_value_proposition": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "collateral_document": forms.Select(attrs={"class": "form-select"}),
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

            self.fields["client_account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            if not self.fields["client_account"].queryset.exists():
                self.fields["client_account"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")

            self.fields["vendor_lead"].queryset = (
                User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name")
            )
            self.fields["collateral_document"].queryset = (
                Document.objects.filter(tenant=self.tenant).order_by("-uploaded_at")
            )

        self.fields["currency"].queryset = Currency.objects.all().order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["partner", "client_account", "vendor_lead", "collateral_document"])
        return cleaned_data
