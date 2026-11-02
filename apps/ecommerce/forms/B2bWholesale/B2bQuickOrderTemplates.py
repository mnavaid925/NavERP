from django import forms
from django.contrib.auth import get_user_model
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplate


class B2bQuickOrderTemplateForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = B2bQuickOrderTemplate
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "total_items_count",
            "times_ordered",
            "last_ordered_at",
            "items_data",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "created_by": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Weekly Warehouse Consumables"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Template guidelines and recurring ordering schedule..."}),
            "scope": forms.Select(attrs={"class": "form-select"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["company"].queryset = B2bCompanyAccount.objects.filter(tenant=self.tenant)
        self.fields["created_by"].queryset = User.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["company"])
        return cleaned
