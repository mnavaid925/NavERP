"""Projects 7.11 Time & Attendance Tracking — TimeActivityCodeForm."""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import TimeActivityCode


class TimeActivityCodeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = TimeActivityCode
        fields = ["code", "name", "category", "is_billable_default", "is_active", "description"]
        help_texts = {
            "code": "Unique alphanumeric code (e.g. DEV, QA, PM, OVERHEAD).",
            "category": "Overhead allocation grouping.",
        }

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()
