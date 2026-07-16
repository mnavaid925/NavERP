"""HRM 3.21 Performance Improvement — Warningletter forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    PerformanceImprovementPlan,
    WarningLetter,
)


class WarningLetterForm(TenantModelForm):
    # status/acknowledged_* are workflow-owned (issue/acknowledge actions); employee_response is captured
    # only via the acknowledge action (WarningAcknowledgeForm), never on this edit form; number auto.
    class Meta:
        model = WarningLetter
        fields = ["issued_to", "issued_by", "level", "category", "incident_date", "description",
                  "policy_reference", "related_pip", "expiry_date"]
        widgets = {
            "incident_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, viewer_profile=None, viewer_is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "issued_to" in self.fields:
                self.fields["issued_to"].queryset = emps
            if "issued_by" in self.fields:
                self.fields["issued_by"].queryset = emps
            if "related_pip" in self.fields:
                # PIPs are confidential — a non-admin sees only PIPs they may see (their own subject/
                # manager rows), never the tenant PIP roster; an admin sees all. Viewer = the letter's
                # issuer (edit) or creator (create).
                rq = PerformanceImprovementPlan.objects.filter(tenant=self.tenant).select_related("subject__party")
                if not viewer_is_admin:
                    viewer = self.instance.issued_by if (self.instance and self.instance.issued_by_id) else viewer_profile
                    rq = rq.filter(Q(subject=viewer) | Q(manager=viewer)) if viewer is not None else rq.none()
                    if self.instance and self.instance.related_pip_id:
                        rq = (rq | PerformanceImprovementPlan.objects.filter(pk=self.instance.related_pip_id)).distinct()
                self.fields["related_pip"].queryset = rq.order_by("-start_date")
