from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetRisk.AssetBusinessContinuityPlans import AssetBusinessContinuityPlan
from apps.scm.models import Asset

User = get_user_model()


class AssetBusinessContinuityPlanForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetBusinessContinuityPlan
        fields = [
            "title",
            "primary_asset",
            "backup_redundant_asset",
            "redundancy_type",
            "recovery_time_objective_hours",
            "recovery_point_objective_hours",
            "maximum_tolerable_downtime_hours",
            "disaster_scenario",
            "failover_procedure",
            "failback_procedure",
            "alternate_facility_site",
            "critical_spares_required",
            "emergency_lead",
            "drill_frequency",
            "last_drill_date",
            "next_drill_date",
            "drill_result",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Primary Turbine Redundancy & Recovery Plan"}
            ),
            "primary_asset": forms.Select(attrs={"class": "form-select"}),
            "backup_redundant_asset": forms.Select(attrs={"class": "form-select"}),
            "redundancy_type": forms.Select(attrs={"class": "form-select"}),
            "recovery_time_objective_hours": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.25", "min": "0", "placeholder": "4.00"}
            ),
            "recovery_point_objective_hours": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.25", "min": "0", "placeholder": "1.00"}
            ),
            "maximum_tolerable_downtime_hours": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.50", "min": "0", "placeholder": "24.00"}
            ),
            "disaster_scenario": forms.Select(attrs={"class": "form-select"}),
            "failover_procedure": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Sequential instructions to switch operations to redundant unit..."}
            ),
            "failback_procedure": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Procedures to safely restore primary unit operations..."}
            ),
            "alternate_facility_site": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Plant 2 Auxiliary Building or Offsite Facility"}
            ),
            "critical_spares_required": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Essential spare parts, supplier SLA commitments, and storage location..."}
            ),
            "emergency_lead": forms.Select(attrs={"class": "form-select"}),
            "drill_frequency": forms.Select(attrs={"class": "form-select"}),
            "last_drill_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_drill_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "drill_result": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["primary_asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["backup_redundant_asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["emergency_lead"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["primary_asset", "backup_redundant_asset", "emergency_lead"])

        primary = cleaned.get("primary_asset")
        backup = cleaned.get("backup_redundant_asset")
        if primary and backup and primary.pk == backup.pk:
            raise ValidationError("Backup / redundant asset cannot be the identical machine as the primary asset.")

        return cleaned
