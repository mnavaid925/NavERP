from decimal import Decimal

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.bi.models.PerformanceScorecards.ScorecardKpiAssignments import ScorecardKpiAssignment
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.core.forms import TenantModelForm


class ScorecardKpiAssignmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ScorecardKpiAssignment
        fields = [
            "scorecard",
            "kpi",
            "objective",
            "perspective",
            "weight",
            "target_value",
            "actual_value",
            "benchmark_overlay_value",
            "manager_notes",
            "sort_order",
        ]
        widgets = {
            "scorecard": forms.Select(attrs={"class": "form-select"}),
            "kpi": forms.Select(attrs={"class": "form-select"}),
            "objective": forms.Select(attrs={"class": "form-select"}),
            "perspective": forms.Select(attrs={"class": "form-select"}),
            "weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "10.00"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "actual_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "benchmark_overlay_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "manager_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Review notes, root causes, corrective actions..."}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["scorecard"].queryset = PerformanceScorecard.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["kpi"].queryset = KpiDefinition.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["objective"].queryset = StrategicObjective.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["scorecard", "kpi", "objective"])
        return cleaned


class ScorecardKpiRecordActualForm(forms.ModelForm):
    class Meta:
        model = ScorecardKpiAssignment
        fields = ["actual_value", "manager_notes"]
        widgets = {
            "actual_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "manager_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Enter performance commentary and variance rationale..."}),
        }
