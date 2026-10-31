from django import forms
from django.utils.text import slugify

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan


class SubscriptionPlanForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "name",
            "code",
            "plan_type",
            "frequency",
            "interval_count",
            "discount_type",
            "discount_value",
            "trial_period_days",
            "min_commitment_cycles",
            "allow_pause",
            "allow_skip",
            "allow_swap",
            "max_pause_days",
            "target_product",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Monthly Coffee Club"}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. monthly-coffee-club"}
            ),
            "plan_type": forms.Select(attrs={"class": "form-select"}),
            "frequency": forms.Select(attrs={"class": "form-select"}),
            "interval_count": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "1", "min": 1}
            ),
            "discount_type": forms.Select(attrs={"class": "form-select"}),
            "discount_value": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "15.00", "step": "0.01", "min": 0}
            ),
            "trial_period_days": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0", "min": 0}
            ),
            "min_commitment_cycles": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "1", "min": 1}
            ),
            "allow_pause": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "allow_skip": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "allow_swap": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "max_pause_days": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "90", "min": 1}
            ),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Terms and conditions, shipment cadence notes, perks...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant, status="active"
            ).order_by("name")

    def clean_code(self):
        code = self.cleaned_data.get("code", "")
        if code:
            code = slugify(code)
        elif self.cleaned_data.get("name"):
            code = slugify(self.cleaned_data.get("name"))
        return code

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["target_product"])
        return cleaned
