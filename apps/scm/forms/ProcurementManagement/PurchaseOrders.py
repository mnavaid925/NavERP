"""SCM 4.1 Procurement Management — PurchaseOrders forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _supplier_parties
from apps.scm.models import (
    PurchaseOrder,
    PurchaseOrderLine,
)


class PurchaseOrderForm(TenantModelForm):
    class Meta:
        model = PurchaseOrder
        # EXCLUDED and why: `status` advances via approve/send/acknowledge/cancel; `version`,
        # `approved_*`, `acknowledged_*`, `cancelled_*` are system-set by those same actions; the
        # money totals are derived from lines.
        fields = ["vendor", "requisition", "quote", "currency", "payment_terms", "order_date",
                  "expected_date", "ship_to", "delivery_address", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if "vendor" in self.fields:
            self.fields["vendor"].queryset = _supplier_parties(self.tenant)
        # requisition / quote / payment_terms / ship_to all target tenant-scoped models and were
        # already scoped by TenantModelForm.


class PurchaseOrderLineForm(TenantModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["item_description", "sku_hint", "uom_hint", "quantity", "unit_price",
                  "tax_rate_pct", "gl_account"]


class BasePurchaseOrderLineFormSet(forms.BaseInlineFormSet):
    """Refuses to remove a line that goods have already been received against.

    ``GoodsReceiptLine.po_line`` is PROTECT, and the amend path is reachable precisely when the
    order is partially_received/received — so without this guard, ticking Remove on a received line
    would raise an unhandled ProtectedError (a 500) from formset.save(). Blocking it here turns that
    into a form error the buyer can act on, and is also the correct rule: you cannot un-order goods
    that have arrived.
    """

    def clean(self):
        super().clean()
        blocked = [
            form.instance.item_description
            for form in self.forms
            if form.instance.pk
            and self._should_delete_form(form)
            and form.instance.receipt_lines.exists()
        ]
        if blocked:
            raise forms.ValidationError(
                "These lines have goods receipts booked against them and cannot be removed: "
                f"{', '.join(blocked)}. Cancel the receipt first."
            )


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine, form=PurchaseOrderLineForm,
    formset=BasePurchaseOrderLineFormSet, extra=2, can_delete=True,
)


class PurchaseOrderAmendForm(forms.Form):
    """Reason captured when amending an already-approved order (the diff itself goes to AuditLog)."""

    amendment_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="Why is this order being amended?",
    )


class PurchaseOrderCancelForm(forms.Form):
    """Reason captured when cancelling an order."""

    cancellation_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="Why is this order being cancelled?",
    )


class PurchaseOrderAcknowledgeForm(forms.Form):
    """Staff-recorded vendor acknowledgement.

    Deliberately NOT a vendor-facing portal form: lesson L32 bars a staff sidebar bullet from
    pointing at a login-gated portal page, so 4.1's "Vendor Portal" bullet is served by this
    staff-side action instead. A real supplier self-service portal is deferred.
    """

    acknowledgement_note = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="What the vendor confirmed",
    )
    promised_ship_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="Ship date the vendor promised",
    )
