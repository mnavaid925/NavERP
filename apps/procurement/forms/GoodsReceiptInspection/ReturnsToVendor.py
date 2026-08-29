"""Procurement 6.12 Goods Receipt & Inspection — ReturnToVendor forms.

Five shapes, one per thing a user actually does:

* ``ReturnToVendorForm`` — the return header a buyer raises against a supplier.
* ``ReturnToVendorLineFormSet`` — what is physically going back, line by line.
* ``RtvShipForm`` — the despatch details, the only writer of ``shipped_on``.
* ``RtvCloseForm`` — the credit-note REFERENCE recorded when the remedy lands. It posts nothing
  to the ledger; see ``ReturnToVendor``'s class docstring.
* ``RtvCancelForm`` — a required reason, because an abandoned return with no explanation is
  indistinguishable from a mistake.

Every tenant-scoped dropdown is narrowed in ``__init__`` AND re-checked in ``clean()``: a narrowed
``<select>`` is UX, not an authorization boundary — a crafted POST carries whatever pk it likes.
``scm.GoodsReceiptLine`` and ``scm.PurchaseOrderLine`` carry NO tenant column of their own, so
their querysets are scoped through their headers (``goods_receipt__tenant`` /
``purchase_order__tenant``) — ``TenantModelForm``'s automatic narrowing cannot see them, and an
unscoped ``ModelChoiceField`` would both DISPLAY and ACCEPT another workspace's line.
"""
from django import forms
from django.db.models import Q

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import ReceiptDiscrepancy, ReturnToVendor, ReturnToVendorLine
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, PurchaseOrder, PurchaseOrderLine


def _supplier_parties(tenant):
    """Parties this workspace can buy from — a LOCAL mirror of the helper in
    ``forms/PurchaseOrderManagement/PurchaseOrderChanges.py`` (sub-modules deliberately don't
    import each other's private helpers). ``core.PartyRole`` distinguishes ``supplier`` from
    ``vendor``; BOTH are accepted so the dropdown never hides half the counterparties."""
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


