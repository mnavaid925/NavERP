"""SCM 4.1 Procurement Management — RFQ forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _scope_to_parent, _supplier_parties
from apps.scm.models import (
    RFQ,
    RFQLine,
    RFQVendor,
    RFQQuote,
    RFQQuoteLine,
)


class RFQForm(TenantModelForm):
    class Meta:
        model = RFQ
        # `status` EXCLUDED — advances via the send/close/award actions.
        fields = ["title", "requisition", "currency", "issue_date", "response_due", "terms", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        # `requisition` targets a tenant-scoped model, so the base class already scoped it.


class RFQLineForm(TenantModelForm):
    class Meta:
        model = RFQLine
        fields = ["item_description", "sku_hint", "uom_hint", "quantity", "specification"]


class BaseRFQLineFormSet(forms.BaseInlineFormSet):
    """Refuses to remove an RFQ line that a supplier has already priced.

    ``RFQQuoteLine.rfq_line`` is CASCADE and an RFQ stays editable while ``sent`` — which is exactly
    the window in which quotes arrive. Without this guard, removing a line would silently destroy
    submitted supplier pricing AND leave the owning quote's cached ``total`` overstated, corrupting
    the comparison matrix and the award decision. Deleting a priced line is not a thing a buyer
    should be able to do quietly; re-issue the RFQ instead.
    """

    def clean(self):
        super().clean()
        blocked = [
            form.instance.item_description
            for form in self.forms
            if form.instance.pk
            and self._should_delete_form(form)
            and form.instance.quote_lines.exists()
        ]
        if blocked:
            raise forms.ValidationError(
                "Suppliers have already quoted these lines, so they cannot be removed: "
                f"{', '.join(blocked)}. Cancel this RFQ and re-issue it instead."
            )


RFQLineFormSet = inlineformset_factory(
    RFQ, RFQLine, form=RFQLineForm, formset=BaseRFQLineFormSet, extra=2, can_delete=True,
)


class RFQVendorForm(TenantModelForm):
    """Invite one supplier to quote."""

    class Meta:
        model = RFQVendor
        fields = ["party", "contact_note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)


RFQVendorFormSet = inlineformset_factory(
    RFQ, RFQVendor, form=RFQVendorForm, extra=2, can_delete=True,
)


class RFQQuoteForm(TenantModelForm):
    """A supplier's quote against an RFQ. The parent RFQ is set by the view, not the form."""

    class Meta:
        model = RFQQuote
        # `status` EXCLUDED — advances via the shortlist/award actions. `total` is derived.
        fields = ["party", "vendor_reference", "received_date", "valid_until", "lead_time_days",
                  "payment_terms", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)


class RFQQuoteLineForm(TenantModelForm):
    class Meta:
        model = RFQQuoteLine
        fields = ["rfq_line", "quantity", "unit_price", "lead_time_days", "note"]

    def __init__(self, *args, rfq=None, **kwargs):
        super().__init__(*args, **kwargs)
        # RFQLine has NO tenant field, so TenantModelForm cannot scope this dropdown. Point it at
        # the parent RFQ's lines only — falling back to none() rather than the unscoped default.
        _scope_to_parent(self, "rfq_line",
                         rfq.lines.all() if rfq is not None else RFQLine.objects.none())


class BaseRFQQuoteLineFormSet(forms.BaseInlineFormSet):
    """Threads the parent RFQ down to each line form so ``rfq_line`` can be scoped to it."""

    def __init__(self, *args, rfq=None, **kwargs):
        self.rfq = rfq
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["rfq"] = self.rfq
        return kwargs


RFQQuoteLineFormSet = inlineformset_factory(
    RFQQuote, RFQQuoteLine, form=RFQQuoteLineForm, formset=BaseRFQQuoteLineFormSet,
    extra=1, can_delete=True,
)
