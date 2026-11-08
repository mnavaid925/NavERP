from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory


class AssetCategoryForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetCategory
        fields = [
            "code",
            "name",
            "parent",
            "category_type",
            "unspsc_code",
            "unspsc_title",
            "default_depreciation_method",
            "default_useful_life_months",
            "default_maintenance_strategy",
            "default_criticality",
            "description",
            "display_order",
            "is_active",
        ]
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. HVAC-CHL, PUMP-CENT"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Centrifugal Water Chillers"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "category_type": forms.Select(attrs={"class": "form-select"}),
            "unspsc_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 40151503"}),
            "unspsc_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Centrifugal pumps"}),
            "default_depreciation_method": forms.Select(attrs={"class": "form-select"}),
            "default_useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "default_maintenance_strategy": forms.Select(attrs={"class": "form-select"}),
            "default_criticality": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Scope and inclusion criteria..."}),
            "display_order": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            parents = AssetCategory.objects.filter(tenant=self.tenant, is_active=True).order_by("code")
            if self.instance and self.instance.pk:
                parents = parents.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = parents

    def clean_code(self):
        code = self.cleaned_data.get("code", "")
        if code:
            code = code.strip().upper()
        return code

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["parent"])
        return cleaned_data
