from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport

User = get_user_model()


class MrbDispositionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MrbDisposition
        fields = [
            "ncr",
            "title",
            "disposition_decision",
            "technical_justification",
            "concession_rationale",
            "rework_instructions",
            "rework_assignee",
            "rework_completed_date",
            "reinspection_required",
            "reinspection_criteria",
            "reinspection_passed",
            "reinspection_by",
            "scrap_cost",
            "rework_labor_cost",
            "vendor_chargeback_cost",
            "mrb_chair",
            "quality_approved_by",
            "engineering_approved_by",
            "operations_approved_by",
            "status",
        ]
        widgets = {
            "ncr": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. MRB Disposition on Solder Bridge Defect Batch 12"}),
            "disposition_decision": forms.Select(attrs={"class": "form-select"}),
            "technical_justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Engineering and quality rationale for the chosen disposition..."}),
            "concession_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Risk justification if Use-As-Is concession is granted..."}),
            "rework_instructions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Step-by-step rework or repair instructions..."}),
            "rework_assignee": forms.Select(attrs={"class": "form-select"}),
            "rework_completed_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "reinspection_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "reinspection_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Post-rework acceptance criteria and test parameters..."}),
            "reinspection_passed": forms.NullBooleanSelect(attrs={"class": "form-select"}),
            "reinspection_by": forms.Select(attrs={"class": "form-select"}),
            "scrap_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "rework_labor_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "vendor_chargeback_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "mrb_chair": forms.Select(attrs={"class": "form-select"}),
            "quality_approved_by": forms.Select(attrs={"class": "form-select"}),
            "engineering_approved_by": forms.Select(attrs={"class": "form-select"}),
            "operations_approved_by": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["ncr"].queryset = NonConformanceReport.objects.filter(tenant=self.tenant).order_by("-created_at")
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["rework_assignee"].queryset = user_qs
            self.fields["reinspection_by"].queryset = user_qs
            self.fields["mrb_chair"].queryset = user_qs
            self.fields["quality_approved_by"].queryset = user_qs
            self.fields["engineering_approved_by"].queryset = user_qs
            self.fields["operations_approved_by"].queryset = user_qs
        else:
            self.fields["ncr"].queryset = NonConformanceReport.objects.none()
            user_none = User.objects.none()
            self.fields["rework_assignee"].queryset = user_none
            self.fields["reinspection_by"].queryset = user_none
            self.fields["mrb_chair"].queryset = user_none
            self.fields["quality_approved_by"].queryset = user_none
            self.fields["engineering_approved_by"].queryset = user_none
            self.fields["operations_approved_by"].queryset = user_none

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "ncr",
                "rework_assignee",
                "reinspection_by",
                "mrb_chair",
                "quality_approved_by",
                "engineering_approved_by",
                "operations_approved_by",
            ],
        )
        return cleaned
