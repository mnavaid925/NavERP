"""HRM 3.2 Organizational Structure — EmployeeProfiles forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class EmployeeProfileForm(TenantModelForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            "party", "employment", "designation", "employee_type", "gender", "date_of_birth",
            "blood_group", "marital_status", "nationality", "personal_email", "work_email", "mobile",
            "work_location", "notice_period_days", "father_name", "spouse_name",
            "national_id", "national_id_type", "passport_number", "passport_expiry",
            "current_address", "permanent_address", "bank_name", "bank_account", "bank_routing",
            "probation_end_date", "confirmed_on", "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation", "emergency_contact_2_name", "emergency_contact_2_phone",
            "emergency_contact_2_relation", "photo", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The employee identity is a *person* Party; never offer organizations here.
        if self.tenant is not None:
            self.fields["party"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="person").order_by("name")

    def clean_photo(self):
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")
