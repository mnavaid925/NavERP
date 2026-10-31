from django import forms
from django.utils.text import slugify

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCuration
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan


class SubscriptionBoxCurationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SubscriptionBoxCuration
        fields = [
            "name",
            "code",
            "plan",
            "cycle_identifier",
            "theme_title",
            "primary_product",
            "preference_tag",
            "has_surprise_item",
            "surprise_item_description",
            "start_date",
            "end_date",
            "is_active",
            "curation_notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Winter Warmth Artisan Roast"}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. winter-warmth-2026"}
            ),
            "plan": forms.Select(attrs={"class": "form-select"}),
            "cycle_identifier": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. 2026-11 or Q4-2026"}
            ),
            "theme_title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Mountain Harvest Collection"}
            ),
            "primary_product": forms.Select(attrs={"class": "form-select"}),
            "preference_tag": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Dark Roast, Vegan, Sensitive Skin"}
            ),
            "has_surprise_item": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "surprise_item_description": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Handcrafted Ceramic Mug & Stirrer"}
            ),
            "start_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "curation_notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 4,
                    "placeholder": "Unboxing notes, tasting profile, artisan bio, usage instructions...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["plan"].queryset = SubscriptionPlan.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["primary_product"].queryset = CatalogProduct.objects.filter(
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
        reject_foreign(self, cleaned, ["plan", "primary_product"])
        return cleaned
