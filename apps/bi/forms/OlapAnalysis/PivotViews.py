import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.models.OlapAnalysis.PivotViews import PivotAnalysisView
from apps.core.forms import TenantModelForm


class PivotAnalysisViewForm(TenantUniqueMixin, TenantModelForm):
    row_dimensions_raw = forms.CharField(
        label="Row Dimensions (JSON array)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Ordered list of dimensions plotted as hierarchical rows, e.g. [\"OrgUnit\", \"GLAccount\"]",
    )
    column_dimensions_raw = forms.CharField(
        label="Column Dimensions (JSON array)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Ordered list of dimensions plotted as hierarchical columns, e.g. [\"FiscalPeriod\"]",
    )
    selected_measures_raw = forms.CharField(
        label="Selected Measures (JSON array)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Measures to evaluate at intersections, e.g. [\"NetRevenue\", \"OperatingMargin\"]",
    )
    filters_json_raw = forms.CharField(
        label="Dimensional Slicers / Filters (JSON array)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Slicers applied to the cube space, e.g. [{\"field\": \"FiscalPeriod.Year\", \"operator\": \"eq\", \"value\": \"2026\"}]",
    )
    conditional_formatting_raw = forms.CharField(
        label="Conditional Formatting Rules (JSON)",
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="Rules for heatmap/threshold styling, e.g. [{\"rule\": \"variance < 0\", \"color\": \"#ef4444\"}]",
    )

    class Meta:
        model = PivotAnalysisView
        fields = [
            "cube",
            "name",
            "slug",
            "description",
            "show_row_subtotals",
            "show_col_subtotals",
            "show_grand_totals",
            "total_position",
            "drill_through_enabled",
            "drill_through_target",
            "status",
            "is_favorite",
        ]
        widgets = {
            "cube": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Regional P&L Cross-Tab"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "total_position": forms.Select(attrs={"class": "form-select"}),
            "drill_through_target": forms.TextInput(attrs={"class": "form-input font-mono text-xs"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "row_dimensions" in data and "row_dimensions_raw" not in data:
                data["row_dimensions_raw"] = json.dumps(data["row_dimensions"]) if isinstance(data["row_dimensions"], list) else str(data["row_dimensions"])
            if "column_dimensions" in data and "column_dimensions_raw" not in data:
                data["column_dimensions_raw"] = json.dumps(data["column_dimensions"]) if isinstance(data["column_dimensions"], list) else str(data["column_dimensions"])
            if "measures_selection" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = json.dumps(data["measures_selection"]) if isinstance(data["measures_selection"], list) else str(data["measures_selection"])
            if "selected_measures" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = json.dumps(data["selected_measures"]) if isinstance(data["selected_measures"], list) else str(data["selected_measures"])
            if "measures_selection_raw" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = data["measures_selection_raw"]
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "row_dimensions" in data and "row_dimensions_raw" not in data:
                data["row_dimensions_raw"] = json.dumps(data["row_dimensions"]) if isinstance(data["row_dimensions"], list) else str(data["row_dimensions"])
            if "column_dimensions" in data and "column_dimensions_raw" not in data:
                data["column_dimensions_raw"] = json.dumps(data["column_dimensions"]) if isinstance(data["column_dimensions"], list) else str(data["column_dimensions"])
            if "measures_selection" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = json.dumps(data["measures_selection"]) if isinstance(data["measures_selection"], list) else str(data["measures_selection"])
            if "selected_measures" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = json.dumps(data["selected_measures"]) if isinstance(data["selected_measures"], list) else str(data["selected_measures"])
            if "measures_selection_raw" in data and "selected_measures_raw" not in data:
                data["selected_measures_raw"] = data["measures_selection_raw"]
            args = (data,) + args[1:]

        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if "total_position" in self.fields:
            self.fields["total_position"].required = False
        if "drill_through_target" in self.fields:
            self.fields["drill_through_target"].required = False
        if self.tenant is not None:
            self.fields["cube"].queryset = OlapCube.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.row_dimensions:
                self.fields["row_dimensions_raw"].initial = json.dumps(self.instance.row_dimensions, indent=2)
            if self.instance.column_dimensions:
                self.fields["column_dimensions_raw"].initial = json.dumps(self.instance.column_dimensions, indent=2)
            if self.instance.selected_measures:
                self.fields["selected_measures_raw"].initial = json.dumps(self.instance.selected_measures, indent=2)
            if self.instance.filters_json:
                self.fields["filters_json_raw"].initial = json.dumps(self.instance.filters_json, indent=2)
            if self.instance.conditional_formatting:
                self.fields["conditional_formatting_raw"].initial = json.dumps(self.instance.conditional_formatting, indent=2)
        else:
            self.fields["row_dimensions_raw"].initial = json.dumps(["OrgUnit", "GLAccount"], indent=2)
            self.fields["column_dimensions_raw"].initial = json.dumps(["FiscalPeriod"], indent=2)
            self.fields["selected_measures_raw"].initial = json.dumps(["NetRevenue", "OperatingMargin"], indent=2)
            self.fields["filters_json_raw"].initial = json.dumps([], indent=2)
            self.fields["conditional_formatting_raw"].initial = json.dumps([], indent=2)

    def clean_row_dimensions_raw(self):
        val = self.cleaned_data.get("row_dimensions_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Row dimensions must be a JSON array.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_column_dimensions_raw(self):
        val = self.cleaned_data.get("column_dimensions_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Column dimensions must be a JSON array.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_selected_measures_raw(self):
        val = self.cleaned_data.get("selected_measures_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Selected measures must be a JSON array.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_filters_json_raw(self):
        val = self.cleaned_data.get("filters_json_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Filters must be a JSON array.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_conditional_formatting_raw(self):
        val = self.cleaned_data.get("conditional_formatting_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, (list, dict)):
                raise forms.ValidationError("Conditional formatting must be a JSON array or object.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_drill_through_target(self):
        val = self.cleaned_data.get("drill_through_target", "").strip()
        if val:
            from django.urls import reverse, NoReverseMatch
            try:
                reverse(val)
            except NoReverseMatch:
                raise forms.ValidationError(
                    f"Invalid URL route name '{val}'. It could not be reversed by Django URL routing."
                )
        return val

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["cube"])
        if cleaned.get("name") and not cleaned.get("slug"):
            from django.utils.text import slugify
            base_slug = slugify(cleaned["name"]) or "view"
            slug = base_slug[:120]
            cleaned["slug"] = slug
            self.instance.slug = slug
        if not cleaned.get("total_position"):
            cleaned["total_position"] = "bottom_right"
            self.instance.total_position = "bottom_right"
        if not cleaned.get("drill_through_target"):
            cleaned["drill_through_target"] = "accounting:journal_entry_list"
            self.instance.drill_through_target = "accounting:journal_entry_list"
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "row_dimensions_raw" in self.cleaned_data:
            instance.row_dimensions = self.cleaned_data["row_dimensions_raw"]
        if "column_dimensions_raw" in self.cleaned_data:
            instance.column_dimensions = self.cleaned_data["column_dimensions_raw"]
        if "selected_measures_raw" in self.cleaned_data:
            instance.selected_measures = self.cleaned_data["selected_measures_raw"]
        if "filters_json_raw" in self.cleaned_data:
            instance.filters_json = self.cleaned_data["filters_json_raw"]
        if "conditional_formatting_raw" in self.cleaned_data:
            instance.conditional_formatting = self.cleaned_data["conditional_formatting_raw"]
        if commit:
            instance.save()
        return instance
