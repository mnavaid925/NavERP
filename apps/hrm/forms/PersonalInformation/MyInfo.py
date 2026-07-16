"""HRM 3.25 Personal Information — MyInfo forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class EmployeeProfileMyInfoForm(TenantModelForm):
    """The employee's OWN direct-edit form — the non-gated subset of ``EmployeeProfile`` only
    (address / personal email / mobile / photo). The sensitive fields (legal name / DOB / national
    ID / passport / bank) are NOT here — they change only via ``EmployeeInfoChangeRequest``."""

    class Meta:
        model = EmployeeProfile
        fields = ["current_address", "permanent_address", "personal_email", "mobile", "photo"]
        widgets = {"current_address": forms.Textarea(attrs={"rows": 2}),
                   "permanent_address": forms.Textarea(attrs={"rows": 2})}

    def clean_photo(self):
        return _validate_upload(self.cleaned_data.get("photo"),
                                allowed_ext=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES, label="Photo")
