from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models import (
    Document,
    DocumentApprovalWorkflow,
    DocumentReviewComment,
    DocumentVersion,
)


class DocumentReviewCommentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentReviewComment
        fields = [
            "document",
            "version",
            "workflow",
            "annotation_type",
            "page_number",
            "coordinate_ref",
            "selected_text",
            "content",
            "parent",
            "is_blocking",
        ]
        widgets = {
            "document": forms.Select(attrs={"class": "form-select"}),
            "version": forms.Select(attrs={"class": "form-select"}),
            "workflow": forms.Select(attrs={"class": "form-select"}),
            "annotation_type": forms.Select(attrs={"class": "form-select"}),
            "page_number": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "coordinate_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 120,450,200,80 or paragraph:3"}),
            "selected_text": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Highlighted or quoted passage..."}),
            "content": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Enter your critique, required revision, or review remarks..."}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "is_blocking": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["document"].queryset = Document.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["version"].queryset = DocumentVersion.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["workflow"].queryset = DocumentApprovalWorkflow.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["parent"].queryset = DocumentReviewComment.objects.filter(tenant=self.tenant, parent__isnull=True).order_by("-created_at")
        self.fields["version"].required = False
        self.fields["workflow"].required = False
        self.fields["coordinate_ref"].required = False
        self.fields["selected_text"].required = False
        self.fields["parent"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["document", "version", "workflow", "parent"])
        doc = cleaned.get("document")
        ver = cleaned.get("version")
        if doc and ver and ver.document_id != doc.id:
            self.add_error("version", "Selected version does not belong to this document.")
        return cleaned


class CommentReplyForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Write a reply in this discussion thread..."}),
        required=True,
    )


class CommentResolveForm(forms.Form):
    STATUS_CHOICES = [
        ("resolved", "Mark Resolved & Closed"),
        ("addressed", "Mark Addressed / Implemented"),
        ("dismissed", "Dismiss as Non-Applicable"),
    ]
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Explain how this comment was addressed or justified..."}),
        required=True,
    )
