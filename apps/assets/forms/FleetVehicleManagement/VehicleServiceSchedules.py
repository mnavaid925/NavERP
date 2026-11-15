"""Form for Vehicle Service Scheduling and Preventive Maintenance (11.19)."""

from django import forms

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import AssetMaintenanceSchedule
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceSchedule
from apps.core.models.Party import Party


class VehicleServiceScheduleForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Vehicle Service Schedules [VSRV]."""

    _TENANT_FIELDS = [
        "vehicle",
        "service_vendor",
        "warranty",
        "maintenance_schedule",
    ]

    class Meta:
        model = VehicleServiceSchedule
        fields = [
            "vehicle",
            "service_title",
            "service_type",
            "service_vendor",
            "warranty",
            "maintenance_schedule",
            "interval_mileage",
            "interval_months",
            "last_service_date",
            "last_service_odometer",
            "next_due_date",
            "next_due_odometer",
            "priority",
            "estimated_cost",
            "currency",
            "is_warranty_covered",
            "work_order_invoice_ref",
            "technician_resolution_notes",
        ]
        widgets = {
            "last_service_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "next_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "technician_resolution_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant is not None:
            self.fields["vehicle"].queryset = FleetVehicle.objects.filter(tenant=self.tenant)
            self.fields["service_vendor"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["warranty"].queryset = AssetWarranty.objects.filter(tenant=self.tenant)
            self.fields["maintenance_schedule"].queryset = AssetMaintenanceSchedule.objects.filter(tenant=self.tenant)

        # Global Currency - do NOT pass to reject_foreign
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        interval_m = cleaned_data.get("interval_mileage")
        if interval_m is not None and interval_m < 0:
            self.add_error("interval_mileage", "Mileage interval cannot be negative.")

        reject_foreign(self, cleaned_data, self._TENANT_FIELDS)
        return cleaned_data
