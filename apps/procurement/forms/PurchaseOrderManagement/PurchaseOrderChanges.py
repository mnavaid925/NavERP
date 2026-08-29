"""Procurement 6.10 Purchase Order Management — PurchaseOrderChange forms.

The request form captures the PROPOSED change (header fields + a line-change formset); the
decide form captures only the reason — the same shape 6.2 established for requisition
amendments, pointed at the dispatched-order window of the PO lifecycle instead.
"""
from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin
from apps.procurement.models import PurchaseOrderChange, PurchaseOrderChangeLine


class PurchaseOrderChangeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = PurchaseOrderChange
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save(); ``status``
        # advances through approve/reject; ``requested_by``/``decided_by``/``decided_at``/
        # ``applied_at``/``decision_note`` are system-set by those same actions;
        # ``purchase_order`` is pinned by the URL in the view (never a choosable field).
        fields = ["change_type", "reason", "new_expected_date", "new_notes"]

    def clean(self):
        cleaned = super().clean()
        # A cancellation carries no proposed changes — mirror the model's rule at form level so
        # the user sees it as a field error instead of a 500 from full_clean().
        if cleaned.get("change_type") == "cancel":
            for field in ("new_expected_date", "new_notes"):
                if cleaned.get(field):
                    self.add_error(field, "A cancellation does not carry proposed changes.")
        return cleaned


class PurchaseOrderChangeLineForm(TenantModelForm):
    class Meta:
        model = PurchaseOrderChangeLine
        fields = ["action", "target_line", "item_description", "sku_hint", "uom_hint",
                  "quantity", "unit_price", "tax_rate_pct"]


class BasePurchaseOrderChangeLineFormSet(forms.BaseInlineFormSet):
    """Scopes the ``target_line`` dropdown to THIS change's order and validates each row.

    The queryset narrowing happens here rather than per-form because the parent order is only
    known once the formset has its instance; the crafted-POST re-check still matters (a hand-
    edited POST can carry any line pk), so ``clean()`` verifies every chosen target actually
    belongs to the amended order.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        order = getattr(self.instance, "purchase_order", None)
        if order is not None:
            for form in self.forms:
                if "target_line" in form.fields:
                    form.fields["target_line"].queryset = order.lines.all()

    def clean(self):
        super().clean()
        order = getattr(self.instance, "purchase_order", None)
        if order is None:
            return
        seen_targets = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            data = form.cleaned_data
            if data.get("DELETE"):
                continue  # a row being dropped proposes nothing — it must not block its twin
            target = data.get("target_line")
            if target is not None:
                if target.purchase_order_id != order.pk:
                    form.add_error("target_line",
                                   "That line belongs to a different purchase order.")
                elif target in seen_targets:
                    # Two live rows against one line would apply in form order and silently keep
                    # only the last (or double-delete) — refuse the ambiguity instead.
                    form.add_error("target_line", "This line is targeted by more than one row.")
                seen_targets.append(target)


PurchaseOrderChangeLineFormSet = inlineformset_factory(
    PurchaseOrderChange, PurchaseOrderChangeLine, form=PurchaseOrderChangeLineForm,
    # max_num caps a crafted management form at a sane row count — each accepted row becomes a
    # line write on approval.
    formset=BasePurchaseOrderChangeLineFormSet, extra=1, can_delete=True, max_num=25,
    validate_max=True,
)


class ChangeOrderDecisionForm(forms.Form):
    """Reason captured when approving or rejecting a change order (optional on approve)."""

    decision_note = forms.CharField(required=False, max_length=2000,
                                    widget=forms.Textarea(attrs={"class": "form-textarea",
                                                                 "rows": 2}),
                                    help_text="Recorded against the decision")


def _supplier_parties(tenant):
    """Parties this workspace can buy from — local mirror of scm's helper (peer apps don't
    import each other's internals). ``core.PartyRole`` distinguishes ``supplier`` from
    ``vendor``; BOTH are accepted so the dropdown never hides half the counterparties."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct()


class GeneratePOForm(forms.Form):
    """The one decision drafting a PO genuinely needs from the buyer: WHICH supplier.

    Everything else derivable comes straight off the requisition (currency, ship-to org unit,
    expected date falls back to required-by / earliest line needed-by inside the generator) so
    the form stays a single honest question instead of a re-typing exercise.
    """

    vendor = forms.ModelChoiceField(
        label="Supplier",
        queryset=_supplier_parties(None),  # narrowed to the workspace in __init__
        help_text="The order is issued to this party once submitted and approved.",
    )
    expected_date = forms.DateField(
        label="Expected delivery date", required=False,
        help_text="Blank = requisition required-by, else the earliest line needed-by date.",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = _supplier_parties(tenant)
