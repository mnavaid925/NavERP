"""HRM 3.4 Employee Offboarding — Separationcase forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    SeparationCase,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


# ----------------------------------------------------------------------- 3.4 Employee Offboarding
class SeparationCaseForm(TenantModelForm):
    # SECURITY: every lifecycle field is excluded — `status`, `submitted_at`, `approver`,
    # `approved_at`, `rejection_reason`/`withdrawal_reason`, both letter-generated stamps, and the
    # derived `expected_last_working_day` (computed in save()). They're advanced only by the audited
    # workflow actions; exposing them would let a crafted POST skip approval/clearance.
    class Meta:
        model = SeparationCase
        fields = ["employee", "separation_type", "exit_reason", "resignation_letter",
                  "notice_period_days", "notice_start_date", "actual_last_working_day",
                  "notice_buyout_type", "requires_kt", "notes"]

    def clean_resignation_letter(self):
        return _validate_upload(self.cleaned_data.get("resignation_letter"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="File")
