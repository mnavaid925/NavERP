"""Procurement 6.4 Vendor Management — VendorInvoiceSubmission forms.

The submission form is SUPPLIER-facing (rendered by the vendor portal views, which pin
``tenant``, ``supplier`` and ``submitted_by`` server-side); staff never create or edit a
submission, they only review it — hence the separate bare review-note form.
"""
from django import forms

from apps.procurement.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.procurement.models import VendorInvoiceSubmission
from apps.scm.models import PurchaseOrder


class VendorInvoiceSubmissionForm(TenantUniqueMixin, TenantModelForm):
    """The supplier-facing submission form. Pass supplier= when constructing (view does);
    the PO dropdown narrows to that supplier's own orders."""

    class Meta:
        model = VendorInvoiceSubmission
        fields = ["purchase_order", "invoice_ref", "invoice_date", "amount", "note"]
        widgets = {"invoice_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.supplier = supplier
        if supplier is not None:
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(
                vendor=supplier).order_by("-order_date", "-id")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["purchase_order"])
        # Crafted-POST guard: a PO chosen from outside MY supplier list is refused even if the
        # narrowed queryset never offered it (narrowing is UX, not authorization).
        po = cleaned.get("purchase_order")
        sup = self.supplier
        if po is not None and sup is not None and po.vendor_id != sup.pk:
            self.add_error("purchase_order", "That PO belongs to a different supplier.")
        return cleaned


class SubmissionReviewForm(forms.Form):
    """Note captured on accept/reject (optional on accept, encouraged on reject)."""

    review_note = forms.CharField(
        required=False, max_length=2000, label="Review note",
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}))
