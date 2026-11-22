from django import forms

from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection


class TemplateSectionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TemplateSection
        fields = [
            "template",
            "title",
            "section_type",
            "content",
            "order",
            "is_locked",
            "is_mandatory",
        ]
        widgets = {
            "template": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Confidentiality & Non-Disclosure Clause"}),
            "section_type": forms.Select(attrs={"class": "form-select"}),
            "content": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-sm",
                    "rows": 8,
                    "placeholder": "Enter section content, clause wording, or disclaimer...",
                }
            ),
            "order": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "is_locked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_mandatory": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["template"].queryset = DocumentTemplate.objects.filter(tenant=self.tenant).only("id", "name", "number").order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["template"])
        return cleaned_data
