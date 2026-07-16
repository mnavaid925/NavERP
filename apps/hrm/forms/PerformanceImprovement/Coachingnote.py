"""HRM 3.21 Performance Improvement — Coachingnote forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    CoachingNote,
    EmployeeProfile,
    PerformanceImprovementPlan,
)


class CoachingNoteForm(TenantModelForm):
    # `coach` is resolved server-side from request.user (NEVER form-typed — the strictest-confidentiality
    # model; a user must not log a coaching note as someone else, like Feedback.giver); `number` auto.
    class Meta:
        model = CoachingNote
        fields = ["employee", "related_pip", "note_date", "category", "content"]
        widgets = {
            "note_date": forms.DateInput(attrs={"type": "date"}),
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "related_pip" in self.fields:
                # A non-admin sees only PIPs they may see (their own subject/manager rows); an admin sees all.
                rq = PerformanceImprovementPlan.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.coach if (self.instance and self.instance.coach_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(manager=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.related_pip_id:
                        rq = (rq | PerformanceImprovementPlan.objects.filter(pk=self.instance.related_pip_id)).distinct()
                self.fields["related_pip"].queryset = rq.order_by("-start_date")
