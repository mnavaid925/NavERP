"""HRM 3.27 Communication Hub — TalentPoolMemberships forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    TalentPool,
    TalentPoolMembership,
)


class TalentPoolMembershipForm(TenantModelForm):
    class Meta:
        model = TalentPoolMembership
        fields = ["pool", "employee", "joined_on", "status", "review", "performance_rating",
                  "potential_rating", "flight_risk", "retention_action_plan", "notes"]
        widgets = {"retention_action_plan": forms.Textarea(attrs={"rows": 3}),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "pool" in self.fields:
                self.fields["pool"].queryset = (
                    TalentPool.objects.filter(tenant=self.tenant, is_active=True).order_by("pool_type", "name"))
            if "employee" in self.fields:
                self.fields["employee"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        for f in ("performance_rating", "potential_rating"):
            v = cleaned.get(f)
            if v is not None and not (Decimal("1") <= v <= Decimal("5")):
                self.add_error(f, "Must be between 1 and 5.")
        # unique_together(tenant, pool, employee) — guard it (tenant is form-excluded).
        pool, employee = cleaned.get("pool"), cleaned.get("employee")
        if pool and employee and self.tenant is not None:
            dupe = TalentPoolMembership.objects.filter(tenant=self.tenant, pool=pool, employee=employee)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("employee", "This employee is already a member of that talent pool.")
        return cleaned
