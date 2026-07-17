"""Form tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- Mass-assignment guards: status / number / version / totals / secret-ish system fields
  are never ModelForm fields.
- Supplier scoping (_supplier_parties accepts BOTH the 'supplier' and 'vendor' PartyRole
  spellings; excludes parties with neither).
- The two formset DELETE guards that are this module's freshest regressions:
  BasePurchaseOrderLineFormSet (blocks deleting a received line) and BaseRFQLineFormSet
  (blocks deleting a quoted line).
- GoodsReceiptNoteForm's bill-vs-PO-vendor match guard.
"""
import datetime
from decimal import Decimal

import pytest

from apps.scm.tests._helpers import formset_data

pytestmark = pytest.mark.django_db


# ================================================================ Mass-assignment exclusions
class TestMassAssignmentExclusions:
    def test_requisition_form_excludes_system_fields(self):
        from apps.scm.forms import PurchaseRequisitionForm
        form = PurchaseRequisitionForm(tenant=None)
        for field in ("status", "requester", "estimated_total", "number", "approved_by",
                     "approved_at", "decision_note"):
            assert field not in form.fields

    def test_requisition_line_form_excludes_line_total(self):
        from apps.scm.forms import PurchaseRequisitionLineForm
        form = PurchaseRequisitionLineForm(tenant=None)
        assert "line_total" not in form.fields
        assert "requisition" not in form.fields

    def test_rfq_form_excludes_status(self):
        from apps.scm.forms import RFQForm
        form = RFQForm(tenant=None)
        assert "status" not in form.fields
        assert "number" not in form.fields

    def test_rfq_quote_form_excludes_status_and_total(self):
        from apps.scm.forms import RFQQuoteForm
        form = RFQQuoteForm(tenant=None)
        assert "status" not in form.fields
        assert "total" not in form.fields
        assert "number" not in form.fields
        assert "rfq" not in form.fields  # set by the view, not the form

    def test_purchaseorder_form_excludes_status_version_totals(self):
        from apps.scm.forms import PurchaseOrderForm
        form = PurchaseOrderForm(tenant=None)
        for field in ("status", "version", "amendment_reason", "subtotal", "tax_total", "total",
                     "number", "approved_by", "approved_at", "acknowledged_at",
                     "acknowledgement_note", "promised_ship_date", "cancelled_at",
                     "cancellation_reason"):
            assert field not in form.fields

    def test_purchaseorderline_form_excludes_line_total(self):
        from apps.scm.forms import PurchaseOrderLineForm
        form = PurchaseOrderLineForm(tenant=None)
        assert "line_total" not in form.fields
        assert "purchase_order" not in form.fields

    def test_goodsreceiptnote_form_excludes_status_and_match_fields(self):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(tenant=None)
        for field in ("status", "match_status", "match_notes", "received_by", "number"):
            assert field not in form.fields

    def test_goodsreceiptline_form_excludes_goods_receipt(self):
        from apps.scm.forms import GoodsReceiptLineForm
        form = GoodsReceiptLineForm(tenant=None)
        assert "goods_receipt" not in form.fields


# ================================================================ Supplier scoping
class TestSupplierScoping:
    def test_supplier_parties_accepts_both_supplier_and_vendor_roles(
        self, tenant_a, supplier_a, vendor_a,
    ):
        from apps.scm.forms._common import _supplier_parties
        pks = set(_supplier_parties(tenant_a).values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert vendor_a.pk in pks

    def test_supplier_parties_excludes_non_buy_from_parties(self, tenant_a, non_supplier_party_a):
        from apps.scm.forms._common import _supplier_parties
        pks = set(_supplier_parties(tenant_a).values_list("pk", flat=True))
        assert non_supplier_party_a.pk not in pks

    def test_supplier_parties_none_tenant_returns_empty(self):
        from apps.scm.forms._common import _supplier_parties
        assert _supplier_parties(None).count() == 0

    def test_purchaseorder_form_vendor_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import PurchaseOrderForm
        form = PurchaseOrderForm(tenant=tenant_a)
        pks = set(form.fields["vendor"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_rfqvendor_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import RFQVendorForm
        form = RFQVendorForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks


# ================================================================ Formset DELETE guards (regressions)
class TestPurchaseOrderLineFormSetDeleteGuard:
    """BasePurchaseOrderLineFormSet must refuse — not 500 — deleting a line with receipts."""

    def test_deleting_received_line_is_a_validation_error_not_a_crash(
        self, tenant_a, purchase_order_a,
    ):
        from apps.scm.forms import PurchaseOrderLineFormSet
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine, PurchaseOrderLine

        line = purchase_order_a.lines.first()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)

        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "unit_price": line.unit_price,
             "tax_rate_pct": "0", "gl_account": "", "DELETE": "on"},
        ], initial=1)
        formset = PurchaseOrderLineFormSet(data=data, instance=purchase_order_a, form_kwargs={"tenant": tenant_a})

        assert formset.is_valid() is False  # NOT a 500/ProtectedError — a clean form error
        assert any("cannot be removed" in e for e in formset.non_form_errors())
        # The line survives — the guard never called .save()/.delete().
        assert PurchaseOrderLine.objects.filter(pk=line.pk).exists()

    def test_deleting_a_line_with_no_receipts_is_allowed(self, tenant_a, purchase_order_a):
        from apps.scm.forms import PurchaseOrderLineFormSet
        line = purchase_order_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "unit_price": line.unit_price,
             "tax_rate_pct": "0", "gl_account": "", "DELETE": "on"},
        ], initial=1)
        formset = PurchaseOrderLineFormSet(data=data, instance=purchase_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True


class TestRFQLineFormSetDeleteGuard:
    """BaseRFQLineFormSet must refuse to delete a line a supplier already quoted."""

    def test_deleting_quoted_line_is_a_validation_error(self, tenant_a, rfq_sent_a, quote_a):
        from apps.scm.forms import RFQLineFormSet
        from apps.scm.models import RFQQuoteLine

        line = rfq_sent_a.lines.first()
        quote_line = quote_a.lines.get(rfq_line=line)

        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "specification": "", "DELETE": "on"},
        ], initial=1)
        formset = RFQLineFormSet(data=data, instance=rfq_sent_a, form_kwargs={"tenant": tenant_a})

        assert formset.is_valid() is False
        assert any("cannot be removed" in e for e in formset.non_form_errors())
        # The supplier's quote line survives — never CASCADE-deleted by an invalid formset.
        assert RFQQuoteLine.objects.filter(pk=quote_line.pk).exists()

    def test_deleting_an_unquoted_line_is_allowed(self, tenant_a, rfq_a):
        from apps.scm.forms import RFQLineFormSet
        line = rfq_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "specification": "", "DELETE": "on"},
        ], initial=1)
        formset = RFQLineFormSet(data=data, instance=rfq_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True


# ================================================================ GoodsReceiptNoteForm vendor/bill guard
class TestGoodsReceiptNoteFormVendorMatch:
    def test_bill_from_a_different_vendor_is_rejected(
        self, tenant_a, purchase_order_a, vendor_a, usd,
    ):
        from apps.accounting.models import Bill
        from apps.scm.forms import GoodsReceiptNoteForm

        other_bill = Bill.objects.create(
            tenant=tenant_a, party=vendor_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": other_bill.pk,
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is False
        assert "bill" in form.errors

    def test_bill_from_the_same_vendor_is_accepted(self, tenant_a, purchase_order_a, bill_a):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": bill_a.pk,
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True

    def test_no_bill_is_accepted(self, tenant_a, purchase_order_a):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": "",
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True
