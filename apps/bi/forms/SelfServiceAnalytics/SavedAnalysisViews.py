from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.models.SelfServiceAnalytics.SavedAnalysisViews import SavedAnalysisView
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit


class SavedAnalysisViewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SavedAnalysisView
        fields = [
            "name",
            "slug",
            "description",
            "query",
            "sharing_scope",
            "org_unit",
            "is_template",
            "is_favorite",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Executive Sales Exploration"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. q4-executive-sales-view"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Notes or context for colleagues viewing this analysis..."}),
            "query": forms.Select(attrs={"class": "form-select"}),
            "sharing_scope": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "is_template": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_favorite": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False

        if self.tenant is not None:
            if "query" in self.fields:
                self.fields["query"].queryset = AdHocQuery.objects.filter(tenant=self.tenant)
            if "org_unit" in self.fields:
                self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["query", "org_unit"])
        name = cleaned.get("name")
        slug = cleaned.get("slug")
        if not slug and name:
            cleaned["slug"] = slugify(name)[:100] or "view"
        return cleaned


class SavedAnalysisViewShareForm(TenantModelForm):
    class Meta:
        model = SavedAnalysisView
        fields = ["sharing_scope", "org_unit"]
        widgets = {
            "sharing_scope": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "org_unit" in self.fields:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["org_unit"])
        return cleaned
