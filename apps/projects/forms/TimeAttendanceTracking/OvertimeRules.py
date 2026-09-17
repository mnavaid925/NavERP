"""Projects 7.11 Time & Attendance Tracking — OvertimeRuleForm."""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import OvertimeRule


class OvertimeRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OvertimeRule
        fields = [
            "project", "name", "standard_daily_hours", "standard_weekly_hours",
            "daily_overtime_multiplier", "weekly_overtime_multiplier",
            "weekend_multiplier", "holiday_multiplier",
            "requires_pre_approval", "is_active", "notes",
        ]
        help_texts = {
            "project": "Leave blank to apply as default policy across all projects.",
            "standard_daily_hours": "Standard hours per day before daily overtime begins (typically 8.00).",
            "standard_weekly_hours": "Standard hours per week before weekly overtime begins (typically 40.00).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(tenant=self.tenant)
