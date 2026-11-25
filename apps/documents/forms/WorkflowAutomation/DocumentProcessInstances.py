from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.forms.WorkflowAutomation._common import parse_json_field_value
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
            scoped_doc_id = None
            if self.instance and self.instance.pk:
                if self.instance.process_definition_id:
                    self.fields["process_definition"].queryset = (
                        DocumentProcessDefinition.objects.filter(
                            tenant=self.tenant, pk=self.instance.process_definition_id
                        ).only("id", "number", "code", "name", "version_number", "tenant_id")
                    )
                self.fields["process_definition"].disabled = True
                if self.instance.document_id:
                    scoped_doc_id = self.instance.document_id
                    self.fields["document"].queryset = (
                        Document.objects.filter(tenant=self.tenant, pk=self.instance.document_id)
                        .only("id", "number", "title", "current_version_label", "created_at", "tenant_id")
                    )
                self.fields["document"].disabled = True
            else:
                self.fields["process_definition"].queryset = (
                    DocumentProcessDefinition.objects.filter(
                        tenant=self.tenant, status="published", is_active=True
                    )
                    .only("id", "number", "code", "name", "version_number", "tenant_id")
                    .order_by("code", "-version_number")
                )
                self.fields["document"].queryset = (
                    Document.objects.filter(tenant=self.tenant)
                    .only("id", "number", "title", "current_version_label", "created_at", "tenant_id")
                    .order_by("-created_at", "title")
                )
                raw_doc = (
                    (self.data.get(self.add_prefix("document")) if self.is_bound else None)
                    or self.initial.get("document")
                )
                if raw_doc is not None:
                    cand_doc_id = getattr(raw_doc, "pk", raw_doc)
                    if str(cand_doc_id).strip().isdigit():
                        scoped_doc_id = int(str(cand_doc_id).strip())

            ver_qs = DocumentVersion.objects.filter(tenant=self.tenant)
            if scoped_doc_id:
                ver_qs = ver_qs.filter(document_id=scoped_doc_id)
            self.fields["version"].queryset = (
                ver_qs.select_related("document")
                .only("id", "number", "version_label", "document_id", "document__number", "created_at", "tenant_id")
                .order_by("-created_at")
            )
            self.fields["department"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant)
                .only("id", "name", "tenant_id")
                .order_by("name")
            )
            self.fields["current_assignee"].queryset = (
                User.objects.filter(tenant=self.tenant, is_active=True)
                .only("id", "username", "email", "first_name", "last_name", "tenant_id")
                .order_by("username")
            )
        else:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.none()
            self.fields["document"].queryset = Document.objects.none()
            self.fields["version"].queryset = DocumentVersion.objects.none()
            self.fields["department"].queryset = OrgUnit.objects.none()
            self.fields["current_assignee"].queryset = User.objects.none()

        for opt in ("version", "department", "current_assignee", "context_variables_json"):
            self.fields[opt].required = False

    def clean_context_variables_json(self):
        return parse_json_field_value(
            self.cleaned_data.get("context_variables_json"), dict, "context variables"
        )

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
        proc = cleaned.get("process_definition")
        if proc and not (self.instance and self.instance.pk):
            if proc.status != "published" or not proc.is_active:
                self.add_error(
                    "process_definition",
                    "Only active, published process definitions can be launched.",
                )
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
