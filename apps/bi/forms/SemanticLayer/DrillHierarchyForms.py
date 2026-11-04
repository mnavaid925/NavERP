import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class DrillHierarchyForm(TenantUniqueMixin, TenantModelForm):
    levels_json_raw = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-xs",
                "rows": 6,
                "placeholder": '[\n  {"level": 1, "name": "Fiscal Year", "column": "fiscal_year"},\n  {"level": 2, "name": "Fiscal Quarter", "column": "fiscal_quarter"},\n  {"level": 3, "name": "Month", "column": "month_name"}\n]',
            }
        ),
        required=False,
        label="Hierarchy Levels (JSON Array)",
        help_text="Ordered list of drill levels with level, name, and column properties.",
    )

    class Meta:
        model = DrillHierarchy
        fields = [
            "semantic_model",
            "name",
            "code",
            "hierarchy_type",
            "primary_drill_path",
            "description",
            "is_active",
        ]
        widgets = {
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Fiscal Calendar Drill Path"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. fiscal_calendar"}),
            "hierarchy_type": forms.Select(attrs={"class": "form-select"}),
            "primary_drill_path": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk and self.instance.levels_json:
            self.fields["levels_json_raw"].initial = json.dumps(self.instance.levels_json, indent=2)

    def clean_levels_json_raw(self):
        data = self.cleaned_data.get("levels_json_raw", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Hierarchy levels must be a JSON array of level objects.")
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    raise forms.ValidationError(f"Item {idx + 1} must be an object with 'name' and 'column' keys.")
                if "name" not in item or "column" not in item:
                    raise forms.ValidationError(f"Item {idx + 1} missing required 'name' or 'column' keys.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON format: {exc.msg}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.levels_json = self.cleaned_data.get("levels_json_raw") or []
        if commit:
            instance.save()
        return instance
