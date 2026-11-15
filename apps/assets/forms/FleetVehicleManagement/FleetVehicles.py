"""Form for Fleet Vehicle registration and maintenance management (11.19)."""

from django import forms
from django.utils import timezone

from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetClassification.AssetModels import AssetModel
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.core.models.OrgUnit import OrgUnit
from apps.core.models.Party import Party
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.scm.models.AssetManagement.Assets import Asset


class FleetVehicleForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Fleet Vehicles [FLT]."""

    _TENANT_FIELDS = [
        "operational_asset",
        "fixed_asset",
        "asset_category",
        "asset_model",
        "org_unit",
        "primary_driver",
        "custodian_party",
    ]

    class Meta:
        model = FleetVehicle
        fields = [
            "name",
            "vin",
            "license_plate",
            "registration_state",
            "make",
            "model",
            "year",
            "vehicle_type",
            "fuel_type",
            "ownership_type",
            "title_number",
            "registration_expiration_date",
            "safety_inspection_due_date",
            "emissions_inspection_due_date",
            "current_odometer",
            "engine_hours",
            "gross_vehicle_weight_rating_lbs",
            "fuel_tank_capacity_gallons",
            "battery_capacity_kwh",
            "is_telematics_enabled",
            "telematics_device_id",
            "operational_asset",
            "fixed_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "primary_driver",
            "custodian_party",
            "notes",
        ]
        widgets = {
            "registration_expiration_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "safety_inspection_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "emissions_inspection_due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant is not None:
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["asset_model"].queryset = AssetModel.objects.filter(tenant=self.tenant)
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["primary_driver"].queryset = EmployeeProfile.objects.filter(tenant=self.tenant)
            self.fields["custodian_party"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("year")
        current_year = timezone.now().year
        if year is not None:
            if year < 1900 or year > current_year + 2:
                self.add_error("year", f"Model year must be between 1900 and {current_year + 2}.")

        reject_foreign(self, cleaned_data, self._TENANT_FIELDS)
        return cleaned_data
