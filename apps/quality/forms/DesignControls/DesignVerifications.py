from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()


class DesignVerificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DesignVerification
        fields = [
            "project",
            "primary_input",
            "title",
            "activity_type",
            "status",
            "test_method",
            "acceptance_criteria",
            "sample_size",
            "results_summary",
            "pass_fail_result",
            "deviation_notes",
            "executed_by",
            "execution_date",
            "protocol_document",
            "report_document",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "primary_input": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Tensile Strength Test Protocol"}),
            "activity_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "test_method": forms.Select(attrs={"class": "form-select"}),
            "acceptance_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Predetermined objective criteria for verification pass..."}),
            "sample_size": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "results_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Observed test data, mean, standard deviation, and conformance..."}),
            "pass_fail_result": forms.Select(attrs={"class": "form-select"}),
            "deviation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Any test deviations, out-of-spec observations, or anomalies..."}),
            "executed_by": forms.Select(attrs={"class": "form-select"}),
            "execution_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "protocol_document": forms.Select(attrs={"class": "form-select"}),
            "report_document": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["project"].queryset = DesignProject.objects.filter(tenant=self.tenant).order_by("number")
            self.fields["primary_input"].queryset = DesignInput.objects.filter(tenant=self.tenant).select_related("project").order_by("project__number", "identifier")
            self.fields["executed_by"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            doc_qs = ControlledDocument.objects.filter(tenant=self.tenant).order_by("number")
            self.fields["protocol_document"].queryset = doc_qs
            self.fields["report_document"].queryset = doc_qs
        else:
            self.fields["project"].queryset = DesignProject.objects.none()
            self.fields["primary_input"].queryset = DesignInput.objects.none()
            self.fields["executed_by"].queryset = User.objects.none()
            self.fields["protocol_document"].queryset = ControlledDocument.objects.none()
            self.fields["report_document"].queryset = ControlledDocument.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["project", "primary_input", "executed_by", "protocol_document", "report_document"])

        project = cleaned.get("project")
        primary_input = cleaned.get("primary_input")
        if project and primary_input and primary_input.project_id != project.pk:
            self.add_error("primary_input", "Primary design input must belong to the selected design project.")

        return cleaned
