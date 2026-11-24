import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit, WorkflowDefinition
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)


def _parse_json_list(val, field_label):
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for {field_label}: {exc}") from exc
        if not isinstance(parsed, list):
            raise ValidationError(f"{field_label} must be a JSON array.")
        return parsed
    raise ValidationError(f"{field_label} must be a JSON array.")


class DocumentProcessDefinitionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentProcessDefinition
        fields = [
            "name",
            "code",
            "description",
            "process_category",
            "trigger_event",
            "target_document_type",
            "target_folder",
            "department",
            "core_workflow_ref",
            "version_number",
            "sla_target_hours",
            "is_active",
            "swimlanes_json",
            "nodes_json",
            "transitions_json",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Contract Legal Triage & Approval"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. CONTRACT-TRIAGE"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "process_category": forms.Select(attrs={"class": "form-select"}),
            "trigger_event": forms.Select(attrs={"class": "form-select"}),
            "target_document_type": forms.Select(attrs={"class": "form-select"}),
            "target_folder": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "core_workflow_ref": forms.Select(attrs={"class": "form-select"}),
            "version_number": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "sla_target_hours": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "swimlanes_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
            "nodes_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 6}),
            "transitions_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_folder"].queryset = DocumentFolder.objects.filter(
                tenant=self.tenant
            ).order_by("path", "name")
            self.fields["department"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["core_workflow_ref"].queryset = WorkflowDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("name")
        for opt_field in (
            "description",
            "target_document_type",
            "target_folder",
            "department",
            "core_workflow_ref",
            "swimlanes_json",
            "nodes_json",
            "transitions_json",
        ):
            self.fields[opt_field].required = False

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Process code is required.")
        return code

    def clean_swimlanes_json(self):
        return _parse_json_list(self.cleaned_data.get("swimlanes_json"), "swimlanes")

    def clean_nodes_json(self):
        return _parse_json_list(self.cleaned_data.get("nodes_json"), "nodes")

    def clean_transitions_json(self):
        return _parse_json_list(self.cleaned_data.get("transitions_json"), "transitions")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["target_folder", "department", "core_workflow_ref"])
        code = cleaned.get("code")
        version_number = cleaned.get("version_number")
        if self.tenant and code and version_number:
            qs = DocumentProcessDefinition.objects.filter(
                tenant=self.tenant, code=code, version_number=version_number
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "code",
                    f"Process code '{code}' v{version_number} already exists in this workspace.",
                )
        return cleaned


class ProcessDesignerForm(forms.Form):
    swimlanes_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 5}),
    )
    nodes_json = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 8}),
    )
    transitions_json = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 6}),
    )

    def clean_swimlanes_json(self):
        return _parse_json_list(self.cleaned_data.get("swimlanes_json"), "swimlanes")

    def clean_nodes_json(self):
        nodes = _parse_json_list(self.cleaned_data.get("nodes_json"), "nodes")
        if not nodes:
            raise ValidationError("At least one BPMN node is required.")
        return nodes

    def clean_transitions_json(self):
        return _parse_json_list(self.cleaned_data.get("transitions_json"), "transitions")
