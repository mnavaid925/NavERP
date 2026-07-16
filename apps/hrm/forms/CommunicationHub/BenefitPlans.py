"""HRM 3.27 Communication Hub — BenefitPlans forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    BenefitPlan,
)
from apps.hrm.forms.CommunicationHub._helpers import _scope_currency


class BenefitPlanForm(TenantModelForm):
    class Meta:
        model = BenefitPlan
        fields = ["name", "plan_type", "provider", "is_flex_credit_eligible", "flex_credit_amount",
                  "employer_cost_monthly", "employee_cost_monthly", "currency", "coverage_tier_options",
                  "enrollment_window_start", "enrollment_window_end", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, name): Django's validate_unique skips it (tenant is excluded from the
        # form), so guard it here — otherwise a duplicate name 500s on save instead of a friendly error.
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = BenefitPlan.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A benefit plan with this name already exists.")
        for f in ("flex_credit_amount", "employer_cost_monthly", "employee_cost_monthly"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        start, end = cleaned.get("enrollment_window_start"), cleaned.get("enrollment_window_end")
        if start and end and end < start:
            self.add_error("enrollment_window_end", "Window end cannot be before the start.")
        return cleaned
