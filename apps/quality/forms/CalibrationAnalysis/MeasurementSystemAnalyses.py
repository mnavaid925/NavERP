from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysis
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()


class MeasurementSystemAnalysisForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MeasurementSystemAnalysis
        exclude = ("tenant", "number", "raw_study_data", "approved_at", "created_at", "updated_at")
        widgets = {
            "study_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Micrometer 0-25mm Gage R&R"}),
            "gage": forms.Select(attrs={"class": "form-select"}),
            "study_type": forms.Select(attrs={"class": "form-select"}),
            "analysis_method": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "characteristic_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Outer Diameter (OD)"}),
            "study_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "number_of_operators": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "number_of_parts": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "number_of_trials": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "specification_tolerance": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "reference_master_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "repeatability_ev": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "reproducibility_av": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "gage_rr_grr": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "part_variation_pv": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "total_variation_tv": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "percent_gage_rr_study_variation": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "percent_tolerance_pt_ratio": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "number_of_distinct_categories_ndc": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "bias_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "bias_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "linearity_slope": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "linearity_r_squared": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "study_result": forms.Select(attrs={"class": "form-select"}),
            "study_protocol_doc": forms.Select(attrs={"class": "form-select"}),
            "study_lead": forms.Select(attrs={"class": "form-select"}),
            "approved_by": forms.Select(attrs={"class": "form-select"}),
            "conclusion": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["gage"].queryset = CalibrationGage.objects.filter(tenant=self.tenant)
            self.fields["study_protocol_doc"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)
            self.fields["study_lead"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["approved_by"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self, cleaned,
            ["gage", "study_protocol_doc", "study_lead", "approved_by"]
        )
        ops = cleaned.get("number_of_operators")
        parts = cleaned.get("number_of_parts")
        trials = cleaned.get("number_of_trials")
        tol = cleaned.get("specification_tolerance")

        if ops is not None and ops < 1:
            self.add_error("number_of_operators", "Operators must be at least 1.")
        if parts is not None and parts < 1:
            self.add_error("number_of_parts", "Parts must be at least 1.")
        if trials is not None and trials < 1:
            self.add_error("number_of_trials", "Trials must be at least 1.")
        if tol is not None and tol <= Decimal("0"):
            self.add_error("specification_tolerance", "Specification tolerance must be positive.")
        return cleaned
