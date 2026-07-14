"""CRM 1.6 Analytics & Reporting — Dashboards forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    AnalyticsDashboard,
)


class AnalyticsDashboardForm(TenantModelForm):
    """``is_shared`` (publish to the whole tenant) and ``is_default`` (everyone's landing
    dashboard) are tenant-wide settings, so they are only offered to tenant admins. For a
    regular staff user the fields are dropped — the model defaults stand on create and the
    stored values are preserved on edit (security-review: no privilege escalation via the form)."""

    class Meta:
        model = AnalyticsDashboard
        fields = ["name", "description", "owner", "is_shared", "is_default", "layout"]

    def __init__(self, *args, can_share=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_share:
            self.fields.pop("is_shared", None)
            self.fields.pop("is_default", None)
