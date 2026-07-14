"""CRM 1.7 Finance & Billing Management — DealInvoices forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    DealInvoice,
)


class DealInvoiceForm(TenantModelForm):
    """1.7 Invoicing wrapper. The conversion action (``dealinvoice_from_quote``) is the primary
    create path; this manual form links an EXISTING ``accounting.Invoice`` to a deal. ``invoice``
    is editable=False on the model, so it isn't a ModelForm field by default — it's declared here
    explicitly and offered only on create (popped on edit so the link can't be re-pointed)."""

    # Safe default: empty queryset. The base TenantModelForm FILTERS the queryset (it doesn't
    # rebuild it from all()), so a none() default stays empty unless we explicitly scope it below
    # for a real tenant — defense-in-depth so the field is never all-tenant (security-review).
    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(), required=False,
        help_text="Optionally link an existing Accounting invoice. (Tip: use Convert-to-Invoice "
                  "on an accepted quote to generate one automatically.)")

    class Meta:
        model = DealInvoice
        fields = ["opportunity", "quote", "account", "recurring_invoice", "notes"]

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)  # base auto-scopes the Meta FK dropdowns to the tenant
        if editing:
            self.fields.pop("invoice", None)
        elif self.tenant is not None:
            self.fields["invoice"].queryset = Invoice.objects.filter(tenant=self.tenant)
