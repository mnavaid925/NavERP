from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CapaManagement.RootCauseAnalyses import RootCauseAnalysis
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder

User = get_user_model()


class CapaActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CapaAction
        fields = [
            "capa",
            "root_cause",
            "action_type",
            "title",
            "description",
            "assigned_to",
            "department",
            "due_date",
            "status",
            "implementation_notes",
            "controlled_document",
            "change_order",
            "design_project",
        ]
        widgets = {
            "capa": forms.Select(attrs={"class": "form-select"}),
            "root_cause": forms.Select(attrs={"class": "form-select"}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Update Occlusion Pressure Test Calibration Protocol SOP"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed work instructions, remediation steps, and expected deliverables..."}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "implementation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Evidence of execution, completion summary, and outcome..."}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "change_order": forms.Select(attrs={"class": "form-select"}),
            "design_project": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            self.fields["root_cause"].queryset = RootCauseAnalysis.objects.filter(tenant=self.tenant)
            self.fields["assigned_to"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)
            self.fields["change_order"].queryset = DocumentChangeOrder.objects.filter(tenant=self.tenant)
            self.fields["design_project"].queryset = DesignProject.objects.filter(tenant=self.tenant)
        else:
            self.fields["capa"].queryset = CapaInvestigation.objects.none()
            self.fields["root_cause"].queryset = RootCauseAnalysis.objects.none()
            self.fields["assigned_to"].queryset = User.objects.none()
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["controlled_document"].queryset = ControlledDocument.objects.none()
            self.fields["change_order"].queryset = DocumentChangeOrder.objects.none()
            self.fields["design_project"].queryset = DesignProject.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "capa",
                "root_cause",
                "assigned_to",
                "department",
                "controlled_document",
                "change_order",
                "design_project",
            ],
        )
        return cleaned
