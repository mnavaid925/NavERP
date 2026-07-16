"""HRM 3.7 Interview Process — Interviewfeedback forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Interview,
    InterviewFeedback,
    InterviewPanelist,
)


class InterviewFeedbackForm(TenantModelForm):
    # `number` auto; `submitted_by`/`submitted_at` AND `is_submitted` are workflow-owned — submission is
    # the dedicated submit POST action only (a form checkbox would let a submitted card be un-submitted).
    class Meta:
        model = InterviewFeedback
        fields = ["interview", "panelist", "overall_recommendation", "summary"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["interview"].queryset = (
                Interview.objects.filter(tenant=self.tenant)
                .select_related("application__candidate").order_by("-scheduled_at"))
            # Scope the panelist picker to the chosen interview's panel: on edit the interview is fixed;
            # on create it comes from ?interview= (initial) or the bound POST (data). When it can't be
            # resolved (or is junk), fall back to the full tenant list — clean() (below) still rejects a
            # cross-interview pick server-side, and the isdigit guard stops a hand-edited ?interview=abc
            # from raising ValueError while building the queryset.
            interview_id = None
            if self.instance and self.instance.pk and self.instance.interview_id:
                interview_id = self.instance.interview_id
            else:
                raw = (self.initial or {}).get("interview") or (self.data or {}).get("interview")
                if raw and str(raw).isdigit():
                    interview_id = int(raw)
            if interview_id:
                panel_qs = InterviewPanelist.objects.filter(interview_id=interview_id, tenant=self.tenant)
            else:
                panel_qs = InterviewPanelist.objects.filter(tenant=self.tenant)
            self.fields["panelist"].queryset = (
                panel_qs.select_related("interviewer", "interview").order_by("interview__pk", "role"))
        self.fields["panelist"].required = False

    def clean(self):
        cleaned = super().clean()
        interview = cleaned.get("interview")
        panelist = cleaned.get("panelist")
        if panelist and interview and panelist.interview_id != interview.id:
            self.add_error("panelist", "That panelist is not on the selected interview.")
        return cleaned
