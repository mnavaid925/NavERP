"""Form for Vehicle Fuel Log transactions and mileage tracking (11.19)."""

from django import forms

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLog
from apps.core.models.Party import Party
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile


class VehicleFuelLogForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Vehicle Fuel Logs [VFUL]."""

    _TENANT_FIELDS = [
        "vehicle",
        "driver",
        "fuel_vendor",
    ]

    class Meta:
        model = VehicleFuelLog
        fields = [
            "vehicle",
            "driver",
            "fuel_vendor",
            "fuel_date",
            "odometer_at_fueling",
            "fuel_type",
            "quantity_gallons",
            "unit_price",
            "total_cost",
            "currency",
            "is_full_tank",
            "fuel_card_token",
            "fuel_station_name",
            "station_city_state",
            "route_category",
            "receipt_reference",
            "notes",
        ]
        widgets = {
            "fuel_date": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant is not None:
            self.fields["vehicle"].queryset = FleetVehicle.objects.filter(tenant=self.tenant)
            self.fields["driver"].queryset = EmployeeProfile.objects.filter(tenant=self.tenant)
            self.fields["fuel_vendor"].queryset = Party.objects.filter(tenant=self.tenant)

        # Global Currency - do NOT pass to reject_foreign
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity_gallons")
        if quantity is not None and quantity <= 0:
            self.add_error("quantity_gallons", "Quantity pumped must be greater than zero.")

        odometer = cleaned_data.get("odometer_at_fueling")
        if odometer is not None and odometer < 0:
            self.add_error("odometer_at_fueling", "Odometer reading cannot be negative.")

        reject_foreign(self, cleaned_data, self._TENANT_FIELDS)
        return cleaned_data
