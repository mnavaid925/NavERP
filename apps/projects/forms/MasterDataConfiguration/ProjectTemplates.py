"""Projects 7.19 — ProjectTemplate forms."""
import json

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Party
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import (
    WBS_MAX_JSON_BYTES,
    WORKFLOW_MAX_JSON_BYTES,
    ProjectTemplate,
    normalize_default_roles,
    normalize_wbs_structure,
    normalize_workflow_config,
)
from apps.projects.models.ProjectInitiation.Projects import Project

User = get_user_model()


def _parse_bounded_json(raw, max_bytes, label):
    if len(raw.encode("utf-8")) > max_bytes:
        raise forms.ValidationError(f"{label} exceeds the {max_bytes}-byte limit.")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise forms.ValidationError(f"Invalid JSON: {exc}")


class ProjectTemplateForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for creating and updating project templates."""

    default_roles_raw = forms.CharField(
        label="Default Team Roles (one per line or JSON array)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "Project Manager\nLead Developer\nQA Specialist"}),
        required=False,
        strip=False,
        help_text="Standard project team roles suggested for projects using this blueprint.",
    )
    wbs_structure_raw = forms.CharField(
        label="Work Breakdown Structure (JSON)",
        widget=forms.Textarea(attrs={"rows": 8, "class": "form-textarea font-mono text-sm", "placeholder": '[\n  {\n    "phase": "Discovery",\n    "order": 1,\n    "tasks": [{"name": "Scope Definition", "duration_days": 5, "is_milestone": false}]\n  }\n]'}),
        required=False,
        strip=False,
        help_text="Structured phase, deliverable, and task definitions in JSON format.",
    )
    workflow_config_raw = forms.CharField(
        label="Lifecycle Stage-Gate Config (JSON)",
        widget=forms.Textarea(attrs={"rows": 6, "class": "form-textarea font-mono text-sm", "placeholder": '{"rules": [], "approval_gates": []}'}),
        required=False,
        strip=False,
        help_text="Use rules and approval_gates entries; they materialize through Projects 7.17 on instantiation.",
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
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check"}),
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
        raw = self.cleaned_data.get("default_roles_raw", "")
        if len(raw.encode("utf-8")) > 16384:
            raise forms.ValidationError("Default roles JSON exceeds the 16,384-byte limit.")
        val = raw.strip()
        if not val:
            return []
        if val.startswith("["):
            parsed = _parse_bounded_json(val, 16384, "Default roles JSON")
        else:
            parsed = [line.strip() for line in val.splitlines() if line.strip()]
        return normalize_default_roles(parsed)

    def clean_wbs_structure_raw(self):
        raw = self.cleaned_data.get("wbs_structure_raw", "")
        if len(raw.encode("utf-8")) > WBS_MAX_JSON_BYTES:
            raise forms.ValidationError(
                f"WBS structure exceeds the {WBS_MAX_JSON_BYTES}-byte limit."
            )
        val = raw.strip()
        if not val:
            return []
        parsed = _parse_bounded_json(val, WBS_MAX_JSON_BYTES, "WBS structure")
        return normalize_wbs_structure(parsed)

    def clean_workflow_config_raw(self):
        raw = self.cleaned_data.get("workflow_config_raw", "")
        if len(raw.encode("utf-8")) > WORKFLOW_MAX_JSON_BYTES:
            raise forms.ValidationError(
                f"Workflow config exceeds the {WORKFLOW_MAX_JSON_BYTES}-byte limit."
            )
        val = raw.strip()
        if not val:
            return {"rules": [], "approval_gates": []}
        parsed = _parse_bounded_json(val, WORKFLOW_MAX_JSON_BYTES, "Workflow config")
        return normalize_workflow_config(parsed)

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
        help_text="Name of the new draft project.",
    )
    project_code = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PRJ-2026-09"}),
        help_text="Short project code.",
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        initial=timezone.localdate,
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
        widget=forms.CheckboxInput(attrs={"class": "form-check"}),
        help_text="Automatically create initial WBS tasks and milestones from template.",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["client"].queryset = Party.objects.filter(tenant=tenant).order_by("name")
            self.fields["project_manager"].queryset = User.objects.filter(
                Q(tenant=tenant) | Q(tenant__isnull=True),
                is_active=True,
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        target_end_date = cleaned.get("target_end_date")
        if start_date and target_end_date and target_end_date < start_date:
            self.add_error("target_end_date", "Target end date cannot precede the start date.")
        return cleaned
