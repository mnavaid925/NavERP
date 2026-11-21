from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.LimsManagement.OosInvestigations import OosInvestigation

User = get_user_model()


class OosInvestigationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OosInvestigation
        fields = [
            "title",
            "test_worksheet",
            "sample",
            "investigation_phase",
            "status",
            "severity",
            "analyst_interview_completed",
            "calculation_verification_completed",
            "instrument_verification_completed",
            "reagent_verification_completed",
            "lab_error_identified",
            "lab_error_description",
            "manufacturing_investigation_required",
            "process_equipment_checked",
            "raw_material_lots_checked",
            "environmental_conditions_checked",
            "assignable_cause",
            "hypothesis_testing_summary",
            "retest_plan_authorized",
            "retest_results_summary",
            "final_batch_disposition",
            "investigation_lead",
            "qa_approver",
            "target_completion_date",
            "capa",
            "non_conformance",
            "summary_and_conclusions",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "test_worksheet": forms.Select(attrs={"class": "form-select"}),
            "sample": forms.Select(attrs={"class": "form-select"}),
            "investigation_phase": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "analyst_interview_completed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "calculation_verification_completed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "instrument_verification_completed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "reagent_verification_completed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "lab_error_identified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "lab_error_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "manufacturing_investigation_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "process_equipment_checked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "raw_material_lots_checked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "environmental_conditions_checked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "assignable_cause": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "hypothesis_testing_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "retest_plan_authorized": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "retest_results_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "final_batch_disposition": forms.Select(attrs={"class": "form-select"}),
            "investigation_lead": forms.Select(attrs={"class": "form-select"}),
            "qa_approver": forms.Select(attrs={"class": "form-select"}),
            "target_completion_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "capa": forms.Select(attrs={"class": "form-select"}),
            "non_conformance": forms.Select(attrs={"class": "form-select"}),
            "summary_and_conclusions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            LabTestWorksheet = apps.get_model("quality", "LabTestWorksheet")
            self.fields["test_worksheet"].queryset = LabTestWorksheet.objects.filter(tenant=self.tenant)

            LabSample = apps.get_model("quality", "LabSample")
            self.fields["sample"].queryset = LabSample.objects.filter(tenant=self.tenant)

            self.fields["investigation_lead"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["qa_approver"].queryset = User.objects.filter(tenant=self.tenant)

            CapaInvestigation = apps.get_model("quality", "CapaInvestigation")
            self.fields["capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)

            NonConformanceReport = apps.get_model("quality", "NonConformanceReport")
            self.fields["non_conformance"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "test_worksheet",
                "sample",
                "investigation_lead",
                "qa_approver",
                "capa",
                "non_conformance",
            ],
        )
        return cleaned_data
