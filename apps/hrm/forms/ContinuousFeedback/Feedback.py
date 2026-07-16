"""HRM 3.20 Continuous Feedback — Feedback forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Feedback,
    KudosBadge,
    Objective,
    PerformanceReview,
)


class FeedbackForm(TenantModelForm):
    # `giver` is resolved from request.user server-side (never form-typed, mirroring how
    # GoalCheckIn.created_by is set in the view). `status`/`number`/`acknowledged_at` are
    # workflow-owned (the create-as-request path + the feedback_acknowledge action set them) —
    # never on this form, same reasoning as PerformanceReviewForm's workflow fields. `requested_from`
    # is a system linkage set from the ?respond_to= URL param in feedback_create, not a manual field.
    # `is_anonymous` masks the giver on READ only (the FK is still stored).
    class Meta:
        model = Feedback
        fields = ["receiver", "feedback_type", "visibility", "message", "is_anonymous",
                  "badge", "related_objective", "related_review"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "receiver" in self.fields:
                self.fields["receiver"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "badge" in self.fields:
                self.fields["badge"].queryset = (
                    KudosBadge.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
            if "related_objective" in self.fields:
                # Objectives are company-open in NavERP (unlike reviews), so no visibility scoping.
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant)
                    .select_related("goal_period").order_by("title"))
            if "related_review" in self.fields:
                # Confidentiality (3.19): only surface reviews the FEEDBACK GIVER may see (their own
                # subject/reviewer rows) — never the tenant-wide review roster (who-is-reviewed is
                # confidential). The giver is the edit instance's giver, or (on create) the
                # viewer_profile the view passes.
                giver = self.instance.giver if self.instance and self.instance.giver_id else viewer_profile
                rq = PerformanceReview.objects.filter(tenant=self.tenant).select_related("subject__party")
                rq = rq.filter(Q(subject=giver) | Q(reviewer=giver)) if giver is not None else rq.none()
                self.fields["related_review"].queryset = rq.order_by("-created_at")
