"""Model tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- Per-tenant sequential/unique auto-numbers (PR-/RFQ-/QT-/PO-/GRN-).
- __str__ representations.
- Derived money (line_total / estimated_total / subtotal-tax-total / quote total) and
  that PurchaseOrderLine.received_quantity() excludes cancelled receipts.
- Status-derived properties (is_editable / is_closed / approval_tier / needs_elevated_approval).
- The three-way match (GoodsReceiptNote.recompute_match) — the module's most important
  logic, including the NET-vs-tax regression.
- PurchaseRequisition.budget_check() — including the same-GL-account regression.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ Auto-numbering
class TestAutoNumbering:
    def test_requisition_numbers_sequential_per_tenant(self, tenant_a, tenant_b):
        from apps.scm.models import PurchaseRequisition
        r1 = PurchaseRequisition.objects.create(tenant=tenant_a, title="One")
        r2 = PurchaseRequisition.objects.create(tenant=tenant_a, title="Two")
        r3 = PurchaseRequisition.objects.create(tenant=tenant_b, title="Globex one")
        assert r1.number == "PR-00001"
        assert r2.number == "PR-00002"
        assert r3.number == "PR-00001"  # separate per-tenant sequence

    def test_requisition_number_unique_together(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        r1 = PurchaseRequisition.objects.create(tenant=tenant_a, title="One")
        with pytest.raises(IntegrityError):
            PurchaseRequisition.objects.create(tenant=tenant_a, title="Dup", number=r1.number)

    def test_rfq_numbers_prefixed_rfq(self, tenant_a):
        from apps.scm.models import RFQ
        rfq = RFQ.objects.create(tenant=tenant_a, title="First RFQ")
        assert rfq.number == "RFQ-00001"

    def test_quote_numbers_prefixed_qt(self, tenant_a, rfq_sent_a, supplier_a):
        from apps.scm.models import RFQQuote
        q1 = RFQQuote.objects.create(tenant=tenant_a, rfq=rfq_sent_a, party=supplier_a)
        q2 = RFQQuote.objects.create(tenant=tenant_a, rfq=rfq_sent_a, party=supplier_a)
        assert q1.number == "QT-00001"
        assert q2.number == "QT-00002"

    def test_purchase_order_numbers_prefixed_po(self, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a)
        assert po.number == "PO-00001"

    def test_goods_receipt_numbers_prefixed_grn(self, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a, receipt_date=datetime.date(2026, 1, 10),
        )
        assert grn.number == "GRN-00001"

    def test_purchase_order_number_unique_together(self, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a)
        with pytest.raises(IntegrityError):
            PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, number=po.number)


# ================================================================ __str__
class TestStrRepresentations:
    def test_requisition_str(self, requisition_a):
        assert requisition_a.number in str(requisition_a)
        assert "Office supplies" in str(requisition_a)

    def test_requisition_line_str(self, requisition_a):
        line = requisition_a.lines.first()
        assert "Printer paper" in str(line)

    def test_rfq_str(self, rfq_a):
        assert rfq_a.number in str(rfq_a)

    def test_rfq_line_str(self, rfq_a):
        line = rfq_a.lines.first()
        assert "Printer paper" in str(line)

    def test_rfq_vendor_str(self, tenant_a, rfq_sent_a, supplier_a):
        invite = rfq_sent_a.invited_vendors.first()
        assert str(supplier_a) in str(invite)

    def test_rfq_quote_str(self, quote_a, supplier_a):
        assert quote_a.number in str(quote_a)
        assert str(supplier_a) in str(quote_a)

    def test_purchase_order_str(self, purchase_order_a, supplier_a):
        assert purchase_order_a.number in str(purchase_order_a)
        assert str(supplier_a) in str(purchase_order_a)

    def test_purchase_order_line_str(self, purchase_order_a):
        line = purchase_order_a.lines.first()
        assert "Printer paper" in str(line)

    def test_goods_receipt_str(self, goods_receipt_a):
        assert goods_receipt_a.number in str(goods_receipt_a)

    def test_goods_receipt_line_str(self, goods_receipt_a):
        line = goods_receipt_a.lines.first()
        assert str(line.po_line_id) in str(line)


# ================================================================ Status defaults + derived properties
class TestPurchaseRequisitionProperties:
    def test_default_status_is_draft(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="x")
        assert req.status == "draft"

    def test_is_editable_true_for_draft_and_pending(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        for status in ("draft", "pending_approval"):
            req = PurchaseRequisition(tenant=tenant_a, title="x", status=status)
            assert req.is_editable is True

    def test_is_editable_false_for_approved(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition(tenant=tenant_a, title="x", status="approved")
        assert req.is_editable is False

    def test_approval_tier_standard_under_1000(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition(tenant=tenant_a, title="x", estimated_total=Decimal("500.00"))
        code, label = req.approval_tier()
        assert code == "standard"
        assert req.needs_elevated_approval() is False

    def test_approval_tier_manager_between_1000_and_10000(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition(tenant=tenant_a, title="x", estimated_total=Decimal("5000.00"))
        code, _ = req.approval_tier()
        assert code == "manager"
        assert req.needs_elevated_approval() is True

    def test_approval_tier_executive_over_10000(self, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition(tenant=tenant_a, title="x", estimated_total=Decimal("50000.00"))
        code, _ = req.approval_tier()
        assert code == "executive"
        assert req.needs_elevated_approval() is True

    def test_recalc_totals_sums_lines(self, requisition_a):
        assert requisition_a.estimated_total == Decimal("150.00")

    def test_recalc_totals_recovers_from_tampering(self, requisition_a):
        """estimated_total is editable=False (not on the ModelForm); direct tampering is
        wiped out the next time recalc_totals() runs off the real lines."""
        requisition_a.estimated_total = Decimal("999999.00")
        requisition_a.save(update_fields=["estimated_total"])
        requisition_a.recalc_totals()
        assert requisition_a.estimated_total == Decimal("150.00")


class TestPurchaseOrderProperties:
    def test_is_editable_true_for_draft_and_pending(self, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        for status in ("draft", "pending_approval"):
            po = PurchaseOrder(tenant=tenant_a, vendor=supplier_a, status=status)
            assert po.is_editable is True

    def test_is_editable_false_once_sent(self, purchase_order_a):
        purchase_order_a.status = "sent"
        assert purchase_order_a.is_editable is False

    def test_is_closed_true_for_cancelled_and_closed(self, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        for status in ("cancelled", "closed"):
            po = PurchaseOrder(tenant=tenant_a, vendor=supplier_a, status=status)
            assert po.is_closed is True

    def test_recalc_totals_includes_tax(self, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder, PurchaseOrderLine
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        PurchaseOrderLine.objects.create(
            purchase_order=po, item_description="Widget", quantity=Decimal("2"),
            unit_price=Decimal("100.00"), tax_rate_pct=Decimal("10.00"),
        )
        po.recalc_totals()
        assert po.subtotal == Decimal("200.00")
        assert po.tax_total == Decimal("20.00")
        assert po.total == Decimal("220.00")

    def test_received_by_line_aggregates_across_receipts(self, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()
        grn1 = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn1, po_line=line, quantity_received=Decimal("4"))
        grn2 = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 11), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn2, po_line=line, quantity_received=Decimal("3"))
        assert purchase_order_a.received_by_line() == {line.pk: Decimal("7")}

    def test_received_quantity_excludes_cancelled_receipts(self, tenant_a, purchase_order_a):
        """Regression guard: PurchaseOrderLine.received_quantity() must ignore any
        GoodsReceiptLine whose parent GRN is cancelled (SCM PurchaseOrders.py)."""
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine, PurchaseOrderLine
        line = purchase_order_a.lines.first()
        grn1 = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn1, po_line=line, quantity_received=Decimal("4"))
        grn2 = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 11), status="cancelled",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn2, po_line=line, quantity_received=Decimal("6"))

        fresh = PurchaseOrderLine.objects.get(pk=line.pk)
        assert fresh.received_quantity() == Decimal("4")
        assert fresh.outstanding_quantity() == Decimal("6")  # 10 ordered - 4 received


class TestRFQProperties:
    def test_is_editable_true_for_draft_and_sent(self, tenant_a):
        from apps.scm.models import RFQ
        for status in ("draft", "sent"):
            rfq = RFQ(tenant=tenant_a, title="x", status=status)
            assert rfq.is_editable is True

    def test_is_editable_false_once_awarded(self, rfq_sent_a):
        rfq_sent_a.status = "awarded"
        assert rfq_sent_a.is_editable is False

    def test_awarded_quote_returns_none_before_award(self, rfq_sent_a, quote_a):
        assert rfq_sent_a.awarded_quote() is None

    def test_awarded_quote_returns_the_awarded_row(self, rfq_sent_a, quote_a):
        quote_a.status = "awarded"
        quote_a.save(update_fields=["status"])
        assert rfq_sent_a.awarded_quote() == quote_a


class TestGoodsReceiptLineValidation:
    def test_rejection_reason_required_when_rejecting(self, goods_receipt_a):
        line = goods_receipt_a.lines.first()
        line.quantity_rejected = Decimal("1")
        line.rejection_reason = ""
        with pytest.raises(ValidationError):
            line.full_clean()

    def test_rejection_reason_not_required_when_not_rejecting(self, goods_receipt_a):
        line = goods_receipt_a.lines.first()
        line.quantity_rejected = Decimal("0")
        line.rejection_reason = ""
        line.full_clean()  # must not raise


# ================================================================ Three-way match (priority)
class TestThreeWayMatch:
    """GoodsReceiptNote.recompute_match — verdict precedence + the NET-vs-tax regression."""

    def test_no_bill_not_matched(self, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
        assert grn.recompute_match() == "not_matched"
        assert grn.match_status == "not_matched"

    def test_within_tolerance_and_fully_received_matched(self, tenant_a, purchase_order_a, bill_a):
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received", bill=bill_a,
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
        assert grn.recompute_match() == "matched"

    def test_price_beyond_tolerance_price_variance(self, tenant_a, purchase_order_a, supplier_a, usd):
        from apps.accounting.models import Bill, BillLine
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()  # ordered 10 x $15.00 = $150 net
        bill = Bill.objects.create(
            tenant=tenant_a, party=supplier_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        BillLine.objects.create(
            bill=bill, description="Printer paper", quantity=Decimal("10"), unit_price=Decimal("20.00"),
        )  # billed net = $200, ~33% over the $150 received value
        bill.recalc_totals()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received", bill=bill,
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
        assert grn.recompute_match() == "price_variance"

    def test_short_receipt_quantity_variance(self, tenant_a, purchase_order_a, supplier_a, usd):
        from apps.accounting.models import Bill, BillLine
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()  # ordered 10
        bill = Bill.objects.create(
            tenant=tenant_a, party=supplier_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        BillLine.objects.create(
            bill=bill, description="Printer paper", quantity=Decimal("6"), unit_price=Decimal("15.00"),
        )  # billed net = $90 — matches the (short) received value exactly
        bill.recalc_totals()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received", bill=bill,
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("6"))
        assert grn.recompute_match() == "quantity_variance"

    def test_over_received_wins_over_price_variance(self, tenant_a, purchase_order_a, supplier_a, usd):
        """Precedence: an over-receipt is reported even when there is ALSO a large price
        gap on the bill — accepting un-ordered goods is the more serious finding."""
        from apps.accounting.models import Bill, BillLine
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()  # ordered 10
        bill = Bill.objects.create(
            tenant=tenant_a, party=supplier_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        BillLine.objects.create(
            bill=bill, description="Printer paper", quantity=Decimal("1"), unit_price=Decimal("500.00"),
        )  # wildly off price, on top of the over-receipt
        bill.recalc_totals()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received", bill=bill,
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("12"))
        assert grn.recompute_match() == "over_received"

    def test_taxed_bill_still_matches_on_net_value(self, tenant_a, purchase_order_a, supplier_a, usd):
        """CRITICAL regression: received_value() is ex-tax and billed_value() uses
        bill.subtotal (also ex-tax). A taxed bill whose NET value matches must still read
        'matched' — comparing against bill.total instead would flag every taxed bill as a
        price variance equal to its own tax rate. See GoodsReceiptNotes.py billed_value().
        """
        from apps.accounting.models import Bill, BillLine
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
        line = purchase_order_a.lines.first()  # 10 x $15.00 = $150 net
        bill = Bill.objects.create(
            tenant=tenant_a, party=supplier_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        BillLine.objects.create(
            bill=bill, description="Printer paper", quantity=Decimal("10"), unit_price=Decimal("15.00"),
            tax_rate_pct=Decimal("10.00"),
        )
        bill.recalc_totals()
        assert bill.subtotal == Decimal("150.00")
        assert bill.tax_total == Decimal("15.00")
        assert bill.total == Decimal("165.00")  # comparing against THIS would wrongly read as a variance

        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received", bill=bill,
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
        assert grn.recompute_match() == "matched"


# ================================================================ Budget check (priority)
class TestBudgetCheck:
    def test_no_budget_returns_none(self, tenant_a):
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="No budget", status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="x", quantity=1, estimated_unit_price=Decimal("10.00"),
        )
        assert req.budget_check() is None

    def test_no_costed_lines_returns_none(self, tenant_a, budget_a):
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="Uncosted", budget=budget_a, status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="x", quantity=1, estimated_unit_price=Decimal("10.00"),
        )  # no gl_account set
        assert req.budget_check() is None

    def test_committed_only_counts_same_gl_account(self, tenant_a, budget_a, gl_expense, gl_expense_2):
        """CRITICAL regression: an approved requisition's spend on a DIFFERENT gl_account
        must not inflate `committed` for a requisition costed against gl_expense — summing
        every other requisition's whole estimated_total regardless of account produces a
        phantom overrun on any budget that funds more than one account."""
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

        other_req = PurchaseRequisition.objects.create(
            tenant=tenant_a, title="Laptops", budget=budget_a, status="approved",
        )
        PurchaseRequisitionLine.objects.create(
            requisition=other_req, item_description="Laptops", quantity=1,
            estimated_unit_price=Decimal("4000.00"), gl_account=gl_expense_2,
        )
        other_req.recalc_totals()

        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="Paper", budget=budget_a, status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="Paper", quantity=1,
            estimated_unit_price=Decimal("2000.00"), gl_account=gl_expense,
        )
        req.recalc_totals()

        check = req.budget_check()
        assert check["budgeted"] == Decimal("10000.00")   # only the gl_expense budget line
        assert check["committed"] == Decimal("0.00")       # other_req's spend is on a DIFFERENT account
        assert check["requested"] == Decimal("2000.00")
        assert check["remaining"] == Decimal("8000.00")
        assert check["over_budget"] is False

    def test_committed_counts_other_requisitions_on_the_same_gl_account(self, tenant_a, budget_a, gl_expense):
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

        other_req = PurchaseRequisition.objects.create(
            tenant=tenant_a, title="Other paper buy", budget=budget_a, status="approved",
        )
        PurchaseRequisitionLine.objects.create(
            requisition=other_req, item_description="Paper", quantity=1,
            estimated_unit_price=Decimal("3000.00"), gl_account=gl_expense,
        )
        other_req.recalc_totals()

        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="More paper", budget=budget_a, status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="Paper", quantity=1,
            estimated_unit_price=Decimal("2000.00"), gl_account=gl_expense,
        )
        req.recalc_totals()

        check = req.budget_check()
        assert check["committed"] == Decimal("3000.00")
        assert check["remaining"] == Decimal("5000.00")  # 10000 - 3000 - 2000

    def test_committed_excludes_non_committed_statuses(self, tenant_a, budget_a, gl_expense):
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
        draft_other = PurchaseRequisition.objects.create(
            tenant=tenant_a, title="Still draft", budget=budget_a, status="draft",
        )
        PurchaseRequisitionLine.objects.create(
            requisition=draft_other, item_description="x", quantity=1,
            estimated_unit_price=Decimal("9000.00"), gl_account=gl_expense,
        )
        draft_other.recalc_totals()

        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="y", budget=budget_a, status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="y", quantity=1,
            estimated_unit_price=Decimal("500.00"), gl_account=gl_expense,
        )
        req.recalc_totals()

        check = req.budget_check()
        assert check["committed"] == Decimal("0.00")

    def test_over_budget_true_when_remaining_negative(self, tenant_a, budget_a, gl_expense):
        from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="Big spend", budget=budget_a, status="draft")
        PurchaseRequisitionLine.objects.create(
            requisition=req, item_description="Server racks", quantity=1,
            estimated_unit_price=Decimal("15000.00"), gl_account=gl_expense,
        )
        req.recalc_totals()
        check = req.budget_check()
        assert check["remaining"] < 0
        assert check["over_budget"] is True