class ReturnToVendorForm(TenantUniqueMixin, TenantModelForm):
    """The return header.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ReturnToVendor.clean()`` compares every chosen FK's tenant against ``self.tenant_id``,
    and without the stamp every CREATE would be falsely rejected as cross-tenant.

    EXCLUDED and why — every one of these is system-owned, and a field that reaches the form
    reaches a crafted POST:

    * ``tenant`` — stamped by the view / ``TenantUniqueMixin``, never chosen.
    * ``number`` — assigned once by ``TenantNumbered.save()``.
    * ``status`` — moved ONLY by ``authorize`` / ``mark_shipped`` / ``close`` / ``cancel``; on the
      form it would let a POST jump a draft straight to ``closed``.
    * ``shipped_on`` — stamped by ``mark_shipped()``.
    * ``authorized_by`` / ``authorized_at`` / ``closed_at`` / ``cancelled_at`` /
      ``cancellation_reason`` — verb stamps; ``authorized_by`` in particular is the signature on
      the return and must never be choosable.
    * ``created_by`` — the signed-in user, never choosable.
    * ``created_at`` / ``updated_at`` — system timestamps.

    Date widgets are NOT overridden here: ``TenantModelForm`` already swaps every ``DateField``
    to ``DateInput(type="date", class="form-input")`` and sets matching ``input_formats`` (L22).
    """

    class Meta:
        model = ReturnToVendor
        fields = [
            "vendor", "purchase_order", "goods_receipt", "discrepancy", "reason", "reason_note",
            "remedy", "supplier_rma_number", "carrier_name", "tracking_number",
            "expected_return_date", "credit_note_ref", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        self.fields["vendor"].queryset = _supplier_parties(tenant)

        if tenant is None:
            # A tenant-less user (the superuser) must never be offered another workspace's rows.
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.none()
            self.fields["goods_receipt"].queryset = GoodsReceiptNote.objects.none()
            self.fields["discrepancy"].queryset = ReceiptDiscrepancy.objects.none()
            return

        # ``PurchaseOrder.__str__`` is ``f"{number} · {vendor}"`` and ``GoodsReceiptNote`` walks
        # its own order — every rendered <option> hops one relation, so an unbounded dropdown
        # costs 1 + N queries without these select_related calls. The chained-__str__ case belongs
        # on the FORM queryset, not just on the list view's.
        self.fields["purchase_order"].queryset = (
            PurchaseOrder.objects.filter(tenant=tenant)
            .select_related("vendor").order_by("-order_date", "-id")
        )
        # A cancelled receipt never happened; returning goods against it would be meaningless —
        # EXCEPT where this return already points at one, in which case dropping it from the
        # queryset would render a <select> with no matching option and, because the field is
        # ``null=True, blank=True``, silently save ``goods_receipt = NULL`` on the next edit,
        # losing the origin link with no error. Same exemption ``ReturnToVendorLineForm`` applies
        # to a stored receipt line.
        offerable = ~Q(status="cancelled")
        if self.instance.pk and self.instance.goods_receipt_id:
            offerable |= Q(pk=self.instance.goods_receipt_id)
        self.fields["goods_receipt"].queryset = (
            GoodsReceiptNote.objects.filter(tenant=tenant).filter(offerable)
            .select_related("purchase_order").order_by("-receipt_date", "-id")
        )
        self.fields["discrepancy"].queryset = (
            ReceiptDiscrepancy.objects.filter(tenant=tenant)
            .select_related("goods_receipt").order_by("-id")
        )

    def clean(self):
        cleaned = super().clean()
        # The model's clean() checks the same tenancy, but only once ``instance.tenant`` is
        # stamped; this re-check is keyed on fields the form actually renders, so a crafted pk
        # lands as a field error the user can see rather than as a non-field 500.
        _reject_foreign(self, cleaned, ["vendor", "purchase_order", "goods_receipt",
                                        "discrepancy"])
        return cleaned


class ReturnToVendorLineForm(forms.ModelForm):
    """One returned line. A PLAIN ModelForm on purpose — ``ReturnToVendorLine`` carries no tenant
    of its own (it is scoped through its parent RTV), so ``TenantModelForm`` has nothing to
    narrow; and neither ``scm.GoodsReceiptLine`` nor ``scm.PurchaseOrderLine`` has a tenant column
    for it to find even if it did. Both querysets are therefore narrowed HERE, through their
    headers.

    ``return_to_vendor`` is excluded: it comes from the parent instance via the inline formset.
    """

    class Meta:
        model = ReturnToVendorLine
        fields = [
            "goods_receipt_line", "po_line", "item_description", "sku_hint", "uom_hint",
            "quantity_returned", "lot_number", "serial_number", "condition_note",
        ]
        widgets = {
            "goods_receipt_line": forms.Select(attrs={"class": "form-select"}),
            "po_line": forms.Select(attrs={"class": "form-select"}),
            "item_description": forms.TextInput(attrs={"class": "form-input"}),
            "sku_hint": forms.TextInput(attrs={"class": "form-input"}),
            "uom_hint": forms.TextInput(attrs={"class": "form-input"}),
            "quantity_returned": forms.NumberInput(attrs={"class": "form-input",
                                                          "step": "0.0001", "min": "0.0001"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "condition_note": forms.TextInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, receipt=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Blank copies the source line's text in ReturnToVendorLine.save() — don't demand it.
        self.fields["item_description"].required = False
        # ``quantity_returned`` carries ``default=1`` for programmatic creation, and
        # ``Field.formfield()`` copies a model default onto the FORM field's ``initial``. On an
        # EXTRA row that default is poison: ``has_changed()`` compares initial ``1`` against the
        # blank the browser posts, decides the untouched trailing row WAS edited, and Django then
        # validates it — so the page answers a row nobody filled in with a validation error. A
        # blank trailing row must stay blank, and a returned quantity is a fact to type. Existing
        # rows are unaffected: their initial comes from ``self.initial`` (model_to_dict).
        self.fields["quantity_returned"].initial = None

        if receipt is not None:
            # The header names a receipt, so only ITS lines can be returned. GoodsReceiptLine has
            # no tenant column — without this narrowing the dropdown would list (and accept)
            # every receipt line in the database.
            self.fields["goods_receipt_line"].queryset = (
                GoodsReceiptLine.objects.filter(goods_receipt=receipt)
                .select_related("goods_receipt", "po_line").order_by("id")
            )
        elif tenant is not None:
            # The header names no receipt yet, so every live receipt line in THIS workspace is
            # offerable. A cancelled receipt never happened — except where this row already
            # points at one, in which case dropping it from the queryset would turn a stored
            # value into an "invalid choice" the user cannot fix (the ASN precedent for a PO that
            # has since moved on).
            offerable = ~Q(goods_receipt__status="cancelled")
            current_id = getattr(self.instance, "goods_receipt_line_id", None)
            if current_id:
                offerable |= Q(pk=current_id)
            self.fields["goods_receipt_line"].queryset = (
                GoodsReceiptLine.objects.filter(goods_receipt__tenant=tenant)
                .filter(offerable)
                .select_related("goods_receipt", "po_line")
                .order_by("-goods_receipt_id", "id")
            )
        else:
            self.fields["goods_receipt_line"].queryset = GoodsReceiptLine.objects.none()

        if tenant is not None:
            self.fields["po_line"].queryset = (
                PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)
                .select_related("purchase_order").order_by("-purchase_order_id", "id")
            )
        else:
            self.fields["po_line"].queryset = PurchaseOrderLine.objects.none()


class BaseReturnToVendorLineFormSet(forms.BaseInlineFormSet):
    """Feeds every row the parent's tenant and receipt.

    The narrowing lives here rather than on the form because neither is knowable until the
    formset has its instance — the same reason ``BaseAsnLineFormSet`` narrows ``po_line`` from
    the parent's purchase order. ``clean()`` re-checks the result: a hand-edited POST can carry
    any line pk at all, and a line from another workspace must land as a FIELD error on the row
    that carries it, never as a saved row.
    """

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["tenant"] = getattr(self.instance, "tenant", None)
        kwargs["receipt"] = getattr(self.instance, "goods_receipt", None)
        return kwargs

    def clean(self):
        super().clean()
        tenant_id = getattr(self.instance, "tenant_id", None)
        if tenant_id is None:
            return
        header_receipt_id = getattr(self.instance, "goods_receipt_id", None)

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if self.can_delete and self._should_delete_form(form):
                # A row being dropped declares nothing — it neither collides nor blocks.
                continue

            receipt_line = form.cleaned_data.get("goods_receipt_line")
            if receipt_line is not None:
                if receipt_line.goods_receipt.tenant_id != tenant_id:
                    form.add_error("goods_receipt_line",
                                   "That record belongs to another workspace.")
                elif header_receipt_id and receipt_line.goods_receipt_id != header_receipt_id:
                    form.add_error("goods_receipt_line",
                                   "That line belongs to a different goods receipt.")

            po_line = form.cleaned_data.get("po_line")
            if po_line is not None and po_line.purchase_order.tenant_id != tenant_id:
                form.add_error("po_line", "That record belongs to another workspace.")


#: ``max_num`` caps a crafted management form at a sane row count — every accepted row is a write.
ReturnToVendorLineFormSet = inlineformset_factory(
    ReturnToVendor, ReturnToVendorLine, form=ReturnToVendorLineForm,
    formset=BaseReturnToVendorLineFormSet, extra=2, can_delete=True,
    max_num=50, validate_max=True,
)


class RtvShipForm(forms.Form):
    """Despatch details. The ONLY writer of ``shipped_on`` — the field is ``editable=False`` on
    the model for exactly that reason. Carrier and tracking are optional here: leaving them blank
    keeps whatever the header already carries rather than erasing it."""

    carrier_name = forms.CharField(
        label="Carrier", required=False, max_length=120,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    tracking_number = forms.CharField(
        required=False, max_length=64,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    shipped_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="Blank = today",
    )


class RtvCloseForm(forms.Form):
    """Close the return once the remedy lands."""

    credit_note_ref = forms.CharField(
        label="Credit note reference", required=False, max_length=64,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="Reference only — no ledger entry is created.",
    )


class RtvCancelForm(forms.Form):
    """Why the return was abandoned. Required — a cancelled RTV with no reason reads as a data
    error rather than a decision, and the supplier has usually already been told about it."""

    cancellation_reason = forms.CharField(
        label="Reason", required=True, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
