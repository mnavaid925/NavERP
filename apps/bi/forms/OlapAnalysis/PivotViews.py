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
        super().__init__(*args, **kwargs)
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
