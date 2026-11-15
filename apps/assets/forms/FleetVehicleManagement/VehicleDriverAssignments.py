"""Form for Vehicle Driver Assignment and Safety records (11.19)."""

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignment
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile

User = get_user_model()


class VehicleDriverAssignmentForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Vehicle Driver Assignments [VDRV]."""

    _TENANT_FIELDS = [
        "vehicle",
        "driver",
        "user",
    ]

    class Meta:
        model = VehicleDriverAssignment
        fields = [
            "vehicle",
            "driver",
            "user",
            "assignment_role",
            "start_datetime",
            "end_datetime",
            "start_odometer",
            "end_odometer",
            "driver_license_number",
            "driver_license_state",
            "license_class",
            "license_expiration_date",
            "medical_card_expiration_date",
            "hazmat_endorsed",
            "safety_score",
            "speeding_event_count",
            "harsh_braking_count",
            "harsh_acceleration_count",
            "incident_count",
            "duty_status",
            "supervisor_notes",
        ]
        widgets = {
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
            "license_expiration_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "medical_card_expiration_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "supervisor_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant is not None:
            self.fields["vehicle"].queryset = FleetVehicle.objects.filter(tenant=self.tenant)
            self.fields["driver"].queryset = EmployeeProfile.objects.filter(tenant=self.tenant)
            self.fields["user"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_datetime")
        end = cleaned_data.get("end_datetime")
        if start and end and end < start:
            self.add_error("end_datetime", "End datetime cannot precede start datetime.")

        start_odo = cleaned_data.get("start_odometer")
        end_odo = cleaned_data.get("end_odometer")
        if start_odo is not None and end_odo is not None and end_odo < start_odo:
            self.add_error("end_odometer", "Ending odometer cannot be less than starting odometer.")

        reject_foreign(self, cleaned_data, self._TENANT_FIELDS)
        return cleaned_data
