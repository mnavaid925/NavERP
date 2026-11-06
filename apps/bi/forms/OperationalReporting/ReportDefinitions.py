import json
from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit


class ReportDefinitionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReportDefinition
        fields = [
            "name",
            "slug",
            "category",
            "report_type",
            "paper_size",
            "orientation",
            "semantic_model",
            "warehouse_table",
            "org_unit",
            "status",
            "is_prebuilt_template",
            "watermark_text",
            "description",
            "raw_query",
            "styling_css",
            "margins_json",
            "bands_config_json",
            "columns_config_json",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Monthly Profit & Loss Statement"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. monthly-profit-loss"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "report_type": forms.Select(attrs={"class": "form-select"}),
            "paper_size": forms.Select(attrs={"class": "form-select"}),
            "orientation": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "watermark_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CONFIDENTIAL or DRAFT"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Business purpose and regulatory scope of this operational report..."}),
            "raw_query": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": "Optional raw SQL/ORM query specification"}),
            "styling_css": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": "Optional custom CSS styling for printable view"}),
            "margins_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2, "placeholder": '{"top": 15, "bottom": 15, "left": 15, "right": 15}'}),
            "bands_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": '{"title_band": {"height_mm": 20}, "detail_band": {"height_mm": 10}}'}),
            "columns_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": '[{"field": "code", "title": "Account Code", "width": "20%"}, ...]'}),
            "is_prebuilt_template": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if "margins_json" in self.fields:
            self.fields["margins_json"].required = False
        if "bands_config_json" in self.fields:
            self.fields["bands_config_json"].required = False
        if "columns_config_json" in self.fields:
            self.fields["columns_config_json"].required = False

        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["semantic_model"].empty_label = "— None (Direct / Custom Table) —"

            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("table_name")
            self.fields["warehouse_table"].empty_label = "— None (Governed Semantic Model) —"

            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["org_unit"].empty_label = "— All Departments / Org Units —"

    def clean_margins_json(self):
        val = self.cleaned_data.get("margins_json")
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return val or {"top": 15, "bottom": 15, "left": 15, "right": 15}

    def clean_bands_config_json(self):
        val = self.cleaned_data.get("bands_config_json")
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return val or {}

    def clean_columns_config_json(self):
        val = self.cleaned_data.get("columns_config_json")
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return val or []

    def clean_styling_css(self):
        val = self.cleaned_data.get("styling_css", "") or ""
        lower = val.lower()
        forbidden = ["</style", "<script", "</script", "<iframe", "</iframe", "javascript:", "onload=", "onerror="]
        for bad in forbidden:
            if bad in lower:
                raise forms.ValidationError(f"Invalid CSS: HTML tag closing, script injection, or javascript scheme ('{bad}') is not permitted.")
        return val

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model", "warehouse_table", "org_unit"])
        name = cleaned_data.get("name")
        slug = cleaned_data.get("slug")
        if not slug and name:
            cleaned_data["slug"] = slugify(name)[:120]
        return cleaned_data


class ReportCloneForm(forms.Form):
    new_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Monthly Profit & Loss Statement (Fork)"}),
    )
    new_slug = forms.SlugField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "Auto-generated from name if blank"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant

    def clean_new_slug(self):
        slug = self.cleaned_data.get("new_slug")
        if not slug:
            return slug
        if self.tenant and ReportDefinition.objects.filter(tenant=self.tenant, slug=slug).exists():
            raise forms.ValidationError("A report with this slug already exists.")
        return slug

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("new_name")
        slug = cleaned.get("new_slug")
        if not slug and name:
            slug = slugify(name)[:120]
            if self.tenant and ReportDefinition.objects.filter(tenant=self.tenant, slug=slug).exists():
                self.add_error("new_slug", "A report with this auto-generated slug already exists. Please choose a different slug.")
            cleaned["new_slug"] = slug
        return cleaned
