from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym


class DocumentSearchSynonymForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentSearchSynonym
        fields = [
            "term",
            "synonyms",
            "category",
            "is_bidirectional",
            "language",
            "is_active",
        ]
        widgets = {
            "term": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SOP, NDA, purchase order"}),
            "synonyms": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Comma-separated synonyms e.g. standard operating procedure, procedure, work instruction",
            }),
            "category": forms.Select(attrs={"class": "form-select"}),
            "is_bidirectional": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "language": forms.TextInput(attrs={"class": "form-input", "placeholder": "en"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def clean_term(self):
        term = self.cleaned_data.get("term", "").strip()
        if not term:
            raise ValidationError("Term cannot be blank.")
        if "," in term:
            raise ValidationError("Base term should not contain commas. Put equivalents in synonyms.")
        return term

    def clean_synonyms(self):
        raw_synonyms = self.cleaned_data.get("synonyms", "")
        if not raw_synonyms:
            raise ValidationError("At least one synonym must be provided.")

        items = [s.strip() for s in raw_synonyms.split(",") if s.strip()]
        if not items:
            raise ValidationError("Please provide at least one valid synonym separated by commas.")

        term = self.cleaned_data.get("term", "").strip().lower()
        deduped = []
        seen = set()
        for item in items:
            item_lower = item.lower()
            if item_lower == term:
                continue  # skip self
            if item_lower not in seen:
                seen.add(item_lower)
                deduped.append(item)

        if not deduped:
            raise ValidationError("Synonyms cannot be identical only to the base term itself.")

        return ", ".join(deduped)
