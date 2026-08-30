"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoiceLine form.

One form, used twice: standalone (add / edit one line from the page) and as the inline formset
row inside ``SupplierInvoiceFormSet`` on the header page. Both paths pass ``tenant=`` — the
formset via ``form_kwargs``, the standalone views directly.

**No ``TenantUniqueMixin``:** the child carries no ``tenant`` column to stamp, and it has no
unique-together to repair. ``TenantModelForm`` is still the base because three of its dropdowns
(``item``, ``gl_account``, ``tax_code``) point at tenant-scoped models it narrows for free.

**The two dropdowns it must narrow itself.** ``scm.PurchaseOrderLine`` and
``scm.GoodsReceiptLine`` are plain models with NO tenant column, so ``TenantModelForm`` cannot
scope them and ``_reject_foreign`` cannot check them — they are narrowed through their own
headers here and re-checked against that header in ``clean()``. A narrowed ``<select>`` is UX;
the check is the boundary.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantModelForm, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly — a
# ``from apps.procurement.models import X`` is a star-import cycle until the Integrator wires the
# sub-package, and it would 500 at URLconf import.
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.scm.models import GoodsReceiptLine, PurchaseOrderLine


class SupplierInvoiceLineForm(TenantModelForm):
    """One invoiced line.

    ``line_total`` and ``matched_qty`` are absent because they are ``editable=False`` — derived
    in ``save()`` and by ``run_match()`` respectively, never keyed by a person.
    """

    class Meta:
        model = SupplierInvoiceLine
        fields = ["po_line", "receipt_line", "item", "description", "sku_hint", "uom_hint",
                  "quantity", "unit_price", "tax_rate_pct", "gl_account", "tax_code"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        # ``invoice_id`` (not ``self.instance.invoice`` — an extra formset row has no header yet
        # and touching the accessor there raises RelatedObjectDoesNotExist).
        invoice_id = getattr(self.instance, "invoice_id", None)

        orders = PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)
        if invoice_id:
            # Once the header names an order, only that order's lines are meaningful — anything
            # else would be matched against the wrong prices. Left wide when the invoice is
            # PO-less, which is exactly the non-PO invoice case.
            order_id = self.instance.invoice.purchase_order_id
            if order_id:
                orders = orders.filter(purchase_order_id=order_id)
        self.fields["po_line"].queryset = orders.select_related("purchase_order").order_by("id")

        receipts = GoodsReceiptLine.objects.filter(goods_receipt__tenant=tenant)
        if getattr(self.instance, "po_line_id", None):
            # A receipt line can only be matched against the ordered line it was booked against.
            receipts = receipts.filter(po_line_id=self.instance.po_line_id)
        self.fields["receipt_line"].queryset = (
            receipts.select_related("goods_receipt", "po_line").order_by("id"))

        # item / gl_account / tax_code are already tenant-narrowed by TenantModelForm — models
        # that carry a ``tenant`` column are its job, and re-filtering here would add nothing.

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "gl_account", "tax_code"])

        tenant_id = self.tenant.pk if self.tenant is not None else None

        # The two tenant-less children, checked through their OWN headers — the only place a
        # tenant can be read off them.
        po_line = cleaned.get("po_line")
        if po_line is not None and tenant_id and po_line.purchase_order.tenant_id != tenant_id:
            self.add_error("po_line", "That record belongs to another workspace.")
        receipt_line = cleaned.get("receipt_line")
        if receipt_line is not None and tenant_id and receipt_line.goods_receipt.tenant_id != tenant_id:
            self.add_error("receipt_line", "That record belongs to another workspace.")

        return cleaned
