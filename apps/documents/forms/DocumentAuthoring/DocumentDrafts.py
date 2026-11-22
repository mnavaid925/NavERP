from django import forms

from apps.core.models import OrgUnit, Party
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate


class DocumentDraftForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentDraft
        fields = [
            "title",
            "document_type",
            "template",
            "draft_version",
            "content",
            "content_format",
            "department",
            "related_party",
            "is_collaboration_locked",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Standard Operating Procedure - Quality Control"}),
            "document_type": forms.Select(attrs={"class": "form-select"}),
            "template": forms.Select(attrs={"class": "form-select"}),
            "draft_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "0.1"}),
            "content": forms.Textarea(
                attrs={"class": "form-textarea font-mono text-sm", "rows": 14, "placeholder": "Author document draft body text..."}
            ),
            "content_format": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "related_party": forms.Select(attrs={"class": "form-select"}),
            "is_collaboration_locked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["template"].queryset = DocumentTemplate.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["related_party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["template", "department", "related_party"])
        if self.instance and self.instance.pk and self.instance.status in ("promoted", "discarded"):
            raise forms.ValidationError(f"Cannot modify draft because it is {self.instance.get_status_display().lower()}.")
        return cleaned_data
