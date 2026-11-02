from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bCompanyUsers import B2bCompanyUser


class B2bCompanyUserForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = B2bCompanyUser
        exclude = ["tenant", "number", "created_at", "updated_at", "monthly_spend_current"]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "user": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "job_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Senior Procurement Officer"}),
            "department": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Facilities Management"}),
            "order_spend_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "5000.00"}),
            "monthly_spend_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "25000.00"}),
            "can_place_orders": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_request_quotes": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_view_invoices": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_manage_users": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "can_approve_orders": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "reports_to_approver": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["company"].queryset = B2bCompanyAccount.objects.filter(tenant=self.tenant)
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant)
            approver_qs = B2bCompanyUser.objects.filter(
                tenant=self.tenant, can_approve_orders=True
            ).select_related("user", "company")
            if self.instance and self.instance.pk:
                approver_qs = approver_qs.exclude(pk=self.instance.pk)
            self.fields["reports_to_approver"].queryset = approver_qs
        self.fields["user"].queryset = User.objects.filter(is_active=True)

    def clean_order_spend_limit(self):
        val = self.cleaned_data.get("order_spend_limit")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Order spend limit cannot be negative.")
        return val

    def clean_monthly_spend_limit(self):
        val = self.cleaned_data.get("monthly_spend_limit")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Monthly spend limit cannot be negative.")
        return val

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["company", "party", "reports_to_approver"])
        company = cleaned.get("company")
        approver = cleaned.get("reports_to_approver")
        if approver:
            if self.instance and self.instance.pk and approver.pk == self.instance.pk:
                self.add_error("reports_to_approver", "A user cannot report to themselves as approver.")
            if company and approver.company_id != company.id:
                self.add_error("reports_to_approver", "The designated approver must belong to the same wholesale company.")
        return cleaned
