from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetPerformance.AssetEnergyReadings import AssetEnergyReading
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()


class AssetEnergyReadingForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetEnergyReading
        fields = [
            "fixed_asset",
            "operational_asset",
            "reading_timestamp",
            "utility_type",
            "meter_serial_number",
            "consumption_value",
            "unit_of_measure",
            "peak_demand_kw",
            "power_factor",
            "operating_hours",
            "units_produced",
            "emission_factor",
            "ghg_scope",
            "cost_per_unit",
            "utility_provider",
            "status",
            "notes",
            "recorded_by",
        ]
        exclude = [
            "tenant",
            "number",
            "energy_intensity_per_hour",
            "energy_intensity_per_unit",
            "carbon_emissions_kg_co2e",
            "total_energy_cost",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "reading_timestamp": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "utility_type": forms.Select(attrs={"class": "form-select"}),
            "meter_serial_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. MTR-ELEC-BLDG4"}),
            "consumption_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "unit_of_measure": forms.TextInput(attrs={"class": "form-input", "placeholder": "kWh / m3 / liters"}),
            "peak_demand_kw": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "power_factor": forms.NumberInput(attrs={"class": "form-input", "step": "0.001", "min": "0.000", "max": "1.000"}),
            "operating_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "units_produced": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "emission_factor": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "ghg_scope": forms.Select(attrs={"class": "form-select"}),
            "cost_per_unit": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "utility_provider": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Meter conditions, tariff tier, notes..."}),
            "recorded_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant).order_by("name")
            self.fields["utility_provider"].queryset = Party.objects.filter(tenant=tenant).order_by("name")
            self.fields["recorded_by"].queryset = User.objects.filter(tenant=tenant, is_active=True).order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fixed_asset", "operational_asset", "utility_provider"])

        pf = cleaned.get("power_factor")
        if pf is not None and (pf < Decimal("0.000") or pf > Decimal("1.000")):
            self.add_error("power_factor", "Power factor cos phi must be between 0.000 and 1.000.")

        consumption = cleaned.get("consumption_value")
        if consumption is not None and consumption < Decimal("0.0000"):
            self.add_error("consumption_value", "Consumption quantity cannot be negative.")

        return cleaned
