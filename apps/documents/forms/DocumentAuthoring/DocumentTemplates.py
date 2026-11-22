import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate


class DocumentTemplateForm(TenantUniqueMixin, TenantModelForm):
    available_tokens_json = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-sm",
                "placeholder": '{"company_name": "Legal Company Name", "author_name": "Primary Author"}',
            }
        ),
        help_text="Valid JSON object specifying token names and descriptions",
        label="Available Tokens (JSON)",
    )

    class Meta:
        model = DocumentTemplate
        fields = [
            "name",
            "template_type",
            "category",
            "description",
            "content",
            "styling_rules",
            "is_active",
            "is_locked",
            "version",
            "target_org_unit",
            "owner",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Master Services Agreement Template"}),
            "template_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "content": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-sm",
                    "rows": 12,
                    "placeholder": "Enter template body markup with tokens e.g. {{company_name}}...",
                }
            ),
            "styling_rules": forms.Textarea(
                attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": "Optional CSS rules or styling requirements"}
            ),
            "version": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
            "target_org_unit": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_locked": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
        if self.instance and self.instance.pk and self.instance.available_tokens:
            self.initial["available_tokens_json"] = json.dumps(self.instance.available_tokens, indent=2)

    def clean_available_tokens_json(self):
        raw = self.cleaned_data.get("available_tokens_json", "").strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if not isinstance(val, dict):
                raise forms.ValidationError("Must be a valid JSON dictionary mapping token keys to descriptions.")
            return val
        except (ValueError, TypeError) as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_org_unit", "owner"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "available_tokens_json" in self.cleaned_data:
            instance.available_tokens = self.cleaned_data["available_tokens_json"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance
