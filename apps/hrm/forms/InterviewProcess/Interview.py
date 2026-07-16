"""HRM 3.7 Interview Process — Interview forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Interview,
    InterviewPanelist,
    JobApplication,
)


# ----------------------------------------------------------------------- 3.7 Interview Process
class InterviewForm(TenantModelForm):
    # SECURITY/workflow: `status` (state machine), `scheduled_by` (set to request.user in the view),
    # `reminder_sent_at`/`feedback_reminder_sent_at` (stamped by the send-reminder actions) are OUT of
    # the form. `scheduled_at` gets the round-tripping datetime-local widget from TenantModelForm.
    class Meta:
        model = Interview
        fields = ["application", "title", "round_number", "mode", "scheduled_at", "duration_minutes",
                  "location", "video_provider", "meeting_url", "interviewer_instructions", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # select_related the dropdown's __str__ traversal (candidate + requisition) to avoid an
            # N+1 per option; the base already tenant-scopes the queryset.
            self.fields["application"].queryset = (
                JobApplication.objects.filter(tenant=self.tenant)
                .select_related("candidate", "requisition").order_by("-applied_at"))


class InterviewPanelistForm(TenantModelForm):
    # Inline-add on the interview detail hub; `interview` is set in the view. `rsvp_status`/`notified_at`
    # are workflow-owned (the rsvp action / send-invite stamp them).
    class Meta:
        model = InterviewPanelist
        fields = ["interviewer", "role", "briefing_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["interviewer"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["interviewer"].queryset = get_user_model().objects.none()
