from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models.SearchDiscovery.SearchSynonyms import SearchSynonym


class SearchSynonymForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SearchSynonym
        fields = [
            "name",
            "synonym_type",
            "root_term",
            "synonyms",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Footwear & Sneakers"}
            ),
            "synonym_type": forms.Select(attrs={"class": "form-select"}),
            "root_term": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. sneakers"}
            ),
            "synonyms": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "e.g. trainers, running shoes, kicks",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Internal notes or merchandising rationale...",
                }
            ),
        }
