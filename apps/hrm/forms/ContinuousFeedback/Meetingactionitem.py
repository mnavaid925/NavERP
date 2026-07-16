"""HRM 3.20 Continuous Feedback — Meetingactionitem forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    MeetingActionItem,
)


class MeetingActionItemForm(TenantModelForm):
    # `meeting` is set from the URL in the nested create view; `status` is toggled only by
    # meetingactionitem_toggle (off the form, like KeyResultForm/ReviewRatingForm workflow fields);
    # `number`/`completed_at` are auto/workflow.
    class Meta:
        model = MeetingActionItem
        fields = ["description", "owner", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "owner" in self.fields:
            # Scope the owner to the 1:1's two participants — an action item must NOT be assignable to
            # an outsider (who could then edit/toggle/delete it while being blocked from viewing the
            # meeting: an inconsistent trust boundary). `meeting` is on the instance (set from the URL
            # on create, or carried by the edited row).
            meeting = self.instance.meeting if self.instance and self.instance.meeting_id else None
            base = EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
            self.fields["owner"].queryset = (
                base.filter(pk__in=[meeting.manager_id, meeting.employee_id]) if meeting is not None else base
            ).order_by("party__name")
