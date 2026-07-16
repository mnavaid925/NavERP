"""HRM 3.15 Statutory Compliance — Statutorystaterule forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    StatutoryStateRule,
)


class StatutoryStateRuleForm(TenantModelForm):
    # PT-only and LWF-only fields are all shown; model.clean() enforces which are required by scheme.
    class Meta:
        model = StatutoryStateRule
        fields = ["state", "scheme", "income_from", "income_to", "pt_monthly_amount",
                  "pt_deduction_month", "lwf_employee_contribution", "lwf_employer_contribution",
                  "lwf_periodicity", "lwf_due_month_1", "lwf_due_month_2", "registration_number",
                  "is_active", "effective_from"]

    def clean(self):
        # The model.clean() "one active LWF rule per (tenant, state)" guard can't fire on CREATE via
        # crud_create — tenant is assigned only AFTER form.is_valid(), so self.tenant_id is None at
        # model-validation time. Enforce that one case here (the form DOES have self.tenant), guarding
        # only the create path (instance.pk is None) so an edit doesn't double-report — model.clean()
        # already covers edit, where the instance carries a real tenant. Mirrors StatutoryReturnForm.clean().
        cleaned = super().clean()
        if self.instance.pk is None and self.tenant is not None:
            if cleaned.get("scheme") == "lwf" and cleaned.get("is_active") and cleaned.get("state"):
                if StatutoryStateRule.objects.filter(
                        tenant=self.tenant, state=cleaned["state"], scheme="lwf", is_active=True).exists():
                    raise forms.ValidationError(
                        "An active LWF rule already exists for this state — deactivate it first.")
        return cleaned
