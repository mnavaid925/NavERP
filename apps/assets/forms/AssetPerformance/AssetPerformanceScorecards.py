from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetPerformance.AssetPerformanceScorecards import AssetPerformanceScorecard
from apps.core.models import OrgUnit
from apps.scm.models import Asset

User = get_user_model()


class AssetPerformanceScorecardForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetPerformanceScorecard
        fields = [
            "fixed_asset",
            "operational_asset",
            "period_type",
            "period_start",
            "period_end",
            "total_calendar_hours",
            "planned_operating_hours",
            "actual_operating_hours",
            "unplanned_downtime_hours",
            "planned_downtime_hours",
            "failure_event_count",
            "average_oee_percentage",
            "total_energy_consumption_kwh",
            "total_carbon_emissions_kg",
            "total_downtime_cost",
            "peer_category_ranking",
            "status",
            "department",
            "evaluated_by",
            "executive_summary",
        ]
        exclude = [
            "tenant",
            "number",
            "idle_capacity_hours",
            "capacity_utilization_rate",
            "availability_rate",
            "mtbf_hours",
            "mttr_hours",
            "performance_index_score",
            "benchmark_grade",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "period_type": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "total_calendar_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "planned_operating_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "actual_operating_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "unplanned_downtime_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "planned_downtime_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "failure_event_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "average_oee_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_energy_consumption_kwh": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_carbon_emissions_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_downtime_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "peer_category_ranking": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "evaluated_by": forms.Select(attrs={"class": "form-select"}),
            "executive_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reliability performance synthesis, asset health summary..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant).order_by("name")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
            self.fields["evaluated_by"].queryset = User.objects.filter(tenant=tenant, is_active=True).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fixed_asset", "operational_asset", "department"])

        start = cleaned.get("period_start")
        end = cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Evaluation end date cannot be earlier than start date.")

        return cleaned
