from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class BackorderPolicyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BackorderPolicy
        fields = [
            "variant",
            "policy_type",
            "storefront_message",
            "expected_availability_date",
            "max_backorder_quantity",
            "auto_notify_waitlist",
            "is_active",
            "notes",
        ]
        widgets = {
            "variant": forms.Select(attrs={"class": "form-select"}),
            "policy_type": forms.Select(attrs={"class": "form-select"}),
            "storefront_message": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Backordered. Expected dispatch in 2-3 weeks."}
            ),
            "expected_availability_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "max_backorder_quantity": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["variant"])
        return cleaned
