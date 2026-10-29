from django import forms
from django.utils.text import slugify

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.Personalization.RecommendationStrategies import RecommendationStrategy
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class RecommendationStrategyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RecommendationStrategy
        fields = [
            "name",
            "code",
            "algorithm",
            "placement",
            "fallback_strategy",
            "max_items",
            "min_rating",
            "same_brand_only",
            "only_in_stock",
            "target_category",
            "target_segment",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. PDP Similar Category Items"}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. pdp-similar-items"}
            ),
            "algorithm": forms.Select(attrs={"class": "form-select"}),
            "placement": forms.Select(attrs={"class": "form-select"}),
            "fallback_strategy": forms.Select(attrs={"class": "form-select"}),
            "max_items": forms.NumberInput(
                attrs={"class": "form-input", "min": 1, "max": 50}
            ),
            "min_rating": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.1", "min": 0, "max": 5}
            ),
            "same_brand_only": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "only_in_stock": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "target_segment": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Operational notes on algorithm weights and fallback policy...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_category"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["target_segment"].queryset = AudienceSegment.objects.filter(
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
        reject_foreign(self, cleaned, ["target_category", "target_segment"])
        return cleaned
