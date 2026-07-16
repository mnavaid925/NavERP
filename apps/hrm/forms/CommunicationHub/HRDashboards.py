"""HRM 3.27 Communication Hub — HRDashboards forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HRDashboard,
)


class HRDashboardForm(TenantModelForm):
    """A saved HR analytics dashboard. ``is_shared`` (publish tenant-wide) and ``is_default``
    (the owner's landing dashboard) are only offered to tenant admins — for a regular user the
    fields are dropped so the model defaults stand (no privilege escalation via the form). ``owner``
    is never a form field: it is always set to the creating user in the view."""

    class Meta:
        model = HRDashboard
        fields = ["name", "description", "is_shared", "is_default", "layout"]

    def __init__(self, *args, can_share=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_share:
            self.fields.pop("is_shared", None)
            self.fields.pop("is_default", None)
