from django import forms
from django.utils.text import slugify

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class AudienceSegmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AudienceSegment
        fields = [
            "name",
            "code",
            "lifecycle_stage",
            "recency_days_max",
            "min_order_count",
            "min_lifetime_spend",
            "target_category",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. VIP High-Value Shoppers"}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. vip-high-value"}
            ),
            "lifecycle_stage": forms.Select(attrs={"class": "form-select"}),
            "recency_days_max": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "e.g. 30", "min": 0}
            ),
            "min_order_count": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "e.g. 3", "min": 0}
            ),
            "min_lifetime_spend": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0.00", "step": "0.01", "min": 0}
            ),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Operational notes on cohort definitions and promotional strategy...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_category"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant, is_active=True
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
        reject_foreign(self, cleaned, ["target_category"])
        return cleaned
