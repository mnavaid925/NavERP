from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CapaManagement.RootCauseAnalyses import RootCauseAnalysis

User = get_user_model()


class RootCauseAnalysisForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RootCauseAnalysis
        fields = [
            "capa",
            "rca_method",
            "problem_statement",
            "why_1",
            "why_2",
            "why_3",
            "why_4",
            "why_5",
            "fishbone_manpower",
            "fishbone_machine",
            "fishbone_material",
            "fishbone_method",
            "fishbone_measurement",
            "fishbone_environment",
            "root_cause_category",
            "root_cause_summary",
            "escape_point_gap",
            "status",
            "lead_investigator",
        ]
        widgets = {
            "capa": forms.Select(attrs={"class": "form-select"}),
            "rca_method": forms.Select(attrs={"class": "form-select"}),
            "problem_statement": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Concise definition of the specific failure symptom, deviation, or defect to investigate..."}),
            "why_1": forms.TextInput(attrs={"class": "form-input", "placeholder": "Why 1: Direct reason for failure..."}),
            "why_2": forms.TextInput(attrs={"class": "form-input", "placeholder": "Why 2: Underlying condition for Why 1..."}),
            "why_3": forms.TextInput(attrs={"class": "form-input", "placeholder": "Why 3: Why that condition occurred..."}),
            "why_4": forms.TextInput(attrs={"class": "form-input", "placeholder": "Why 4: Systemic reason..."}),
            "why_5": forms.TextInput(attrs={"class": "form-input", "placeholder": "Why 5: Fundamental root cause..."}),
            "fishbone_manpower": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Operator fatigue, qualification, procedural adherence, training..."}),
            "fishbone_machine": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Tooling wear, sensor drift, fixture misalignment, software glitch..."}),
            "fishbone_material": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Batch variance, supplier out-of-spec, raw material contamination..."}),
            "fishbone_method": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Ambiguous work instruction, inadequate test parameters, missing check..."}),
            "fishbone_measurement": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Gage R&R error, optical inspection resolution, calibration out..."}),
            "fishbone_environment": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Temperature swing, cleanroom particle excursion, humidity, ESD..."}),
            "root_cause_category": forms.Select(attrs={"class": "form-select"}),
            "root_cause_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Defensible conclusion synthesizing evidence that proves this is the root cause..."}),
            "escape_point_gap": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Why did quality inspection/in-process testing fail to catch the defect before release?..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "lead_investigator": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            self.fields["lead_investigator"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
        else:
            self.fields["capa"].queryset = CapaInvestigation.objects.none()
            self.fields["lead_investigator"].queryset = User.objects.none()

    def clean_status(self):
        status = self.cleaned_data.get("status")
        if status in ["verified"]:
            if not self.instance.pk or self.instance.status != status:
                raise forms.ValidationError(
                    f"Status '{status}' cannot be set directly. Use the verification action."
                )
        return status

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["capa", "lead_investigator"])
        return cleaned
