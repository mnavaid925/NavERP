from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.LimsManagement.LabSpecifications import LabSpecification

User = get_user_model()


class LabSpecificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LabSpecification
        fields = [
            "title",
            "specification_type",
            "status",
            "version",
            "product_code",
            "product_name",
            "analytical_method_number",
            "test_category",
            "sop_document",
            "target_parameter_name",
            "parameter_unit",
            "lower_limit",
            "upper_limit",
            "target_value",
            "text_acceptance_criteria",
            "method_validation_reference",
            "method_validation_date",
            "effective_date",
            "review_due_date",
            "approved_by",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "specification_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "version": forms.TextInput(attrs={"class": "form-input"}),
            "product_code": forms.TextInput(attrs={"class": "form-input"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "analytical_method_number": forms.TextInput(attrs={"class": "form-input"}),
            "test_category": forms.Select(attrs={"class": "form-select"}),
            "sop_document": forms.Select(attrs={"class": "form-select"}),
            "target_parameter_name": forms.TextInput(attrs={"class": "form-input"}),
            "parameter_unit": forms.TextInput(attrs={"class": "form-input"}),
            "lower_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "upper_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "text_acceptance_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "method_validation_reference": forms.TextInput(attrs={"class": "form-input"}),
            "method_validation_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "review_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            ControlledDocument = apps.get_model("quality", "ControlledDocument")
            self.fields["sop_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)
            self.fields["approved_by"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["sop_document", "approved_by"])

        lower = cleaned_data.get("lower_limit")
        upper = cleaned_data.get("upper_limit")
        if lower is not None and upper is not None and lower > upper:
            self.add_error("lower_limit", "Lower limit cannot be greater than upper limit.")
        return cleaned_data
