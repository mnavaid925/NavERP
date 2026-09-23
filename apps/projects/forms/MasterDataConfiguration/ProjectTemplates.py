"""Projects 7.19 — ProjectTemplate forms."""
import json
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate
from apps.projects.models.ProjectInitiation.Projects import Project

User = get_user_model()


class ProjectTemplateForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for creating and updating project templates."""

    default_roles_raw = forms.CharField(
        label="Default Team Roles (one per line or JSON array)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "Project Manager\nLead Developer\nQA Specialist"}),
        required=False,
        help_text="Standard project team roles suggested for projects using this blueprint.",
    )
    wbs_structure_raw = forms.CharField(
        label="Work Breakdown Structure (JSON)",
        widget=forms.Textarea(attrs={"rows": 8, "class": "form-textarea font-mono text-sm", "placeholder": '[\n  {\n    "phase": "Discovery",\n    "order": 1,\n    "tasks": [{"name": "Scope Definition", "duration_days": 5, "is_milestone": false}]\n  }\n]'}),
        required=False,
        help_text="Structured phase, deliverable, and task definitions in JSON format.",
    )
    workflow_config_raw = forms.CharField(
        label="Lifecycle Stage-Gate Config (JSON)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-sm", "placeholder": '{"stage_gates": ["Charter Signoff", "Architecture Review", "UAT Approval"]}'}),
        required=False,
        help_text="Stage-gate approval criteria and transition requirements.",
    )

    class Meta:
        model = ProjectTemplate
        fields = [
            "name",
            "code",
            "methodology",
            "category",
            "complexity",
            "description",
            "estimated_duration_days",
            "target_budget",
            "is_active",
            "is_default",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise Cloud Modernization"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TMPL-CLOUD-01"}),
            "methodology": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "complexity": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "estimated_duration_days": forms.NumberInput(attrs={"class": "form-input"}),
            "target_budget": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.default_roles:
                if isinstance(self.instance.default_roles, list):
                    self.initial["default_roles_raw"] = "\n".join(str(r) for r in self.instance.default_roles)
                else:
                    self.initial["default_roles_raw"] = json.dumps(self.instance.default_roles, indent=2)
            if self.instance.wbs_structure:
                self.initial["wbs_structure_raw"] = json.dumps(self.instance.wbs_structure, indent=2)
            if self.instance.workflow_config:
                self.initial["workflow_config_raw"] = json.dumps(self.instance.workflow_config, indent=2)

    def clean_default_roles_raw(self):
        val = self.cleaned_data.get("default_roles_raw", "").strip()
        if not val:
            return []
        if val.startswith("["):
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, list):
                    raise forms.ValidationError("Default roles JSON must be a list of role names.")
                return parsed
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON: {exc}")
        # Otherwise parse line by line
        return [line.strip() for line in val.splitlines() if line.strip()]

    def clean_wbs_structure_raw(self):
        val = self.cleaned_data.get("wbs_structure_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("WBS structure must be a JSON array of phases.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_workflow_config_raw(self):
        val = self.cleaned_data.get("workflow_config_raw", "").strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Workflow config must be a JSON object.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.default_roles = self.cleaned_data.get("default_roles_raw", [])
        instance.wbs_structure = self.cleaned_data.get("wbs_structure_raw", [])
        instance.workflow_config = self.cleaned_data.get("workflow_config_raw", {})
        if commit:
            instance.save()
        return instance


class ProjectTemplateInstantiateForm(forms.Form):
    """Instantiate a live Project from a ProjectTemplate."""

    project_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Cloud Infrastructure Transformation"}),
        help_text="Name of the new chartered project.",
    )
    project_code = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRJ-2026-09"}),
        help_text="Short project code.",
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        initial=timezone.now,
        help_text="Project initiation/kickoff date.",
    )
    target_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        help_text="Expected delivery completion date.",
    )
    client = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Client organization (Party) commissioning this project.",
    )
    project_manager = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Lead Project Manager accountable for delivery.",
    )
    clone_wbs_tasks = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Automatically create initial WBS tasks and milestones from template.",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["client"].queryset = Party.objects.filter(tenant=tenant, is_active=True).order_by("name")
            self.fields["project_manager"].queryset = User.objects.filter(
                models.Q(tenant=tenant) | models.Q(tenant__isnull=True),
                is_active=True,
            ).order_by("username")
