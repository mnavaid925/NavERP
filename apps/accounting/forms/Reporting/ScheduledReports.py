"""Accounting 2.12 Reporting & Compliance — ScheduledReports forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    ScheduledReport,
)


class ScheduledReportForm(TenantModelForm):
    class Meta:
        model = ScheduledReport
        fields = ["name", "report_type", "frequency", "recipients", "is_active"]
