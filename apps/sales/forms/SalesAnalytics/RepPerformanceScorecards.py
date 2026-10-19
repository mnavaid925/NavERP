"""Sales 8.12 — Forms for `RepPerformanceScorecard`."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecard


class RepPerformanceScorecardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RepPerformanceScorecard
        fields = [
            "rep",
            "territory",
            "manager",
            "forecast_period",
            "quota_plan",
            "coaching_scorecard",
            "period_start",
            "period_end",
            "activities_logged",
            "calls_logged",
            "emails_logged",
            "meetings_logged",
            "meetings_booked",
            "follow_ups_completed",
            "activity_minutes",
            "response_time_hours",
            "opportunities_created",
            "opportunities_won",
            "opportunities_lost",
            "pipeline_value",
            "weighted_pipeline_value",
            "revenue_closed",
            "currency",
            "sales_cycle_days",
            "quota_target",
            "overall_score",
            "rating",
            "strengths",
            "areas_for_improvement",
            "coaching_actions",
            "benchmark_win_rate_pct",
            "benchmark_cycle_days",
            "benchmark_quota_attainment_pct",
            "benchmark_source",
            "benchmark_as_of",
            "segment",
            "status",
            "notes",
        ]
        # Belt-and-braces: the four derived fields are already `editable=False`
        # and are therefore auto-excluded, but naming them here keeps the
        # exclusion auditable next to the field list.
        exclude = [
            "win_rate_pct",
            "average_deal_size",
            "quota_attainment_pct",
            "goal_gap_value",
        ]
        widgets = {
            "rep": forms.Select(attrs={"class": "form-select"}),
            "territory": forms.Select(attrs={"class": "form-select"}),
            "manager": forms.Select(attrs={"class": "form-select"}),
            "forecast_period": forms.Select(attrs={"class": "form-select"}),
            "quota_plan": forms.Select(attrs={"class": "form-select"}),
            "coaching_scorecard": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "activities_logged": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "calls_logged": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "emails_logged": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "meetings_logged": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "meetings_booked": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "follow_ups_completed": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "activity_minutes": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "response_time_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "opportunities_created": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "opportunities_won": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "opportunities_lost": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "pipeline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "weighted_pipeline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "revenue_closed": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "sales_cycle_days": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "quota_target": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "overall_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "rating": forms.Select(attrs={"class": "form-select"}),
            "strengths": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "areas_for_improvement": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "coaching_actions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "benchmark_win_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_cycle_days": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_quota_attainment_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_source": forms.TextInput(attrs={"class": "form-input"}),
            "benchmark_as_of": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "segment": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # `currency` is deliberately NOT in this list: `accounting.Currency` is a
        # GLOBAL master with no `tenant` FK (L29), so there is no tenant to
        # reject it against.
        _reject_foreign(
            self,
            cleaned_data,
            [
                "rep",
                "territory",
                "manager",
                "forecast_period",
                "quota_plan",
                "coaching_scorecard",
            ],
        )
        return cleaned_data
