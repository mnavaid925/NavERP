from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.core.models import Party


class AssetModelForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetModel
        fields = [
            "model_number",
            "name",
            "category",
            "manufacturer",
            "manufacturer_name_fallback",
            "description",
            "standard_warranty_months",
            "warranty_coverage_type",
            "expected_useful_life_months",
            "default_meter_name",
            "default_meter_unit",
            "estimated_replacement_cost",
            "model_status",
            "technical_specifications",
            "is_active",
        ]
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "model_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CAT-320GC, CVHE-500"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 320 GC Hydraulic Excavator"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "manufacturer": forms.Select(attrs={"class": "form-select"}),
            "manufacturer_name_fallback": forms.TextInput(attrs={"class": "form-input", "placeholder": "Manufacturer name if Party record not linked"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Model overview, features, operational design..."}),
            "standard_warranty_months": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "warranty_coverage_type": forms.Select(attrs={"class": "form-select"}),
            "expected_useful_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "default_meter_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Operating Hours, Odometer"}),
            "default_meter_unit": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. h, km, cycles"}),
            "estimated_replacement_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "model_status": forms.Select(attrs={"class": "form-select"}),
            "technical_specifications": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Key engineering specifications (capacity, voltage, dimensions, weight)..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["category"].queryset = AssetCategory.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("code")
            self.fields["manufacturer"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean_model_number(self):
        val = self.cleaned_data.get("model_number", "")
        if val:
            val = val.strip().upper()
        return val

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["category", "manufacturer"])
        return cleaned_data
