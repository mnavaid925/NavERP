"""HRM 3.27 Communication Hub — WellbeingParticipations forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    WellbeingParticipation,
)


class WellbeingParticipationForm(TenantModelForm):
    """RSVP / attendance / points row. ``can_admin`` drops the privileged fields for a plain employee
    (mirrors HRDashboardForm(can_share=...)): a non-admin may register or withdraw only, and never
    self-award points or self-mark attended/completed."""

    # tenant/program/employee are all view-resolved (the (tenant, program, employee) unique_together is
    # therefore guarded by an explicit query in the view, not here — Django can't validate_unique it).
    class Meta:
        model = WellbeingParticipation
        fields = ["status", "points_earned", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, can_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_admin:
            # A plain employee can only RSVP or withdraw — never self-mark attendance or award points.
            self.fields.pop("points_earned", None)
            self.fields["status"].choices = [("registered", "Registered"), ("withdrawn", "Withdrawn")]
