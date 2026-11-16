from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.DesignControls.DesignProjects import DesignProject

User = get_user_model()


class DesignProjectForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DesignProject
        fields = [
            "title",
            "device_name",
            "device_class",
            "regulatory_pathway",
            "intended_use",
            "current_phase",
            "status",
            "project_lead",
            "quality_lead",
            "department",
            "target_completion_date",
            "actual_completion_date",
            "dhf_location",
            "description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. NextGen Infusion Pump System"}),
            "device_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. InfuseFlow Pro 3000"}),
            "device_class": forms.Select(attrs={"class": "form-select"}),
            "regulatory_pathway": forms.Select(attrs={"class": "form-select"}),
            "intended_use": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "State clinical intended use, indications, target patient population..."}),
            "current_phase": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "project_lead": forms.Select(attrs={"class": "form-select"}),
            "quality_lead": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "target_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "actual_completion_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "dhf_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. DHF-VOL-01 or QMS Vault Folder"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Project background, objectives, and scope boundaries..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["project_lead"].queryset = user_qs
            self.fields["quality_lead"].queryset = user_qs
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["project_lead"].queryset = User.objects.none()
            self.fields["quality_lead"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["department", "project_lead", "quality_lead"])
        if self.instance and getattr(self.instance, "dhf_locked", False):
            if self.cleaned_data.get("status") != self.instance.status:
                raise forms.ValidationError("This project's DHF is locked. Re-opening requires formal Change Control.")
        return cleaned
