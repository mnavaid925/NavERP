import json
from django import forms
from django.core.exceptions import ValidationError

from apps.documents.models import TaxonomyTerm


class TaxonomyTermForm(forms.ModelForm):
    class Meta:
        model = TaxonomyTerm
        fields = [
            "name",
            "term_code",
            "category",
            "parent",
            "description",
            "synonyms_json",
            "external_code",
            "is_governed",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Non-Disclosure Agreement"}),
            "term_code": forms.TextInput(attrs={"class": "form-input uppercase", "placeholder": "e.g. TAX_NDA"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "synonyms_json": forms.Textarea(attrs={
                "class": "form-textarea font-mono text-sm",
                "rows": 3,
                "placeholder": '["NDA", "Confidentiality Agreement", "Proprietary Info Agreement"]',
            }),
            "external_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ISO 27001:A.13.2"}),
            "is_governed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        if self.tenant:
            qs = TaxonomyTerm.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = qs
        else:
            self.fields["parent"].queryset = TaxonomyTerm.objects.none()

        self.fields["parent"].empty_label = "— Root Term (No Parent) —"

    def clean_term_code(self):
        code = self.cleaned_data.get("term_code", "").strip().upper()
        if not code:
            raise ValidationError("Term code is required.")
        category = self.cleaned_data.get("category")
        qs = TaxonomyTerm.objects.filter(category=category, term_code=code)
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Term code '{code}' already exists in category '{category}'.")
        return code

    def clean_synonyms_json(self):
        raw = self.cleaned_data.get("synonyms_json", "").strip()
        if not raw:
            return "[]"
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValidationError("Synonyms must be a JSON array of strings.")
                clean_list = [str(x).strip() for x in parsed if str(x).strip()]
                return json.dumps(clean_list)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON: {exc}")
        else:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return json.dumps(items)

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get("parent")
        if parent and self.tenant and parent.tenant != self.tenant:
            raise ValidationError("Parent taxonomy term does not belong to your organization.")
        return cleaned_data
