from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetInventoryTracking.AssetMovementLogs import AssetMovementLog
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, Location


class AssetMovementLogForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetMovementLog
        fields = [
            "title",
            "asset",
            "movement_type",
            "from_location",
            "from_org_unit",
            "from_room_bin",
            "to_location",
            "to_org_unit",
            "to_room_bin",
            "from_custodian",
            "to_custodian",
            "gps_latitude",
            "gps_longitude",
            "gps_address",
            "carrier_name",
            "tracking_number",
            "reason",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "condition_on_receipt",
            "created_at",
            "updated_at",
            "dispatch_date",
            "dispatched_by",
            "received_date",
            "received_by",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CNC Machine Relocation to Bay 4"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "movement_type": forms.Select(attrs={"class": "form-select"}),
            "from_location": forms.Select(attrs={"class": "form-select"}),
            "from_org_unit": forms.Select(attrs={"class": "form-select"}),
            "from_room_bin": forms.TextInput(attrs={"class": "form-input", "placeholder": "Bldg 1, Floor 2, Room 204"}),
            "to_location": forms.Select(attrs={"class": "form-select"}),
            "to_org_unit": forms.Select(attrs={"class": "form-select"}),
            "to_room_bin": forms.TextInput(attrs={"class": "form-input", "placeholder": "Bldg 3, Bay 4, Rack B"}),
            "from_custodian": forms.Select(attrs={"class": "form-select"}),
            "to_custodian": forms.Select(attrs={"class": "form-select"}),
            "gps_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "e.g. 37.774929"}),
            "gps_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "e.g. -122.419416"}),
            "gps_address": forms.TextInput(attrs={"class": "form-input", "placeholder": "Physical address or landmark"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Internal Fleet / Commercial Carrier"}),
            "tracking_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "Tracking code or transfer manifest ID"}),
            "reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason for relocation, project requirements..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Special handling instructions, rigging notes..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("number")
            locations = Location.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
            self.fields["from_location"].queryset = locations
            self.fields["to_location"].queryset = locations
            org_units = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["from_org_unit"].queryset = org_units
            self.fields["to_org_unit"].queryset = org_units
            custodians = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["from_custodian"].queryset = custodians
            self.fields["to_custodian"].queryset = custodians

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                ["asset", "from_location", "to_location", "from_org_unit", "to_org_unit", "from_custodian", "to_custodian"],
            )

        from_loc = cleaned_data.get("from_location")
        to_loc = cleaned_data.get("to_location")
        from_room = cleaned_data.get("from_room_bin", "").strip()
        to_room = cleaned_data.get("to_room_bin", "").strip()

        if from_loc and to_loc and from_loc == to_loc and from_room and to_room and from_room == to_room:
            self.add_error("to_location", "Destination facility and room cannot be identical to source.")

        return cleaned_data
