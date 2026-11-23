import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch


class DocumentSavedSearchForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentSavedSearch
        fields = [
            "name",
            "description",
            "department",
            "visibility",
            "query_text",
            "filters_json",
            "facet_filters_json",
            "sort_by",
            "sort_order",
            "is_pinned",
            "is_favorite",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Active Confidential Contracts"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Purpose of this saved search"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
            "query_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "Keywords, boolean syntax, or wildcard query"}),
            "filters_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '{"classification": "confidential", "document_type": "contract"}'}),
            "facet_filters_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '{"status": ["approved"], "extension": ["pdf"]}'}),
            "sort_by": forms.Select(attrs={"class": "form-select"}),
            "sort_order": forms.Select(attrs={"class": "form-select"}),
            "is_pinned": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_favorite": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["department"].required = False
        self.fields["description"].required = False
        self.fields["query_text"].required = False
        self.fields["filters_json"].required = False
        self.fields["facet_filters_json"].required = False

    def clean_filters_json(self):
        val = self.cleaned_data.get("filters_json")
        if not val or not val.strip():
            return "{}"
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise ValidationError("Must be a valid JSON dictionary of key-value filters.")
            return json.dumps(parsed)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid JSON: {e}")

    def clean_facet_filters_json(self):
        val = self.cleaned_data.get("facet_filters_json")
        if not val or not val.strip():
            return "{}"
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise ValidationError("Must be a valid JSON dictionary of facet filters.")
            return json.dumps(parsed)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid JSON: {e}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["department"])
        return cleaned_data
