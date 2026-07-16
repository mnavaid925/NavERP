"""HRM 3.3 Employee Onboarding — Orientationsession forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OrientationSession,
)


class OrientationSessionForm(TenantModelForm):
    # SECURITY: `attendance_status` is excluded — it's advanced only by the mark-attended /
    # mark-missed workflow actions (which write an audit row). A session is created "scheduled";
    # exposing the field would let attendance be set via a crafted POST with no audit trail.
    class Meta:
        model = OrientationSession
        fields = ["program", "employee", "title", "session_type", "facilitator", "facilitator_name",
                  "scheduled_at", "duration_minutes", "location", "meeting_url", "notes"]
