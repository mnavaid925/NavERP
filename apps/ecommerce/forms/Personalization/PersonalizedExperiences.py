from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.Personalization.PersonalizedExperiences import PersonalizedExperience
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class PersonalizedExperienceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PersonalizedExperience
        fields = [
            "name",
            "experience_type",
            "target_segment",
            "target_category",
            "target_product",
            "headline",
            "subheadline",
            "cta_label",
            "cta_url",
            "hero_image_url",
            "trigger_delay_hours",
            "priority",
            "start_date",
            "end_date",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. VIP Winter Collection Hero"}
            ),
            "experience_type": forms.Select(attrs={"class": "form-select"}),
            "target_segment": forms.Select(attrs={"class": "form-select"}),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "headline": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Exclusive VIP Early Access"}
            ),
            "subheadline": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Supporting promotional message or discount copy...",
                }
            ),
            "cta_label": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Shop Collection"}
            ),
            "cta_url": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. /category/vip-specials/"}
            ),
            "hero_image_url": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. https://cdn.example.com/banner.jpg"}
            ),
            "trigger_delay_hours": forms.NumberInput(
                attrs={"class": "form-input", "min": 0}
            ),
            "priority": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "start_date": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "end_date": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_segment"].queryset = AudienceSegment.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["target_category"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            ).exclude(status="archived").order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["target_segment", "target_category", "target_product"])
        return cleaned
