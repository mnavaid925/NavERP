"""Accounting 2.3 Accounts Payable — Bills forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    Bill,
    BillLine,
)


class BillForm(TenantModelForm):
    class Meta:
        model = Bill
        # `status` EXCLUDED — advances via `bill_approve` (→approved) and `recompute_payment_status`
        # (→partial/paid). Not hand-settable (security review H1).
        fields = ["party", "payment_terms", "bill_date", "due_date", "currency", "document", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct()
            )


class BillLineForm(TenantModelForm):
    class Meta:
        model = BillLine
        fields = ["description", "quantity", "unit_price", "tax_rate_pct", "gl_account"]


BillLineFormSet = inlineformset_factory(
    Bill, BillLine, form=BillLineForm, extra=2, can_delete=True,
)
