"""CRM 1.6 Analytics & Reporting — Reports forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    AnalyticsReport,
    REPORT_GROUP_CHOICES,
)


class AnalyticsReportForm(TenantModelForm):
    """Saved standard report. ``last_run_at`` is system-stamped (editable=False), never on the form.
    ``clean()`` keeps ``group_by`` meaningful per report type so a grouping is never silently
    ignored by the compute layer (e.g. a Service report can only group by month/week/priority)."""

    # Which groupings each report type actually honours in apps/crm/analytics.py.
    ALLOWED_GROUPINGS = {
        "sales_activity": {"month", "week"},
        "sales_performance": {"owner"},
        "funnel": {"stage"},
        "service": {"month", "week", "priority"},
    }

    class Meta:
        model = AnalyticsReport
        fields = ["name", "description", "report_type", "date_range", "group_by", "is_favorite", "owner"]

    def clean(self):
        from apps.crm.models import REPORT_GROUP_CHOICES
        cleaned = super().clean()
        rtype = cleaned.get("report_type")
        grp = cleaned.get("group_by")
        allowed = self.ALLOWED_GROUPINGS.get(rtype)
        if rtype and grp and allowed and grp not in allowed:
            labels = ", ".join(lbl for val, lbl in REPORT_GROUP_CHOICES if val in allowed)
            self.add_error("group_by", f"This report type supports grouping by: {labels}.")
        return cleaned
