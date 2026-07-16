"""HRM 3.17 Payout & Reports — Bankreconciliation forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    BankReconciliation,
    PayoutBatch,
)


class BankReconciliationForm(TenantModelForm):
    # number + matched/unmatched aggregates + reconciled_by/at are set by recompute()/the reconcile action.
    class Meta:
        model = BankReconciliation
        fields = ["batch", "statement_date", "statement_reference", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "batch" in self.fields:
            self.fields["batch"].queryset = (
                PayoutBatch.objects.filter(tenant=self.tenant).select_related("cycle").order_by("-created_at"))
