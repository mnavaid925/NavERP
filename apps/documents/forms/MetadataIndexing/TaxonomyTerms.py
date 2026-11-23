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
        return code

    def clean_synonyms_json(self):
        raw = self.cleaned_data.get("synonyms_json", "").strip()
        if not raw:
            return "[]"
        if raw.startswith("{"):
            raise ValidationError("Synonyms must be a JSON array of strings, not a JSON object.")
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON: {exc}")
            if not isinstance(parsed, list):
                raise ValidationError("Synonyms must be a JSON array of strings.")
            clean_list = [str(x).strip() for x in parsed if str(x).strip()]
            return json.dumps(clean_list)
        else:
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return json.dumps(items)

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get("term_code")
        category = cleaned_data.get("category")
        if code and category:
            qs = TaxonomyTerm.objects.filter(category=category, term_code=code)
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("term_code", f"Term code '{code}' already exists in category '{category}'.")

        parent = cleaned_data.get("parent")
        if parent:
            if self.tenant and parent.tenant != self.tenant:
                self.add_error("parent", "Parent taxonomy term does not belong to your organization.")
            if self.instance and self.instance.pk:
                if parent.pk == self.instance.pk:
                    self.add_error("parent", "A taxonomy term cannot be its own parent.")
                else:
                    curr = parent
                    visited = {self.instance.pk}
                    while curr and curr.parent_id:
                        if curr.parent_id in visited:
                            self.add_error("parent", f"Circular reference detected: '{parent.name}' is already a descendant of this term.")
                            break
                        visited.add(curr.parent_id)
                        curr = curr.parent
        return cleaned_data
