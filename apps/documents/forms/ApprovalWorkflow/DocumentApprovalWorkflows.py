from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models import Document, DocumentApprovalWorkflow, DocumentVersion


class DocumentApprovalWorkflowForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentApprovalWorkflow
        fields = [
            "document",
            "version",
            "title",
            "workflow_type",
            "urgency",
            "target_turnaround_hours",
            "department",
            "due_date",
            "requires_all_comments_resolved",
            "allow_emergency_bypass",
            "definition_json",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Executive Contract Sign-Off"}),
            "workflow_type": forms.Select(attrs={"class": "form-select"}),
            "urgency": forms.Select(attrs={"class": "form-select"}),
            "target_turnaround_hours": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "requires_all_comments_resolved": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "allow_emergency_bypass": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "definition_json": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).select_related("document").order_by("-created_at")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["version"].required = False
        self.fields["department"].required = False
        self.fields["due_date"].required = False
        self.fields["target_turnaround_hours"].required = False
        self.fields["definition_json"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["document", "version", "department"])
        doc = cleaned.get("document")
        ver = cleaned.get("version")
        if doc and ver and ver.document_id != doc.id:
            self.add_error("version", "Selected version does not belong to the selected document.")
        return cleaned


class WorkflowBypassForm(forms.Form):
    bypass_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Enter justified operational or emergency reason for bypassing..."}),
        required=True,
    )
