from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.LimsManagement.LabTestWorksheets import LabTestWorksheet

User = get_user_model()


class LabTestWorksheetForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LabTestWorksheet
        fields = [
            "title",
            "sample",
            "specification",
            "status",
            "disposition",
            "assigned_analyst",
            "reviewer",
            "scheduled_date",
            "execution_date",
            "instrument",
            "instrument_name",
            "reagent_lot_number",
            "reagent_expiry_date",
            "standards_lot_number",
            "standards_expiry_date",
            "raw_data_summary",
            "numeric_result",
            "qualitative_result",
            "is_within_specification",
            "relative_standard_deviation",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "sample": forms.Select(attrs={"class": "form-select"}),
            "specification": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "disposition": forms.Select(attrs={"class": "form-select"}),
            "assigned_analyst": forms.Select(attrs={"class": "form-select"}),
            "reviewer": forms.Select(attrs={"class": "form-select"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "execution_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "instrument": forms.Select(attrs={"class": "form-select"}),
            "instrument_name": forms.TextInput(attrs={"class": "form-input"}),
            "reagent_lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "reagent_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "standards_lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "standards_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "raw_data_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "numeric_result": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "qualitative_result": forms.TextInput(attrs={"class": "form-input"}),
            "is_within_specification": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "relative_standard_deviation": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            LabSample = apps.get_model("quality", "LabSample")
            self.fields["sample"].queryset = LabSample.objects.filter(tenant=self.tenant)

            LabSpecification = apps.get_model("quality", "LabSpecification")
            self.fields["specification"].queryset = LabSpecification.objects.filter(tenant=self.tenant)

            self.fields["assigned_analyst"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["reviewer"].queryset = User.objects.filter(tenant=self.tenant)

            CalibrationGage = apps.get_model("quality", "CalibrationGage")
            self.fields["instrument"].queryset = CalibrationGage.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "sample",
                "specification",
                "assigned_analyst",
                "reviewer",
                "instrument",
            ],
        )

        spec = cleaned_data.get("specification")
        numeric = cleaned_data.get("numeric_result")
        if spec and numeric is not None:
            within = True
            if spec.lower_limit is not None and numeric < spec.lower_limit:
                within = False
            if spec.upper_limit is not None and numeric > spec.upper_limit:
                within = False
            if not within:
                cleaned_data["is_within_specification"] = False
                if cleaned_data.get("disposition") == "conforms":
                    cleaned_data["disposition"] = "oos_flagged"

        return cleaned_data
