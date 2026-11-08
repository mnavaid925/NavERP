from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.AssetClassification.AssetSpecificationTemplates import AssetSpecificationTemplate


class AssetSpecificationTemplateForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetSpecificationTemplate
        fields = [
            "attribute_key",
            "display_name",
            "category",
            "model",
            "data_type",
            "unit_of_measure",
            "default_value",
            "dropdown_options",
            "min_numeric_value",
            "max_numeric_value",
            "validation_regex",
            "is_required",
            "is_filterable",
            "display_order",
            "help_text",
        ]
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "attribute_key": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. rated_voltage, cooling_capacity_tons"}),
            "display_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Rated Operating Voltage"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "model": forms.Select(attrs={"class": "form-select"}),
            "data_type": forms.Select(attrs={"class": "form-select"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. V, kW, PSI, ton, RPM, GPM"}),
            "default_value": forms.TextInput(attrs={"class": "form-input", "placeholder": "Default initial value"}),
            "dropdown_options": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Option A, Option B, Option C (for select data type)"}),
            "min_numeric_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "max_numeric_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "validation_regex": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ^[0-9]{3}-[A-Z]{2}$"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_filterable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "help_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "Guidance for field technicians..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["category"].queryset = AssetCategory.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("code")
            self.fields["model"].queryset = AssetModel.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("model_number")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["category", "model"])

        cat = cleaned_data.get("category")
        mod = cleaned_data.get("model")
        if not cat and not mod:
            self.add_error("category", "Select either an Asset Category or an Equipment Model for this template.")

        return cleaned_data
