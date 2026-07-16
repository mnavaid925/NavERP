"""HRM 3.4 Employee Offboarding — Finalsettlement forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    FinalSettlement,
)


class FinalSettlementForm(TenantModelForm):
    # SECURITY: `status`, the HR/finance approval stamps, `paid_at`, and `gl_posted` are excluded —
    # advanced only by the compute / hr-approve / finance-approve / mark-paid actions. `net_payable`
    # is a derived property (no column). Earnings/deductions are editable so HR can adjust the
    # service-computed figures before approval.
    class Meta:
        model = FinalSettlement
        fields = ["case", "settlement_date",
                  "prorata_salary", "leave_encashment_days", "leave_encashment_amount",
                  "gratuity_eligible", "gratuity_amount", "bonus_amount",
                  "reimbursement_amount", "other_income",
                  "notice_recovery_amount", "loan_recovery", "asset_deduction",
                  "advance_recovery", "tax_deduction", "professional_tax", "other_deduction",
                  "notes"]

    def clean(self):
        cleaned = super().clean()
        case = cleaned.get("case")
        # One settlement per case (also DB-enforced via unique_together) — surface a friendly error
        # rather than an IntegrityError 500.
        if case and self.tenant is not None:
            dupes = FinalSettlement.objects.filter(tenant=self.tenant, case=case)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                self.add_error("case", "A settlement already exists for this separation case.")
        return cleaned
