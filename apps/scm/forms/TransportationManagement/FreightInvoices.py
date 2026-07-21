"""SCM 4.6 Transportation Management System — FreightInvoice form + charge-line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies
from apps.scm.models import FreightInvoice, FreightInvoiceLine


class FreightInvoiceForm(TenantModelForm):
    """The freight-invoice header.

    EXCLUDES `number` (auto), every derived amount (`billed_amount`/`contract_amount`/`variance_*` —
    summed from the lines), the audit/approval status fields (set by the run-audit / approve / dispute
    actions), and `bill` (the accounting hand-off, set by that action). `carrier`/`load`/`shipment`
    auto-scope to this tenant; `currency` is GLOBAL so it needs the shared scoping helper.
    """

    class Meta:
        model = FreightInvoice
        fields = ["carrier", "load", "shipment", "carrier_invoice_number", "invoice_date",
                  "due_date", "currency", "match_tolerance_pct", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


class FreightInvoiceLineForm(TenantModelForm):
    """One charge line — what the carrier billed vs. what the contract expected (the audit inputs)."""

    class Meta:
        model = FreightInvoiceLine
        fields = ["charge_type", "description", "billed_amount", "contract_amount"]


FreightInvoiceLineFormSet = inlineformset_factory(
    FreightInvoice, FreightInvoiceLine, form=FreightInvoiceLineForm, extra=1, can_delete=True,
)
