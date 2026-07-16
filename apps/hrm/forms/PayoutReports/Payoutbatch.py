"""HRM 3.17 Payout & Reports — Payoutbatch forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PayoutBatch,
    PayrollCycle,
)


# ----------------------------------------------------------------------- 3.17 Payout & Reports
class PayoutBatchForm(TenantModelForm):
    # number + all workflow/derived fields (status/generated_*/approved_*/disbursed_at) are set by the
    # generate/approve/disburse actions, never form-typed.
    class Meta:
        model = PayoutBatch
        fields = ["cycle", "bank_file_format", "source_bank_name", "source_account_last4", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "cycle" in self.fields:
            # Only LOCKED cycles can be paid out — a draft/pending/approved cycle must never appear; on
            # create, also drop cycles that already have a batch (one batch per cycle).
            qs = PayrollCycle.objects.filter(tenant=self.tenant, status="locked")
            if self.instance.pk is None:
                qs = qs.exclude(payout_batches__isnull=False)
            self.fields["cycle"].queryset = qs.order_by("-pay_date")

    def clean(self):
        # Enforce the (tenant, cycle) uniqueness at the FORM level — ModelForm.validate_unique() can't
        # (tenant is excluded + only set post-validation in crud_create), so a duplicate would otherwise
        # 500 at the DB. self.tenant is available here. Mirrors FinalSettlementForm.clean().
        cleaned = super().clean()
        cycle = cleaned.get("cycle")
        if cycle and self.tenant is not None:
            dup = PayoutBatch.objects.filter(tenant=self.tenant, cycle=cycle)
            if self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise forms.ValidationError("A payout batch already exists for this payroll cycle.")
        return cleaned
