"""Projects 7.11 Time & Attendance Tracking — ProjectOvertimeRecordForm."""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import ProjectOvertimeRecord


class ProjectOvertimeRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectOvertimeRecord
        fields = [
            "resource", "project", "project_task", "time_entry",
            "date", "overtime_hours", "overtime_type",
            "pay_multiplier", "billable_multiplier", "is_billable", "notes",
        ]
        help_texts = {
            "overtime_hours": "Actual overtime hours worked (e.g. 2.50).",
            "pay_multiplier": "Compensation multiplier (e.g. 1.50 = 1.5x pay).",
            "billable_multiplier": "Billing rate multiplier charged to client.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["resource"].queryset = self.fields["resource"].queryset.filter(tenant=self.tenant)
            self.fields["project"].queryset = self.fields["project"].queryset.filter(tenant=self.tenant)
            self.fields["project_task"].queryset = self.fields["project_task"].queryset.filter(tenant=self.tenant)
            self.fields["time_entry"].queryset = self.fields["time_entry"].queryset.filter(tenant=self.tenant)
