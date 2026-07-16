"""HRM 3.21 Performance Improvement — PerformanceImprovementPlans forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    PerformanceImprovementPlan,
    PerformanceReview,
)


# ------------------------------------------------------------------------- 3.21 Performance Improvement
class PerformanceImprovementPlanForm(TenantModelForm):
    # status/outcome/outcome_*/extended_end_date/*_at/*_by are workflow-owned (set only by the
    # hr_approve/acknowledge/close/extend actions — never on this form, mirroring PerformanceReviewForm).
    class Meta:
        model = PerformanceImprovementPlan
        fields = ["subject", "manager", "triggering_review", "performance_issue", "expected_standards",
                  "improvement_goals", "support_provided", "measurement_criteria", "start_date", "end_date"]
        widgets = {
            "performance_issue": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "expected_standards": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "improvement_goals": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "support_provided": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "measurement_criteria": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "subject" in self.fields:
                self.fields["subject"].queryset = emps
            if "manager" in self.fields:
                self.fields["manager"].queryset = emps
            if "triggering_review" in self.fields:
                # Confidentiality (3.19): a non-admin sees only reviews they may see (their own subject/
                # reviewer rows), NOT the tenant-wide review roster; an admin (full visibility) sees all.
                # Viewer = the PIP's manager (edit) or the passed creator (create); keep the already-linked
                # review selectable on edit.
                rq = PerformanceReview.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.manager if (self.instance and self.instance.manager_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(reviewer=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.triggering_review_id:
                        rq = (rq | PerformanceReview.objects.filter(pk=self.instance.triggering_review_id)).distinct()
                self.fields["triggering_review"].queryset = rq.order_by("-created_at")
