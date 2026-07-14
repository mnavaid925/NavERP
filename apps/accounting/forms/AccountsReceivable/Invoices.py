"""Accounting 2.4 Accounts Receivable — Invoices forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    Invoice,
    InvoiceLine,
)


class InvoiceForm(TenantModelForm):
    class Meta:
        model = Invoice
        # `status` is EXCLUDED — it advances only via `invoice_post` (draft→sent, posts the GL) and
        # `recompute_payment_status` (→partial/paid from confirmed allocations). Letting a member set
        # it by hand bypasses GL posting (security review H1).
        fields = ["kind", "party", "payment_terms", "issue_date", "due_date", "currency", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            )


class InvoiceLineForm(TenantModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_price", "tax_rate_pct", "gl_account"]


InvoiceLineFormSet = inlineformset_factory(
    Invoice, InvoiceLine, form=InvoiceLineForm, extra=2, can_delete=True,
)
