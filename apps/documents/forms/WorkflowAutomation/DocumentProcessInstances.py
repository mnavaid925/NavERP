import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstance,
)


class DocumentProcessInstanceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentProcessInstance
        fields = [
            "process_definition",
            "document",
            "version",
            "department",
            "current_assignee",
            "context_variables_json",
        ]
        widgets = {
            "process_definition": forms.Select(attrs={"class": "form-select"}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "current_assignee": forms.Select(attrs={"class": "form-select"}),
            "context_variables_json": forms.Textarea(
                attrs={"class": "form-textarea font-mono text-xs", "rows": 4}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("code", "-version_number")
            self.fields["document"].queryset = Document.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at", "title")
            self.fields["version"].queryset = (
                DocumentVersion.objects.filter(tenant=self.tenant)
                .select_related("document")
                .defer("extracted_text")
                .order_by("-created_at")
            )
            self.fields["department"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["current_assignee"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("username")

        for opt in ("version", "department", "current_assignee", "context_variables_json"):
            self.fields[opt].required = False

    def clean_context_variables_json(self):
        val = self.cleaned_data.get("context_variables_json")
        if val is None or val == "":
            return {}
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            stripped = val.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON for context variables: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValidationError("Context variables must be a JSON object.")
            return parsed
        raise ValidationError("Context variables must be a JSON object.")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["process_definition", "document", "version", "department", "current_assignee"],
        )
        doc = cleaned.get("document")
        ver = cleaned.get("version")
        if doc and ver and ver.document_id != doc.id:
            self.add_error("version", "Selected version does not belong to the chosen document.")
        return cleaned


class ProcessAdvanceForm(forms.Form):
    OUTCOME_CHOICES = (
        ("approved", "Proceed / Approve Step"),
        ("rejected", "Reject / Route to Rework"),
        ("escalated", "Escalate / Flag SLA Breach"),
        ("completed", "Complete Process Immediately"),
    )

    outcome = forms.ChoiceField(
        choices=OUTCOME_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional step transition note..."}),
    )
