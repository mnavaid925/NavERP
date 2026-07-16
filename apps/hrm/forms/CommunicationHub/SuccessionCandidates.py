"""HRM 3.27 Communication Hub — SuccessionCandidates forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    SuccessionCandidate,
)


class SuccessionCandidateForm(TenantModelForm):
    # plan is set by the view (inline child of a SuccessionPlan).
    class Meta:
        model = SuccessionCandidate
        fields = ["candidate", "readiness", "rank_order", "development_notes"]
        widgets = {"development_notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "candidate" in self.fields:
            self.fields["candidate"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        rank = cleaned.get("rank_order")
        if rank is not None and rank < 1:
            self.add_error("rank_order", "Rank must be 1 or greater.")
        # unique_together(tenant, plan, candidate): plan_id is set on the instance on BOTH add (the
        # view passes SuccessionCandidate(tenant=..., plan=plan)) and edit, so this guard covers both —
        # exclude(pk=self.instance.pk) is a no-op on add (pk is None -> excludes nothing).
        candidate = cleaned.get("candidate")
        if self.instance.plan_id and candidate and self.tenant is not None:
            dupe = SuccessionCandidate.objects.filter(
                tenant=self.tenant, plan_id=self.instance.plan_id, candidate=candidate
            ).exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("candidate", "This employee is already a successor on this plan.")
        return cleaned
