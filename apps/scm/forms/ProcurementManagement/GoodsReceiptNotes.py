"""SCM 4.1 Procurement Management — GoodsReceiptNotes forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _scope_to_parent
from apps.scm.models import (
    GoodsReceiptNote,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)


class GoodsReceiptNoteForm(TenantModelForm):
    class Meta:
        model = GoodsReceiptNote
        # `status` EXCLUDED — advances via the receive/cancel actions. `match_status`/`match_notes`
        # are derived by recompute_match(). `received_by` is set to request.user on create.
        fields = ["purchase_order", "receipt_date", "delivery_note_ref", "bill", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # PurchaseOrder and accounting.Bill are both tenant-scoped, so the base class scoped them.
        # Narrow the PO list further to orders that can actually still receive goods — but keep the
        # current value selectable when editing, or the form would silently drop it.
        if "purchase_order" in self.fields and self.tenant is not None:
            qs = PurchaseOrder.objects.filter(
                tenant=self.tenant, status__in=PurchaseOrder.RECEIVABLE_STATUSES,
            )
            current = getattr(self.instance, "purchase_order_id", None)
            if current:
                qs = PurchaseOrder.objects.filter(tenant=self.tenant).filter(
                    Q(status__in=PurchaseOrder.RECEIVABLE_STATUSES) | Q(pk=current)
                )
            self.fields["purchase_order"].queryset = qs.select_related("vendor")


class GoodsReceiptLineForm(TenantModelForm):
    class Meta:
        model = GoodsReceiptLine
        fields = ["po_line", "quantity_received", "quantity_rejected", "rejection_reason", "notes"]

    def __init__(self, *args, purchase_order=None, **kwargs):
        super().__init__(*args, **kwargs)
        # PurchaseOrderLine has NO tenant field, so TenantModelForm cannot scope this dropdown.
        # Restrict it to the receipt's own order — otherwise the select would list every tenant's
        # order lines and a POST could book a receipt against someone else's PO.
        _scope_to_parent(
            self, "po_line",
            purchase_order.lines.all() if purchase_order is not None else PurchaseOrderLine.objects.none(),
        )

    def clean(self):
        cleaned = super().clean()
        received = cleaned.get("quantity_received") or 0
        rejected = cleaned.get("quantity_rejected") or 0
        if rejected and not cleaned.get("rejection_reason"):
            self.add_error("rejection_reason", "Give a reason when rejecting a quantity.")
        if not received and not rejected and cleaned.get("po_line"):
            self.add_error("quantity_received", "Record a received or rejected quantity.")
        return cleaned


class BaseGoodsReceiptLineFormSet(forms.BaseInlineFormSet):
    """Threads the parent purchase order down to each line form so ``po_line`` can be scoped."""

    def __init__(self, *args, purchase_order=None, **kwargs):
        self.purchase_order = purchase_order
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["purchase_order"] = self.purchase_order
        return kwargs


GoodsReceiptLineFormSet = inlineformset_factory(
    GoodsReceiptNote, GoodsReceiptLine, form=GoodsReceiptLineForm,
    formset=BaseGoodsReceiptLineFormSet, extra=2, can_delete=True,
)
