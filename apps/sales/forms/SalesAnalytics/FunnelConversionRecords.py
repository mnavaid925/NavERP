"""Sales 8.12 — Forms for `FunnelConversionRecord`."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesAnalytics.FunnelConversionRecords import FunnelConversionRecord


class FunnelConversionRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FunnelConversionRecord
        fields = [
            "label",
            "funnel_scope",
            "from_stage",
            "to_stage",
            "territory",
            "owner",
            "source_channel",
            "period_start",
            "period_end",
            "entered_count",
            "converted_count",
            "skipped_count",
            "avg_cycle_days",
            "benchmark_pct",
            "benchmark_source",
            "benchmark_as_of",
            "segment",
            "notes",
        ]
        # Belt and braces: `conversion_rate_pct` and `dropoff_count` are
        # `editable=False` and are already excluded by Django, but naming them
        # makes the intent explicit — the rate and the dropoff are DERIVED from
        # the counts and are never typed.
        exclude = ["conversion_rate_pct", "dropoff_count"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-input"}),
            "funnel_scope": forms.Select(attrs={"class": "form-select"}),
            "from_stage": forms.Select(attrs={"class": "form-select"}),
            "to_stage": forms.Select(attrs={"class": "form-select"}),
            "territory": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "source_channel": forms.TextInput(attrs={"class": "form-input"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "entered_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "converted_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "skipped_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "avg_cycle_days": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_source": forms.TextInput(attrs={"class": "form-input"}),
            "benchmark_as_of": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "segment": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "from_stage" in self.fields:
            self.fields["from_stage"].queryset = self.fields["from_stage"].queryset.select_related("pipeline")
        if "to_stage" in self.fields:
            self.fields["to_stage"].queryset = self.fields["to_stage"].queryset.select_related("pipeline")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            ["from_stage", "to_stage", "territory", "owner"],
        )

        # A ModelForm does NOT call the model's `clean()`, so the "converted
        # cannot exceed entered" rule is re-stated here with the same friendly
        # message. The model's own `clean()` keeps it true for every other
        # write path.
        entered = cleaned_data.get("entered_count")
        converted = cleaned_data.get("converted_count")
        if entered is not None and converted is not None and converted > entered:
            self.add_error(
                "converted_count",
                "Converted count cannot exceed the entered count.",
            )
        return cleaned_data
