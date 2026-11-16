from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument

User = get_user_model()


class DesignInputForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DesignInput
        fields = [
            "project",
            "identifier",
            "title",
            "input_type",
            "priority",
            "status",
            "description",
            "acceptance_criteria",
            "rationale",
            "user_need_parent",
            "controlled_document",
            "owner",
            "version",
        ]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "identifier": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. UN-001 or DI-ENG-005"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Requirement or specification headline"}),
            "input_type": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Precise, objective, and unambiguous requirement statement..."}),
            "acceptance_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Quantitative pass/fail threshold or verification criteria..."}),
            "rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Clinical, engineering, or risk-driven justification..."}),
            "user_need_parent": forms.Select(attrs={"class": "form-select"}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "version": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["project"].queryset = DesignProject.objects.filter(tenant=self.tenant).order_by("number")
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            parent_qs = DesignInput.objects.filter(tenant=self.tenant, input_type="user_need").order_by("identifier")
            if self.instance and self.instance.pk:
                parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["user_need_parent"].queryset = parent_qs
            self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant).order_by("number")
        else:
            self.fields["project"].queryset = DesignProject.objects.none()
            self.fields["owner"].queryset = User.objects.none()
            self.fields["user_need_parent"].queryset = DesignInput.objects.none()
            self.fields["controlled_document"].queryset = ControlledDocument.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["project", "owner", "user_need_parent", "controlled_document"])

        project = cleaned.get("project")
        user_need_parent = cleaned.get("user_need_parent")
        if project and user_need_parent and user_need_parent.project_id != project.pk:
            self.add_error("user_need_parent", "Parent user need must belong to the same design project.")

        return cleaned
