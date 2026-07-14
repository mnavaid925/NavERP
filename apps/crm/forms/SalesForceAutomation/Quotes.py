"""CRM 1.2 Sales Force Automation — Quotes forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Quote,
    QuoteLine,
)


class QuoteForm(TenantModelForm):
    class Meta:
        model = Quote
        # WARNING: status + subtotal/tax_total/total + sent_at/accepted_at are system-managed
        # (set only by recalc_totals() and the quote_send/_accept/_decline actions). Excluded so a
        # member can't forge a total, back-date a send, or self-accept a quote via POST.
        fields = ["name", "opportunity", "account", "price_book", "valid_until",
                  "currency_code", "discount_pct", "terms", "owner"]
        widgets = {"terms": forms.Textarea(attrs={"rows": 4})}


class QuoteLineForm(TenantModelForm):
    """Inline on the quote detail page; tenant/quote/order set in the view."""

    class Meta:
        model = QuoteLine
        fields = ["product", "description", "quantity", "unit_price", "discount_pct", "tax_pct"]
