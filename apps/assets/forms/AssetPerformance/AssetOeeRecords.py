from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetPerformance.AssetOeeRecords import AssetOeeRecord
from apps.scm.models import Asset

User = get_user_model()


class AssetOeeRecordForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetOeeRecord
        fields = [
            "fixed_asset",
            "operational_asset",
            "record_date",
            "shift_name",
            "planned_production_time_minutes",
            "operating_time_minutes",
            "ideal_cycle_time_seconds",
            "total_units_produced",
            "good_units_produced",
            "defect_units_count",
            "rework_units_count",
            "breakdown_loss_minutes",
            "setup_loss_minutes",
            "small_stops_loss_minutes",
            "reduced_speed_loss_minutes",
            "defect_loss_minutes",
            "startup_loss_minutes",
            "status",
            "notes",
            "recorded_by",
        ]
        exclude = [
            "tenant",
            "number",
            "availability_percentage",
            "performance_percentage",
            "quality_percentage",
            "oee_percentage",
            "benchmark_tier",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "record_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "shift_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Shift 1 / Day Shift"}),
            "planned_production_time_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "operating_time_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "ideal_cycle_time_seconds": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_units_produced": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "good_units_produced": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "defect_units_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "rework_units_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "breakdown_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "setup_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "small_stops_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "reduced_speed_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "defect_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "startup_loss_minutes": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Operator observations, scrap causes, bottlenecks..."}),
            "recorded_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant).order_by("name")
            self.fields["recorded_by"].queryset = User.objects.filter(tenant_memberships__tenant=tenant).distinct().order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fixed_asset", "operational_asset"])

        planned = cleaned.get("planned_production_time_minutes")
        operating = cleaned.get("operating_time_minutes")
        if planned is not None and operating is not None and operating > planned:
            self.add_error("operating_time_minutes", "Operating time cannot exceed planned production time.")

        total_units = cleaned.get("total_units_produced") or 0
        good_units = cleaned.get("good_units_produced") or 0
        defects = cleaned.get("defect_units_count") or 0

        if good_units > total_units:
            self.add_error("good_units_produced", "Good units count cannot exceed total units produced.")

        if (good_units + defects) > total_units and total_units > 0:
            self.add_error("defect_units_count", "Sum of good and defect units exceeds total units produced.")

        return cleaned
