"""Projects 7.17 — RecurringTaskSchedule forms."""
from django import forms

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.WorkflowAutomation.RecurringTasks import RecurringTaskSchedule


class RecurringTaskScheduleForm(TenantModelForm):
    """Form for creating and updating RecurringTaskSchedule instances."""

    class Meta:
        model = RecurringTaskSchedule
        fields = [
            "project",
            "title_template",
            "description_template",
            "is_active",
            "frequency",
            "interval_count",
            "days_of_week",
            "day_of_month",
            "priority",
            "effort_hours",
            "assignee_strategy",
            "default_assignee",
            "start_date",
            "end_date",
            "next_run_date",
        ]
        widgets = {
            "description_template": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "frequency": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "assignee_strategy": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "next_run_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned
