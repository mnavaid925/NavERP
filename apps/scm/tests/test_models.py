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


# ================================================================================================
# SCM 4.2 Supplier Relationship Management
# ================================================================================================

# ================================================================ SRM auto-numbering
class TestSRMAutoNumbering:
    def test_scorecard_numbers_sequential_per_tenant(self, tenant_a, tenant_b, supplier_a, supplier_b):
        from apps.scm.models import SupplierScorecard
        s1 = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        s2 = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 2, 1), period_end=datetime.date(2026, 2, 28),
        )
        s3 = SupplierScorecard.objects.create(
            tenant=tenant_b, party=supplier_b,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        assert s1.number == "SCR-00001"
        assert s2.number == "SCR-00002"
        assert s3.number == "SCR-00001"  # separate per-tenant sequence

    def test_scorecard_number_unique_together(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierScorecard
        s1 = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        with pytest.raises(IntegrityError):
            SupplierScorecard.objects.create(
                tenant=tenant_a, party=supplier_a, number=s1.number,
                period_start=datetime.date(2026, 2, 1), period_end=datetime.date(2026, 2, 28),
            )

    def test_contract_numbers_prefixed_sc(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        c = SupplierContract.objects.create(tenant=tenant_a, party=supplier_a, title="Deal")
        assert c.number == "SC-00001"

    def test_contract_number_unique_together(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        c = SupplierContract.objects.create(tenant=tenant_a, party=supplier_a, title="Deal")
        with pytest.raises(IntegrityError):
            SupplierContract.objects.create(tenant=tenant_a, party=supplier_a, title="Dup", number=c.number)

    def test_catalog_numbers_prefixed_cat(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierCatalog
        cat = SupplierCatalog.objects.create(tenant=tenant_a, party=supplier_a, name="Price List")
        assert cat.number == "CAT-00001"

    def test_catalog_number_unique_together(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierCatalog
        cat = SupplierCatalog.objects.create(tenant=tenant_a, party=supplier_a, name="Price List")
        with pytest.raises(IntegrityError):
            SupplierCatalog.objects.create(tenant=tenant_a, party=supplier_a, name="Dup", number=cat.number)

    def test_risk_assessment_numbers_prefixed_sra(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
        )
        assert ra.number == "SRA-00001"

    def test_risk_assessment_number_unique_together(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
        )
        with pytest.raises(IntegrityError):
            SupplierRiskAssessment.objects.create(
                tenant=tenant_a, party=supplier_a, number=ra.number, assessment_date=datetime.date(2026, 2, 1),
            )


# ================================================================ SRM __str__
class TestSRMStrRepresentations:
    def test_supplier_profile_str(self, supplier_profile_a, supplier_a):
        assert supplier_a.name in str(supplier_profile_a)

    def test_scorecard_str(self, scorecard_a, supplier_a):
        assert scorecard_a.number in str(scorecard_a)
        assert supplier_a.name in str(scorecard_a)

    def test_contract_str(self, contract_a):
        assert contract_a.number in str(contract_a)
        assert "Master Supply Agreement" in str(contract_a)

    def test_catalog_str(self, catalog_a):
        assert catalog_a.number in str(catalog_a)
        assert "2026 Price List" in str(catalog_a)

    def test_catalog_item_str(self, catalog_a):
        from apps.scm.models import SupplierCatalogItem
        item = SupplierCatalogItem.objects.create(
            catalog=catalog_a, item_name="Widget", unit_price=Decimal("9.99"),
        )
        assert "Widget" in str(item)
        assert "9.99" in str(item)

    def test_risk_assessment_str(self, risk_assessment_a, supplier_a):
        s = str(risk_assessment_a)
        assert risk_assessment_a.number in s
        assert supplier_a.name in s


# ================================================================ SupplierProfile due-diligence
class TestSupplierProfileDueDiligence:
    def test_progress_zero_when_nothing_checked(self, supplier_profile_a):
        assert supplier_profile_a.due_diligence_progress() == 0
        assert supplier_profile_a.due_diligence_complete is False

    def test_progress_partial(self, supplier_profile_a):
        supplier_profile_a.dd_financials_verified = True
        supplier_profile_a.dd_compliance_verified = True
        assert supplier_profile_a.due_diligence_progress() == 40  # 2/5
        assert supplier_profile_a.due_diligence_complete is False

    def test_progress_complete(self, supplier_profile_dd_a):
        assert supplier_profile_dd_a.due_diligence_progress() == 100
        assert supplier_profile_dd_a.due_diligence_complete is True

    def test_is_active_only_when_approved(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        for status in ("draft", "qualification", "due_diligence", "rejected", "suspended"):
            sp = SupplierProfile(tenant=tenant_a, party=supplier_a, onboarding_status=status)
            assert sp.is_active is False
        sp = SupplierProfile(tenant=tenant_a, party=supplier_a, onboarding_status="approved")
        assert sp.is_active is True

    def test_is_editable_true_for_draft_qualification_due_diligence(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        for status in ("draft", "qualification", "due_diligence"):
            sp = SupplierProfile(tenant=tenant_a, party=supplier_a, onboarding_status=status)
            assert sp.is_editable is True

    def test_is_editable_false_for_approved_rejected_suspended(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        for status in ("approved", "rejected", "suspended"):
            sp = SupplierProfile(tenant=tenant_a, party=supplier_a, onboarding_status=status)
            assert sp.is_editable is False

    def test_default_onboarding_status_is_draft(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        sp = SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a)
        assert sp.onboarding_status == "draft"
        assert sp.tier == "transactional"


# ================================================================ SupplierScorecard score cap (priority regression)
class TestSupplierScorecardScoreCap:
    """Regression: MaxValueValidator(100) on delivery/quality/price/responsiveness stops a
    hand-entered figure > 100 from ever landing on a saved row (SupplierScorecards.py)."""

    def test_delivery_score_above_100_fails_full_clean(self, scorecard_a):
        scorecard_a.delivery_score = Decimal("150.00")
        with pytest.raises(ValidationError):
            scorecard_a.full_clean()

    def test_negative_score_fails_full_clean(self, scorecard_a):
        scorecard_a.quality_score = Decimal("-5.00")
        with pytest.raises(ValidationError):
            scorecard_a.full_clean()

    def test_score_of_exactly_100_is_valid(self, scorecard_a):
        scorecard_a.delivery_score = Decimal("100.00")
        scorecard_a.full_clean()  # must not raise

    def test_score_of_exactly_zero_is_valid(self, scorecard_a):
        scorecard_a.responsiveness_score = Decimal("0.00")
        scorecard_a.full_clean()  # must not raise


# ================================================================ SupplierScorecard.recompute_from_signals (priority)
class TestScorecardRecomputeFromSignals:
    """Derives the four dimension scores from REAL 4.1 procurement history, not opinion."""

    def test_on_time_full_receipt_yields_delivery_100(self, tenant_a, supplier_a, usd):
        from apps.scm.models import (
            PurchaseOrder, PurchaseOrderLine, GoodsReceiptNote, GoodsReceiptLine, SupplierScorecard,
        )
        po = PurchaseOrder.objects.create(
            tenant=tenant_a, vendor=supplier_a, currency=usd, status="approved",
            order_date=datetime.date(2026, 1, 1), expected_date=datetime.date(2026, 1, 20),
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=po, item_description="Widget", quantity=Decimal("10"), unit_price=Decimal("5.00"),
        )
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=po, receipt_date=datetime.date(2026, 1, 15), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("10"))

        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        scorecard.recompute_from_signals(save=False)
        assert scorecard.delivery_score == Decimal("100.00")

    def test_rejected_quantity_drops_quality_below_100(self, tenant_a, supplier_a, usd):
        from apps.scm.models import (
            PurchaseOrder, PurchaseOrderLine, GoodsReceiptNote, GoodsReceiptLine, SupplierScorecard,
        )
        po = PurchaseOrder.objects.create(
            tenant=tenant_a, vendor=supplier_a, currency=usd, status="approved",
            order_date=datetime.date(2026, 1, 1), expected_date=datetime.date(2026, 1, 20),
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=po, item_description="Widget", quantity=Decimal("10"), unit_price=Decimal("5.00"),
        )
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=po, receipt_date=datetime.date(2026, 1, 15), status="received",
        )
        GoodsReceiptLine.objects.create(
            goods_receipt=grn, po_line=line, quantity_received=Decimal("8"),
            quantity_rejected=Decimal("2"), rejection_reason="Damaged in transit",
        )

        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        scorecard.recompute_from_signals(save=False)
        assert scorecard.quality_score == Decimal("80.00")  # 100 - (2 rejected / 10 total * 100)
        assert scorecard.quality_score < Decimal("100")

    def test_manual_override_leaves_scores_untouched(self, tenant_a, supplier_a, usd):
        """Regression: even with a perfect on-time signal sitting right there, manual_override
        must make recompute_from_signals a no-op."""
        from apps.scm.models import (
            PurchaseOrder, PurchaseOrderLine, GoodsReceiptNote, GoodsReceiptLine, SupplierScorecard,
        )
        po = PurchaseOrder.objects.create(
            tenant=tenant_a, vendor=supplier_a, currency=usd, status="approved",
            order_date=datetime.date(2026, 1, 1), expected_date=datetime.date(2026, 1, 20),
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=po, item_description="Widget", quantity=Decimal("10"), unit_price=Decimal("5.00"),
        )
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=po, receipt_date=datetime.date(2026, 1, 15), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("10"))

        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
            manual_override=True, delivery_score=Decimal("42.00"),
        )
        scorecard.recompute_from_signals(save=False)
        assert scorecard.delivery_score == Decimal("42.00")  # untouched
        assert scorecard.quality_score is None  # never populated either

    def test_responsiveness_never_exceeds_100_on_negative_turnaround(self, tenant_a, supplier_a, usd):
        """Regression: a quote dated BEFORE its own RFQ's issue_date (bad/backfilled data)
        must never push responsiveness_score past 100 — it must clamp, not overflow."""
        from apps.scm.models import RFQ, RFQLine, RFQQuote, RFQQuoteLine, SupplierScorecard
        rfq = RFQ.objects.create(
            tenant=tenant_a, title="Weird dates RFQ", currency=usd, status="sent",
            issue_date=datetime.date(2026, 1, 20),  # issued AFTER the "received" quote below
        )
        rfq_line = RFQLine.objects.create(rfq=rfq, item_description="Widget", quantity=Decimal("1"))
        quote = RFQQuote.objects.create(
            tenant=tenant_a, rfq=rfq, party=supplier_a, status="received",
            received_date=datetime.date(2026, 1, 5),  # BEFORE issue_date -> negative turnaround
        )
        RFQQuoteLine.objects.create(
            quote=quote, rfq_line=rfq_line, quantity=Decimal("1"), unit_price=Decimal("10.00"),
        )

        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        scorecard.recompute_from_signals(save=False)
        assert scorecard.responsiveness_score is not None
        assert scorecard.responsiveness_score <= Decimal("100")

    def test_no_signals_leaves_scores_untouched(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierScorecard
        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a,
            period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
        )
        scorecard.recompute_from_signals(save=False)
        assert scorecard.delivery_score is None
        assert scorecard.quality_score is None
        assert scorecard.price_score is None
        assert scorecard.responsiveness_score is None
        assert scorecard.signal_summary == "No procurement signals in this period."


# ================================================================ recompute_from_signals query count (priority)
class TestScorecardRecomputeQueryCount:
    """recompute_from_signals must use prefetch + aggregates — a small CONSTANT query count that
    does not scale with the number of receipts/lines/quotes in the period (perf regression)."""

    def test_query_count_does_not_scale_with_row_count(
        self, tenant_a, supplier_a, usd, django_assert_max_num_queries,
    ):
        from apps.scm.models import (
            PurchaseOrder, PurchaseOrderLine, GoodsReceiptNote, GoodsReceiptLine,
            RFQ, RFQLine, RFQQuote, RFQQuoteLine, SupplierScorecard,
        )
        period_start = datetime.date(2026, 1, 1)
        period_end = datetime.date(2026, 1, 31)

        po = PurchaseOrder.objects.create(
            tenant=tenant_a, vendor=supplier_a, currency=usd, status="approved",
            order_date=datetime.date(2026, 1, 1), expected_date=datetime.date(2026, 1, 20),
        )
        lines = [
            PurchaseOrderLine.objects.create(
                purchase_order=po, item_description=f"Item {i}", quantity=Decimal("30"),
                unit_price=Decimal("5.00"),
            )
            for i in range(3)
        ]
        # ~5 receipts, 2-3 lines each.
        for i in range(5):
            grn = GoodsReceiptNote.objects.create(
                tenant=tenant_a, purchase_order=po,
                receipt_date=datetime.date(2026, 1, 10 + i), status="received",
            )
            for line in lines[: 2 + (i % 2)]:
                GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("2"))

        # ~5 RFQ quotes in the period.
        for i in range(5):
            rfq = RFQ.objects.create(
                tenant=tenant_a, title=f"RFQ {i}", currency=usd, status="sent",
                issue_date=datetime.date(2026, 1, 1),
            )
            rfq_line = RFQLine.objects.create(rfq=rfq, item_description="Widget", quantity=Decimal("1"))
            quote = RFQQuote.objects.create(
                tenant=tenant_a, rfq=rfq, party=supplier_a, status="received",
                received_date=datetime.date(2026, 1, 5),
            )
            RFQQuoteLine.objects.create(
                quote=quote, rfq_line=rfq_line, quantity=Decimal("1"), unit_price=Decimal("10.00"),
            )
            quote.recalc_totals()  # sets RFQQuote.total from its lines — required for price_score

        scorecard = SupplierScorecard.objects.create(
            tenant=tenant_a, party=supplier_a, period_start=period_start, period_end=period_end,
        )
        with django_assert_max_num_queries(8):
            scorecard.recompute_from_signals(save=True)

        assert scorecard.delivery_score is not None
        assert scorecard.price_score is not None


# ================================================================ SupplierScorecard.recompute_overall
class TestScorecardRecomputeOverall:
    def test_blends_only_present_dimensions(self, scorecard_a):
        scorecard_a.delivery_score = Decimal("80.00")
        scorecard_a.recompute_overall()
        assert scorecard_a.overall_score == Decimal("80.00")
        assert scorecard_a.grade == "B"

    @pytest.mark.parametrize("score,grade", [
        (Decimal("95"), "A"), (Decimal("80"), "B"), (Decimal("65"), "C"),
        (Decimal("45"), "D"), (Decimal("20"), "F"),
    ])
    def test_grade_thresholds(self, scorecard_a, score, grade):
        scorecard_a.delivery_score = score
        scorecard_a.quality_score = score
        scorecard_a.price_score = score
        scorecard_a.responsiveness_score = score
        scorecard_a.recompute_overall()
        assert scorecard_a.grade == grade

    def test_no_scores_returns_none_and_empty_grade(self, scorecard_a):
        scorecard_a.recompute_overall()
        assert scorecard_a.overall_score is None
        assert scorecard_a.grade == ""

    def test_grade_for_none_score_is_blank(self):
        """Direct unit test of the defensive branch in _grade_for — unreachable through
        recompute_overall() itself (which short-circuits to "" before ever calling it with
        None), but worth locking down as its own contract."""
        from apps.scm.models import SupplierScorecard
        assert SupplierScorecard._grade_for(None) == ""


# ================================================================ SupplierRiskAssessment.recompute_risk_level (priority)
class TestSupplierRiskAssessmentRecompute:
    """Regression: a single critical (5) factor must force at least 'high' — an averaged
    'medium' must never hide a lone 5/5 red flag (SupplierRiskAssessments.py)."""

    def test_all_low_is_low(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=1, geopolitical_score=1, compliance_score=1, operational_score=1,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("1.00")
        assert ra.risk_level == "low"

    def test_single_critical_factor_floors_at_high_not_medium(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=5, geopolitical_score=1, compliance_score=1, operational_score=1,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("2.00")  # mean is only 2.0 …
        assert ra.risk_level == "high"           # … but the lone 5 forces at least High

    def test_all_high_4s_is_critical(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=4, geopolitical_score=4, compliance_score=4, operational_score=4,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("4.00")
        assert ra.risk_level == "critical"

    def test_mean_of_exactly_3_is_high(self, tenant_a, supplier_a):
        """mean>=3 (and worst<5) lands in the 'elif mean>=3 or worst>=4' branch as High."""
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=3, geopolitical_score=3, compliance_score=3, operational_score=3,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("3.00")
        assert ra.risk_level == "high"

    def test_worst_of_4_with_low_mean_is_medium_not_high(self, tenant_a, supplier_a):
        """The same 'elif mean>=3 or worst>=4' branch, reached via worst>=4 alone with a mean
        under 3 — the *other* half of that branch's ternary, giving Medium not High."""
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=4, geopolitical_score=1, compliance_score=1, operational_score=1,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("1.75")
        assert ra.risk_level == "medium"

    def test_mean_between_2_and_3_with_worst_under_4_is_medium(self, tenant_a, supplier_a):
        """Pure 'elif mean>=2' branch — reached only when neither earlier condition (mean>=3
        or worst>=4) is met."""
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
            financial_score=2, geopolitical_score=2, compliance_score=2, operational_score=3,
        )
        ra.recompute_risk_level()
        assert ra.risk_index == Decimal("2.25")
        assert ra.risk_level == "medium"

    def test_defaults_are_all_low_scores(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
        )
        assert ra.financial_score == 1
        assert ra.geopolitical_score == 1
        assert ra.compliance_score == 1
        assert ra.operational_score == 1
        assert ra.risk_level == "low"  # model default, before any recompute


# ================================================================ SupplierContract date-driven status (priority)
class TestSupplierContractDateDrivenStatus:
    def test_no_end_date_days_to_expiry_is_none(self, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        c = SupplierContract.objects.create(tenant=tenant_a, party=supplier_a, title="Open-ended", status="active")
        assert c.days_to_expiry() is None
        assert c.is_expiring_soon() is False

    def test_end_date_within_notice_window_is_expiring_soon(self, tenant_a, supplier_a):
        from django.utils import timezone
        from apps.scm.models import SupplierContract
        today = timezone.now().date()
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="x", status="active",
            end_date=today + datetime.timedelta(days=10), renewal_notice_days=30,
        )
        assert c.is_expiring_soon() is True
        c.refresh_status()
        assert c.status == "expiring"

    def test_end_date_beyond_notice_window_stays_active(self, tenant_a, supplier_a):
        from django.utils import timezone
        from apps.scm.models import SupplierContract
        today = timezone.now().date()
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="x", status="active",
            end_date=today + datetime.timedelta(days=90), renewal_notice_days=30,
        )
        assert c.is_expiring_soon() is False
        c.refresh_status()
        assert c.status == "active"

    def test_past_end_date_becomes_expired(self, tenant_a, supplier_a):
        from django.utils import timezone
        from apps.scm.models import SupplierContract
        today = timezone.now().date()
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="x", status="active",
            end_date=today - datetime.timedelta(days=1), renewal_notice_days=30,
        )
        c.refresh_status()
        assert c.status == "expired"

    def test_terminated_contract_never_auto_moves(self, tenant_a, supplier_a):
        from django.utils import timezone
        from apps.scm.models import SupplierContract
        today = timezone.now().date()
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="x", status="terminated",
            end_date=today - datetime.timedelta(days=1), renewal_notice_days=30,
        )
        c.refresh_status()
        assert c.status == "terminated"

    def test_renewed_contract_never_auto_moves(self, tenant_a, supplier_a):
        from django.utils import timezone
        from apps.scm.models import SupplierContract
        today = timezone.now().date()
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="x", status="renewed",
            end_date=today - datetime.timedelta(days=1), renewal_notice_days=30,
        )
        c.refresh_status()
        assert c.status == "renewed"


# ================================================================ SupplierCatalog
class TestSupplierCatalog:
    def test_item_count_reflects_related_items(self, catalog_a):
        from apps.scm.models import SupplierCatalogItem
        assert catalog_a.item_count() == 0
        SupplierCatalogItem.objects.create(catalog=catalog_a, item_name="Widget", unit_price=Decimal("5.00"))
        SupplierCatalogItem.objects.create(catalog=catalog_a, item_name="Gadget", unit_price=Decimal("10.00"))
        assert catalog_a.item_count() == 2


# ================================================================================================
# SCM 4.3 Inventory Management
# ================================================================================================

# ================================================================ Auto-numbering (TRF-/ADJ-)
class TestInventoryAutoNumbering:
    def test_transfer_numbers_sequential_per_tenant(self, tenant_a, tenant_b, location_a, location_a2, location_b):
        from apps.scm.models import Location, StockTransfer
        other_b = Location.objects.create(tenant=tenant_b, code="WH2", name="Globex Overflow")
        t1 = StockTransfer.objects.create(tenant=tenant_a, from_location=location_a, to_location=location_a2,
                                          transfer_date=datetime.date(2026, 1, 1))
        t2 = StockTransfer.objects.create(tenant=tenant_a, from_location=location_a, to_location=location_a2,
                                          transfer_date=datetime.date(2026, 1, 2))
        t3 = StockTransfer.objects.create(tenant=tenant_b, from_location=location_b, to_location=other_b,
                                          transfer_date=datetime.date(2026, 1, 1))
        assert t1.number == "TRF-00001"
        assert t2.number == "TRF-00002"
        assert t3.number == "TRF-00001"  # separate per-tenant sequence

    def test_transfer_number_unique_together(self, tenant_a, location_a, location_a2):
        from apps.scm.models import StockTransfer
        t1 = StockTransfer.objects.create(tenant=tenant_a, from_location=location_a, to_location=location_a2,
                                          transfer_date=datetime.date(2026, 1, 1))
        with pytest.raises(IntegrityError):
            StockTransfer.objects.create(tenant=tenant_a, from_location=location_a, to_location=location_a2,
                                         transfer_date=datetime.date(2026, 1, 2), number=t1.number)

    def test_adjustment_numbers_sequential_per_tenant(self, tenant_a, tenant_b, location_a, location_b):
        from apps.scm.models import StockAdjustment
        a1 = StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                            adjustment_date=datetime.date(2026, 1, 1))
        a2 = StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                            adjustment_date=datetime.date(2026, 1, 2))
        a3 = StockAdjustment.objects.create(tenant=tenant_b, location=location_b,
                                            adjustment_date=datetime.date(2026, 1, 1))
        assert a1.number == "ADJ-00001"
        assert a2.number == "ADJ-00002"
        assert a3.number == "ADJ-00001"  # separate per-tenant sequence

    def test_adjustment_number_unique_together(self, tenant_a, location_a):
        from apps.scm.models import StockAdjustment
        a1 = StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                            adjustment_date=datetime.date(2026, 1, 1))
        with pytest.raises(IntegrityError):
            StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                           adjustment_date=datetime.date(2026, 1, 2), number=a1.number)


# ================================================================ unique_together (raw ORM, not the form)
class TestInventoryUniqueTogether:
    def test_sku_unique_per_tenant(self, tenant_a, item_a):
        from apps.scm.models import Item
        with pytest.raises(IntegrityError):
            Item.objects.create(tenant=tenant_a, sku=item_a.sku, name="Duplicate SKU")

    def test_uom_code_unique_per_tenant(self, tenant_a, uom_each_a):
        from apps.scm.models import UOM
        with pytest.raises(IntegrityError):
            UOM.objects.create(tenant=tenant_a, code=uom_each_a.code, name="Duplicate code")

    def test_location_code_unique_per_tenant(self, tenant_a, location_a):
        from apps.scm.models import Location
        with pytest.raises(IntegrityError):
            Location.objects.create(tenant=tenant_a, code=location_a.code, name="Duplicate code")

    def test_lot_number_unique_per_tenant_and_item(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.models import LotSerial
        with pytest.raises(IntegrityError):
            LotSerial.objects.create(tenant=tenant_a, item=item_lot_a, kind="lot", number=lot_a.number)

    def test_reorder_rule_unique_per_item_and_location(self, tenant_a, reorder_rule_a, item_a, location_a):
        from apps.scm.models import ReorderRule
        with pytest.raises(IntegrityError):
            ReorderRule.objects.create(tenant=tenant_a, item=item_a, location=location_a)


# ================================================================ __str__
class TestInventoryStrRepresentations:
    def test_item_category_str(self, category_a):
        assert str(category_a) == "Widgets"

    def test_uom_str(self, uom_each_a):
        assert str(uom_each_a) == "EA"

    def test_item_str(self, item_a):
        assert str(item_a) == "WIDGET-1 · Widget"

    def test_location_str(self, location_a):
        assert str(location_a) == "WH1 · Main Warehouse"

    def test_lot_serial_str(self, lot_a, item_lot_a):
        assert str(lot_a) == f"{item_lot_a.sku}·{lot_a.number}"

    def test_stock_move_str_positive(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        move = StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("5"),
            unit_cost=Decimal("1.00"), move_type="receipt", moved_at=timezone.now(),
        )
        assert str(move) == f"+5 {item_a.sku} @ {location_a.code}"

    def test_stock_move_str_negative_has_no_extra_sign(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        move = StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("-5"),
            unit_cost=Decimal("1.00"), move_type="issue", moved_at=timezone.now(),
        )
        assert str(move) == f"-5 {item_a.sku} @ {location_a.code}"

    def test_stock_transfer_str_uses_location_codes_not_raw_ids(self, stock_transfer_a, location_a, location_a2):
        """Regression: __str__ used to interpolate from_location_id/to_location_id (raw pks).
        It must show the human-readable codes, like every other model's __str__ in this module."""
        s = str(stock_transfer_a)
        assert stock_transfer_a.number in s
        assert location_a.code in s
        assert location_a2.code in s

    def test_stock_transfer_line_str(self, stock_transfer_a, item_a):
        line = stock_transfer_a.lines.first()
        assert str(line) == f"{item_a.sku} ×{line.quantity}"
        assert str(line).startswith("WIDGET-1 ×5")

    def test_stock_adjustment_str(self, stock_adjustment_a):
        s = str(stock_adjustment_a)
        assert stock_adjustment_a.number in s
        assert "Cycle Count" in s

    def test_stock_adjustment_line_str(self, stock_adjustment_a, item_a):
        line = stock_adjustment_a.lines.first()
        assert str(line) == f"{item_a.sku} Δ{line.quantity_delta}"
        assert str(line).startswith("WIDGET-1 Δ10")

    def test_reorder_rule_str(self, reorder_rule_a, item_a, location_a):
        s = str(reorder_rule_a)
        assert item_a.sku in s
        assert location_a.code in s


# ================================================================ Item — derived on-hand / value / average cost
class TestItemDerivedOnHand:
    def test_on_hand_defaults_to_zero(self, item_a):
        assert item_a.on_hand() == Decimal("0")

    def test_on_hand_is_derived_from_stock_move_sum(self, tenant_a, item_a, location_a, location_a2):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_a, location=location_a2, quantity=Decimal("4"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        assert item_a.on_hand() == Decimal("14")

    def test_on_hand_scoped_to_one_location(self, tenant_a, item_a, location_a, location_a2):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_a, location=location_a2, quantity=Decimal("4"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        assert item_a.on_hand(location=location_a) == Decimal("10")
        assert item_a.on_hand(location=location_a2) == Decimal("4")

    def test_total_value_uses_average_cost(self, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        item_a.refresh_from_db()
        assert item_a.total_value() == Decimal("50.00")

    def test_total_value_reuses_a_passed_in_on_hand(self, item_a):
        """Passing on_hand avoids a second aggregate — verify it's actually USED, not ignored."""
        item_a.average_cost = Decimal("3.5000")
        assert item_a.total_value(on_hand=Decimal("100")) == Decimal("350.00")

    def test_apply_receipt_rolls_weighted_average_from_empty(self, item_a):
        assert item_a.average_cost == Decimal("0")
        item_a.apply_receipt(Decimal("10"), Decimal("4.00"))
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("4.0000")

    def test_apply_receipt_called_twice_without_posting_does_not_accumulate(self, item_a):
        """apply_receipt reads the PRE-receipt on-hand from the StockMove ledger (never from its
        own prior call) — calling it twice in a row without ever posting the corresponding moves
        means on_hand() is still 0 the second time, so the second call simply overwrites, it does
        not blend. Blending across receipts is the posting service's job (_post_stock_move), which
        posts the move BETWEEN calls — see test_apply_receipt_blends_a_second_posted_receipt."""
        item_a.apply_receipt(Decimal("10"), Decimal("4.00"))
        item_a.refresh_from_db()
        item_a.apply_receipt(Decimal("10"), Decimal("8.00"))
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("8.0000")

    def test_apply_receipt_blends_a_second_posted_receipt(self, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("4.00"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("8.00"), move_type="receipt")
        item_a.refresh_from_db()
        # (10*4 + 10*8) / 20 = 6.0000
        assert item_a.average_cost == Decimal("6.0000")

    def test_is_stocked_true_for_stock_item_type(self, item_a):
        assert item_a.item_type == "stock"
        assert item_a.is_stocked is True

    def test_is_stocked_false_for_service_item_type(self, tenant_a):
        from apps.scm.models import Item
        service = Item.objects.create(tenant=tenant_a, sku="SVC-1", name="Consulting", item_type="service")
        assert service.is_stocked is False


class TestStockMoveValue:
    def test_value_is_quantity_times_unit_cost(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        move = StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("4"),
            unit_cost=Decimal("2.50"), move_type="receipt", moved_at=timezone.now(),
        )
        assert move.value == Decimal("10.00")

    def test_value_is_negative_for_an_outbound_move(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        move = StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("-4"),
            unit_cost=Decimal("2.50"), move_type="issue", moved_at=timezone.now(),
        )
        assert move.value == Decimal("-10.00")

    def test_apply_receipt_does_not_touch_stock_move(self, item_a):
        """apply_receipt only rolls the cached figure — it must never write a StockMove itself
        (that is the posting service's job); on_hand stays derived from the ledger alone."""
        item_a.apply_receipt(Decimal("10"), Decimal("4.00"))
        assert item_a.on_hand() == Decimal("0")

    def test_apply_receipt_noop_for_zero_quantity(self, item_a):
        item_a.average_cost = Decimal("10.0000")
        item_a.save(update_fields=["average_cost"])
        item_a.apply_receipt(Decimal("0"), Decimal("99.00"))
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")

    def test_apply_receipt_noop_for_negative_quantity(self, item_a):
        item_a.average_cost = Decimal("10.0000")
        item_a.save(update_fields=["average_cost"])
        item_a.apply_receipt(Decimal("-5"), Decimal("99.00"))
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")


# ================================================================ Location — derived hierarchy + value
class TestLocationDerived:
    def test_is_leaf_true_without_children(self, location_a):
        assert location_a.is_leaf is True

    def test_is_leaf_false_with_children(self, tenant_a, location_a):
        from apps.scm.models import Location
        Location.objects.create(tenant=tenant_a, code="WH1-A", name="Zone A", parent=location_a)
        assert location_a.is_leaf is False

    def test_path_walks_full_ancestry(self, tenant_a, location_a):
        from apps.scm.models import Location
        zone = Location.objects.create(tenant=tenant_a, code="ZONE-A", name="Zone A",
                                       location_type="zone", parent=location_a)
        bin_ = Location.objects.create(tenant=tenant_a, code="BIN-01", name="Bin 1",
                                       location_type="bin", parent=zone)
        assert bin_.path() == "WH1 › ZONE-A › BIN-01"

    def test_path_guards_a_malformed_cycle(self, tenant_a, location_a, location_a2):
        """A pathological self-referential loop (data corruption, or bypassing the form's
        self-parent guard directly via the ORM) must terminate, not hang the page."""
        location_a.parent = location_a2
        location_a.save(update_fields=["parent"])
        location_a2.parent = location_a
        location_a2.save(update_fields=["parent"])
        result = location_a.path()  # must return, not infinite-loop
        assert location_a.code in result
        assert location_a2.code in result

    def test_on_hand_value_sums_quantity_times_unit_cost(self, tenant_a, item_a, location_a, location_a2):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_a, location=location_a2, quantity=Decimal("100"),
                         unit_cost=Decimal("9.00"), move_type="receipt")
        assert location_a.on_hand_value() == Decimal("50.00")  # location_a2's value excluded

    def test_on_hand_value_zero_with_no_moves(self, location_a):
        assert location_a.on_hand_value() == Decimal("0.00")

    def test_on_hand_value_is_one_query(self, tenant_a, item_a, location_a, django_assert_max_num_queries):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        with django_assert_max_num_queries(1):
            location_a.on_hand_value()


# ================================================================ LotSerial — derived on-hand
class TestLotSerialDerived:
    def test_on_hand_defaults_to_zero(self, lot_a):
        assert lot_a.on_hand() == Decimal("0")

    def test_on_hand_is_derived_from_its_moves(self, tenant_a, item_lot_a, location_a, lot_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("2.00"), move_type="receipt", lot_serial=lot_a)
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("-6"),
                         unit_cost=Decimal("2.00"), move_type="issue", lot_serial=lot_a)
        assert lot_a.on_hand() == Decimal("14")


# ================================================================ ReorderRule
class TestReorderRule:
    def test_on_hand_map_empty_rules_returns_empty_dict(self, tenant_a):
        from apps.scm.models import ReorderRule
        assert ReorderRule.on_hand_map(tenant_a, []) == {}

    def test_on_hand_map_groups_by_item_and_location(self, tenant_a, item_a, location_a, reorder_rule_a):
        from apps.scm.models import ReorderRule
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("7"),
                         unit_cost=Decimal("1.00"), move_type="receipt")
        m = ReorderRule.on_hand_map(tenant_a, [reorder_rule_a])
        assert m[(item_a.pk, location_a.pk)] == Decimal("7")

    def test_current_on_hand_reuses_a_passed_value(self, reorder_rule_a):
        assert reorder_rule_a.current_on_hand(on_hand=Decimal("42")) == Decimal("42")

    def test_current_on_hand_falls_back_to_a_live_query(self, tenant_a, item_a, location_a, reorder_rule_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("3"),
                         unit_cost=Decimal("1.00"), move_type="receipt")
        assert reorder_rule_a.current_on_hand() == Decimal("3")

    def test_is_below_point_true_at_or_under(self, reorder_rule_a):
        assert reorder_rule_a.is_below_point(on_hand=Decimal("10")) is True   # == reorder_point
        assert reorder_rule_a.is_below_point(on_hand=Decimal("5")) is True    # < reorder_point

    def test_is_below_point_false_above(self, reorder_rule_a):
        assert reorder_rule_a.is_below_point(on_hand=Decimal("11")) is False

    def test_suggested_quantity_uses_fixed_reorder_quantity_when_larger_than_gap(self, reorder_rule_a):
        # reorder_point=10, safety_stock=5 -> target=15; on_hand=12 -> gap=3; reorder_quantity=20 wins.
        assert reorder_rule_a.suggested_quantity(on_hand=Decimal("12")) == Decimal("20")

    def test_suggested_quantity_uses_gap_when_larger_than_fixed_quantity(self, tenant_a, item_a, location_a):
        from apps.scm.models import ReorderRule
        rule = ReorderRule.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            reorder_point=Decimal("10"), safety_stock=Decimal("50"), reorder_quantity=Decimal("5"),
        )
        # target = 60; on_hand=0 -> gap=60 > fixed reorder_quantity(5) -> gap wins.
        assert rule.suggested_quantity(on_hand=Decimal("0")) == Decimal("60")

    def test_suggested_quantity_zero_when_on_hand_already_at_target(self, reorder_rule_a):
        assert reorder_rule_a.suggested_quantity(on_hand=Decimal("15")) == Decimal("0")

    def test_suggested_quantity_falls_back_to_gap_when_no_fixed_quantity(self, tenant_a, item_a, location_a):
        from apps.scm.models import ReorderRule
        rule = ReorderRule.objects.create(
            tenant=tenant_a, item=item_a, location=location_a,
            reorder_point=Decimal("10"), safety_stock=Decimal("0"), reorder_quantity=Decimal("0"),
        )
        assert rule.suggested_quantity(on_hand=Decimal("0")) == Decimal("10")


# ================================================================ StockTransfer / StockAdjustment state
class TestStockTransferProperties:
    def test_is_editable_only_in_draft(self, stock_transfer_a):
        assert stock_transfer_a.is_editable is True
        stock_transfer_a.status = "completed"
        assert stock_transfer_a.is_editable is False

    def test_clean_rejects_same_source_and_destination(self, tenant_a, location_a):
        from apps.scm.models import StockTransfer
        transfer = StockTransfer(tenant=tenant_a, from_location=location_a, to_location=location_a,
                                 transfer_date=datetime.date(2026, 1, 1))
        with pytest.raises(ValidationError):
            transfer.clean()


class TestStockAdjustmentProperties:
    def test_is_editable_only_in_draft(self, stock_adjustment_a):
        assert stock_adjustment_a.is_editable is True
        stock_adjustment_a.status = "posted"
        assert stock_adjustment_a.is_editable is False

    def test_value_impact_sums_signed_delta_times_cost(self, stock_adjustment_a):
        # One line: +10 @ $8.00
        assert stock_adjustment_a.value_impact() == Decimal("80.00")

    def test_value_impact_zero_with_no_lines(self, tenant_a, location_a):
        from apps.scm.models import StockAdjustment
        adj = StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                             adjustment_date=datetime.date(2026, 1, 1))
        assert adj.value_impact() == Decimal("0.00")

    def test_clean_requires_notes_when_reason_is_other(self, tenant_a, location_a):
        from apps.scm.models import StockAdjustment
        adj = StockAdjustment(tenant=tenant_a, location=location_a, reason="other",
                              adjustment_date=datetime.date(2026, 1, 1), notes="")
        with pytest.raises(ValidationError):
            adj.clean()

    def test_clean_allows_other_with_notes(self, tenant_a, location_a):
        from apps.scm.models import StockAdjustment
        adj = StockAdjustment(tenant=tenant_a, location=location_a, reason="other",
                              adjustment_date=datetime.date(2026, 1, 1), notes="Explained.")
        adj.clean()  # must not raise


# ================================================================================================
# Priority regressions (posting service) — apps/scm/views/_helpers.py
# ================================================================================================

# ---------------------------------------------------------------- Regression 1: lot/location guard
class TestInsufficientStockLotLocationRegression:
    """`_insufficient_stock` must scope to (item, location, lot) — NOT the lot's tenant-wide total.
    A lot's global on-hand can cover a draw while the SPECIFIC location asked to release it never
    held any of that lot at all."""

    def test_refused_when_location_never_held_the_lot_even_though_its_global_total_covers_it(
        self, tenant_a, item_lot_a, location_a, location_a2, lot_a,
    ):
        from apps.scm.views._helpers import _post_stock_move, _insufficient_stock
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("50"),
                         unit_cost=Decimal("10.00"), move_type="receipt", lot_serial=lot_a)
        # Tenant-wide the lot has plenty...
        assert lot_a.on_hand() == Decimal("50")
        # ...but location_a2 never received any of it.
        shortfall = _insufficient_stock(item_lot_a, location_a2, Decimal("10"), lot_a)
        assert shortfall != ""
        assert lot_a.number in shortfall
        assert location_a2.code in shortfall
        # And location_a2's on-hand for this item must not have gone negative — nothing was posted.
        assert item_lot_a.on_hand(location=location_a2) == Decimal("0")

    def test_allowed_when_the_location_actually_holds_enough_of_the_lot(
        self, tenant_a, item_lot_a, location_a, lot_a,
    ):
        from apps.scm.views._helpers import _post_stock_move, _insufficient_stock
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("50"),
                         unit_cost=Decimal("10.00"), move_type="receipt", lot_serial=lot_a)
        assert _insufficient_stock(item_lot_a, location_a, Decimal("10"), lot_a) == ""


# ---------------------------------------------------------------- Regression 3: cumulative weighted average
class TestCumulativeWeightedAverageRegression:
    """Two adjustment lines for the SAME item at different unit costs must blend cumulatively
    against the item's just-updated average — not each roll from a stale, pre-adjustment read."""

    def test_two_lines_same_item_blend_cumulatively(self, tenant_a, item_a, location_a):
        from apps.scm.models import StockAdjustment, StockAdjustmentLine
        from apps.scm.views._helpers import _post_stock_move, _post_adjustment

        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("100"),
                         unit_cost=Decimal("10.00"), move_type="receipt")
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")

        adj = StockAdjustment.objects.create(tenant=tenant_a, location=location_a, reason="found",
                                             adjustment_date=datetime.date(2026, 1, 20))
        StockAdjustmentLine.objects.create(adjustment=adj, item=item_a, quantity_delta=Decimal("5"),
                                           unit_cost=Decimal("20.00"))
        StockAdjustmentLine.objects.create(adjustment=adj, item=item_a, quantity_delta=Decimal("5"),
                                           unit_cost=Decimal("30.00"))

        _post_adjustment(adj, user=None)
        item_a.refresh_from_db()
        # The stale-read bug gave 10.9091; the cumulative roll gives 11.3636.
        assert item_a.average_cost == Decimal("11.3636")
        assert item_a.on_hand() == Decimal("110")

    def test_shared_items_returns_one_instance_per_item_id(self, tenant_a, stock_adjustment_a, item_a):
        from apps.scm.views._helpers import _shared_items
        from apps.scm.models import StockAdjustmentLine
        StockAdjustmentLine.objects.create(adjustment=stock_adjustment_a, item=item_a,
                                           quantity_delta=Decimal("1"), unit_cost=Decimal("1.00"))
        lines = list(stock_adjustment_a.lines.select_related("item"))
        assert len(lines) == 2
        shared = _shared_items(lines)
        assert len(shared) == 1  # one Item instance for both lines
        assert shared[item_a.pk] is lines[0].item


# ---------------------------------------------------------------- Regression 5: zero-cost receipt dilutes
class TestZeroCostReceiptDilutesRegression:
    """`_post_stock_move` tests ``unit_cost is not None`` — a genuinely free receipt (found stock,
    a zero-cost sample) must still drag the average DOWN, not be skipped as if no cost were given."""

    def test_zero_unit_cost_dilutes_the_average(self, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("10.00"), move_type="receipt")
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")

        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("0"), move_type="receipt")
        item_a.refresh_from_db()
        # (10*10.00 + 10*0) / 20 = 5.0000 — NOT still 10.0000.
        assert item_a.average_cost == Decimal("5.0000")

    def test_unit_cost_none_explicitly_skips_the_roll(self, tenant_a, item_a, location_a):
        """A caller that explicitly passes unit_cost=None (cost genuinely unknown) is a DIFFERENT
        case from unit_cost=0 (a known, free receipt) — the average must NOT move."""
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("10.00"), move_type="receipt")
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")

        move = _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                                unit_cost=None, move_type="receipt")
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("10.0000")  # unchanged — no cost given, no roll
        assert move.unit_cost == Decimal("0")  # the move row itself still gets a concrete 0


# ---------------------------------------------------------------- _post_transfer / _post_adjustment posting
class TestPostTransferService:
    def test_posts_a_paired_negative_and_positive_move(self, tenant_a, stock_transfer_a, location_a, location_a2, item_a):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_transfer
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        _post_transfer(stock_transfer_a, user=None)
        moves = StockMove.objects.filter(tenant=tenant_a, reference=stock_transfer_a.number).order_by("quantity")
        assert [m.quantity for m in moves] == [Decimal("-5.0000"), Decimal("5.0000")]
        assert item_a.on_hand(location=location_a) == Decimal("15")
        assert item_a.on_hand(location=location_a2) == Decimal("5")

    def test_refuses_an_over_transfer(self, tenant_a, stock_transfer_a, location_a, item_a):
        """Only 3 on hand at the source but the line asks for 5 -> ValidationError, nothing posted."""
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_transfer
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("3"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        with pytest.raises(ValidationError):
            _post_transfer(stock_transfer_a, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=stock_transfer_a.number).exists()


class TestPostAdjustmentService:
    def test_posts_one_signed_move_per_line(self, tenant_a, stock_adjustment_a, item_a, location_a):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_adjustment
        _post_adjustment(stock_adjustment_a, user=None)
        moves = StockMove.objects.filter(tenant=tenant_a, reference=stock_adjustment_a.number)
        assert moves.count() == 1
        assert moves.first().quantity == Decimal("10.0000")
        assert item_a.on_hand(location=location_a) == Decimal("10")

    def test_refuses_a_write_off_that_would_go_negative(self, tenant_a, location_a, item_a):
        from apps.scm.models import StockAdjustment, StockAdjustmentLine, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_adjustment
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        adj = StockAdjustment.objects.create(tenant=tenant_a, location=location_a, reason="write_off",
                                             adjustment_date=datetime.date(2026, 1, 20))
        StockAdjustmentLine.objects.create(adjustment=adj, item=item_a, quantity_delta=Decimal("-5"),
                                           unit_cost=Decimal("5.00"))
        with pytest.raises(ValidationError):
            _post_adjustment(adj, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=adj.number).exists()


# ================================================================================================
# SCM 4.4 Warehouse Management
# ================================================================================================

# ================================================================ Auto-numbering
class TestWarehouseAutoNumbering:
    def test_putawaytask_numbers_sequential_per_tenant(self, tenant_a, tenant_b, item_a, location_a,
                                                        location_a2, item_b, location_b):
        from apps.scm.models import Location, PutawayTask
        bin_b = Location.objects.create(tenant=tenant_b, code="BIN-X", name="Globex Bin X")
        t1 = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                        to_location=location_a2, quantity=Decimal("1"))
        t2 = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                        to_location=location_a2, quantity=Decimal("1"))
        t3 = PutawayTask.objects.create(tenant=tenant_b, item=item_b, from_location=location_b,
                                        to_location=bin_b, quantity=Decimal("1"))
        assert t1.number == "PUT-00001"
        assert t2.number == "PUT-00002"
        assert t3.number == "PUT-00001"  # separate per-tenant sequence

    def test_putawaytask_number_unique_together(self, tenant_a, item_a, location_a, location_a2):
        from apps.scm.models import PutawayTask
        t1 = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                        to_location=location_a2, quantity=Decimal("1"))
        with pytest.raises(IntegrityError):
            PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                       to_location=location_a2, quantity=Decimal("1"), number=t1.number)

    def test_picktask_number_prefixed_pik(self, tenant_a):
        from apps.scm.models import PickTask
        task = PickTask.objects.create(tenant=tenant_a)
        assert task.number == "PIK-00001"

    def test_picktask_number_unique_together(self, tenant_a):
        from apps.scm.models import PickTask
        t1 = PickTask.objects.create(tenant=tenant_a)
        with pytest.raises(IntegrityError):
            PickTask.objects.create(tenant=tenant_a, number=t1.number)

    def test_cyclecounttask_number_prefixed_cc(self, tenant_a, location_a):
        from apps.scm.models import CycleCountTask
        task = CycleCountTask.objects.create(tenant=tenant_a, location=location_a,
                                             scheduled_date=datetime.date(2026, 1, 20))
        assert task.number == "CC-00001"

    def test_cyclecounttask_number_unique_together(self, tenant_a, location_a):
        from apps.scm.models import CycleCountTask
        t1 = CycleCountTask.objects.create(tenant=tenant_a, location=location_a,
                                           scheduled_date=datetime.date(2026, 1, 20))
        with pytest.raises(IntegrityError):
            CycleCountTask.objects.create(tenant=tenant_a, location=location_a,
                                          scheduled_date=datetime.date(2026, 1, 21), number=t1.number)

    def test_yardvisit_number_prefixed_yrd(self, tenant_a):
        from apps.scm.models import YardVisit
        visit = YardVisit.objects.create(tenant=tenant_a, carrier_name="Acme Haulage")
        assert visit.number == "YRD-00001"

    def test_yardvisit_number_unique_together(self, tenant_a):
        from apps.scm.models import YardVisit
        v1 = YardVisit.objects.create(tenant=tenant_a, carrier_name="Acme Haulage")
        with pytest.raises(IntegrityError):
            YardVisit.objects.create(tenant=tenant_a, carrier_name="Another Haulier", number=v1.number)


# ================================================================ __str__
class TestWarehouseStrRepresentations:
    def test_putawaytask_str(self, putawaytask_a, item_a, location_a2):
        s = str(putawaytask_a)
        assert putawaytask_a.number in s
        assert item_a.sku in s
        assert location_a2.code in s

    def test_picktask_str(self, picktask_a):
        s = str(picktask_a)
        assert picktask_a.number in s
        assert "Single Order" in s

    def test_picktaskline_str(self, picktask_a, item_a):
        line = picktask_a.lines.first()
        assert str(line) == f"{item_a.sku} ×{line.quantity_requested}"
        assert str(line).startswith("WIDGET-1 ×5")

    def test_cyclecounttask_str(self, cyclecounttask_a, location_a):
        s = str(cyclecounttask_a)
        assert cyclecounttask_a.number in s
        assert location_a.code in s

    def test_cyclecounttaskline_str(self, cyclecounttask_a, item_a):
        line = cyclecounttask_a.lines.first()
        assert str(line) == f"{item_a.sku}: expected {line.expected_quantity}"

    def test_yardvisit_str(self, yardvisit_a):
        s = str(yardvisit_a)
        assert yardvisit_a.number in s
        assert "Acme Haulage" in s


# ================================================================ PutawayTask properties
class TestPutawayTaskProperties:
    def test_is_editable_true_pending_and_in_progress(self, putawaytask_a):
        assert putawaytask_a.is_editable is True
        putawaytask_a.status = "in_progress"
        assert putawaytask_a.is_editable is True

    def test_is_editable_false_once_completed_or_cancelled(self, putawaytask_a):
        putawaytask_a.status = "completed"
        assert putawaytask_a.is_editable is False
        putawaytask_a.status = "cancelled"
        assert putawaytask_a.is_editable is False

    def test_is_open_true_pending_and_in_progress(self, putawaytask_a):
        assert putawaytask_a.is_open is True
        putawaytask_a.status = "in_progress"
        assert putawaytask_a.is_open is True

    def test_is_open_false_once_completed_or_cancelled(self, putawaytask_a):
        putawaytask_a.status = "completed"
        assert putawaytask_a.is_open is False
        putawaytask_a.status = "cancelled"
        assert putawaytask_a.is_open is False

    def test_clean_rejects_same_source_and_destination(self, tenant_a, item_a, location_a):
        from apps.scm.models import PutawayTask
        task = PutawayTask(tenant=tenant_a, item=item_a, from_location=location_a,
                           to_location=location_a, quantity=Decimal("1"))
        with pytest.raises(ValidationError):
            task.clean()

    def test_clean_allows_different_locations(self, putawaytask_a):
        putawaytask_a.clean()  # must not raise


# ================================================================ PickTask / PickTaskLine properties
class TestPickTaskProperties:
    def test_is_editable_true_pending_and_released(self, picktask_a):
        assert picktask_a.is_editable is True
        picktask_a.status = "released"
        assert picktask_a.is_editable is True

    def test_is_editable_false_once_picking_or_beyond(self, picktask_a):
        for status in ("picking", "picked", "packed", "cancelled"):
            picktask_a.status = status
            assert picktask_a.is_editable is False

    def test_line_count(self, picktask_a):
        assert picktask_a.line_count() == 1

    def test_is_short_false_when_fully_picked(self, picktask_a):
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        assert picktask_a.is_short() is False

    def test_is_short_true_when_under_picked(self, picktask_a):
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested - Decimal("1")
        line.save(update_fields=["quantity_picked"])
        assert picktask_a.is_short() is True

    def test_is_short_false_with_no_lines(self, tenant_a):
        from apps.scm.models import PickTask
        empty = PickTask.objects.create(tenant=tenant_a)
        assert empty.is_short() is False

    def test_picktaskline_shortfall(self, picktask_a):
        line = picktask_a.lines.first()
        line.quantity_picked = Decimal("2")
        assert line.shortfall == Decimal("3")  # requested 5 - picked 2


# ================================================================ CycleCountTask / line properties
class TestCycleCountTaskProperties:
    def test_is_editable_true_scheduled_and_in_progress(self, cyclecounttask_a):
        assert cyclecounttask_a.is_editable is True
        cyclecounttask_a.status = "in_progress"
        assert cyclecounttask_a.is_editable is True

    def test_is_editable_false_once_counted_or_beyond(self, cyclecounttask_a):
        for status in ("counted", "reconciled", "cancelled"):
            cyclecounttask_a.status = status
            assert cyclecounttask_a.is_editable is False

    def test_variance_count_and_net_variance_with_mixed_lines(self, tenant_a, cyclecounttask_a, item_lot_a):
        from apps.scm.models import CycleCountTaskLine
        line1 = cyclecounttask_a.lines.first()
        line1.expected_quantity = Decimal("10")
        line1.counted_quantity = Decimal("12")  # variance +2
        line1.save(update_fields=["expected_quantity", "counted_quantity"])
        line2 = CycleCountTaskLine.objects.create(
            cycle_count=cyclecounttask_a, item=item_lot_a,
            expected_quantity=Decimal("5"), counted_quantity=Decimal("5"),  # no variance
        )
        line3 = CycleCountTaskLine.objects.create(
            cycle_count=cyclecounttask_a, item=item_lot_a, expected_quantity=Decimal("3"),
        )  # uncounted — contributes nothing
        assert cyclecounttask_a.variance_count() == 1
        assert cyclecounttask_a.has_variance() is True
        assert cyclecounttask_a.net_variance() == Decimal("2")

        # Passing lines= reuses them rather than re-querying — same result.
        lines = list(cyclecounttask_a.lines.all())
        assert cyclecounttask_a.variance_count(lines=lines) == 1
        assert cyclecounttask_a.net_variance(lines=lines) == Decimal("2")

    def test_variance_count_zero_when_nothing_counted(self, cyclecounttask_a):
        assert cyclecounttask_a.variance_count() == 0
        assert cyclecounttask_a.has_variance() is False
        assert cyclecounttask_a.net_variance() == Decimal("0")

    def test_cyclecounttaskline_variance_zero_while_uncounted(self, cyclecounttask_a):
        line = cyclecounttask_a.lines.first()
        line.expected_quantity = Decimal("10")
        assert line.counted_quantity is None
        assert line.variance == Decimal("0")  # not a phantom shortfall
        assert line.has_variance is False

    def test_cyclecounttaskline_variance_and_has_variance_once_counted(self, cyclecounttask_a):
        line = cyclecounttask_a.lines.first()
        line.expected_quantity = Decimal("10")
        line.counted_quantity = Decimal("7")
        assert line.variance == Decimal("-3")
        assert line.has_variance is True

    def test_cyclecounttaskline_counted_zero_is_not_uncounted(self, cyclecounttask_a):
        """counted_quantity=0 is a REAL count (nothing there), distinct from None (not yet counted)."""
        line = cyclecounttask_a.lines.first()
        line.expected_quantity = Decimal("4")
        line.counted_quantity = Decimal("0")
        assert line.variance == Decimal("-4")
        assert line.has_variance is True

    def test_cyclecounttaskline_no_variance_when_counted_matches_expected(self, cyclecounttask_a):
        line = cyclecounttask_a.lines.first()
        line.expected_quantity = Decimal("6")
        line.counted_quantity = Decimal("6")
        assert line.variance == Decimal("0")
        assert line.has_variance is False


# ================================================================ YardVisit properties
class TestYardVisitProperties:
    def test_is_editable_true_scheduled_arrived_at_dock(self, yardvisit_a):
        for status in ("scheduled", "arrived", "at_dock"):
            yardvisit_a.status = status
            assert yardvisit_a.is_editable is True

    def test_is_editable_false_departed_or_cancelled(self, yardvisit_a):
        for status in ("departed", "cancelled"):
            yardvisit_a.status = status
            assert yardvisit_a.is_editable is False

    def test_is_open_true_scheduled_arrived_at_dock(self, yardvisit_a):
        for status in ("scheduled", "arrived", "at_dock"):
            yardvisit_a.status = status
            assert yardvisit_a.is_open is True

    def test_is_open_false_departed_or_cancelled(self, yardvisit_a):
        for status in ("departed", "cancelled"):
            yardvisit_a.status = status
            assert yardvisit_a.is_open is False

    def test_dwell_minutes_none_before_arrival(self, yardvisit_a):
        assert yardvisit_a.arrived_at is None
        assert yardvisit_a.dwell_minutes() is None

    def test_dwell_minutes_computed_between_arrival_and_departure(self, yardvisit_a):
        from django.utils import timezone
        arrived = timezone.now() - datetime.timedelta(minutes=90)
        departed = timezone.now() - datetime.timedelta(minutes=15)
        yardvisit_a.arrived_at = arrived
        yardvisit_a.departed_at = departed
        assert yardvisit_a.dwell_minutes() == 75

    def test_dwell_minutes_falls_back_to_now_while_still_on_site(self, yardvisit_a):
        from django.utils import timezone
        yardvisit_a.arrived_at = timezone.now() - datetime.timedelta(minutes=10)
        yardvisit_a.departed_at = None
        dwell = yardvisit_a.dwell_minutes()
        assert dwell is not None
        assert 9 <= dwell <= 11  # ~10 minutes, tolerant of test execution time


# ================================================================================================
# Priority regression 1a — GRN cancel must refuse once its stock has already been put away
# ================================================================================================
class TestReverseGrnReceiptPutawayGuardRegression:
    """`_reverse_grn_receipt` must refuse once the received stock has moved on to a bin via
    putaway — reversing blind would drive the staging location negative while the bin keeps the
    un-reversed stock. A receipt still sitting in staging must still reverse normally (the guard
    must not be over-broad)."""

    def test_refused_once_the_stock_has_been_put_away_elsewhere(
        self, tenant_a, goods_receipt_a, location_a, location_a2, item_a,
    ):
        from apps.scm.models import PutawayTask, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_putaway, _reverse_grn_receipt

        goods_receipt_a.status = "received"
        goods_receipt_a.save(update_fields=["status"])
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt", reference=goods_receipt_a.number)
        task = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                          to_location=location_a2, quantity=Decimal("10"))
        _post_putaway(task, user=None)
        assert item_a.on_hand(location=location_a) == Decimal("0")
        assert item_a.on_hand(location=location_a2) == Decimal("10")

        with pytest.raises(ValidationError):
            _reverse_grn_receipt(goods_receipt_a, user=None)
        # Nothing changed by the refused reversal — staging never went negative, the bin keeps its stock.
        assert item_a.on_hand(location=location_a) == Decimal("0")
        assert item_a.on_hand(location=location_a2) == Decimal("10")
        assert not StockMove.objects.filter(tenant=tenant_a, reference=goods_receipt_a.number,
                                            move_type="receipt", quantity__lt=0).exists()

    def test_allowed_when_the_stock_still_sits_in_staging(self, tenant_a, goods_receipt_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move, _reverse_grn_receipt

        goods_receipt_a.status = "received"
        goods_receipt_a.save(update_fields=["status"])
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt", reference=goods_receipt_a.number)
        reversed_count = _reverse_grn_receipt(goods_receipt_a, user=None)
        assert reversed_count == 1
        assert item_a.on_hand(location=location_a) == Decimal("0")  # fully returned


# ================================================================================================
# _post_putaway / _post_pick posting services
# ================================================================================================
class TestPostPutawayService:
    def test_posts_a_paired_move_leaving_tenant_wide_total_unchanged(
        self, tenant_a, item_a, location_a, location_a2,
    ):
        from apps.scm.models import PutawayTask, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_putaway
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        before = item_a.on_hand()
        task = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                          to_location=location_a2, quantity=Decimal("4"))
        _post_putaway(task, user=None)
        assert item_a.on_hand() == before  # unchanged tenant-wide
        assert item_a.on_hand(location=location_a) == Decimal("6")
        assert item_a.on_hand(location=location_a2) == Decimal("4")
        moves = StockMove.objects.filter(tenant=tenant_a, reference=task.number).order_by("quantity")
        assert [m.quantity for m in moves] == [Decimal("-4.0000"), Decimal("4.0000")]

    def test_refuses_an_over_putaway(self, tenant_a, item_a, location_a, location_a2):
        from apps.scm.models import PutawayTask, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_putaway
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("3"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        task = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                          to_location=location_a2, quantity=Decimal("5"))
        with pytest.raises(ValidationError):
            _post_putaway(task, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=task.number).exists()
        assert item_a.on_hand(location=location_a) == Decimal("3")  # unchanged

    def test_refused_when_staging_never_held_the_item_at_all(self, tenant_a, item_a, location_a, location_a2):
        """Absent-prerequisite (L35): no receipt has ever landed at the staging location — refused
        outright, never treated as unlimited."""
        from apps.scm.models import PutawayTask, StockMove
        from apps.scm.views._helpers import _post_putaway
        task = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                          to_location=location_a2, quantity=Decimal("1"))
        with pytest.raises(ValidationError):
            _post_putaway(task, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=task.number).exists()


class TestPostPickService:
    def test_short_pick_issues_only_the_picked_quantity_not_the_requested(
        self, tenant_a, item_a, location_a,
    ):
        from apps.scm.models import PickTask, PickTaskLine, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_pick
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        task = PickTask.objects.create(tenant=tenant_a)
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("8"), quantity_picked=Decimal("5"))
        posted = _post_pick(task, user=None)
        assert posted == 1
        move = StockMove.objects.get(tenant=tenant_a, reference=task.number)
        assert move.quantity == Decimal("-5.0000")  # picked, NOT the requested 8
        assert item_a.on_hand(location=location_a) == Decimal("5")

    def test_zero_picked_line_contributes_no_move(self, tenant_a, item_a, location_a):
        from apps.scm.models import PickTask, PickTaskLine, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_pick
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        task = PickTask.objects.create(tenant=tenant_a)
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("5"), quantity_picked=Decimal("3"))
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("2"), quantity_picked=Decimal("0"))
        posted = _post_pick(task, user=None)
        assert posted == 1
        assert StockMove.objects.filter(tenant=tenant_a, reference=task.number).count() == 1

    def test_nothing_picked_raises_and_posts_nothing(self, tenant_a, item_a, location_a):
        """Absent-prerequisite (L35): a task with nothing picked must be REJECTED outright."""
        from apps.scm.models import PickTask, PickTaskLine, StockMove
        from apps.scm.views._helpers import _post_pick
        task = PickTask.objects.create(tenant=tenant_a)
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("5"), quantity_picked=Decimal("0"))
        with pytest.raises(ValidationError):
            _post_pick(task, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=task.number).exists()

    def test_over_pick_at_the_bin_is_refused(self, tenant_a, item_a, location_a):
        """Only 2 on hand at the bin but the line records 5 picked -> refused, nothing posted."""
        from apps.scm.models import PickTask, PickTaskLine, StockMove
        from apps.scm.views._helpers import _post_stock_move, _post_pick
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        task = PickTask.objects.create(tenant=tenant_a)
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("5"), quantity_picked=Decimal("5"))
        with pytest.raises(ValidationError):
            _post_pick(task, user=None)
        assert not StockMove.objects.filter(tenant=tenant_a, reference=task.number).exists()
        assert item_a.on_hand(location=location_a) == Decimal("2")  # unchanged


# ================================================================================================
# SCM 4.5 Order Management System
# ================================================================================================

# ================================================================ Auto-numbering
class TestSalesOrderAutoNumbering:
    def test_number_prefixed_so_and_sequential_per_tenant(self, tenant_a, tenant_b, customer_a, customer_b):
        from apps.scm.models import SalesOrder
        o1 = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a)
        o2 = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a)
        o3 = SalesOrder.objects.create(tenant=tenant_b, customer=customer_b)
        assert o1.number == "SO-00001"
        assert o2.number == "SO-00002"
        assert o3.number == "SO-00001"  # separate per-tenant sequence

    def test_number_unique_together(self, tenant_a, customer_a):
        from apps.scm.models import SalesOrder
        o1 = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a)
        with pytest.raises(IntegrityError):
            SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, number=o1.number)


# ================================================================ __str__
class TestSalesOrderStrRepresentations:
    def test_salesorder_str(self, sales_order_a, customer_a):
        s = str(sales_order_a)
        assert sales_order_a.number in s
        assert customer_a.name in s

    def test_salesorder_str_without_a_customer_falls_back_to_placeholder(self, tenant_a):
        from apps.scm.models import SalesOrder
        order = SalesOrder(tenant=tenant_a)
        assert str(order) == "SO · ?"

    def test_salesorderline_str_with_item(self, sales_order_a, item_a):
        line = sales_order_a.lines.first()
        assert str(line) == f"{item_a.sku} ×{line.quantity_ordered}"
        assert str(line).startswith("WIDGET-1 ×10")

    def test_salesorderline_str_unmapped_uses_description(self, sales_order_a):
        from apps.scm.models import SalesOrderLine
        line = SalesOrderLine.objects.create(sales_order=sales_order_a, item=None,
                                             description="From a quote", quantity_ordered=Decimal("1"))
        assert str(line) == "From a quote ×1"

    def test_salesorderline_str_unmapped_with_no_description_falls_back(self, sales_order_a):
        from apps.scm.models import SalesOrderLine
        line = SalesOrderLine.objects.create(sales_order=sales_order_a, item=None, quantity_ordered=Decimal("1"))
        assert str(line) == "unmapped ×1"

    def test_salesorderallocation_str(self, allocation_a, location_a):
        assert str(allocation_a) == f"{allocation_a.quantity} @ {location_a.code}"


# ================================================================ SalesOrder properties
class TestSalesOrderProperties:
    def test_is_editable_true_only_while_draft(self, sales_order_a):
        assert sales_order_a.is_editable is True
        sales_order_a.status = "submitted"
        assert sales_order_a.is_editable is False

    def test_is_closed_true_cancelled_and_closed(self, sales_order_a):
        for status in ("cancelled", "closed"):
            sales_order_a.status = status
            assert sales_order_a.is_closed is True
        sales_order_a.status = "submitted"
        assert sales_order_a.is_closed is False

    def test_is_held_true_when_either_flag_is_set(self, sales_order_a):
        assert sales_order_a.is_held is False
        sales_order_a.credit_hold = True
        assert sales_order_a.is_held is True
        sales_order_a.credit_hold = False
        sales_order_a.fraud_flag = True
        assert sales_order_a.is_held is True


# ================================================================ SalesOrderLine.is_unmapped
class TestSalesOrderLineIsUnmapped:
    def test_true_without_an_item(self, sales_order_a):
        from apps.scm.models import SalesOrderLine
        line = SalesOrderLine.objects.create(sales_order=sales_order_a, item=None, description="x",
                                             quantity_ordered=Decimal("1"))
        assert line.is_unmapped is True

    def test_false_with_an_item(self, sales_order_a):
        line = sales_order_a.lines.first()
        assert line.is_unmapped is False


# ================================================================================================
# Derived money — recalc_totals / line_subtotal / line_tax / line_total (priority 5)
# ================================================================================================
class TestSalesOrderRecalcTotals:
    def test_discount_and_tax_produce_exact_decimals_not_integer_truncated(
        self, tenant_a, sales_order_a, item_a,
    ):
        """`recalc_totals` sums lines in PYTHON specifically to avoid the F()-expression
        integer-division trap on SQLite (see the model docstring) — this pins the exact figures."""
        from apps.scm.models import SalesOrderLine
        sales_order_a.lines.all().delete()
        line = SalesOrderLine.objects.create(
            sales_order=sales_order_a, item=item_a, quantity_ordered=Decimal("7"),
            unit_price=Decimal("9.99"), discount_pct=Decimal("15"), tax_pct=Decimal("5"),
        )
        assert line.line_subtotal == Decimal("59.4405")
        assert line.line_tax == Decimal("2.972025")
        assert line.line_total == Decimal("62.412525")
        sales_order_a.recalc_totals()
        sales_order_a.refresh_from_db()
        assert sales_order_a.subtotal == Decimal("59.44")
        assert sales_order_a.tax_total == Decimal("2.97")
        assert sales_order_a.total == Decimal("62.41")

    def test_multiple_lines_are_summed(self, tenant_a, sales_order_a, item_a):
        from apps.scm.models import SalesOrderLine
        SalesOrderLine.objects.create(sales_order=sales_order_a, item=item_a, quantity_ordered=Decimal("2"),
                                      unit_price=Decimal("50.00"))
        total = sales_order_a.recalc_totals()
        assert total == Decimal("250.00")  # 10x15 + 2x50


class TestSalesOrderLineDerivedQuantities:
    def test_quantity_allocated_counts_reserved_and_released_not_cancelled(
        self, tenant_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("3"))
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("2"), status="released")
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("1"), status="cancelled")
        assert sales_order_line_a.quantity_allocated() == Decimal("5")  # 3 reserved + 2 released

    def test_quantity_backordered_and_is_backordered(self, tenant_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("4"))
        assert sales_order_line_a.quantity_backordered() == Decimal("6")  # ordered 10 - 4
        assert sales_order_line_a.is_backordered is True

    def test_fully_allocated_line_is_not_backordered(self, tenant_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("10"))
        assert sales_order_line_a.quantity_backordered() == Decimal("0")
        assert sales_order_line_a.is_backordered is False

    def test_no_allocations_at_all_is_zero(self, sales_order_line_a):
        assert sales_order_line_a.quantity_allocated() == Decimal("0")
        assert sales_order_line_a.quantity_backordered() == Decimal("10")


# ================================================================================================
# SalesOrderAllocation.clean() — never promise more of a line than was ordered (priority 3)
# ================================================================================================
class TestSalesOrderAllocationClean:
    def test_blocks_allocating_more_than_ordered(self, tenant_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        alloc = SalesOrderAllocation(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                     location=location_a, quantity=Decimal("11"))  # ordered 10
        with pytest.raises(ValidationError):
            alloc.clean()

    def test_allows_up_to_the_full_ordered_quantity(self, tenant_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        alloc = SalesOrderAllocation(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                     location=location_a, quantity=Decimal("10"))
        alloc.clean()  # must not raise

    def test_counts_existing_active_allocations_against_the_cap(
        self, tenant_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("6"))
        second = SalesOrderAllocation(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                      location=location_a, quantity=Decimal("5"))  # 6 + 5 > 10
        with pytest.raises(ValidationError):
            second.clean()

    def test_excludes_self_on_edit(self, tenant_a, sales_order_line_a, location_a):
        """Re-cleaning an existing row with the SAME quantity must not double-count itself."""
        from apps.scm.models import SalesOrderAllocation
        alloc = SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                                    location=location_a, quantity=Decimal("10"))
        alloc.notes = "no quantity change"
        alloc.clean()  # must not raise

    def test_ignores_cancelled_allocations_when_summing_room(
        self, tenant_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("8"), status="cancelled")
        alloc = SalesOrderAllocation(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                     location=location_a, quantity=Decimal("10"))
        alloc.clean()  # the cancelled 8 doesn't count against the cap


class TestSalesOrderAllocationProperties:
    def test_is_active_true_for_reserved_and_released(self, allocation_a):
        assert allocation_a.is_active is True
        allocation_a.status = "released"
        assert allocation_a.is_active is True

    def test_is_active_false_once_cancelled(self, allocation_a):
        allocation_a.status = "cancelled"
        assert allocation_a.is_active is False

    def test_sales_order_property_traverses_the_line(self, allocation_a, sales_order_submitted_a):
        assert allocation_a.sales_order == sales_order_submitted_a


# ================================================================================================
# recompute_allocation_status — the workflow-status derivation (priority 2)
# ================================================================================================
class TestRecomputeAllocationStatus:
    def test_no_allocations_stays_submitted(self, sales_order_submitted_a):
        assert sales_order_submitted_a.recompute_allocation_status() == "submitted"

    def test_partial_allocation_moves_to_partially_fulfilled(
        self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("4"))
        assert sales_order_submitted_a.recompute_allocation_status() == "partially_fulfilled"

    def test_full_allocation_moves_to_allocated_and_stamps_promised_date(
        self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        assert sales_order_submitted_a.promised_date is None
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("10"))
        assert sales_order_submitted_a.recompute_allocation_status() == "allocated"
        sales_order_submitted_a.refresh_from_db()
        assert sales_order_submitted_a.promised_date is not None

    def test_promised_date_not_moved_by_a_later_recompute(
        self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("10"))
        sales_order_submitted_a.recompute_allocation_status()
        sales_order_submitted_a.refresh_from_db()
        first_promised = sales_order_submitted_a.promised_date
        sales_order_submitted_a.recompute_allocation_status()
        sales_order_submitted_a.refresh_from_db()
        assert sales_order_submitted_a.promised_date == first_promised

    @pytest.mark.parametrize("terminal_status", [
        "draft", "on_hold", "fulfilled", "invoiced", "cancelled", "closed",
    ])
    def test_leaves_non_allocatable_statuses_untouched(
        self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a, terminal_status,
    ):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("10"))
        sales_order_submitted_a.status = terminal_status
        sales_order_submitted_a.save(update_fields=["status", "updated_at"])
        assert sales_order_submitted_a.recompute_allocation_status() == terminal_status
        sales_order_submitted_a.refresh_from_db()
        assert sales_order_submitted_a.status == terminal_status


# ================================================================================================
# Priority regression 1c — recompute_allocation_status / _atp_rows query-count locks
# ================================================================================================
class TestRecomputeAllocationStatusQueryCountRegression:
    """ONE grouped aggregate over every line, not one aggregate per line — the cost at 6 lines
    must equal the cost at 12 lines."""

    def test_cost_is_flat_across_line_count(self, tenant_a, customer_a, item_a):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.scm.models import SalesOrder, SalesOrderLine

        def _submitted_order(n_lines):
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=datetime.date(2026, 1, 5))
            for _ in range(n_lines):
                SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                              unit_price=Decimal("1"))
            order.recalc_totals()
            order.status = "submitted"
            order.save(update_fields=["status", "updated_at"])
            return order

        six = _submitted_order(6)
        with CaptureQueriesContext(connection) as ctx6:
            six.recompute_allocation_status()
        twelve = _submitted_order(12)
        with CaptureQueriesContext(connection) as ctx12:
            twelve.recompute_allocation_status()
        assert len(ctx6.captured_queries) == len(ctx12.captured_queries)


class TestAtpRowsQueryCountRegression:
    """THREE queries total regardless of location count — the cost at 1 pickable location must
    equal the cost at 6."""

    def test_cost_is_flat_across_location_count(self, tenant_a, item_a, location_a):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.scm.models import Location
        from apps.scm.views.OrderManagement.SalesOrderAllocations import _atp_rows

        with CaptureQueriesContext(connection) as ctx1:
            _atp_rows(tenant_a, item_a)
        one_location_cost = len(ctx1.captured_queries)
        for i in range(5):
            Location.objects.create(tenant=tenant_a, code=f"ATPX-{i}", name=f"ATP extra {i}", is_pickable=True)
        with CaptureQueriesContext(connection) as ctx6:
            _atp_rows(tenant_a, item_a)
        six_location_cost = len(ctx6.captured_queries)
        assert one_location_cost == six_location_cost


# ================================================================================================
# Priority regression 1d — has_active_allocations must actually run (once raised NameError)
# ================================================================================================
class TestHasActiveAllocationsRegression:
    def test_false_with_no_allocations(self, sales_order_submitted_a):
        assert sales_order_submitted_a.has_active_allocations() is False

    def test_true_while_reserved(self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("2"))
        assert sales_order_submitted_a.has_active_allocations() is True

    def test_true_while_released(self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("2"), status="released")
        assert sales_order_submitted_a.has_active_allocations() is True

    def test_false_once_cancelled(self, tenant_a, sales_order_submitted_a, sales_order_line_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=sales_order_line_a,
                                            location=location_a, quantity=Decimal("2"), status="cancelled")
        assert sales_order_submitted_a.has_active_allocations() is False


# ================================================================================================
# SCM 4.6 Transportation Management System
# ================================================================================================

# ================================================================ Auto-numbering
class TestTMSAutoNumbering:
    def test_carrier_numbers_prefixed_car_and_sequential_per_tenant(
        self, tenant_a, tenant_b, carrier_party_a, carrier_party_b,
    ):
        from apps.scm.models import Carrier
        c1 = Carrier.objects.create(tenant=tenant_a, party=carrier_party_a)
        c2 = Carrier.objects.create(tenant=tenant_a, party=carrier_party_a)
        c3 = Carrier.objects.create(tenant=tenant_b, party=carrier_party_b)
        assert c1.number == "CAR-00001"
        assert c2.number == "CAR-00002"
        assert c3.number == "CAR-00001"  # separate per-tenant sequence

    def test_carrier_number_unique_together(self, tenant_a, carrier_party_a):
        from apps.scm.models import Carrier
        c1 = Carrier.objects.create(tenant=tenant_a, party=carrier_party_a)
        with pytest.raises(IntegrityError):
            Carrier.objects.create(tenant=tenant_a, party=carrier_party_a, number=c1.number)

    def test_load_numbers_prefixed_ld_and_sequential_per_tenant(self, tenant_a, tenant_b):
        from apps.scm.models import Load
        l1 = Load.objects.create(tenant=tenant_a)
        l2 = Load.objects.create(tenant=tenant_a)
        l3 = Load.objects.create(tenant=tenant_b)
        assert l1.number == "LD-00001"
        assert l2.number == "LD-00002"
        assert l3.number == "LD-00001"

    def test_shipment_numbers_prefixed_shp_and_sequential_per_tenant(self, tenant_a, tenant_b):
        from apps.scm.models import Shipment
        s1 = Shipment.objects.create(tenant=tenant_a)
        s2 = Shipment.objects.create(tenant=tenant_a)
        s3 = Shipment.objects.create(tenant=tenant_b)
        assert s1.number == "SHP-00001"
        assert s2.number == "SHP-00002"
        assert s3.number == "SHP-00001"

    def test_freightinvoice_numbers_prefixed_frt_and_sequential_per_tenant(
        self, tenant_a, tenant_b, carrier_a, carrier_b,
    ):
        from apps.scm.models import FreightInvoice
        f1 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        f2 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        f3 = FreightInvoice.objects.create(tenant=tenant_b, carrier=carrier_b)
        assert f1.number == "FRT-00001"
        assert f2.number == "FRT-00002"
        assert f3.number == "FRT-00001"


# ================================================================ __str__
class TestTMSStrRepresentations:
    def test_carrier_str_includes_number_and_party_name(self, carrier_a, carrier_party_a):
        s = str(carrier_a)
        assert carrier_a.number in s
        assert carrier_party_a.name in s

    def test_load_str_includes_number_origin_and_destination(self, load_a):
        s = str(load_a)
        assert load_a.number in s
        assert "Chicago, IL" in s
        assert "Dallas, TX" in s

    def test_shipment_str_includes_number_and_direction(self, shipment_a):
        s = str(shipment_a)
        assert shipment_a.number in s
        assert "Outbound" in s

    def test_freightinvoice_str_includes_number_and_carrier_name(self, freight_invoice_a, carrier_a):
        s = str(freight_invoice_a)
        assert freight_invoice_a.number in s
        assert carrier_a.name in s

    def test_loadstop_str(self, load_a):
        from apps.scm.models import LoadStop
        stop = LoadStop.objects.create(load=load_a, sequence=1, stop_type="pickup", address_text="Dock 3")
        assert str(stop) == "#1 Pickup · Dock 3"

    def test_trackingevent_str(self, shipment_a):
        from apps.scm.models import TrackingEvent
        from django.utils import timezone
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup",
                                             event_at=timezone.now())
        assert str(event).startswith("Picked Up @")

    def test_carrierratecard_str(self, carrier_a):
        from apps.scm.models import CarrierRateCard
        card = CarrierRateCard.objects.create(carrier=carrier_a, lane_name="Chicago → Dallas",
                                              mode="truckload")
        assert str(card) == "Chicago → Dallas (Full Truckload (FTL))"

    def test_freightinvoiceline_str(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        line = FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, charge_type="fuel_surcharge",
                                                  billed_amount=Decimal("50.00"))
        assert str(line) == "Fuel Surcharge · 50.00"


# ================================================================ Carrier properties
class TestCarrierProperties:
    def test_name_comes_from_the_party(self, carrier_a, carrier_party_a):
        assert carrier_a.name == carrier_party_a.name

    def test_name_blank_without_a_party(self, tenant_a):
        from apps.scm.models import Carrier
        carrier = Carrier(tenant=tenant_a)
        assert carrier.name == ""

    def test_is_active_true_only_when_status_active(self, carrier_a):
        assert carrier_a.is_active is True
        carrier_a.status = "suspended"
        assert carrier_a.is_active is False

    def test_insurance_expired_false_without_a_date(self, carrier_a):
        assert carrier_a.insurance_expired is False

    def test_insurance_expired_true_for_a_past_date(self, carrier_a):
        from django.utils import timezone
        carrier_a.insurance_certificate_expiry = timezone.localdate() - datetime.timedelta(days=1)
        assert carrier_a.insurance_expired is True

    def test_insurance_expired_false_for_a_future_date(self, carrier_a):
        from django.utils import timezone
        carrier_a.insurance_certificate_expiry = timezone.localdate() + datetime.timedelta(days=1)
        assert carrier_a.insurance_expired is False


class TestCarrierRateCardProperties:
    def test_rate_with_fuel_grosses_up_the_base_rate(self, carrier_a):
        from apps.scm.models import CarrierRateCard
        card = CarrierRateCard.objects.create(carrier=carrier_a, base_rate=Decimal("1000.00"),
                                              fuel_surcharge_pct=Decimal("10.00"))
        assert card.rate_with_fuel == Decimal("1100.000")

    def test_rate_with_fuel_with_no_surcharge_equals_base_rate(self, carrier_a):
        from apps.scm.models import CarrierRateCard
        card = CarrierRateCard.objects.create(carrier=carrier_a, base_rate=Decimal("500.00"))
        assert card.rate_with_fuel == Decimal("500.000")


# ================================================================================================
# Carrier.recompute_scorecard — derived on-time-delivery %, never a phantom-zero wipe
# ================================================================================================
class TestCarrierRecomputeScorecard:
    def test_mixed_on_time_and_late_delivered_shipments_set_the_right_pct(self, tenant_a, carrier_a):
        from django.utils import timezone
        from apps.scm.models import Shipment
        # 2 on-time (delivered on/before planned) + 1 late = 66.67%
        Shipment.objects.create(
            tenant=tenant_a, carrier=carrier_a, status="delivered",
            planned_delivery_date=datetime.date(2026, 1, 10),
            actual_delivery_at=timezone.make_aware(datetime.datetime(2026, 1, 9, 12, 0)),
        )
        Shipment.objects.create(
            tenant=tenant_a, carrier=carrier_a, status="delivered",
            planned_delivery_date=datetime.date(2026, 1, 10),
            actual_delivery_at=timezone.make_aware(datetime.datetime(2026, 1, 10, 12, 0)),
        )
        Shipment.objects.create(
            tenant=tenant_a, carrier=carrier_a, status="delivered",
            planned_delivery_date=datetime.date(2026, 1, 10),
            actual_delivery_at=timezone.make_aware(datetime.datetime(2026, 1, 12, 12, 0)),
        )
        pct = carrier_a.recompute_scorecard()
        assert pct == Decimal("66.67")
        carrier_a.refresh_from_db()
        assert carrier_a.on_time_delivery_pct == Decimal("66.67")
        assert "2/3" in carrier_a.performance_summary

    def test_undated_delivered_shipments_never_drag_the_score(self, tenant_a, carrier_a):
        """A delivered shipment missing a planned date (or an actual-delivery stamp) must not count
        toward the denominator — only datable, delivered shipments are scored."""
        from django.utils import timezone
        from apps.scm.models import Shipment
        Shipment.objects.create(tenant=tenant_a, carrier=carrier_a, status="delivered")  # no dates at all
        Shipment.objects.create(
            tenant=tenant_a, carrier=carrier_a, status="delivered",
            planned_delivery_date=datetime.date(2026, 1, 10),
            actual_delivery_at=timezone.make_aware(datetime.datetime(2026, 1, 9, 12, 0)),
        )
        pct = carrier_a.recompute_scorecard()
        assert pct == Decimal("100.00")
        assert "1/1" in carrier_a.performance_summary

    def test_no_delivered_shipments_leaves_the_score_untouched(self, tenant_a, carrier_a):
        """No signal yet must never zero out a previously-derived score (no phantom-zero wipe)."""
        carrier_a.on_time_delivery_pct = Decimal("77.00")
        carrier_a.performance_summary = "A prior score"
        carrier_a.save(update_fields=["on_time_delivery_pct", "performance_summary"])
        result = carrier_a.recompute_scorecard()
        assert result == Decimal("77.00")
        carrier_a.refresh_from_db()
        assert carrier_a.on_time_delivery_pct == Decimal("77.00")
        assert carrier_a.performance_summary == "No delivered shipments with a planned date yet."


# ================================================================ Load properties + utilization
class TestLoadProperties:
    def test_is_editable_true_while_planning_or_tendered(self, load_a):
        assert load_a.is_editable is True
        load_a.status = "tendered"
        assert load_a.is_editable is True
        load_a.status = "booked"
        assert load_a.is_editable is False

    def test_is_closed_true_delivered_and_cancelled(self, load_a):
        for status in ("delivered", "cancelled"):
            load_a.status = status
            assert load_a.is_closed is True
        load_a.status = "in_transit"
        assert load_a.is_closed is False


class TestLoadUtilization:
    def test_weight_and_volume_utilization_pct_from_assigned_shipments(self, tenant_a, load_a, carrier_a):
        from apps.scm.models import Shipment
        load_a.equipment_capacity_weight_kg = Decimal("1000.00")
        load_a.equipment_capacity_volume_cbm = Decimal("10.000")
        load_a.save(update_fields=["equipment_capacity_weight_kg", "equipment_capacity_volume_cbm"])
        Shipment.objects.create(tenant=tenant_a, carrier=carrier_a, load=load_a,
                                weight_kg=Decimal("300.00"), volume_cbm=Decimal("2.000"))
        Shipment.objects.create(tenant=tenant_a, carrier=carrier_a, load=load_a,
                                weight_kg=Decimal("200.00"), volume_cbm=Decimal("1.000"))
        assert load_a.weight_utilization_pct() == Decimal("50.0")
        assert load_a.volume_utilization_pct() == Decimal("30.0")

    def test_utilization_accepts_a_precomputed_planned_total(self, load_a):
        load_a.equipment_capacity_weight_kg = Decimal("1000.00")
        assert load_a.weight_utilization_pct(Decimal("250")) == Decimal("25.0")

    def test_utilization_returns_none_when_capacity_is_none(self, load_a):
        load_a.equipment_capacity_weight_kg = None
        load_a.equipment_capacity_volume_cbm = None
        assert load_a.weight_utilization_pct() is None
        assert load_a.volume_utilization_pct() is None

    def test_utilization_returns_none_when_capacity_is_zero(self, load_a):
        load_a.equipment_capacity_weight_kg = Decimal("0")
        load_a.equipment_capacity_volume_cbm = Decimal("0")
        assert load_a.weight_utilization_pct() is None
        assert load_a.volume_utilization_pct() is None

    def test_planned_weight_and_volume_are_zero_with_no_shipments(self, load_a):
        assert load_a.planned_weight_kg() == Decimal("0")
        assert load_a.planned_volume_cbm() == Decimal("0")


# ================================================================ Shipment properties
class TestShipmentProperties:
    def test_is_editable_true_while_planned_or_booked(self, shipment_a):
        assert shipment_a.is_editable is True
        shipment_a.status = "booked"
        assert shipment_a.is_editable is True
        shipment_a.status = "in_transit"
        assert shipment_a.is_editable is False

    def test_is_closed_true_delivered_and_cancelled(self, shipment_a):
        for status in ("delivered", "cancelled"):
            shipment_a.status = status
            assert shipment_a.is_closed is True
        shipment_a.status = "exception"
        assert shipment_a.is_closed is False

    def test_is_delayed_true_past_planned_delivery_while_still_moving(self, shipment_a):
        from django.utils import timezone
        shipment_a.planned_delivery_date = timezone.localdate() - datetime.timedelta(days=1)
        shipment_a.status = "in_transit"
        assert shipment_a.is_delayed is True

    def test_is_delayed_false_once_delivered(self, shipment_a):
        from django.utils import timezone
        shipment_a.planned_delivery_date = timezone.localdate() - datetime.timedelta(days=1)
        shipment_a.status = "delivered"
        assert shipment_a.is_delayed is False

    def test_is_delayed_false_without_a_planned_date(self, shipment_a):
        shipment_a.planned_delivery_date = None
        shipment_a.status = "in_transit"
        assert shipment_a.is_delayed is False


# ================================================================================================
# Shipment.apply_tracking_event — the event projects onto the shipment's summary/status fields
# ================================================================================================
class TestShipmentApplyTrackingEvent:
    def test_pickup_event_moves_booked_shipment_to_in_transit_and_stamps_pickup_once(
        self, tenant_a, shipment_a,
    ):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        shipment_a.status = "booked"
        shipment_a.save(update_fields=["status"])
        t1 = timezone.now()
        event1 = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup", event_at=t1)
        shipment_a.apply_tracking_event(event1)
        assert shipment_a.status == "in_transit"
        assert shipment_a.actual_pickup_at == t1

        # A second pickup event must not re-stamp the actual pickup time.
        t2 = t1 + datetime.timedelta(hours=3)
        event2 = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup", event_at=t2)
        shipment_a.apply_tracking_event(event2)
        assert shipment_a.actual_pickup_at == t1

    def test_delivered_event_closes_the_shipment_and_stamps_delivery(self, tenant_a, shipment_a):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        t = timezone.now()
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="delivered", event_at=t)
        shipment_a.apply_tracking_event(event)
        assert shipment_a.status == "delivered"
        assert shipment_a.actual_delivery_at == t

    def test_pod_signed_event_also_records_proof_of_delivery(self, tenant_a, shipment_a):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        t = timezone.now()
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="pod_signed", event_at=t)
        shipment_a.apply_tracking_event(event)
        assert shipment_a.status == "delivered"
        assert shipment_a.pod_received is True
        assert shipment_a.pod_received_at == t

    def test_exception_event_flags_the_shipment(self, tenant_a, shipment_a):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="exception",
                                             event_at=timezone.now())
        shipment_a.apply_tracking_event(event)
        assert shipment_a.status == "exception"

    def test_event_on_a_delivered_shipment_is_recorded_but_status_is_not_dragged_backwards(
        self, tenant_a, shipment_a,
    ):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        shipment_a.status = "delivered"
        shipment_a.actual_delivery_at = timezone.now()
        shipment_a.save(update_fields=["status", "actual_delivery_at"])
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="exception",
                                             event_at=timezone.now())
        shipment_a.apply_tracking_event(event)
        assert shipment_a.status == "delivered"  # terminal-state guard
        assert shipment_a.current_status_text == event.get_event_type_display()

    def test_event_on_a_cancelled_shipment_does_not_change_status_or_stamp_pickup(
        self, tenant_a, shipment_a,
    ):
        from django.utils import timezone
        from apps.scm.models import TrackingEvent
        shipment_a.status = "cancelled"
        shipment_a.save(update_fields=["status"])
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup",
                                             event_at=timezone.now())
        shipment_a.apply_tracking_event(event)
        assert shipment_a.status == "cancelled"
        assert shipment_a.actual_pickup_at is None


# ================================================================ FreightInvoice properties
class TestFreightInvoiceProperties:
    def test_is_editable_true_while_pending_and_not_handed_off(self, freight_invoice_a):
        assert freight_invoice_a.is_editable is True
        freight_invoice_a.approval_status = "approved"
        assert freight_invoice_a.is_editable is False

    def test_is_over_billed_true_only_for_a_positive_variance(self, freight_invoice_a):
        freight_invoice_a.variance_amount = Decimal("10.00")
        assert freight_invoice_a.is_over_billed is True
        freight_invoice_a.variance_amount = Decimal("-10.00")
        assert freight_invoice_a.is_over_billed is False
        freight_invoice_a.variance_amount = Decimal("0.00")
        assert freight_invoice_a.is_over_billed is False


# ================================================================================================
# FreightInvoice.recalc_amounts — sums billed/contract from lines in Python
# ================================================================================================
class TestFreightInvoiceRecalcAmounts:
    def test_recalc_sums_billed_and_contract_and_derives_variance(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, charge_type="linehaul",
                                          billed_amount=Decimal("500.00"), contract_amount=Decimal("480.00"))
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, charge_type="fuel_surcharge",
                                          billed_amount=Decimal("50.00"), contract_amount=Decimal("50.00"))
        freight_invoice_a.recalc_amounts()
        assert freight_invoice_a.billed_amount == Decimal("550.00")
        assert freight_invoice_a.contract_amount == Decimal("530.00")
        assert freight_invoice_a.variance_amount == Decimal("20.00")
        assert freight_invoice_a.variance_pct == Decimal("3.77")

    def test_recalc_with_zero_contract_leaves_variance_pct_none(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a,
                                          billed_amount=Decimal("100.00"), contract_amount=Decimal("0"))
        freight_invoice_a.recalc_amounts()
        assert freight_invoice_a.variance_pct is None

    def test_recalc_with_no_lines_is_all_zero(self, freight_invoice_a):
        freight_invoice_a.recalc_amounts()
        assert freight_invoice_a.billed_amount == Decimal("0")
        assert freight_invoice_a.contract_amount == Decimal("0")
        assert freight_invoice_a.variance_amount == Decimal("0")


# ================================================================================================
# FreightInvoice.run_audit — the freight three-way-adjacent match verdict
# ================================================================================================
class TestFreightInvoiceRunAudit:
    def test_within_tolerance_is_matched(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a,
                                          billed_amount=Decimal("510.00"), contract_amount=Decimal("500.00"))
        status = freight_invoice_a.run_audit()
        assert status == "matched"
        assert freight_invoice_a.match_status == "matched"

    def test_outside_tolerance_is_price_variance(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a,
                                          billed_amount=Decimal("600.00"), contract_amount=Decimal("500.00"))
        status = freight_invoice_a.run_audit()
        assert status == "price_variance"

    def test_zero_contract_amount_is_not_matched(self, freight_invoice_a):
        status = freight_invoice_a.run_audit()  # no lines -> contract_amount stays 0
        assert status == "not_matched"

    def test_second_invoice_with_the_same_carrier_and_invoice_number_is_flagged_duplicate(
        self, tenant_a, carrier_a,
    ):
        from apps.scm.models import FreightInvoice, FreightInvoiceLine
        inv1 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a,
                                             carrier_invoice_number="CARR-INV-100")
        FreightInvoiceLine.objects.create(freight_invoice=inv1, billed_amount=Decimal("100"),
                                          contract_amount=Decimal("100"))
        assert inv1.run_audit() == "matched"

        inv2 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a,
                                             carrier_invoice_number="CARR-INV-100")
        FreightInvoiceLine.objects.create(freight_invoice=inv2, billed_amount=Decimal("100"),
                                          contract_amount=Decimal("100"))
        assert inv2.run_audit() == "duplicate"

    def test_blank_carrier_invoice_number_never_triggers_the_duplicate_check(self, tenant_a, carrier_a):
        from apps.scm.models import FreightInvoice, FreightInvoiceLine
        inv1 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        FreightInvoiceLine.objects.create(freight_invoice=inv1, billed_amount=Decimal("100"),
                                          contract_amount=Decimal("100"))
        inv1.run_audit()
        inv2 = FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        FreightInvoiceLine.objects.create(freight_invoice=inv2, billed_amount=Decimal("100"),
                                          contract_amount=Decimal("100"))
        assert inv2.run_audit() == "matched"

    def test_disputed_invoice_stays_disputed_even_when_back_within_tolerance(self, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a,
                                          billed_amount=Decimal("500.00"), contract_amount=Decimal("500.00"))
        freight_invoice_a.match_status = "disputed"
        freight_invoice_a.dispute_reason = "carrier overcharged on a prior audit"
        freight_invoice_a.save(update_fields=["match_status", "dispute_reason"])
        status = freight_invoice_a.run_audit()
        assert status == "disputed"


# ================================================================================================
# SCM 4.7 Demand Planning & Forecasting
# ================================================================================================

# ================================================================ Auto-numbering
class TestDemandPlanningAutoNumbering:
    def test_seasonality_profile_numbers_sequential_per_tenant(self, tenant_a, tenant_b):
        from apps.scm.models import SeasonalityProfile
        p1 = SeasonalityProfile.objects.create(tenant=tenant_a, name="One")
        p2 = SeasonalityProfile.objects.create(tenant=tenant_a, name="Two")
        p3 = SeasonalityProfile.objects.create(tenant=tenant_b, name="Globex one")
        assert (p1.number, p2.number, p3.number) == ("SEA-00001", "SEA-00002", "SEA-00001")

    def test_demand_forecast_numbers_prefixed_df(self, tenant_a, demand_forecast_a):
        assert demand_forecast_a.number == "DF-00001"

    def test_demand_signal_numbers_prefixed_ds(self, tenant_a, demand_signal_a):
        assert demand_signal_a.number == "DS-00001"

    def test_forecast_adjustment_numbers_prefixed_fa(self, tenant_a, forecast_adjustment_a):
        assert forecast_adjustment_a.number == "FA-00001"

    def test_demand_forecast_number_unique_together_with_tenant(self, tenant_a, demand_forecast_a):
        from apps.scm.models import DemandForecast
        with pytest.raises(IntegrityError):
            DemandForecast.objects.create(
                tenant=tenant_a, name="Dup", item=demand_forecast_a.item,
                horizon_start=demand_forecast_a.horizon_start,
                horizon_end=demand_forecast_a.horizon_end, number=demand_forecast_a.number,
            )

    def test_seasonality_index_unique_together_with_profile(self, seasonality_profile_a):
        from apps.scm.models import SeasonalityIndex
        with pytest.raises(IntegrityError):
            SeasonalityIndex.objects.create(profile=seasonality_profile_a, period_number=1)

    def test_forecast_period_unique_together_with_forecast(self, forecast_with_periods_a):
        from apps.scm.models import DemandForecastPeriod
        row = forecast_with_periods_a.periods.first()
        with pytest.raises(IntegrityError):
            DemandForecastPeriod.objects.create(
                forecast=forecast_with_periods_a, sequence=row.sequence,
                period_start=row.period_start, period_end=row.period_end,
            )


# ================================================================ __str__
class TestDemandPlanningStrRepresentations:
    def test_seasonality_profile_str(self, seasonality_profile_a):
        assert str(seasonality_profile_a) == "SEA-00001 · Widget seasonality"

    def test_seasonality_index_str(self, seasonality_profile_a):
        row = seasonality_profile_a.indices.get(period_number=12)
        assert str(row) == "P12 × 1.5000"

    def test_demand_forecast_str_carries_the_item_sku(self, demand_forecast_a, item_a):
        assert str(demand_forecast_a) == f"DF-00001 · {item_a.sku}"

    def test_demand_forecast_str_survives_a_missing_item(self, tenant_a):
        from apps.scm.models import DemandForecast
        obj = DemandForecast(tenant=tenant_a, name="No item", number="DF-00099",
                             horizon_start=datetime.date(2026, 1, 1),
                             horizon_end=datetime.date(2026, 3, 31))
        assert str(obj) == "DF-00099 · ?"

    def test_forecast_period_str(self, forecast_period_a):
        assert forecast_period_a.period_label in str(forecast_period_a)

    def test_demand_signal_str_names_the_item(self, demand_signal_a, item_a):
        assert str(demand_signal_a) == f"DS-00001 · Order Surge · {item_a.sku}"

    def test_demand_signal_str_falls_back_to_category_then_network(self, tenant_a, category_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        by_category = DemandSignal.objects.create(tenant=tenant_a, category=category_a,
                                                  observed_at=timezone.now())
        network = DemandSignal.objects.create(tenant=tenant_a, observed_at=timezone.now())
        assert str(by_category).endswith(category_a.name)
        assert str(network).endswith("network")

    def test_forecast_adjustment_str(self, forecast_adjustment_a):
        assert str(forecast_adjustment_a) == "FA-00001 · Sales"


# ================================================================================================
# _forecasting.py — the pure Decimal statistical library (zero ORM)
# ================================================================================================
class TestForecastingEngineContracts:
    """Every engine returns EXACTLY ``horizon`` values and degrades safely on a short/empty series."""

    ENGINES = ("naive", "seasonal_naive", "moving_average", "weighted_moving_average",
               "exponential_smoothing", "holt_linear", "holt_winters")

    def test_every_engine_returns_exactly_horizon_values(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 12, 14, 20, 30, 40, 50, 45, 30, 20, 15, 12)]
        for name in self.ENGINES:
            values = fx.run_method(name, series, 5)
            assert len(values) == 5, name
            assert all(isinstance(v, Decimal) for v in values), name

    def test_every_engine_survives_an_empty_series(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        for name in self.ENGINES:
            assert fx.run_method(name, [], 4) == [Decimal("0")] * 4, name

    def test_every_engine_survives_a_one_point_series(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        for name in self.ENGINES:
            assert len(fx.run_method(name, [Decimal("7")], 3)) == 3, name

    def test_run_method_with_a_zero_horizon_returns_an_empty_list(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.run_method("naive", [Decimal("5")], 0) == []

    def test_unknown_method_falls_back_to_moving_average(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (1, 2, 3, 4)]
        assert fx.run_method("no_such_engine", series, 2) == fx.moving_average(series, 2, 3)

    def test_naive_repeats_the_last_observation(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.naive([Decimal(1), Decimal(9)], 3) == [Decimal(9)] * 3

    def test_seasonal_naive_repeats_one_full_season_back(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (1, 2, 3, 4)]
        assert fx.seasonal_naive(series, 4, period=4) == series

    def test_moving_average_is_the_mean_of_the_last_window(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (1, 2, 3, 4)]
        assert fx.moving_average(series, 2, window=3) == [Decimal(3), Decimal(3)]

    def test_weighted_moving_average_leans_on_the_most_recent_point(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (1, 2, 3)]
        # (1*1 + 2*2 + 3*3) / 6 = 2.333... — above the flat mean of 2.
        assert fx.weighted_moving_average(series, 1, window=3)[0] > fx.mean(series)

    def test_exponential_smoothing_clamps_an_out_of_range_alpha_to_the_default(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(1), Decimal(10)]
        default = fx.exponential_smoothing(series, 1, Decimal("0.3"))
        assert fx.exponential_smoothing(series, 1, Decimal("0")) == default
        assert fx.exponential_smoothing(series, 1, Decimal("7")) == default
        assert fx.exponential_smoothing(series, 1, Decimal("1")) == [Decimal(10)]

    def test_holt_linear_falls_back_to_naive_below_two_points(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.holt_linear([Decimal(5)], 3) == fx.naive([Decimal(5)], 3)

    def test_holt_linear_slopes_on_a_trending_series(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        values = fx.holt_linear([Decimal(v) for v in (10, 20, 30, 40)], 3)
        assert values[0] < values[1] < values[2]

    def test_holt_winters_falls_back_to_holt_linear_under_two_seasons(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in range(1, 13)]  # 12 points = one season of 12
        assert fx.holt_winters(series, 4, period=12) == fx.holt_linear(series, 4)

    def test_holt_winters_fits_a_season_with_two_full_seasons(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        season = [10, 12, 14, 20, 30, 40, 50, 45, 30, 20, 15, 12]
        values = fx.holt_winters([Decimal(v) for v in season * 2], 12, period=12)
        assert len(values) == 12
        assert len(set(values)) > 1  # a seasonal fit is NOT a flat line

    def test_std_dev_needs_two_points(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.std_dev([Decimal(5)]) == Decimal("0")
        assert fx.std_dev([Decimal(1), Decimal(3)]) > Decimal("0")

    def test_junk_values_coerce_to_zero_rather_than_raising(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.mean(["NaN-ish", None, Decimal(3)]) == Decimal(1)


class TestClipOutliers:
    def test_preserves_the_series_length(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 10, 10, 1000)]
        assert len(fx.clip_outliers(series, Decimal("1"))) == len(series)

    def test_clamps_a_spike_back_to_the_boundary(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 10, 10, 1000)]
        clipped = fx.clip_outliers(series, Decimal("1"))
        assert clipped[3] < Decimal("1000")
        assert clipped[:3] == series[:3]

    def test_a_short_series_is_returned_untouched(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(1), Decimal(500)]
        assert fx.clip_outliers(series) == series

    def test_a_non_positive_sigma_is_a_no_op(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 10, 10, 1000)]
        assert fx.clip_outliers(series, Decimal("0")) == series

    def test_a_flat_series_has_no_outliers_to_clip(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(10)] * 5
        assert fx.clip_outliers(series) == series


class TestBestFit:
    def test_returns_the_engine_with_the_lowest_out_of_sample_error(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)]
        name, values = fx.best_fit(series, 3)
        # A clean linear ramp: only the trend engines reproduce the held-out tail exactly.
        assert name == "holt_linear"
        assert len(values) == 3
        assert values[0] > series[-1]  # the trend keeps climbing past the history

    def test_the_winner_is_scored_on_the_holdout_not_on_the_full_series(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        series = [Decimal(v) for v in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)]
        holdout = min(max(len(series) // 4, 1), 6)
        train, actual = series[:-holdout], series[-holdout:]
        scores = {name: fx.mape(actual, fx.run_method(name, train, holdout))
                  for name in fx._FITTABLE}
        expected = min((n for n, e in scores.items() if e is not None), key=lambda n: scores[n])
        assert fx.best_fit(series, 3)[0] == expected

    def test_falls_back_to_moving_average_with_too_little_history(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        short = [Decimal(1), Decimal(2), Decimal(3)]
        name, values = fx.best_fit(short, 3)
        assert name == "moving_average"
        assert values == fx.moving_average(short, 3)

    def test_falls_back_to_moving_average_on_an_empty_series(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.best_fit([], 3) == ("moving_average", [Decimal("0")] * 3)

    def test_falls_back_when_every_engine_scores_undefined(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        # An all-zero holdout makes MAPE undefined for every engine, so nothing can win.
        name, values = fx.best_fit([Decimal("0")] * 8, 3)
        assert name == "moving_average"
        assert values == [Decimal("0")] * 3


class TestAccuracyMetricFunctions:
    def test_mape_is_none_when_every_actual_is_zero(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.mape([Decimal(0), Decimal(0)], [Decimal(1), Decimal(2)]) is None

    def test_mape_ignores_the_zero_actual_periods(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.mape([Decimal(100), Decimal(0)], [Decimal(80), Decimal(50)]) == Decimal(20)

    def test_wmape_is_none_when_the_denominator_is_zero(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.wmape([Decimal(0)], [Decimal(5)]) is None

    def test_wmape_survives_a_zero_demand_period(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        # Sum|a-f| = 20 + 50, Sum|a| = 100 -> 70 %.
        assert fx.wmape([Decimal(100), Decimal(0)], [Decimal(80), Decimal(50)]) == Decimal(70)

    def test_bias_pct_is_positive_when_the_forecast_ran_high(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.bias_pct([Decimal(100)], [Decimal(120)]) == Decimal(20)

    def test_bias_pct_is_none_when_actual_sums_to_zero(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.bias_pct([Decimal(0), Decimal(0)], [Decimal(5), Decimal(5)]) is None

    def test_tracking_signal_is_none_with_no_pairs(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.tracking_signal([], []) is None
        assert fx.tracking_signal([Decimal(5)], []) is None

    def test_tracking_signal_is_zero_when_the_forecast_was_exact(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.tracking_signal([Decimal(5)], [Decimal(5)]) == Decimal("0")

    def test_tracking_signal_flags_a_persistent_over_forecast(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.tracking_signal([Decimal(100)] * 5, [Decimal(120)] * 5) == Decimal(5)

    def test_forecast_value_added_is_positive_when_the_override_helped(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        # 100 % baseline error - 10 % final error = +90 points removed.
        assert fx.forecast_value_added([Decimal(10)], [Decimal(20)], [Decimal(11)]) == Decimal(90)

    def test_forecast_value_added_is_negative_when_the_override_hurt(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.forecast_value_added([Decimal(10)], [Decimal(11)], [Decimal(20)]) < Decimal(0)

    def test_forecast_value_added_is_none_when_either_side_is_undefined(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.forecast_value_added([Decimal(0)], [Decimal(1)], [Decimal(1)]) is None


class TestServiceLevelZTable:
    def test_maps_the_tabulated_levels(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.z_for_service_level(Decimal("50")) == Decimal("0.00")
        assert fx.z_for_service_level(Decimal("90")) == Decimal("1.28")
        assert fx.z_for_service_level(Decimal("95")) == Decimal("1.65")
        assert fx.z_for_service_level(Decimal("97.5")) == Decimal("1.96")
        assert fx.z_for_service_level(Decimal("99.9")) == Decimal("3.09")

    def test_an_untabulated_level_takes_the_nearest_level_at_or_below(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.z_for_service_level(Decimal("94")) == Decimal("1.41")  # the 92 row

    def test_below_the_table_and_above_it_both_stay_in_range(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.z_for_service_level(Decimal("10")) == Decimal("0.00")
        assert fx.z_for_service_level(Decimal("100")) == Decimal("3.09")

    def test_junk_input_degrades_to_the_floor_rather_than_raising(self):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        assert fx.z_for_service_level("not-a-number") == Decimal("0.00")


# ================================================================================================
# _history.py — the DERIVED demand series (there is deliberately NO stored history table)
# ================================================================================================
class TestPeriodCalendar:
    BUCKETS = ("day", "week", "month", "quarter")

    def test_period_count_matches_len_period_range_for_every_bucket(self):
        from apps.scm.models.DemandPlanning import _history as hist
        start, end = datetime.date(2026, 1, 15), datetime.date(2026, 7, 4)
        for bucket in self.BUCKETS:
            assert hist.period_count(start, end, bucket) == len(
                hist.period_range(start, end, bucket)), bucket

    def test_period_count_matches_len_period_range_across_a_year_boundary(self):
        from apps.scm.models.DemandPlanning import _history as hist
        start, end = datetime.date(2025, 11, 3), datetime.date(2026, 2, 27)
        for bucket in self.BUCKETS:
            assert hist.period_count(start, end, bucket) == len(
                hist.period_range(start, end, bucket)), bucket

    def test_an_inverted_span_is_zero_periods(self):
        from apps.scm.models.DemandPlanning import _history as hist
        assert hist.period_count(datetime.date(2026, 5, 1), datetime.date(2026, 1, 1), "month") == 0
        assert hist.period_range(datetime.date(2026, 5, 1), datetime.date(2026, 1, 1), "month") == []

    def test_missing_endpoints_are_zero_periods(self):
        from apps.scm.models.DemandPlanning import _history as hist
        assert hist.period_count(None, datetime.date(2026, 1, 1), "month") == 0
        assert hist.period_range(datetime.date(2026, 1, 1), None, "month") == []

    def test_period_range_limit_stops_the_walk(self):
        from apps.scm.models.DemandPlanning import _history as hist
        rows = hist.period_range(datetime.date(2026, 1, 1), datetime.date(2030, 1, 1), "month",
                                 limit=5)
        assert len(rows) == 5

    def test_period_end_is_the_last_day_inside_the_bucket(self):
        from apps.scm.models.DemandPlanning import _history as hist
        rows = hist.period_range(datetime.date(2026, 1, 1), datetime.date(2026, 2, 28), "month")
        assert rows[0] == (datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))

    def test_bucket_start_normalises_to_the_grid(self):
        from apps.scm.models.DemandPlanning import _history as hist
        value = datetime.date(2026, 5, 20)  # a Wednesday
        assert hist.bucket_start(value, "week") == datetime.date(2026, 5, 18)  # Monday
        assert hist.bucket_start(value, "month") == datetime.date(2026, 5, 1)
        assert hist.bucket_start(value, "quarter") == datetime.date(2026, 4, 1)
        assert hist.bucket_start(value, "day") == value

    def test_next_bucket_rolls_the_year_over(self):
        from apps.scm.models.DemandPlanning import _history as hist
        assert hist.next_bucket(datetime.date(2026, 12, 1), "month") == datetime.date(2027, 1, 1)
        assert hist.next_bucket(datetime.date(2026, 10, 1), "quarter") == datetime.date(2027, 1, 1)

    def test_period_labels_read_the_way_a_planner_writes_them(self):
        from apps.scm.models.DemandPlanning import _history as hist
        assert hist.period_label(datetime.date(2026, 3, 1), "month") == "Mar 2026"
        assert hist.period_label(datetime.date(2026, 4, 1), "quarter") == "Q2 2026"
        assert hist.period_label(datetime.date(2026, 5, 18), "week").startswith("W")

    def test_periods_per_year_defaults_to_months(self):
        from apps.scm.models.DemandPlanning import _history as hist
        assert hist.periods_per_year("week") == 52
        assert hist.periods_per_year("quarter") == 4
        assert hist.periods_per_year("nonsense") == 12


def _history_window():
    """The 12 whole months before this one — derived from timezone.localdate() (L16)."""
    from django.utils import timezone
    from apps.scm.tests._helpers import add_months, month_start
    this_month = month_start(timezone.localdate())
    return add_months(this_month, -12), this_month - datetime.timedelta(days=1)


class TestDemandSeries:
    def test_series_is_dense_and_zero_filled(self, tenant_a, item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning._history import demand_series
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=add_months(this_month, -2), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("40"), unit_price=Decimal("1"))
        start, end = _history_window()
        rows = demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="month")
        assert len(rows) == 12  # every bucket present, not only the one that sold
        assert dict(rows)[add_months(this_month, -2)] == Decimal("40")
        assert dict(rows)[add_months(this_month, -5)] == Decimal("0")

    def test_draft_and_cancelled_orders_are_not_demand(self, tenant_a, item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning._history import demand_series
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        when = add_months(this_month, -1)
        for status in ("draft", "cancelled", "submitted"):
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=when, status=status)
            SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                          quantity_ordered=Decimal("10"), unit_price=Decimal("1"))
        start, end = _history_window()
        rows = dict(demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="month"))
        assert rows[when] == Decimal("10")  # only the submitted order counted

    def test_stock_issues_are_negated_to_read_as_demand(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        from apps.scm.models.DemandPlanning._history import demand_series
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        when = add_months(this_month, -1)
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("-25"),
            move_type="issue",
            moved_at=timezone.make_aware(datetime.datetime.combine(
                when + datetime.timedelta(days=3), datetime.time(12, 0))),
        )
        start, end = _history_window()
        rows = dict(demand_series(tenant_a.pk, item=item_a, source="stock_issues",
                                  start=start, end=end, bucket="month"))
        assert rows[when] == Decimal("25")  # the ledger stores -25; demand reads +25

    def test_manual_source_derives_nothing(self, tenant_a, item_a, demand_history_a):
        from apps.scm.models.DemandPlanning._history import demand_series
        start, end = _history_window()
        rows = demand_series(tenant_a.pk, item=item_a, source="manual", start=start, end=end,
                             bucket="month")
        assert len(rows) == 12
        assert all(qty == Decimal("0") for _, qty in rows)

    def test_a_customer_filter_narrows_the_series(self, tenant_a, item_a, customer_a,
                                                  demand_history_a):
        from apps.core.models import Party, PartyRole
        from apps.scm.models.DemandPlanning._history import demand_series
        other = Party.objects.create(tenant=tenant_a, name="Second customer", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=other, role="customer")
        start, end = _history_window()
        mine = demand_series(tenant_a.pk, item=item_a, customer=customer_a, start=start, end=end,
                             bucket="month")
        theirs = demand_series(tenant_a.pk, item=item_a, customer=other, start=start, end=end,
                               bucket="month")
        assert sum((q for _, q in mine), Decimal("0")) > Decimal("0")
        assert sum((q for _, q in theirs), Decimal("0")) == Decimal("0")

    def test_outlier_clipping_keeps_the_series_length(self, tenant_a, item_a, customer_a,
                                                      demand_history_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning._history import demand_series
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        spike = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=add_months(this_month, -3), status="submitted")
        SalesOrderLine.objects.create(sales_order=spike, item=item_a,
                                      quantity_ordered=Decimal("5000"), unit_price=Decimal("1"))
        start, end = _history_window()
        raw = demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="month")
        clipped = demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="month",
                                exclude_outliers=True, sigma=Decimal("1"))
        assert len(clipped) == len(raw)
        assert max(q for _, q in clipped) < max(q for _, q in raw)

    def test_missing_tenant_or_item_returns_nothing(self, item_a):
        from apps.scm.models.DemandPlanning._history import demand_series
        start, end = _history_window()
        assert demand_series(None, item=item_a, start=start, end=end) == []
        assert demand_series(1, item=None, start=start, end=end) == []

    def test_an_unknown_bucket_degrades_to_months(self, tenant_a, item_a, demand_history_a):
        from apps.scm.models.DemandPlanning._history import demand_series
        start, end = _history_window()
        rows = demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="fortnight")
        assert len(rows) == 12

    def test_another_tenants_orders_never_leak_in(self, tenant_a, item_a, sales_order_b):
        from apps.scm.models.DemandPlanning._history import demand_series
        start, end = _history_window()
        rows = demand_series(tenant_a.pk, item=item_a, start=start, end=end, bucket="month")
        assert sum((q for _, q in rows), Decimal("0")) == Decimal("0")


class TestDemandSeriesMap:
    def test_batch_map_returns_the_same_numbers_as_the_per_item_form(
        self, tenant_a, item_a, item_lot_a, customer_a, demand_history_a,
    ):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning._history import demand_series, demand_series_map
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=add_months(this_month, -4), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_lot_a,
                                      quantity_ordered=Decimal("7"), unit_price=Decimal("1"))
        start, end = _history_window()
        batch = demand_series_map(tenant_a.pk, [item_a, item_lot_a], start=start, end=end,
                                  bucket="month")
        for item in (item_a, item_lot_a):
            single = demand_series(tenant_a.pk, item=item, start=start, end=end, bucket="month")
            assert batch[item.pk] == single, item.sku

    def test_batch_map_is_dense_for_an_item_with_no_history(self, tenant_a, item_a, item_lot_a,
                                                            demand_history_a):
        from apps.scm.models.DemandPlanning._history import demand_series_map
        start, end = _history_window()
        batch = demand_series_map(tenant_a.pk, [item_a.pk, item_lot_a.pk], start=start, end=end,
                                  bucket="month")
        assert len(batch[item_lot_a.pk]) == 12
        assert all(q == Decimal("0") for _, q in batch[item_lot_a.pk])

    def test_batch_map_runs_in_one_grouped_query(self, tenant_a, item_a, item_lot_a,
                                                 demand_history_a, django_assert_max_num_queries):
        from apps.scm.models.DemandPlanning._history import demand_series_map
        start, end = _history_window()
        with django_assert_max_num_queries(1):
            demand_series_map(tenant_a.pk, [item_a.pk, item_lot_a.pk], start=start, end=end,
                              bucket="month")

    def test_batch_map_negates_stock_issues_too(self, tenant_a, item_a, location_a):
        from django.utils import timezone
        from apps.scm.models import StockMove
        from apps.scm.models.DemandPlanning._history import demand_series_map
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        when = add_months(this_month, -1)
        StockMove.objects.create(
            tenant=tenant_a, item=item_a, location=location_a, quantity=Decimal("-12"),
            move_type="issue",
            moved_at=timezone.make_aware(datetime.datetime.combine(
                when + datetime.timedelta(days=2), datetime.time(9, 0))),
        )
        start, end = _history_window()
        batch = demand_series_map(tenant_a.pk, [item_a.pk], start=start, end=end, bucket="month",
                                  source="stock_issues")
        assert dict(batch[item_a.pk])[when] == Decimal("12")

    def test_manual_source_yields_a_zero_filled_map(self, tenant_a, item_a, demand_history_a):
        from apps.scm.models.DemandPlanning._history import demand_series_map
        start, end = _history_window()
        batch = demand_series_map(tenant_a.pk, [item_a.pk], start=start, end=end, bucket="month",
                                  source="manual")
        assert all(q == Decimal("0") for _, q in batch[item_a.pk])

    def test_empty_inputs_return_an_empty_map(self, tenant_a, item_a):
        from apps.scm.models.DemandPlanning._history import demand_series_map
        start, end = datetime.date(2026, 1, 1), datetime.date(2026, 3, 31)
        assert demand_series_map(tenant_a.pk, [], start=start, end=end) == {}
        assert demand_series_map(None, [item_a], start=start, end=end) == {}
        assert demand_series_map(tenant_a.pk, [item_a], start=end, end=start) == {}


# ================================================================================================
# SeasonalityProfile / SeasonalityIndex
# ================================================================================================
def _flat_profile(tenant, item, factor="2.0000", **kwargs):
    """A monthly seasonal profile whose every month carries the SAME index.

    Month-independent on purpose: an assertion that keyed off "December is 1.5" would only exercise
    the seasonal path for the weeks of the year the horizon happens to cover December.
    """
    from apps.scm.models import SeasonalityIndex, SeasonalityProfile
    profile = SeasonalityProfile.objects.create(
        tenant=tenant, name="Flat curve", profile_type="seasonal", bucket="month", scope="item",
        item=item, **kwargs)
    for month in range(1, 13):
        SeasonalityIndex.objects.create(profile=profile, period_number=month,
                                        index_factor=Decimal(factor))
    return profile


class TestSeasonalityProfileIndexing:
    def test_index_for_period_reads_the_matching_index_row(self, seasonality_profile_a):
        assert seasonality_profile_a.index_for_period(datetime.date(2026, 12, 5)) == Decimal("1.5000")
        assert seasonality_profile_a.index_for_period(datetime.date(2026, 6, 5)) == Decimal("1.0000")

    def test_a_period_with_no_index_row_is_neutral(self, tenant_a, item_a):
        from apps.scm.models import SeasonalityIndex, SeasonalityProfile
        profile = SeasonalityProfile.objects.create(tenant=tenant_a, name="Sparse", scope="item",
                                                    item=item_a)
        SeasonalityIndex.objects.create(profile=profile, period_number=1,
                                        index_factor=Decimal("3.0000"))
        assert profile.index_for_period(datetime.date(2026, 7, 1)) == Decimal("1")

    def test_index_map_is_keyed_by_period_number(self, seasonality_profile_a):
        assert seasonality_profile_a.index_map()[12] == Decimal("1.5000")
        assert len(seasonality_profile_a.index_map()) == 12

    def test_a_windowed_promotion_only_lifts_inside_its_window(self, promotion_profile_a):
        inside = promotion_profile_a.event_start
        after = promotion_profile_a.event_end + datetime.timedelta(days=1)
        assert promotion_profile_a.index_for_period(inside) == Decimal("1.25")
        assert promotion_profile_a.index_for_period(after) == Decimal("1")

    def test_apply_to_splits_a_seasonal_curve_into_the_index_column(self, seasonality_profile_a):
        seasonal, uplift = seasonality_profile_a.apply_to(Decimal("100"), datetime.date(2026, 12, 1))
        assert seasonal == Decimal("1.5000")
        assert uplift == Decimal("0")

    def test_apply_to_splits_a_promotion_into_the_uplift_column(self, promotion_profile_a):
        seasonal, uplift = promotion_profile_a.apply_to(Decimal("100"),
                                                        promotion_profile_a.event_start)
        assert seasonal == Decimal("1")
        assert uplift == Decimal("25.00")

    def test_period_number_for_each_bucket(self, tenant_a, item_a):
        from apps.scm.models import SeasonalityProfile
        value = datetime.date(2026, 5, 18)
        month = SeasonalityProfile(tenant=tenant_a, bucket="month")
        week = SeasonalityProfile(tenant=tenant_a, bucket="week")
        quarter = SeasonalityProfile(tenant=tenant_a, bucket="quarter")
        assert month.period_number_for(value) == 5
        assert quarter.period_number_for(value) == 2
        assert week.period_number_for(value) == value.isocalendar()[1]

    def test_period_from_launch_counts_months_from_the_launch_date(self, tenant_a):
        from apps.scm.models import SeasonalityProfile
        profile = SeasonalityProfile(tenant=tenant_a, bucket="period_from_launch",
                                     event_start=datetime.date(2026, 1, 1))
        assert profile.period_number_for(datetime.date(2026, 1, 15)) == 1  # 1-based: the launch month
        assert profile.period_number_for(datetime.date(2026, 4, 1)) == 4
        assert profile.period_number_for(datetime.date(2025, 12, 1)) == 1  # never below 1

    def test_period_from_launch_without_a_launch_date_is_period_one(self, tenant_a):
        from apps.scm.models import SeasonalityProfile
        profile = SeasonalityProfile(tenant=tenant_a, bucket="period_from_launch")
        assert profile.period_number_for(datetime.date(2026, 4, 1)) == 1

    def test_expected_period_count_per_bucket(self, tenant_a):
        from apps.scm.models import SeasonalityProfile
        assert SeasonalityProfile(bucket="month").expected_period_count == 12
        assert SeasonalityProfile(bucket="week").expected_period_count == 53
        assert SeasonalityProfile(bucket="quarter").expected_period_count == 4
        assert SeasonalityProfile(bucket="period_from_launch").expected_period_count is None

    def test_variance_pct_reads_as_percentage_points_around_neutral(self, seasonality_profile_a):
        assert seasonality_profile_a.indices.get(period_number=12).variance_pct == Decimal("50.0000")
        assert seasonality_profile_a.indices.get(period_number=1).variance_pct == Decimal("0.0000")

    def test_clean_requires_a_window_on_a_promotion(self, tenant_a, item_a):
        from apps.scm.models import SeasonalityProfile
        profile = SeasonalityProfile(tenant=tenant_a, name="Promo", profile_type="promotion",
                                     scope="item", item=item_a)
        with pytest.raises(ValidationError) as excinfo:
            profile.clean()
        assert "event_start" in excinfo.value.message_dict

    def test_clean_rejects_an_inverted_event_window(self, tenant_a, item_a):
        from apps.scm.models import SeasonalityProfile
        profile = SeasonalityProfile(tenant=tenant_a, name="Promo", profile_type="event",
                                     scope="item", item=item_a,
                                     event_start=datetime.date(2026, 6, 1),
                                     event_end=datetime.date(2026, 5, 1))
        with pytest.raises(ValidationError) as excinfo:
            profile.clean()
        assert "event_end" in excinfo.value.message_dict

    def test_clean_requires_the_scope_target(self, tenant_a):
        from apps.scm.models import SeasonalityProfile
        for scope in ("item", "category", "location"):
            with pytest.raises(ValidationError) as excinfo:
                SeasonalityProfile(tenant=tenant_a, name="X", scope=scope).clean()
            assert scope in excinfo.value.message_dict

    def test_global_scope_needs_no_target(self, tenant_a):
        from apps.scm.models import SeasonalityProfile
        SeasonalityProfile(tenant=tenant_a, name="X", scope="global").clean()  # must not raise


# ================================================================================================
# DemandForecast.generate_periods — the period grid
# ================================================================================================
class TestGeneratePeriods:
    def test_builds_the_grid_from_the_horizon(self, demand_forecast_a, demand_history_a):
        from apps.scm.tests._helpers import add_months
        written = demand_forecast_a.generate_periods()
        rows = list(demand_forecast_a.periods.all())
        assert written == 3
        assert [row.sequence for row in rows] == [1, 2, 3]
        start = demand_forecast_a.horizon_start
        assert [row.period_start for row in rows] == [start, add_months(start, 1), add_months(start, 2)]
        assert rows[0].period_end == add_months(start, 1) - datetime.timedelta(days=1)
        assert rows[0].period_label == start.strftime("%b %Y")

    def test_baseline_comes_from_the_derived_history(self, demand_forecast_a, demand_history_a):
        demand_forecast_a.generate_periods()
        # moving_average(window 3) over a flat 100/month history.
        assert all(row.baseline_quantity == Decimal("100.0000")
                   for row in demand_forecast_a.periods.all())

    def test_historical_quantity_snapshots_the_same_period_last_year(self, demand_forecast_a,
                                                                     demand_history_a):
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.first().historical_quantity == Decimal("100.0000")

    def test_generate_advances_a_draft_to_statistical_and_stamps_generated_at(self,
                                                                              demand_forecast_a):
        assert demand_forecast_a.status == "draft"
        demand_forecast_a.generate_periods()
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.status == "statistical"
        assert demand_forecast_a.generated_at is not None

    def test_regenerating_updates_in_place_rather_than_duplicating(self, demand_forecast_a,
                                                                    demand_history_a):
        demand_forecast_a.generate_periods()
        pks = set(demand_forecast_a.periods.values_list("pk", flat=True))
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.count() == 3
        assert set(demand_forecast_a.periods.values_list("pk", flat=True)) == pks

    def test_a_locked_period_survives_a_regenerate_untouched(self, demand_forecast_a,
                                                             demand_history_a):
        demand_forecast_a.generate_periods()
        row = demand_forecast_a.periods.first()
        row.is_locked, row.baseline_quantity, row.final_quantity = True, Decimal("999"), Decimal("999")
        row.save(update_fields=["is_locked", "baseline_quantity", "final_quantity"])
        demand_forecast_a.generate_periods()
        row.refresh_from_db()
        assert row.baseline_quantity == Decimal("999.0000")
        assert row.final_quantity == Decimal("999.0000")

    def test_regenerate_locked_overwrites_a_locked_period_on_request(self, demand_forecast_a,
                                                                     demand_history_a):
        demand_forecast_a.generate_periods()
        row = demand_forecast_a.periods.first()
        row.is_locked, row.baseline_quantity = True, Decimal("999")
        row.save(update_fields=["is_locked", "baseline_quantity"])
        demand_forecast_a.generate_periods(regenerate_locked=True)
        row.refresh_from_db()
        assert row.baseline_quantity == Decimal("100.0000")

    def test_a_seasonal_profile_multiplies_the_baseline(self, tenant_a, item_a, demand_forecast_a,
                                                        demand_history_a):
        demand_forecast_a.seasonality_profile = _flat_profile(tenant_a, item_a, "2.0000")
        demand_forecast_a.save(update_fields=["seasonality_profile"])
        demand_forecast_a.generate_periods()
        row = demand_forecast_a.periods.first()
        assert row.seasonal_index_applied == Decimal("2.0000")
        assert row.event_uplift_quantity == Decimal("0.0000")
        assert row.final_quantity == Decimal("200.0000")

    def test_clearing_the_profile_resets_the_seasonal_and_uplift_columns(
        self, tenant_a, item_a, demand_forecast_a, demand_history_a,
    ):
        demand_forecast_a.seasonality_profile = _flat_profile(tenant_a, item_a, "2.0000")
        demand_forecast_a.save(update_fields=["seasonality_profile"])
        demand_forecast_a.generate_periods()
        demand_forecast_a.seasonality_profile = None
        demand_forecast_a.save(update_fields=["seasonality_profile"])
        demand_forecast_a.generate_periods()
        row = demand_forecast_a.periods.first()
        assert row.seasonal_index_applied == Decimal("1.0000")
        assert row.event_uplift_quantity == Decimal("0.0000")
        assert row.final_quantity == Decimal("100.0000")

    def test_deactivating_the_profile_also_resets_the_columns(self, tenant_a, item_a,
                                                              demand_forecast_a, demand_history_a):
        profile = _flat_profile(tenant_a, item_a, "2.0000")
        demand_forecast_a.seasonality_profile = profile
        demand_forecast_a.save(update_fields=["seasonality_profile"])
        demand_forecast_a.generate_periods()
        profile.is_active = False
        profile.save(update_fields=["is_active"])
        demand_forecast_a.refresh_from_db()
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.first().seasonal_index_applied == Decimal("1.0000")

    def test_a_promotion_profile_lands_in_the_uplift_column_only(self, demand_forecast_a,
                                                                 promotion_profile_a,
                                                                 demand_history_a):
        demand_forecast_a.seasonality_profile = promotion_profile_a
        demand_forecast_a.save(update_fields=["seasonality_profile"])
        demand_forecast_a.generate_periods()
        rows = list(demand_forecast_a.periods.all())
        assert rows[0].seasonal_index_applied == Decimal("1.0000")
        assert rows[0].event_uplift_quantity == Decimal("25.0000")  # 25 % of a 100 baseline
        assert rows[0].final_quantity == Decimal("125.0000")
        assert rows[1].event_uplift_quantity == Decimal("0.0000")  # outside the promo window

    def test_manual_method_does_not_overwrite_the_typed_quantities(self, demand_forecast_a,
                                                                    demand_history_a):
        demand_forecast_a.generate_periods()
        demand_forecast_a.method = "manual"
        demand_forecast_a.save(update_fields=["method"])
        row = demand_forecast_a.periods.first()
        row.baseline_quantity, row.final_quantity = Decimal("555"), Decimal("555")
        row.save(update_fields=["baseline_quantity", "final_quantity"])
        demand_forecast_a.generate_periods()
        row.refresh_from_db()
        assert row.baseline_quantity == Decimal("555.0000")
        assert row.final_quantity == Decimal("555.0000")

    def test_manual_method_still_refreshes_the_derived_dates_and_labels(self, demand_forecast_a,
                                                                        demand_history_a):
        demand_forecast_a.generate_periods()
        demand_forecast_a.method = "manual"
        demand_forecast_a.save(update_fields=["method"])
        row = demand_forecast_a.periods.first()
        row.period_label = "clobbered"
        row.save(update_fields=["period_label"])
        demand_forecast_a.generate_periods()
        row.refresh_from_db()
        assert row.period_label == demand_forecast_a.horizon_start.strftime("%b %Y")

    def test_best_fit_stamps_the_engine_it_picked(self, demand_forecast_a, demand_history_a):
        from apps.scm.models import DemandForecast
        demand_forecast_a.method = "best_fit"
        demand_forecast_a.save(update_fields=["method"])
        demand_forecast_a.generate_periods()
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.selected_method in dict(DemandForecast.METHOD_CHOICES)
        assert demand_forecast_a.effective_method == demand_forecast_a.selected_method

    def test_switching_off_best_fit_clears_the_stamped_engine(self, demand_forecast_a,
                                                              demand_history_a):
        demand_forecast_a.method = "best_fit"
        demand_forecast_a.save(update_fields=["method"])
        demand_forecast_a.generate_periods()
        demand_forecast_a.method = "moving_average"
        demand_forecast_a.save(update_fields=["method"])
        demand_forecast_a.generate_periods()
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.selected_method == ""
        assert demand_forecast_a.effective_method == "moving_average"

    def test_like_item_copies_the_reference_items_history_scaled(self, tenant_a, item_a,
                                                                  item_lot_a, customer_a,
                                                                  demand_forecast_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        for back in range(12, 0, -1):  # history on the REFERENCE item only
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=add_months(this_month, -back),
                                              status="submitted")
            SalesOrderLine.objects.create(sales_order=order, item=item_lot_a,
                                          quantity_ordered=Decimal("200"), unit_price=Decimal("1"))
        demand_forecast_a.method = "like_item"
        demand_forecast_a.reference_item = item_lot_a
        demand_forecast_a.reference_scale_pct = Decimal("50")
        demand_forecast_a.save(update_fields=["method", "reference_item", "reference_scale_pct"])
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.first().baseline_quantity == Decimal("100.0000")

    def test_a_shortened_horizon_drops_the_orphan_periods(self, demand_forecast_a,
                                                          demand_history_a):
        from apps.scm.tests._helpers import add_months
        demand_forecast_a.generate_periods()
        demand_forecast_a.horizon_end = add_months(demand_forecast_a.horizon_start,
                                                   1) - datetime.timedelta(days=1)
        demand_forecast_a.save(update_fields=["horizon_end"])
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.count() == 1

    def test_a_shortened_horizon_keeps_a_locked_orphan(self, demand_forecast_a, demand_history_a):
        from apps.scm.tests._helpers import add_months
        demand_forecast_a.generate_periods()
        last = demand_forecast_a.periods.last()
        last.is_locked = True
        last.save(update_fields=["is_locked"])
        demand_forecast_a.horizon_end = add_months(demand_forecast_a.horizon_start,
                                                   1) - datetime.timedelta(days=1)
        demand_forecast_a.save(update_fields=["horizon_end"])
        demand_forecast_a.generate_periods()
        assert demand_forecast_a.periods.filter(pk=last.pk).exists()

    def test_an_empty_horizon_writes_nothing(self, demand_forecast_a):
        demand_forecast_a.horizon_end = demand_forecast_a.horizon_start - datetime.timedelta(days=1)
        demand_forecast_a.save(update_fields=["horizon_end"])
        assert demand_forecast_a.generate_periods() == 0
        assert demand_forecast_a.periods.count() == 0

    def test_generate_never_writes_more_than_max_horizon_periods_rows(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import month_start
        from django.utils import timezone
        start = month_start(timezone.localdate())
        # A daily horizon far past the cap — clean() would reject it, but generate() is also
        # reachable on rows written before the cap existed, so the walk is capped too.
        forecast = DemandForecast.objects.create(
            tenant=tenant_a, name="Runaway", item=item_a, bucket="day", horizon_start=start,
            horizon_end=start + datetime.timedelta(days=5000), history_months=1)
        forecast.generate_periods()
        assert forecast.periods.count() == DemandForecast.MAX_HORIZON_PERIODS


# ================================================================================================
# DemandForecast.recompute_consensus — the collaborative roll-up
# ================================================================================================
def _accept(adjustment):
    """Flip an adjustment to accepted WITHOUT going through save() — arranging state, not acting."""
    from apps.scm.models import ForecastAdjustment
    ForecastAdjustment.objects.filter(pk=adjustment.pk).update(status="accepted")
    adjustment.refresh_from_db()
    return adjustment


def _propose(forecast, tenant, **kwargs):
    from apps.scm.models import ForecastAdjustment
    payload = {"adjustment_type": "absolute", "proposed_quantity": Decimal("0"),
               "rationale": "test"}
    payload.update(kwargs)
    return ForecastAdjustment.objects.create(tenant=tenant, forecast=forecast, **payload)


class TestRecomputeConsensus:
    def test_one_accepted_absolute_moves_the_period_to_the_target(self, tenant_a,
                                                                   forecast_with_periods_a,
                                                                   forecast_period_a):
        _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                         adjustment_type="absolute", proposed_quantity=Decimal("140")))
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.consensus_quantity == Decimal("40.0000")
        assert forecast_period_a.final_quantity == Decimal("140.0000")

    def test_two_accepted_absolutes_land_on_the_target_not_on_double_it(self, tenant_a,
                                                                        forecast_with_periods_a,
                                                                        forecast_period_a):
        """Each adjustment is RE-resolved against the number as it stands when its turn comes."""
        for _ in range(2):
            _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                             adjustment_type="absolute", proposed_quantity=Decimal("140")))
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("140.0000")  # not 180

    def test_two_accepted_deltas_do_stack(self, tenant_a, forecast_with_periods_a,
                                          forecast_period_a):
        for _ in range(2):
            _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                             adjustment_type="delta", proposed_quantity=Decimal("10")))
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("120.0000")

    def test_a_percent_adjustment_resolves_against_the_live_base(self, tenant_a,
                                                                 forecast_with_periods_a,
                                                                 forecast_period_a):
        _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                         adjustment_type="percent", adjustment_pct=Decimal("10")))
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("110.0000")

    def test_rejecting_an_accepted_adjustment_backs_its_delta_out(self, tenant_a,
                                                                  forecast_with_periods_a,
                                                                  forecast_period_a):
        from apps.scm.models import ForecastAdjustment
        adjustment = _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                                      adjustment_type="delta", proposed_quantity=Decimal("40")))
        forecast_with_periods_a.recompute_consensus()
        ForecastAdjustment.objects.filter(pk=adjustment.pk).update(status="rejected")
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.consensus_quantity == Decimal("0.0000")
        assert forecast_period_a.final_quantity == Decimal("100.0000")

    def test_a_proposed_adjustment_never_moves_the_plan(self, tenant_a, forecast_with_periods_a,
                                                        forecast_period_a):
        _propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                 adjustment_type="delta", proposed_quantity=Decimal("40"))
        forecast_with_periods_a.recompute_consensus()
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("100.0000")

    def test_a_horizon_wide_adjustment_is_split_pro_rata(self, tenant_a, forecast_with_periods_a):
        rows = list(forecast_with_periods_a.periods.all())
        rows[1].baseline_quantity = Decimal("300")
        rows[1].save(update_fields=["baseline_quantity"])
        _accept(_propose(forecast_with_periods_a, tenant_a, adjustment_type="delta",
                         proposed_quantity=Decimal("50")))
        forecast_with_periods_a.recompute_consensus()
        rows = list(forecast_with_periods_a.periods.all())
        # Weights 100 / 300 / 100 = 500 total -> 10 / 30 / 10.
        assert [row.consensus_quantity for row in rows] == [
            Decimal("10.0000"), Decimal("30.0000"), Decimal("10.0000")]

    def test_a_horizon_wide_adjustment_splits_evenly_when_the_base_is_zero(
        self, tenant_a, forecast_with_periods_a,
    ):
        forecast_with_periods_a.periods.update(baseline_quantity=Decimal("0"))
        _accept(_propose(forecast_with_periods_a, tenant_a, adjustment_type="delta",
                         proposed_quantity=Decimal("30")))
        forecast_with_periods_a.recompute_consensus()
        assert [row.consensus_quantity for row in forecast_with_periods_a.periods.all()] == [
            Decimal("10.0000")] * 3

    def test_a_locked_period_takes_no_share_of_a_horizon_wide_adjustment(
        self, tenant_a, forecast_with_periods_a,
    ):
        locked = forecast_with_periods_a.periods.all()[1]
        locked.is_locked = True
        locked.save(update_fields=["is_locked"])
        _accept(_propose(forecast_with_periods_a, tenant_a, adjustment_type="delta",
                         proposed_quantity=Decimal("40")))
        forecast_with_periods_a.recompute_consensus()
        rows = list(forecast_with_periods_a.periods.all())
        assert rows[1].consensus_quantity == Decimal("0.0000")
        assert [rows[0].consensus_quantity, rows[2].consensus_quantity] == [
            Decimal("20.0000"), Decimal("20.0000")]

    def test_an_adjustment_aimed_at_a_locked_period_takes_no_effect(self, tenant_a,
                                                                    forecast_with_periods_a,
                                                                    forecast_period_a):
        forecast_period_a.is_locked = True
        forecast_period_a.save(update_fields=["is_locked"])
        _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                         adjustment_type="delta", proposed_quantity=Decimal("40")))
        forecast_with_periods_a.recompute_consensus()
        assert all(row.consensus_quantity == Decimal("0.0000")
                   for row in forecast_with_periods_a.periods.all())

    def test_the_resolved_quantity_is_written_back_for_the_screens(self, tenant_a,
                                                                    forecast_with_periods_a,
                                                                    forecast_period_a):
        adjustment = _accept(_propose(forecast_with_periods_a, tenant_a, period=forecast_period_a,
                                      adjustment_type="absolute",
                                      proposed_quantity=Decimal("175")))
        forecast_with_periods_a.recompute_consensus()
        adjustment.refresh_from_db()
        assert adjustment.resolved_quantity == Decimal("75.0000")

    def test_recompute_on_a_forecast_with_no_periods_is_a_no_op(self, demand_forecast_a):
        assert demand_forecast_a.recompute_consensus() == 0

    def test_recompute_on_an_all_locked_grid_is_a_no_op(self, forecast_with_periods_a):
        forecast_with_periods_a.periods.update(is_locked=True)
        assert forecast_with_periods_a.recompute_consensus() == 0


# ================================================================================================
# DemandSignal — sensing, apply, the live detector and the staleness sweep
# ================================================================================================
class TestDemandSignalProperties:
    def test_signed_impact_quantity_carries_the_direction(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        base = dict(tenant=tenant_a, observed_at=timezone.now(), impact_quantity=Decimal("30"))
        up = DemandSignal(impact_direction="increase", **base)
        down = DemandSignal(impact_direction="decrease", **base)
        flat = DemandSignal(impact_direction="neutral", **base)
        assert up.signed_impact_quantity == Decimal("30")
        assert down.signed_impact_quantity == Decimal("-30")
        assert flat.signed_impact_quantity == Decimal("0")

    def test_a_negative_magnitude_is_still_read_through_the_direction(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        signal = DemandSignal(tenant=tenant_a, observed_at=timezone.now(),
                              impact_quantity=Decimal("-30"), impact_direction="increase")
        assert signal.signed_impact_quantity == Decimal("30")

    def test_is_open_tracks_the_triage_statuses(self, demand_signal_a):
        assert demand_signal_a.is_open
        demand_signal_a.status = "applied"
        assert not demand_signal_a.is_open

    def test_effective_window_falls_back_to_observed_at_plus_horizon(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        signal = DemandSignal.objects.create(tenant=tenant_a, observed_at=timezone.now(),
                                             horizon_days=7)
        start, end = signal.effective_window()
        assert start == timezone.localdate()
        assert end == start + datetime.timedelta(days=6)

    def test_effective_window_prefers_the_stated_dates(self, demand_signal_a):
        start, end = demand_signal_a.effective_window()
        assert (start, end) == (demand_signal_a.effective_from, demand_signal_a.effective_to)

    def test_clean_rejects_an_inverted_window(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        signal = DemandSignal(tenant=tenant_a, observed_at=timezone.now(),
                              effective_from=datetime.date(2026, 6, 1),
                              effective_to=datetime.date(2026, 5, 1))
        with pytest.raises(ValidationError) as excinfo:
            signal.clean()
        assert "effective_to" in excinfo.value.message_dict


class TestDemandSignalApplyToForecast:
    def test_only_overlapping_periods_move(self, demand_signal_a, forecast_with_periods_a):
        moved = demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        rows = list(forecast_with_periods_a.periods.all())
        assert moved == 1  # the signal window covers the first bucket only
        assert rows[0].signal_adjustment_quantity == Decimal("30.0000")
        assert rows[1].signal_adjustment_quantity == Decimal("0.0000")
        assert rows[2].signal_adjustment_quantity == Decimal("0.0000")

    def test_the_impact_is_disaggregated_pro_rata_across_the_window(self, demand_signal_a,
                                                                    forecast_with_periods_a):
        from apps.scm.tests._helpers import add_months
        rows = list(forecast_with_periods_a.periods.all())
        rows[1].baseline_quantity = Decimal("200")
        rows[1].save(update_fields=["baseline_quantity"])
        demand_signal_a.effective_to = add_months(demand_signal_a.effective_from,
                                                  2) - datetime.timedelta(days=1)
        demand_signal_a.save(update_fields=["effective_to"])
        assert demand_signal_a.apply_to_forecast(forecast_with_periods_a) == 2
        rows = list(forecast_with_periods_a.periods.all())
        # Weights 100 / 200 -> 30 splits 10 / 20, NOT 15 / 15.
        assert rows[0].signal_adjustment_quantity == Decimal("10.0000")
        assert rows[1].signal_adjustment_quantity == Decimal("20.0000")

    def test_an_even_split_when_the_seasonalised_baseline_is_zero(self, demand_signal_a,
                                                                  forecast_with_periods_a):
        from apps.scm.tests._helpers import add_months
        forecast_with_periods_a.periods.update(baseline_quantity=Decimal("0"))
        demand_signal_a.effective_to = add_months(demand_signal_a.effective_from,
                                                  2) - datetime.timedelta(days=1)
        demand_signal_a.save(update_fields=["effective_to"])
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        assert [row.signal_adjustment_quantity
                for row in forecast_with_periods_a.periods.all()[:2]] == [Decimal("15.0000")] * 2

    def test_the_final_quantity_follows_the_waterfall(self, demand_signal_a,
                                                      forecast_with_periods_a):
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        assert forecast_with_periods_a.periods.first().final_quantity == Decimal("130.0000")

    def test_a_decrease_signal_pulls_the_forecast_down(self, demand_signal_a,
                                                       forecast_with_periods_a):
        demand_signal_a.impact_direction = "decrease"
        demand_signal_a.save(update_fields=["impact_direction"])
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        assert forecast_with_periods_a.periods.first().final_quantity == Decimal("70.0000")

    def test_an_explicit_quantity_overrides_the_signals_own_impact(self, demand_signal_a,
                                                                    forecast_with_periods_a):
        demand_signal_a.apply_to_forecast(forecast_with_periods_a, quantity=Decimal("-5"))
        assert forecast_with_periods_a.periods.first().signal_adjustment_quantity == Decimal("-5.0000")

    def test_a_locked_periods_final_quantity_is_left_alone(self, demand_signal_a,
                                                           forecast_with_periods_a,
                                                           forecast_period_a):
        forecast_period_a.is_locked = True
        forecast_period_a.save(update_fields=["is_locked"])
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("100.0000")

    def test_applying_marks_the_signal_applied_and_records_the_forecast(self, demand_signal_a,
                                                                        forecast_with_periods_a):
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "applied"
        assert demand_signal_a.applied_to_forecast_id == forecast_with_periods_a.pk

    def test_no_overlapping_period_leaves_the_signal_untouched(self, demand_signal_a,
                                                               forecast_with_periods_a):
        from apps.scm.tests._helpers import add_months
        demand_signal_a.effective_from = add_months(demand_signal_a.effective_from, -6)
        demand_signal_a.effective_to = add_months(demand_signal_a.effective_from, 1)
        demand_signal_a.save(update_fields=["effective_from", "effective_to"])
        assert demand_signal_a.apply_to_forecast(forecast_with_periods_a) == 0
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"

    def test_applying_a_second_time_double_counts_which_is_why_the_view_guards_it(
        self, demand_signal_a, forecast_with_periods_a,
    ):
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        assert forecast_with_periods_a.periods.first().signal_adjustment_quantity == Decimal("60.0000")


class TestDetectOrderSurge:
    def test_a_dropoff_is_raised_when_nothing_has_been_ordered(self, tenant_a,
                                                               approved_forecast_a):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        created = detect_order_surge(tenant_a)
        assert len(created) == 1
        signal = created[0]
        assert signal.signal_type == "order_dropoff"
        assert signal.impact_direction == "decrease"
        assert signal.source == "internal_orders"

    def test_the_dedupe_key_is_the_forecast_number_and_period_sequence(self, tenant_a,
                                                                       approved_forecast_a):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        signal = detect_order_surge(tenant_a)[0]
        assert signal.source_reference == f"{approved_forecast_a.number}:1"

    def test_running_the_detector_twice_creates_nothing_new(self, tenant_a, approved_forecast_a):
        from apps.scm.models import DemandSignal
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        detect_order_surge(tenant_a)
        assert detect_order_surge(tenant_a) == []
        assert DemandSignal.objects.filter(tenant=tenant_a).count() == 1

    def test_a_dismissed_signal_still_suppresses_a_repeat(self, tenant_a, approved_forecast_a):
        from apps.scm.models import DemandSignal
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        signal = detect_order_surge(tenant_a)[0]
        DemandSignal.objects.filter(pk=signal.pk).update(status="dismissed")
        assert detect_order_surge(tenant_a) == []

    def test_a_surge_is_raised_when_orders_run_hot(self, tenant_a, approved_forecast_a,
                                                   customer_a, item_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=timezone.localdate(), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("10000"), unit_price=Decimal("1"))
        created = detect_order_surge(tenant_a)
        assert len(created) == 1
        assert created[0].signal_type == "order_surge"
        assert created[0].impact_direction == "increase"
        assert created[0].confidence == "high"

    def test_a_five_figure_deviation_is_clamped_to_the_column_ceiling(self, tenant_a,
                                                                      approved_forecast_a,
                                                                      customer_a, item_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=timezone.localdate(), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("1000000"), unit_price=Decimal("1"))
        signal = detect_order_surge(tenant_a)[0]
        assert signal.impact_pct == Decimal("9999.99")  # DecimalField(6, 2) ceiling, not a DataError

    def test_a_forecast_that_is_not_approved_is_never_sensed(self, tenant_a,
                                                             forecast_with_periods_a):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        assert forecast_with_periods_a.status == "statistical"
        assert detect_order_surge(tenant_a) == []

    def test_a_period_forecast_at_zero_is_skipped(self, tenant_a, approved_forecast_a):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        approved_forecast_a.periods.update(final_quantity=Decimal("0"))
        assert detect_order_surge(tenant_a) == []

    def test_a_deviation_inside_the_threshold_raises_nothing(self, tenant_a, approved_forecast_a,
                                                             customer_a, item_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        # Book exactly the run rate the current period expects, so the deviation is 0 %.
        period = approved_forecast_a.periods.first()
        today = timezone.localdate()
        elapsed = Decimal((today - period.period_start).days + 1)
        total_days = Decimal((period.period_end - period.period_start).days + 1)
        on_plan = (period.final_quantity * elapsed / total_days).quantize(Decimal("0.0001"))
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, order_date=today,
                                          status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=on_plan,
                                      unit_price=Decimal("1"))
        assert detect_order_surge(tenant_a) == []

    def test_a_tenant_less_call_is_a_no_op(self):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        assert detect_order_surge(None) == []

    def test_another_tenants_forecast_is_never_sensed(self, tenant_b, approved_forecast_a):
        from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge
        assert detect_order_surge(tenant_b) == []


class TestExpireStaleSignals:
    def _signal(self, tenant, item, **kwargs):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        payload = {"tenant": tenant, "item": item, "observed_at": timezone.now()}
        payload.update(kwargs)
        return DemandSignal.objects.create(**payload)

    def test_an_open_signal_whose_window_has_passed_is_retired(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        today = timezone.localdate()
        signal = self._signal(tenant_a, item_a, effective_from=today - datetime.timedelta(days=30),
                              effective_to=today - datetime.timedelta(days=1))
        assert expire_stale_signals(tenant_a) == 1
        signal.refresh_from_db()
        assert signal.status == "expired"

    def test_a_signal_still_inside_its_window_is_left_alone(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        today = timezone.localdate()
        signal = self._signal(tenant_a, item_a, effective_from=today,
                              effective_to=today + datetime.timedelta(days=10))
        assert expire_stale_signals(tenant_a) == 0
        signal.refresh_from_db()
        assert signal.status == "new"

    def test_a_signal_with_no_stated_end_is_resolved_through_its_horizon(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        stale = self._signal(tenant_a, item_a, horizon_days=7,
                             observed_at=timezone.now() - datetime.timedelta(days=60))
        fresh = self._signal(tenant_a, item_a, horizon_days=90)
        assert expire_stale_signals(tenant_a) == 1
        stale.refresh_from_db()
        fresh.refresh_from_db()
        assert (stale.status, fresh.status) == ("expired", "new")

    def test_an_already_actioned_signal_is_never_retired(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        today = timezone.localdate()
        signal = self._signal(tenant_a, item_a, effective_from=today - datetime.timedelta(days=30),
                              effective_to=today - datetime.timedelta(days=1))
        DemandSignal.objects.filter(pk=signal.pk).update(status="applied")
        assert expire_stale_signals(tenant_a) == 0

    def test_an_under_review_signal_is_retired_too(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        today = timezone.localdate()
        signal = self._signal(tenant_a, item_a, effective_to=today - datetime.timedelta(days=1))
        DemandSignal.objects.filter(pk=signal.pk).update(status="under_review")
        assert expire_stale_signals(tenant_a) == 1

    def test_another_tenants_stale_signal_is_not_touched(self, tenant_a, tenant_b, item_b):
        from django.utils import timezone
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        today = timezone.localdate()
        self._signal(tenant_b, item_b, effective_to=today - datetime.timedelta(days=1))
        assert expire_stale_signals(tenant_a) == 0

    def test_a_tenant_less_call_is_a_no_op(self):
        from apps.scm.models.DemandPlanning.DemandSignals import expire_stale_signals
        assert expire_stale_signals(None) == 0


# ================================================================================================
# ForecastAdjustment
# ================================================================================================
class TestForecastAdjustmentModel:
    def test_delta_against_reduces_every_type_to_a_signed_delta(self, tenant_a,
                                                                forecast_with_periods_a):
        from apps.scm.models import ForecastAdjustment
        absolute = ForecastAdjustment(adjustment_type="absolute", proposed_quantity=Decimal("140"))
        delta = ForecastAdjustment(adjustment_type="delta", proposed_quantity=Decimal("-15"))
        percent = ForecastAdjustment(adjustment_type="percent", adjustment_pct=Decimal("25"))
        assert absolute.delta_against(Decimal("100")) == Decimal("40")
        assert delta.delta_against(Decimal("100")) == Decimal("-15")
        assert percent.delta_against(Decimal("100")) == Decimal("25")

    def test_resolved_quantity_is_derived_in_save(self, forecast_adjustment_a):
        assert forecast_adjustment_a.resolved_quantity == Decimal("40.0000")  # 140 target - 100 base

    def test_resolved_quantity_is_re_derived_even_on_a_narrow_update_fields_save(
        self, forecast_adjustment_a, forecast_period_a,
    ):
        forecast_period_a.baseline_quantity = Decimal("50")
        forecast_period_a.save(update_fields=["baseline_quantity"])
        forecast_adjustment_a.period.refresh_from_db()
        forecast_adjustment_a.save(update_fields=["confidence"])
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.resolved_quantity == Decimal("90.0000")

    def test_base_quantity_is_the_period_when_one_is_named(self, forecast_adjustment_a):
        assert forecast_adjustment_a.base_quantity() == Decimal("100.0000")

    def test_base_quantity_is_the_whole_horizon_when_no_period_is_named(self, tenant_a,
                                                                        forecast_with_periods_a):
        from apps.scm.models import ForecastAdjustment
        adjustment = ForecastAdjustment.objects.create(
            tenant=tenant_a, forecast=forecast_with_periods_a, adjustment_type="delta",
            proposed_quantity=Decimal("1"), rationale="whole horizon")
        assert adjustment.base_quantity() == Decimal("300.0000")

    def test_base_quantity_is_zero_without_a_forecast(self):
        from apps.scm.models import ForecastAdjustment
        assert ForecastAdjustment().base_quantity() == Decimal("0")

    def test_clean_rejects_a_period_belonging_to_another_forecast(self, tenant_a,
                                                                  forecast_with_periods_a,
                                                                  item_a):
        from apps.scm.models import DemandForecast, ForecastAdjustment
        from apps.scm.tests._helpers import add_months
        other = DemandForecast.objects.create(
            tenant=tenant_a, name="Other", item=item_a,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=add_months(forecast_with_periods_a.horizon_start,
                                   3) - datetime.timedelta(days=1))
        other.generate_periods()
        adjustment = ForecastAdjustment(tenant=tenant_a, forecast=forecast_with_periods_a,
                                        period=other.periods.first(), rationale="crafted")
        with pytest.raises(ValidationError) as excinfo:
            adjustment.clean()
        assert "period" in excinfo.value.message_dict

    def test_clean_accepts_a_period_of_its_own_forecast(self, forecast_adjustment_a):
        forecast_adjustment_a.clean()  # must not raise

    def test_is_reviewable_only_while_proposed(self, forecast_adjustment_a):
        assert forecast_adjustment_a.is_reviewable
        forecast_adjustment_a.status = "accepted"
        assert not forecast_adjustment_a.is_reviewable


# ================================================================================================
# DemandForecast / DemandForecastPeriod properties + clean()
# ================================================================================================
class TestDemandForecastProperties:
    def test_is_editable_tracks_the_open_statuses(self, demand_forecast_a):
        for status, editable in (("draft", True), ("statistical", True), ("in_review", True),
                                 ("approved", False), ("archived", False)):
            demand_forecast_a.status = status
            assert demand_forecast_a.is_editable is editable, status

    def test_effective_method_prefers_what_best_fit_actually_picked(self, demand_forecast_a):
        assert demand_forecast_a.effective_method == "moving_average"
        demand_forecast_a.selected_method = "holt_winters"
        assert demand_forecast_a.effective_method == "holt_winters"
        assert demand_forecast_a.effective_method_display == "Holt-Winters"

    def test_effective_method_display_falls_back_to_the_raw_slug(self, demand_forecast_a):
        demand_forecast_a.selected_method = "not_a_choice"
        assert demand_forecast_a.effective_method_display == "not_a_choice"

    def test_history_window_ends_the_day_before_the_horizon_opens(self, demand_forecast_a):
        from apps.scm.tests._helpers import add_months
        start, end = demand_forecast_a.history_window()
        assert end == demand_forecast_a.horizon_start - datetime.timedelta(days=1)
        assert start == add_months(demand_forecast_a.horizon_start, -24)

    def test_total_forecast_quantity_is_an_aggregate_not_a_stored_column(self,
                                                                         forecast_with_periods_a):
        assert forecast_with_periods_a.total_forecast_quantity() == Decimal("300.0000")

    def test_period_actuals_map_is_keyed_by_period_start(self, forecast_with_periods_a):
        actuals = forecast_with_periods_a.period_actuals_map()
        assert set(actuals) == {row.period_start for row in forecast_with_periods_a.periods.all()}

    def test_accuracy_metrics_are_all_none_before_anything_has_elapsed(self,
                                                                       forecast_with_periods_a):
        metrics = forecast_with_periods_a.accuracy_metrics()
        assert metrics["points"] == 0
        assert metrics["mape"] is None and metrics["wmape"] is None
        assert metrics["bias_pct"] is None and metrics["tracking_signal"] is None

    def test_accuracy_metrics_score_the_elapsed_periods(self, tenant_a, item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast, SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        start = add_months(this_month, -3)
        forecast = DemandForecast.objects.create(
            tenant=tenant_a, name="Elapsed plan", item=item_a, bucket="month", horizon_start=start,
            horizon_end=this_month - datetime.timedelta(days=1))
        forecast.generate_periods()
        for row in forecast.periods.all():
            row.baseline_quantity, row.final_quantity = Decimal("100"), Decimal("100")
            row.save(update_fields=["baseline_quantity", "final_quantity"])
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, order_date=start,
                                          status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("80"), unit_price=Decimal("1"))
        metrics = forecast.accuracy_metrics()
        assert metrics["points"] == 3
        assert metrics["mape"] == Decimal("25")  # |80-100|/80 over the only non-zero actual
        assert metrics["bias_pct"] > Decimal("0")  # the plan ran high

    def test_clean_rejects_a_horizon_that_ends_before_it_starts(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        forecast = DemandForecast(tenant=tenant_a, name="X", item=item_a,
                                  horizon_start=datetime.date(2026, 6, 1),
                                  horizon_end=datetime.date(2026, 1, 1))
        with pytest.raises(ValidationError) as excinfo:
            forecast.clean()
        assert "horizon_end" in excinfo.value.message_dict

    def test_clean_rejects_a_horizon_starting_before_the_minimum_year(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        forecast = DemandForecast(tenant=tenant_a, name="X", item=item_a,
                                  horizon_start=datetime.date(1800, 1, 1),
                                  horizon_end=datetime.date(1800, 3, 31))
        with pytest.raises(ValidationError) as excinfo:
            forecast.clean()
        assert "horizon_start" in excinfo.value.message_dict

    def test_clean_rejects_a_span_beyond_the_period_cap(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        forecast = DemandForecast(tenant=tenant_a, name="X", item=item_a, bucket="day",
                                  horizon_start=datetime.date(2026, 1, 1),
                                  horizon_end=datetime.date(2030, 1, 1))
        with pytest.raises(ValidationError) as excinfo:
            forecast.clean()
        assert "horizon_end" in excinfo.value.message_dict
        assert str(DemandForecast.MAX_HORIZON_PERIODS) in str(excinfo.value.message_dict)

    def test_clean_accepts_a_span_exactly_at_the_cap(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        start = datetime.date(2026, 1, 1)
        forecast = DemandForecast(
            tenant=tenant_a, name="X", item=item_a, bucket="day", horizon_start=start,
            horizon_end=start + datetime.timedelta(days=DemandForecast.MAX_HORIZON_PERIODS - 1))
        forecast.clean()  # must not raise

    def test_clean_requires_a_reference_item_for_a_like_item_forecast(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        forecast = DemandForecast(tenant=tenant_a, name="X", item=item_a, method="like_item",
                                  horizon_start=datetime.date(2026, 1, 1),
                                  horizon_end=datetime.date(2026, 3, 31))
        with pytest.raises(ValidationError) as excinfo:
            forecast.clean()
        assert "reference_item" in excinfo.value.message_dict

    def test_clean_rejects_a_reference_item_that_is_the_forecast_item(self, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        forecast = DemandForecast(tenant=tenant_a, name="X", item=item_a, reference_item=item_a,
                                  horizon_start=datetime.date(2026, 1, 1),
                                  horizon_end=datetime.date(2026, 3, 31))
        with pytest.raises(ValidationError) as excinfo:
            forecast.clean()
        assert "reference_item" in excinfo.value.message_dict


class TestDemandForecastPeriodProperties:
    def test_pre_adjustment_quantity_is_the_waterfall_up_to_consensus(self):
        from apps.scm.models import DemandForecastPeriod
        row = DemandForecastPeriod(baseline_quantity=Decimal("100"),
                                   seasonal_index_applied=Decimal("1.2"),
                                   event_uplift_quantity=Decimal("10"),
                                   signal_adjustment_quantity=Decimal("5"),
                                   consensus_quantity=Decimal("50"))
        assert row.pre_adjustment_quantity == Decimal("135.0")  # consensus deliberately excluded

    def test_seasonal_quantity_is_the_middle_step(self):
        from apps.scm.models import DemandForecastPeriod
        row = DemandForecastPeriod(baseline_quantity=Decimal("100"),
                                   seasonal_index_applied=Decimal("1.5"))
        assert row.seasonal_quantity == Decimal("150.0")

    def test_a_null_index_reads_as_neutral(self):
        from apps.scm.models import DemandForecastPeriod
        row = DemandForecastPeriod(baseline_quantity=Decimal("100"), seasonal_index_applied=None)
        assert row.seasonal_quantity == Decimal("100")

    def test_forecast_value_prices_the_units(self):
        from apps.scm.models import DemandForecastPeriod
        row = DemandForecastPeriod(final_quantity=Decimal("10"), unit_price=Decimal("2.50"))
        assert row.forecast_value == Decimal("25.00")


class TestQuantityClamping:
    def test_q4_clamps_to_what_the_column_holds(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _q4
        assert _q4(Decimal("1E+20")) == Decimal("9999999999.9999")
        assert _q4(Decimal("-1E+20")) == Decimal("-9999999999.9999")
        assert _q4(Decimal("1.23456")) == Decimal("1.2346")
        assert _q4(None) == Decimal("0.0000")


# ================================================================================================
# ReorderRule — the 4.7 safety-stock calculation extension (4.3's rule, extended in place)
# ================================================================================================
def _flat_history(months=12, qty="100"):
    """A flat monthly demand series, anchored on timezone.localdate() (L16)."""
    from django.utils import timezone
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return [(add_months(start, -m), Decimal(qty)) for m in range(months, 0, -1)]


def _lumpy_history(values):
    from django.utils import timezone
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return [(add_months(start, -(len(values) - i)), Decimal(v)) for i, v in enumerate(values)]


PER_DAY = Decimal("30.4375")  # the mean-days-per-month constant calculate() converts with


class TestReorderRuleSafetyStockCalculation:
    def test_calculate_writes_only_the_computed_columns(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        rule.save()
        rule.refresh_from_db()
        assert rule.safety_stock == Decimal("5.00")      # the buyer's number, untouched
        assert rule.reorder_point == Decimal("10.00")
        assert rule.computed_safety_stock > Decimal("0")
        assert rule.computed_reorder_point > Decimal("0")
        assert rule.last_calculated_at is not None

    def test_calculate_returns_the_pair_it_computed(self, reorder_rule_service_level_a):
        safety, point = reorder_rule_service_level_a.calculate(series=_flat_history())
        assert (safety, point) == (reorder_rule_service_level_a.computed_safety_stock,
                                   reorder_rule_service_level_a.computed_reorder_point)

    def test_average_daily_demand_converts_the_monthly_bucket(self, reorder_rule_service_level_a):
        reorder_rule_service_level_a.calculate(series=_flat_history(qty="100"))
        expected = (Decimal("100") / PER_DAY).quantize(Decimal("0.0001"))
        assert reorder_rule_service_level_a.avg_daily_demand == expected

    def test_service_level_counts_lead_time_variability(self, reorder_rule_service_level_a):
        """Ignoring sigma_L is the usual way a 'correct' formula still stocks out."""
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())  # flat demand -> sigma_d == 0
        with_variability = rule.computed_safety_stock
        rule.lead_time_variability_days = Decimal("0")
        rule.calculate(series=_flat_history())
        assert with_variability > Decimal("0")
        assert rule.computed_safety_stock == Decimal("0.00")

    def test_service_level_scales_with_the_z_factor(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        at_95 = rule.computed_safety_stock
        rule.service_level_pct = Decimal("99")
        rule.calculate(series=_flat_history())
        assert rule.computed_safety_stock > at_95

    def test_the_reorder_point_is_lead_time_demand_plus_the_buffer(self,
                                                                   reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        expected = ((Decimal("100") / PER_DAY) * Decimal(rule.lead_time_days)
                    + rule.computed_safety_stock)
        assert abs(rule.computed_reorder_point - expected) <= Decimal("0.01")

    def test_fixed_keeps_the_hand_entered_safety_stock(self, reorder_rule_a):
        assert reorder_rule_a.safety_stock_method == "fixed"
        reorder_rule_a.lead_time_days = 10
        reorder_rule_a.calculate(series=_flat_history())
        assert reorder_rule_a.computed_safety_stock == Decimal("5.00")

    def test_periodic_review_covers_a_longer_window_than_the_lead_time_alone(
        self, reorder_rule_service_level_a,
    ):
        rule = reorder_rule_service_level_a
        series = _lumpy_history([50, 150, 60, 200, 40, 180, 70, 120, 90, 160, 30, 210])
        rule.calculate(series=series)
        service_level = rule.computed_safety_stock
        rule.safety_stock_method, rule.review_period_days = "periodic_review", 30
        rule.calculate(series=series)
        assert rule.computed_safety_stock > service_level

    def test_avg_max_needs_no_statistics(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.safety_stock_method = "avg_max"
        rule.calculate(series=_flat_history())
        # Flat demand: max_daily == avg_daily, so safety = avg x (L + sigma_L) - avg x L.
        expected = ((Decimal("100") / PER_DAY) * rule.lead_time_variability_days)
        assert abs(rule.computed_safety_stock - expected) <= Decimal("0.01")

    def test_avg_max_on_an_empty_series_is_zero(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.safety_stock_method = "avg_max"
        rule.calculate(series=[])
        assert rule.computed_safety_stock == Decimal("0.00")

    def test_forecast_error_sizes_the_buffer_from_the_measured_error(
        self, reorder_rule_service_level_a, forecast_with_periods_a,
    ):
        from apps.scm.models.DemandPlanning import _forecasting as fx
        rule = reorder_rule_service_level_a
        rule.safety_stock_method = "forecast_error"
        rule.demand_forecast = forecast_with_periods_a
        rule.calculate(series=_flat_history(),
                       forecast_errors={forecast_with_periods_a.pk: Decimal("30")})
        avg = Decimal("100") / PER_DAY
        expected = (fx.z_for_service_level(Decimal("95")) * avg * Decimal("0.30")
                    * Decimal(rule.lead_time_days).sqrt())
        assert abs(rule.computed_safety_stock - expected) <= Decimal("0.01")

    def test_a_supplied_none_error_is_honoured_and_not_recomputed(
        self, reorder_rule_service_level_a, forecast_with_periods_a, django_assert_num_queries,
    ):
        """A PRESENT None means "this forecast has no measurable error yet" and must be believed.

        The batch caller passes a map, not a bare value, precisely so a supplied None can be told
        apart from "the caller supplied nothing". When they were conflated, every forecast without
        elapsed periods fell back to `accuracy_metrics()` — one aggregate per rule, which is the
        N+1 the batching exists to remove.
        """
        rule = reorder_rule_service_level_a
        rule.safety_stock_method = "forecast_error"
        rule.demand_forecast = forecast_with_periods_a
        with django_assert_num_queries(0):
            rule.calculate(series=_flat_history(),
                           forecast_errors={forecast_with_periods_a.pk: None})

    def test_forecast_error_without_a_linked_forecast_falls_back_to_service_level(
        self, reorder_rule_service_level_a,
    ):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        service_level = rule.computed_safety_stock
        rule.safety_stock_method = "forecast_error"  # no demand_forecast attached
        rule.calculate(series=_flat_history())
        assert rule.computed_safety_stock == service_level

    def test_forecast_error_falls_back_when_the_forecast_has_no_measurable_error(
        self, reorder_rule_service_level_a, forecast_with_periods_a,
    ):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        service_level = rule.computed_safety_stock
        rule.safety_stock_method = "forecast_error"
        rule.demand_forecast = forecast_with_periods_a  # nothing elapsed -> WMAPE is None
        rule.calculate(series=_flat_history())
        assert rule.computed_safety_stock == service_level

    def test_a_seasonal_profile_scales_the_buffer(self, tenant_a, item_a,
                                                  reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        plain = rule.computed_safety_stock
        rule.seasonality_profile = _flat_profile(tenant_a, item_a, "2.0000")
        rule.calculate(series=_flat_history())
        assert rule.computed_safety_stock == (plain * Decimal("2")).quantize(Decimal("0.01"))

    def test_an_inactive_seasonal_profile_does_not_scale(self, tenant_a, item_a,
                                                          reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        plain = rule.computed_safety_stock
        rule.seasonality_profile = _flat_profile(tenant_a, item_a, "2.0000", is_active=False)
        rule.calculate(series=_flat_history())
        assert rule.computed_safety_stock == plain

    def test_xyz_class_reads_the_coefficient_of_variation(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        assert rule.xyz_class == "X"  # perfectly steady
        rule.calculate(series=_lumpy_history([0, 0, 0, 500, 0, 0, 0, 600, 0, 0, 0, 400]))
        assert rule.xyz_class == "Z"  # erratic

    def test_xyz_class_is_blank_without_demand(self, reorder_rule_service_level_a):
        reorder_rule_service_level_a.calculate(series=_flat_history(qty="0"))
        assert reorder_rule_service_level_a.xyz_class == ""

    def test_a_negative_result_is_floored_at_zero(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.safety_stock_method = "avg_max"
        rule.lead_time_days, rule.lead_time_variability_days = 30, Decimal("0")
        rule.calculate(series=_lumpy_history([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]))
        assert rule.computed_safety_stock >= Decimal("0")

    def test_demand_history_passes_an_injected_series_straight_through(self,
                                                                       reorder_rule_service_level_a):
        series = _flat_history()
        assert reorder_rule_service_level_a.demand_history(series) is series

    def test_demand_history_derives_from_the_live_orders_when_none_is_injected(
        self, reorder_rule_service_level_a, demand_history_a,
    ):
        rows = reorder_rule_service_level_a.demand_history()
        assert sum((q for _, q in rows), Decimal("0")) > Decimal("0")


class TestReorderRuleApplyComputed:
    def test_apply_computed_is_the_only_promoter(self, reorder_rule_service_level_a):
        rule = reorder_rule_service_level_a
        rule.calculate(series=_flat_history())
        rule.save()
        computed_safety, computed_point = rule.computed_safety_stock, rule.computed_reorder_point
        assert rule.safety_stock == Decimal("5.00")  # calculate() alone changed nothing live
        rule.apply_computed()
        rule.refresh_from_db()
        assert rule.safety_stock == computed_safety
        assert rule.reorder_point == computed_point

    def test_apply_computed_returns_the_before_after_diff_for_the_audit_log(
        self, reorder_rule_service_level_a,
    ):
        rule = reorder_rule_service_level_a
        rule.refresh_from_db()
        before = str(rule.safety_stock)
        rule.calculate(series=_flat_history())
        rule.save()
        changes = rule.apply_computed()
        assert changes["safety_stock"][0] == before
        assert changes["safety_stock"][1] == str(rule.computed_safety_stock)
        assert set(changes) == {"safety_stock", "reorder_point"}

    def test_safety_stock_variance_is_computed_minus_live(self, reorder_rule_a):
        reorder_rule_a.computed_safety_stock = Decimal("20.00")
        assert reorder_rule_a.safety_stock_variance == Decimal("15.00")
        assert reorder_rule_a.safety_stock_variance_pct == Decimal("300")

    def test_variance_pct_is_none_when_there_is_nothing_to_compare_against(self, reorder_rule_b):
        reorder_rule_b.computed_safety_stock = Decimal("20.00")
        assert reorder_rule_b.safety_stock_variance_pct is None


class TestAssignAbcClasses:
    def _rule(self, tenant, location, sku, revenue, customer):
        from apps.scm.models import Item, ReorderRule, SalesOrder, SalesOrderLine
        item = Item.objects.create(tenant=tenant, sku=sku, name=sku)
        if revenue:
            order = SalesOrder.objects.create(tenant=tenant, customer=customer,
                                              order_date=datetime.date(2026, 1, 5),
                                              status="submitted")
            SalesOrderLine.objects.create(sales_order=order, item=item,
                                          quantity_ordered=Decimal("1"),
                                          unit_price=Decimal(revenue))
        return ReorderRule.objects.create(tenant=tenant, item=item, location=location)

    def test_the_top_earner_lands_in_a(self, tenant_a, location_a, customer_a):
        from apps.scm.models import ReorderRule
        top = self._rule(tenant_a, location_a, "TOP", "1000", customer_a)
        middle = self._rule(tenant_a, location_a, "MID", "100", customer_a)
        tail = self._rule(tenant_a, location_a, "TAIL", "10", customer_a)
        classes = ReorderRule.assign_abc_classes(tenant_a, [tail, middle, top])
        assert classes[top.pk] == "A"
        assert classes[middle.pk] == "B"
        assert classes[tail.pk] == "C"

    def test_a_single_rule_is_a_not_c(self, tenant_a, location_a, customer_a):
        """The band is decided by where the item STARTS on the Pareto curve, not where it ends."""
        from apps.scm.models import ReorderRule
        only = self._rule(tenant_a, location_a, "ONLY", "5000", customer_a)
        assert ReorderRule.assign_abc_classes(tenant_a, [only])[only.pk] == "A"

    def test_no_revenue_leaves_every_class_blank(self, tenant_a, location_a, customer_a):
        from apps.scm.models import ReorderRule
        rule = self._rule(tenant_a, location_a, "NOSALES", None, customer_a)
        assert ReorderRule.assign_abc_classes(tenant_a, [rule])[rule.pk] == ""

    def test_draft_and_cancelled_orders_do_not_count_as_revenue(self, tenant_a, location_a,
                                                                 customer_a):
        from apps.scm.models import Item, ReorderRule, SalesOrder, SalesOrderLine
        item = Item.objects.create(tenant=tenant_a, sku="DRAFTONLY", name="Draft only")
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=datetime.date(2026, 1, 5), status="draft")
        SalesOrderLine.objects.create(sales_order=order, item=item, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("9999"))
        rule = ReorderRule.objects.create(tenant=tenant_a, item=item, location=location_a)
        assert ReorderRule.assign_abc_classes(tenant_a, [rule])[rule.pk] == ""

    def test_an_empty_rule_set_returns_an_empty_map(self, tenant_a):
        from apps.scm.models import ReorderRule
        assert ReorderRule.assign_abc_classes(tenant_a, []) == {}

    def test_the_ranking_runs_in_one_grouped_query(self, tenant_a, location_a, customer_a,
                                                   django_assert_max_num_queries):
        from apps.scm.models import ReorderRule
        rules = [self._rule(tenant_a, location_a, f"SKU-{i}", str(100 - i), customer_a)
                 for i in range(6)]
        with django_assert_max_num_queries(1):
            ReorderRule.assign_abc_classes(tenant_a, rules)


# ================================================================ Bucket-aware year-back alignment
class TestSamePeriodLastYear:
    def test_a_weekly_bucket_steps_back_52_whole_weeks(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _same_period_last_year
        monday = datetime.date(2026, 5, 18)
        back = _same_period_last_year(monday, "week")
        assert back == monday - datetime.timedelta(days=364)
        assert back.weekday() == 0  # still a Monday, so the grid stays aligned

    def test_a_daily_bucket_steps_back_365_days(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _same_period_last_year
        assert _same_period_last_year(datetime.date(2026, 5, 18), "day") == datetime.date(2025, 5, 18)

    def test_a_monthly_bucket_keeps_the_calendar_day(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _same_period_last_year
        assert _same_period_last_year(datetime.date(2026, 5, 1), "month") == datetime.date(2025, 5, 1)

    def test_a_leap_day_falls_back_to_the_28th(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _same_period_last_year
        assert _same_period_last_year(datetime.date(2024, 2, 29), "month") == datetime.date(2023, 2, 28)

    def test_months_before_never_underflows_below_year_one(self):
        from apps.scm.models.DemandPlanning.DemandForecasts import _months_before
        assert _months_before(datetime.date(2026, 3, 15), 2) == datetime.date(2026, 1, 1)
        assert _months_before(datetime.date(2026, 3, 15), 15) == datetime.date(2024, 12, 1)


class TestWeeklyBucketForecast:
    def test_a_weekly_horizon_builds_weekly_buckets(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.models.DemandPlanning._history import bucket_start
        start = bucket_start(timezone.localdate(), "week")
        forecast = DemandForecast.objects.create(
            tenant=tenant_a, name="Weekly plan", item=item_a, bucket="week", horizon_start=start,
            horizon_end=start + datetime.timedelta(days=27))
        assert forecast.generate_periods() == 4
        rows = list(forecast.periods.all())
        assert rows[0].period_start == start
        assert rows[0].period_end == start + datetime.timedelta(days=6)
        assert rows[1].period_start == start + datetime.timedelta(days=7)
        assert rows[0].period_label.startswith("W")


class TestDemandSeriesLocationScope:
    def test_stock_issues_are_narrowed_to_one_location(self, tenant_a, item_a, location_a,
                                                       location_a2):
        from django.utils import timezone
        from apps.scm.models import StockMove
        from apps.scm.models.DemandPlanning._history import demand_series
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        when = add_months(this_month, -1)
        for location, qty in ((location_a, "-10"), (location_a2, "-40")):
            StockMove.objects.create(
                tenant=tenant_a, item=item_a, location=location, quantity=Decimal(qty),
                move_type="issue",
                moved_at=timezone.make_aware(datetime.datetime.combine(
                    when + datetime.timedelta(days=4), datetime.time(10, 0))))
        start, end = add_months(this_month, -12), this_month - datetime.timedelta(days=1)
        network = dict(demand_series(tenant_a.pk, item=item_a, source="stock_issues", start=start,
                                     end=end, bucket="month"))
        one_site = dict(demand_series(tenant_a.pk, item=item_a, location=location_a,
                                      source="stock_issues", start=start, end=end, bucket="month"))
        assert network[when] == Decimal("50")
        assert one_site[when] == Decimal("10")


# ================================================================================================
# SCM 4.8 Manufacturing
# ================================================================================================

# ================================================================ Auto-numbering + uniqueness
class TestManufacturingAutoNumbering:
    def test_work_center_numbers_are_sequential_per_tenant(self, tenant_a, tenant_b):
        from apps.scm.models import WorkCenter
        a1 = WorkCenter.objects.create(tenant=tenant_a, code="C1", name="One")
        a2 = WorkCenter.objects.create(tenant=tenant_a, code="C2", name="Two")
        b1 = WorkCenter.objects.create(tenant=tenant_b, code="C1", name="Globex one")
        assert (a1.number, a2.number) == ("WC-00001", "WC-00002")
        assert b1.number == "WC-00001"  # separate per-tenant sequence

    def test_bom_numbers_are_prefixed_bom(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        bom = BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name="R", version="9")
        assert bom.number == "BOM-00001"

    def test_work_order_numbers_are_prefixed_wo(self, tenant_a, item_a):
        from apps.scm.models import WorkOrder
        order = WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                         quantity_planned=Decimal("1"))
        assert order.number == "WO-00001"

    def test_time_log_numbers_are_prefixed_prd(self, tenant_a, work_order_a, work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        log = ProductionTimeLog.objects.create(tenant=tenant_a, work_order=work_order_a,
                                               work_center=work_center_a,
                                               started_at=timezone.now())
        assert log.number == "PRD-00001"

    def test_work_centre_code_is_unique_per_tenant(self, tenant_a, work_center_a):
        from apps.scm.models import WorkCenter
        with pytest.raises(IntegrityError):
            WorkCenter.objects.create(tenant=tenant_a, code=work_center_a.code, name="Clash")

    def test_the_same_work_centre_code_is_free_in_another_tenant(self, tenant_b, work_center_a):
        from apps.scm.models import WorkCenter
        twin = WorkCenter.objects.create(tenant=tenant_b, code=work_center_a.code, name="Twin")
        assert twin.pk != work_center_a.pk

    def test_bom_item_version_is_unique_per_tenant(self, tenant_a, bom_a, item_a):
        from apps.scm.models import BillOfMaterials
        with pytest.raises(IntegrityError):
            BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name="Clash",
                                           version=bom_a.version)

    def test_work_order_number_is_unique_per_tenant(self, tenant_a, work_order_a, item_a):
        from apps.scm.models import WorkOrder
        with pytest.raises(IntegrityError):
            WorkOrder.objects.create(tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
                                     number=work_order_a.number)

    def test_time_log_number_is_unique_per_tenant(self, tenant_a, time_log_a,
                                                  released_work_order_a, work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        with pytest.raises(IntegrityError):
            ProductionTimeLog.objects.create(tenant=tenant_a, work_order=released_work_order_a,
                                             work_center=work_center_a, started_at=timezone.now(),
                                             number=time_log_a.number)


# ================================================================ __str__ + defaults
class TestManufacturingStrAndDefaults:
    def test_work_centre_str(self, work_center_a):
        assert str(work_center_a) == "WC-CNC · CNC Cell"

    def test_bom_str(self, bom_a):
        assert str(bom_a) == f"{bom_a.number} · Widget recipe v1"

    def test_bom_line_str(self, bom_a, component_bolt_a):
        line = bom_a.lines.first()
        assert str(line) == f"{component_bolt_a} × 2.0000"

    def test_work_order_str(self, work_order_a, item_a):
        work_order_a.refresh_from_db()
        assert str(work_order_a) == f"{work_order_a.number} · {item_a} × 5.0000"

    def test_work_order_component_str(self, stocked_work_order_a):
        component = stocked_work_order_a.components.first()
        assert str(component) == f"{component.item} × {component.quantity_required}"

    def test_time_log_str(self, time_log_a):
        assert str(time_log_a) == f"{time_log_a.number} · Machine 60m"

    def test_a_new_work_order_defaults_to_draft_make_to_stock_normal_forward(self, tenant_a,
                                                                             item_a):
        from apps.scm.models import WorkOrder
        order = WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                         quantity_planned=Decimal("1"))
        assert order.status == "draft"
        assert order.order_policy == "make_to_stock"
        assert order.priority == "normal"
        assert order.schedule_direction == "forward"
        assert order.quantity_produced == Decimal("0")
        assert order.quantity_scrapped == Decimal("0")
        assert order.produced_unit_cost == Decimal("0")
        assert order.released_by_id is None

    def test_a_new_bom_defaults_to_draft_manufacture_one_output(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        bom = BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name="Defaults")
        assert (bom.status, bom.bom_type, bom.version) == ("draft", "manufacture", "1")
        assert bom.output_quantity == Decimal("1")
        assert bom.is_default is False
        assert bom.lead_time_days == 0

    def test_a_new_work_centre_defaults_to_an_active_8_hour_machine(self, tenant_a):
        from apps.scm.models import WorkCenter
        centre = WorkCenter.objects.create(tenant=tenant_a, code="D1", name="Defaults")
        assert centre.center_type == "machine"
        assert centre.capacity_hours_per_day == Decimal("8")
        assert centre.efficiency_pct == Decimal("100")
        assert centre.setup_minutes == 0
        assert centre.is_active is True

    def test_every_status_choice_is_reachable_on_a_work_order(self):
        from apps.scm.models import WorkOrder
        assert [value for value, _ in WorkOrder.STATUS_CHOICES] == [
            "draft", "planned", "released", "in_progress", "completed", "closed", "cancelled"]
        assert WorkOrder.EDITABLE_STATUSES == ("draft", "planned")
        assert WorkOrder.OPEN_STATUSES == ("released", "in_progress")

    def test_bom_and_time_log_choice_sets(self):
        from apps.scm.models import BillOfMaterials, BOMLine, ProductionTimeLog, WorkOrderComponent
        assert [v for v, _ in BillOfMaterials.STATUS_CHOICES] == ["draft", "active", "obsolete"]
        assert [v for v, _ in BillOfMaterials.BOM_TYPE_CHOICES] == ["manufacture", "kit", "phantom"]
        assert [v for v, _ in BOMLine.ISSUE_METHOD_CHOICES] == ["manual", "backflush"]
        assert [v for v, _ in WorkOrderComponent.ISSUE_METHOD_CHOICES] == ["manual", "backflush"]
        assert [v for v, _ in ProductionTimeLog.ENTRY_TYPE_CHOICES] == [
            "setup", "labor", "machine", "downtime"]


# ================================================================ WorkOrder.clean()
class TestWorkOrderClean:
    def test_a_bom_for_a_different_item_is_refused(self, tenant_a, bom_a, item_lot_a):
        """The create form offers every active BOM (the item isn't known until the form binds), so
        this clean() is the only thing standing between a mis-picked recipe and a run that
        consumes the wrong components."""
        from apps.scm.models import WorkOrder
        order = WorkOrder(tenant=tenant_a, item=item_lot_a, bom=bom_a,
                          quantity_planned=Decimal("1"))
        with pytest.raises(ValidationError) as exc:
            order.full_clean()
        assert "bom" in exc.value.error_dict
        assert "pick a BOM for the item being built" in str(exc.value)

    def test_the_matching_bom_passes(self, tenant_a, bom_a, item_a):
        from apps.scm.models import WorkOrder
        WorkOrder(tenant=tenant_a, item=item_a, bom=bom_a,
                  quantity_planned=Decimal("1")).full_clean()

    def test_a_planned_end_before_the_start_is_refused(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import WorkOrder
        now = timezone.now()
        order = WorkOrder(tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
                          planned_start=now, planned_end=now - datetime.timedelta(hours=1))
        with pytest.raises(ValidationError) as exc:
            order.full_clean()
        assert "planned_end" in exc.value.error_dict

    def test_a_make_to_order_run_without_its_peg_is_refused(self, tenant_a, item_a):
        from apps.scm.models import WorkOrder
        order = WorkOrder(tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
                          order_policy="make_to_order")
        with pytest.raises(ValidationError) as exc:
            order.full_clean()
        assert "sales_order" in exc.value.error_dict

    def test_a_zero_planned_quantity_is_refused(self, tenant_a, item_a):
        from apps.scm.models import WorkOrder
        with pytest.raises(ValidationError):
            WorkOrder(tenant=tenant_a, item=item_a, quantity_planned=Decimal("0")).full_clean()


# ================================================================ WorkOrder derived state
class TestWorkOrderDerivedState:
    def test_is_editable_only_in_draft_and_planned(self, work_order_a):
        for status, editable in (("draft", True), ("planned", True), ("released", False),
                                 ("in_progress", False), ("completed", False), ("closed", False),
                                 ("cancelled", False)):
            work_order_a.status = status
            assert work_order_a.is_editable is editable, status

    def test_is_open_only_while_released_or_in_progress(self, work_order_a):
        for status, live in (("draft", False), ("planned", False), ("released", True),
                             ("in_progress", True), ("completed", False), ("closed", False)):
            work_order_a.status = status
            assert work_order_a.is_open is live, status

    def test_quantity_remaining_nets_produced_and_scrapped(self, work_order_a):
        work_order_a.quantity_produced = Decimal("3")
        work_order_a.quantity_scrapped = Decimal("1")
        assert work_order_a.quantity_remaining == Decimal("1.0000")

    def test_quantity_remaining_never_goes_negative(self, work_order_a):
        work_order_a.quantity_produced = Decimal("9")
        assert work_order_a.quantity_remaining == Decimal("0.0000")

    def test_planned_hours_is_derived_from_the_window(self, work_order_a):
        from django.utils import timezone
        start = timezone.now()
        work_order_a.planned_start = start
        work_order_a.planned_end = start + datetime.timedelta(hours=7, minutes=30)
        assert work_order_a.planned_hours == Decimal("7.50")

    def test_planned_hours_is_zero_without_a_window(self, work_order_a):
        assert work_order_a.planned_hours == Decimal("0")

    def test_actual_hours_sums_the_time_logs(self, released_work_order_a, time_log_a):
        assert released_work_order_a.actual_hours == Decimal("1.00")

    def test_duration_variance_compares_actual_against_planned(self, released_work_order_a,
                                                               time_log_a):
        from django.utils import timezone
        start = timezone.now()
        released_work_order_a.planned_start = start
        released_work_order_a.planned_end = start + datetime.timedelta(hours=3)
        assert released_work_order_a.duration_variance_hours == Decimal("-2.00")


# ================================================================ Component snapshot
class TestWorkOrderComponentSnapshot:
    def test_explode_components_snapshots_the_recipe(self, work_order_a, component_bolt_a,
                                                     component_plate_a):
        assert work_order_a.explode_components() == 2
        rows = list(work_order_a.components.order_by("sequence"))
        assert [row.item_id for row in rows] == [component_bolt_a.pk, component_plate_a.pk]
        assert [row.quantity_required for row in rows] == [Decimal("10.0000"), Decimal("5.0000")]
        assert [row.sequence for row in rows] == [10, 20]
        assert [row.unit_cost for row in rows] == [Decimal("2.0000"), Decimal("5.0000")]

    def test_explode_components_is_a_no_op_once_lines_exist(self, stocked_work_order_a):
        """A hand-edited component set is never silently overwritten by a re-explode."""
        assert stocked_work_order_a.explode_components() == 0
        assert stocked_work_order_a.components.count() == 2

    def test_explode_components_does_nothing_without_a_bom(self, tenant_a, item_a):
        from apps.scm.models import WorkOrder
        order = WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                         quantity_planned=Decimal("4"))
        assert order.explode_components() == 0

    def test_the_snapshot_survives_a_later_recipe_edit(self, stocked_work_order_a, bom_a):
        """Components are a SNAPSHOT — a BOM edited next month cannot rewrite what a run three
        weeks ago actually required."""
        bom_a.lines.update(quantity_per=Decimal("99"))
        rows = list(stocked_work_order_a.components.order_by("sequence"))
        assert [row.quantity_required for row in rows] == [Decimal("10.0000"), Decimal("5.0000")]

    def test_quantity_outstanding_and_issued_value(self, stocked_work_order_a):
        component = stocked_work_order_a.components.order_by("sequence").first()
        assert component.quantity_outstanding == Decimal("10.0000")
        component.quantity_issued = Decimal("4")
        assert component.quantity_outstanding == Decimal("6.0000")
        assert component.issued_value == Decimal("8.0000")

    def test_quantity_outstanding_never_goes_negative(self, stocked_work_order_a):
        component = stocked_work_order_a.components.first()
        component.quantity_issued = Decimal("999")
        assert component.quantity_outstanding == Decimal("0.0000")


# ================================================================ material_shortfalls
class TestWorkOrderMaterialShortfalls:
    def test_a_short_component_is_reported_with_its_gap(self, work_order_a, component_bolt_a,
                                                        component_plate_a, location_a):
        from apps.scm.tests._helpers import seed_stock
        work_order_a.explode_components()
        seed_stock(work_order_a.tenant, component_bolt_a, location_a, "4", "2.0000")
        seed_stock(work_order_a.tenant, component_plate_a, location_a, "100", "5.0000")
        shortfalls = work_order_a.material_shortfalls()
        assert len(shortfalls) == 1
        row = shortfalls[0]
        assert row["component"].item_id == component_bolt_a.pk
        assert (row["required"], row["available"], row["short"]) == (
            Decimal("10.0000"), Decimal("4"), Decimal("6.0000"))

    def test_a_fully_covered_run_reports_nothing(self, stocked_work_order_a):
        assert stocked_work_order_a.material_shortfalls() == []

    def test_no_component_location_means_no_shortfall_report(self, stocked_work_order_a):
        stocked_work_order_a.component_location = None
        assert stocked_work_order_a.material_shortfalls() == []


# ================================================================ Derived costs (ledger + logs)
def _issue_everything(order, user):
    """Draw every outstanding component through the real posting helper."""
    from apps.scm.views.Manufacturing.WorkOrders import _issue_components
    components = list(order.components.select_related("item", "lot_serial"))
    return _issue_components(order, components,
                             {c.pk: c.quantity_outstanding for c in components}, user)


class TestWorkOrderDerivedCosts:
    def test_material_cost_is_summed_from_the_ledger_not_the_snapshot(self, released_work_order_a,
                                                                      admin_user):
        assert released_work_order_a.material_cost == Decimal("0.0000")  # nothing drawn yet
        _issue_everything(released_work_order_a, admin_user)
        assert released_work_order_a.material_cost == Decimal("45.0000")

    def test_labour_and_machine_cost_come_from_the_time_logs(self, released_work_order_a,
                                                             work_center_a, time_log_a, tenant_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            entry_type="labor", started_at=started,
            ended_at=started + datetime.timedelta(hours=2))
        assert released_work_order_a.machine_cost == Decimal("10.0000")   # 1 h x 10.00
        assert released_work_order_a.labor_cost == Decimal("40.0000")     # 2 h x 20.00

    def test_downtime_is_excluded_from_the_cost_pool(self, released_work_order_a, work_center_a,
                                                     tenant_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            entry_type="downtime", downtime_reason="breakdown", started_at=started,
            ended_at=started + datetime.timedelta(hours=5))
        assert released_work_order_a.labor_cost == Decimal("0.0000")
        assert released_work_order_a.machine_cost == Decimal("0.0000")

    def test_setup_time_absorbs_at_the_labour_rate(self, released_work_order_a, work_center_a,
                                                   tenant_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            entry_type="setup", started_at=started,
            ended_at=started + datetime.timedelta(minutes=30))
        assert released_work_order_a.labor_cost == Decimal("10.0000")  # 0.5 h x 20.00

    def test_nothing_about_the_cost_pool_is_a_stored_column(self):
        from apps.scm.models import WorkOrder
        stored = {field.name for field in WorkOrder._meta.fields}
        for derived in ("material_cost", "labor_cost", "machine_cost", "wip_value"):
            assert derived not in stored, derived

    def test_wip_value_is_cost_in_less_value_taken_out(self, released_work_order_a, admin_user,
                                                       time_log_a):
        _issue_everything(released_work_order_a, admin_user)
        # 45.00 material + 10.00 machine (1 h) - nothing produced yet.
        assert released_work_order_a.wip_value == Decimal("55.0000")


# ================================================================ computed_unit_cost (the big one)
class TestWorkOrderComputedUnitCost:
    def test_it_divides_the_UNABSORBED_pool_by_this_layer_only(self, released_work_order_a,
                                                               admin_user, time_log_a):
        """The regression lock. Pool = 45 material + 10 machine = 55.

        Layer 1 of 3 units absorbs 55/3; layer 2 of 2 units must then see an EMPTY pool, not
        55/5 again — the formula this replaced banked 3x(55/3) + 2x(55/5) = 77.00 against 55.00
        of real cost, and drove wip_value negative.
        """
        from apps.scm.views._helpers import _post_stock_move
        _issue_everything(released_work_order_a, admin_user)
        first = released_work_order_a.computed_unit_cost(Decimal("3"))
        assert first == Decimal("18.3333")  # 55 / 3
        _post_stock_move(released_work_order_a.tenant, item=released_work_order_a.item,
                         location=released_work_order_a.output_location, quantity=Decimal("3"),
                         move_type="production", unit_cost=first,
                         reference=released_work_order_a.number)
        # 55 - (3 x 18.3333) = 0.0001 unabsorbed; spread over 2 more units that is sub-quantum.
        assert released_work_order_a.computed_unit_cost(Decimal("2")) == Decimal("0.0000")

    def test_a_zero_or_negative_good_quantity_costs_nothing(self, released_work_order_a):
        assert released_work_order_a.computed_unit_cost(Decimal("0")) == Decimal("0")
        assert released_work_order_a.computed_unit_cost(Decimal("-5")) == Decimal("0")
        assert released_work_order_a.computed_unit_cost(None) == Decimal("0")

    def test_an_already_absorbed_pool_costs_nothing(self, released_work_order_a):
        assert released_work_order_a.computed_unit_cost(Decimal("5")) == Decimal("0")

    def test_scrap_is_absorbed_by_the_units_that_survived(self, released_work_order_a, admin_user):
        """The pool divides by the GOOD quantity, so a scrappy run reports a HIGHER unit cost
        rather than hiding the loss."""
        _issue_everything(released_work_order_a, admin_user)
        assert released_work_order_a.computed_unit_cost(Decimal("5")) == Decimal("9.0000")
        assert released_work_order_a.computed_unit_cost(Decimal("4")) == Decimal("11.2500")


# ================================================================ BillOfMaterials effectivity
class TestBillOfMaterialsEffectivity:
    def test_a_draft_recipe_is_never_effective(self, bom_draft_a):
        assert bom_draft_a.is_effective() is False

    def test_an_active_open_ended_recipe_is_effective_today(self, bom_a):
        from django.utils import timezone
        assert bom_a.is_effective(timezone.localdate()) is True

    def test_a_window_that_has_not_opened_is_not_effective(self, bom_a):
        from django.utils import timezone
        today = timezone.localdate()
        bom_a.effective_from = today + datetime.timedelta(days=5)
        assert bom_a.is_effective(today) is False

    def test_a_window_that_has_closed_is_not_effective(self, bom_a):
        from django.utils import timezone
        today = timezone.localdate()
        bom_a.effective_to = today - datetime.timedelta(days=1)
        assert bom_a.is_effective(today) is False

    def test_active_for_prefers_the_default_recipe(self, tenant_a, item_a, bom_a):
        from apps.scm.models import BillOfMaterials
        BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name="Alt", version="2",
                                       status="active")
        assert BillOfMaterials.active_for(tenant_a, item_a) == bom_a

    def test_active_for_returns_none_without_a_tenant_or_item(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        assert BillOfMaterials.active_for(None, item_a) is None
        assert BillOfMaterials.active_for(tenant_a, None) is None

    def test_make_vs_buy_is_derived_not_a_flag(self, tenant_a, item_a, bom_a, component_bolt_a):
        from apps.scm.models import BillOfMaterials, Item
        assert BillOfMaterials.is_manufactured(tenant_a, item_a) is True
        assert BillOfMaterials.is_manufactured(tenant_a, component_bolt_a) is False
        assert "is_manufactured" not in {f.name for f in Item._meta.fields}

    def test_manufactured_item_ids_answers_the_whole_tenant_at_once(self, tenant_a, item_a, bom_a,
                                                                    bom_draft_a,
                                                                    django_assert_max_num_queries):
        from apps.scm.models import BillOfMaterials
        with django_assert_max_num_queries(1):
            ids = BillOfMaterials.manufactured_item_ids(tenant_a)
        assert ids == {item_a.pk}  # bom_draft_a is draft, so its item is still bought

    def test_manufactured_item_ids_is_empty_without_a_tenant(self):
        from apps.scm.models import BillOfMaterials
        assert BillOfMaterials.manufactured_item_ids(None) == set()

    def test_explosion_index_agrees_with_active_for(self, tenant_a, item_a, bom_a):
        from apps.scm.models import BillOfMaterials
        index = BillOfMaterials.explosion_index(tenant_a.pk)
        assert index[item_a.pk] == BillOfMaterials.active_for(tenant_a, item_a)

    def test_explosion_index_is_empty_without_a_tenant(self):
        from apps.scm.models import BillOfMaterials
        assert BillOfMaterials.explosion_index(None) == {}


# ================================================================ BillOfMaterials.clean() / save()
class TestBillOfMaterialsValidation:
    def test_effective_to_before_from_is_refused(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        bom = BillOfMaterials(tenant=tenant_a, item=item_a, name="Bad window", version="7",
                              effective_from=datetime.date(2026, 6, 1),
                              effective_to=datetime.date(2026, 5, 1))
        with pytest.raises(ValidationError) as exc:
            bom.full_clean()
        assert "effective_to" in exc.value.error_dict

    def test_a_second_default_recipe_is_refused_on_a_validated_form(self, tenant_a, item_a, bom_a):
        from apps.scm.models import BillOfMaterials
        clash = BillOfMaterials(tenant=tenant_a, item=item_a, name="Second default", version="2",
                                is_default=True)
        with pytest.raises(ValidationError) as exc:
            clash.full_clean()
        assert "is_default" in exc.value.error_dict

    def test_save_demotes_a_sibling_default_for_programmatic_writers(self, tenant_a, item_a,
                                                                     bom_a):
        from apps.scm.models import BillOfMaterials
        BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name="Seeded default",
                                       version="3", is_default=True)
        bom_a.refresh_from_db()
        assert bom_a.is_default is False

    def test_an_output_quantity_of_zero_is_refused(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        with pytest.raises(ValidationError):
            BillOfMaterials(tenant=tenant_a, item=item_a, name="Zero", version="8",
                            output_quantity=Decimal("0")).full_clean()

    def test_a_lead_time_beyond_ten_years_is_refused(self, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        with pytest.raises(ValidationError):
            BillOfMaterials(tenant=tenant_a, item=item_a, name="Slow", version="9",
                            lead_time_days=3651).full_clean()

    def test_scrap_pct_is_bounded_to_100(self, bom_a, component_bolt_a):
        from apps.scm.models import BOMLine
        with pytest.raises(ValidationError):
            BOMLine(bom=bom_a, component=component_bolt_a, quantity_per=Decimal("1"),
                    scrap_pct=Decimal("101")).full_clean()


# ================================================================ BillOfMaterials.explode()
class TestBillOfMaterialsExplode:
    def _item(self, tenant, sku, cost="1.0000"):
        from apps.scm.models import Item
        return Item.objects.create(tenant=tenant, sku=sku, name=sku, standard_cost=Decimal(cost))

    def _bom(self, tenant, item, components, version="1"):
        from apps.scm.models import BillOfMaterials, BOMLine
        bom = BillOfMaterials.objects.create(tenant=tenant, item=item, name=f"{item.sku} recipe",
                                             version=version, status="active")
        for index, (component, per) in enumerate(components):
            BOMLine.objects.create(bom=bom, sequence=(index + 1) * 10, component=component,
                                   quantity_per=Decimal(per))
        return bom

    def test_a_single_level_recipe_scales_by_the_order_quantity(self, bom_a, component_bolt_a,
                                                                component_plate_a):
        rows = bom_a.explode(Decimal("5"))
        assert [(row["item"].pk, row["quantity"], row["level"]) for row in rows] == [
            (component_bolt_a.pk, Decimal("10.0000"), 1),
            (component_plate_a.pk, Decimal("5.0000"), 1)]

    def test_scrap_grosses_the_requirement_up(self, bom_a):
        line = bom_a.lines.order_by("sequence").first()
        line.scrap_pct = Decimal("10")
        line.save(update_fields=["scrap_pct"])
        assert line.effective_quantity_per == Decimal("2.2000")
        assert bom_a.explode(Decimal("5"))[0]["quantity"] == Decimal("11.0000")

    def test_output_quantity_divides_the_requirement(self, bom_a):
        bom_a.output_quantity = Decimal("10")
        bom_a.save(update_fields=["output_quantity"])
        assert bom_a.explode(Decimal("5"))[0]["quantity"] == Decimal("1.0000")

    def test_a_component_with_its_own_recipe_recurses(self, tenant_a):
        top = self._item(tenant_a, "TOP-1")
        mid = self._item(tenant_a, "MID-1")
        raw = self._item(tenant_a, "RAW-1")
        self._bom(tenant_a, top, [(mid, "2")])
        self._bom(tenant_a, mid, [(raw, "3")])
        rows = top.boms.first().explode(Decimal("1"))
        assert [(row["item"].pk, row["quantity"], row["level"]) for row in rows] == [
            (raw.pk, Decimal("6.0000"), 2)]

    def test_a_cycle_terminates_and_emits_the_revisited_item_as_a_leaf(self, tenant_a):
        """A -> B -> A across two individually-valid BOMs. Silently losing the requirement would
        UNDERSTATE the shortage, which is the more dangerous failure — so it is emitted, not
        dropped."""
        alpha = self._item(tenant_a, "CYC-A")
        beta = self._item(tenant_a, "CYC-B")
        bom_alpha = self._bom(tenant_a, alpha, [(beta, "2")])
        self._bom(tenant_a, beta, [(alpha, "3")])
        rows = bom_alpha.explode(Decimal("1"))
        assert len(rows) == 1
        assert rows[0]["item"].pk == alpha.pk       # the revisited ancestor, emitted as a LEAF
        assert rows[0]["quantity"] == Decimal("6.0000")
        assert rows[0]["level"] == 2

    def test_the_depth_cap_stops_a_legal_but_absurd_nesting(self, tenant_a):
        chain = [self._item(tenant_a, f"CHN-{i}") for i in range(4)]
        for parent, child in zip(chain, chain[1:]):
            self._bom(tenant_a, parent, [(child, "1")])
        top_bom = chain[0].boms.first()
        assert [row["item"].pk for row in top_bom.explode(Decimal("1"))] == [chain[3].pk]
        capped = top_bom.explode(Decimal("1"), depth_cap=2)
        assert [row["item"].pk for row in capped] == [chain[2].pk]
        assert capped[0]["level"] == 2

    def test_the_documented_caps(self):
        from apps.scm.models import BillOfMaterials
        assert BillOfMaterials.MAX_EXPLODE_DEPTH == 5
        assert BillOfMaterials.MAX_EXPLODE_ROWS == 5000

    def test_max_explode_rows_truncates_a_wide_graph_rather_than_running_away(self, tenant_a,
                                                                              monkeypatch):
        """Depth alone does NOT bound the output — the result is the PRODUCT of the branch
        factors, so the row budget is a denial-of-service bound, not a tidiness one."""
        from apps.scm.models import BillOfMaterials
        monkeypatch.setattr(BillOfMaterials, "MAX_EXPLODE_ROWS", 3)
        wide = self._item(tenant_a, "WIDE-1")
        leaves = [self._item(tenant_a, f"LEAF-{i}") for i in range(8)]
        bom = self._bom(tenant_a, wide, [(leaf, "1") for leaf in leaves])
        rows = bom.explode(Decimal("1"))
        assert len(rows) == 3
        assert bom.explode_was_truncated(rows) is True

    def test_the_budget_is_shared_across_every_frame_of_the_recursion(self, tenant_a,
                                                                      monkeypatch):
        """A per-frame budget would let a nested recipe emit MAX_EXPLODE_ROWS per level."""
        from apps.scm.models import BillOfMaterials
        monkeypatch.setattr(BillOfMaterials, "MAX_EXPLODE_ROWS", 4)
        top = self._item(tenant_a, "BDG-TOP")
        mids = [self._item(tenant_a, f"BDG-MID-{i}") for i in range(3)]
        self._bom(tenant_a, top, [(mid, "1") for mid in mids])
        for i, mid in enumerate(mids):
            leaves = [self._item(tenant_a, f"BDG-LEAF-{i}-{j}") for j in range(3)]
            self._bom(tenant_a, mid, [(leaf, "1") for leaf in leaves])
        rows = top.boms.first().explode(Decimal("1"))
        assert len(rows) == 4  # not 3 x 3 = 9, and not 4 per branch either

    def test_an_untruncated_explosion_reports_so(self, bom_a):
        rows = bom_a.explode(Decimal("1"))
        assert bom_a.explode_was_truncated(rows) is False

    def test_estimated_unit_cost_rolls_up_the_exploded_leaves(self, bom_a):
        # 2 bolts @ 2.00 + 1 plate @ 5.00, per 1 output unit.
        assert bom_a.estimated_unit_cost() == Decimal("9.0000")

    def test_estimated_unit_cost_reuses_supplied_rows(self, bom_a, django_assert_max_num_queries):
        rows = bom_a.explode(bom_a.output_quantity)
        with django_assert_max_num_queries(0):
            assert bom_a.estimated_unit_cost(rows=rows) == Decimal("9.0000")

    def test_component_count_counts_the_single_level_lines(self, bom_a):
        assert bom_a.component_count == 2


# ================================================================ WorkCenter capacity + OEE
class TestWorkCenterCapacityAndOEE:
    def test_cost_per_hour_is_machine_plus_labour(self, work_center_a):
        assert work_center_a.cost_per_hour == Decimal("30.0000")

    def test_effective_capacity_scales_by_efficiency(self, work_center_a):
        work_center_a.efficiency_pct = Decimal("75")
        assert work_center_a.effective_capacity_hours(10) == Decimal("60.00")

    def test_scheduled_hours_counts_a_run_that_STRADDLES_the_window_edge(self, tenant_a, item_a,
                                                                         work_center_a):
        from django.utils import timezone
        from apps.scm.models import WorkOrder
        now = timezone.now()
        WorkOrder.objects.create(
            tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
            work_center=work_center_a, planned_start=now - datetime.timedelta(days=1),
            planned_end=now + datetime.timedelta(days=1))
        assert work_center_a.scheduled_hours(
            now, now + datetime.timedelta(days=7)) == Decimal("48.00")

    def test_scheduled_hours_excludes_cancelled_and_closed_runs(self, tenant_a, item_a,
                                                                work_center_a):
        from django.utils import timezone
        from apps.scm.models import WorkOrder
        now = timezone.now()
        for status in ("cancelled", "closed"):
            order = WorkOrder.objects.create(
                tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
                work_center=work_center_a, planned_start=now,
                planned_end=now + datetime.timedelta(hours=4))
            WorkOrder.objects.filter(pk=order.pk).update(status=status)
        assert work_center_a.scheduled_hours(now, now + datetime.timedelta(days=7)) == Decimal("0")

    def test_scheduled_hours_is_zero_without_a_window(self, work_center_a):
        assert work_center_a.scheduled_hours(None, None) == Decimal("0")

    def test_the_batched_map_agrees_with_the_per_instance_figure(self, tenant_a, item_a,
                                                                 work_center_a, work_center_a2,
                                                                 django_assert_max_num_queries):
        from django.utils import timezone
        from apps.scm.models import WorkCenter, WorkOrder
        now = timezone.now()
        for centre, hours in ((work_center_a, 4), (work_center_a2, 6)):
            WorkOrder.objects.create(
                tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"), work_center=centre,
                planned_start=now, planned_end=now + datetime.timedelta(hours=hours))
        end = now + datetime.timedelta(days=7)
        with django_assert_max_num_queries(1):
            mapped = WorkCenter.scheduled_hours_map(tenant_a, now, end)
        assert mapped == {work_center_a.pk: Decimal("4.00"), work_center_a2.pk: Decimal("6.00")}
        assert mapped[work_center_a.pk] == work_center_a.scheduled_hours(now, end)

    def test_the_batched_map_is_empty_without_a_tenant_or_window(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import WorkCenter
        assert WorkCenter.scheduled_hours_map(None, timezone.now(), timezone.now()) == {}
        assert WorkCenter.scheduled_hours_map(tenant_a, None, None) == {}

    def test_actual_hours_sums_the_booked_minutes(self, work_center_a, time_log_a):
        from django.utils import timezone
        now = timezone.now()
        assert work_center_a.actual_hours(now - datetime.timedelta(days=1), now) == Decimal("1.00")

    def test_utilization_reads_the_supplied_actual_without_re_aggregating(
        self, work_center_a, time_log_a, django_assert_max_num_queries,
    ):
        from django.utils import timezone
        now = timezone.now()
        with django_assert_max_num_queries(0):
            pct = work_center_a.utilization_pct(now - datetime.timedelta(days=30), now, days=30,
                                                actual=Decimal("120.00"))
        assert pct == Decimal("50.00")  # 120 booked / 240 capacity

    def test_utilization_is_zero_when_the_centre_has_no_capacity(self, work_center_a):
        from django.utils import timezone
        work_center_a.capacity_hours_per_day = Decimal("0")
        now = timezone.now()
        assert work_center_a.utilization_pct(now - datetime.timedelta(days=1), now) == Decimal("0")

    def test_the_oee_chip_splits_runtime_from_downtime_and_scrap(self, tenant_a,
                                                                 released_work_order_a,
                                                                 work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        now = timezone.now()
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            entry_type="machine", started_at=now - datetime.timedelta(hours=3),
            ended_at=now - datetime.timedelta(hours=2), quantity_completed=Decimal("8"),
            quantity_scrapped=Decimal("2"))
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            entry_type="downtime", downtime_reason="breakdown",
            started_at=now - datetime.timedelta(hours=2),
            ended_at=now - datetime.timedelta(minutes=90))
        chip = work_center_a.oee_chip(now - datetime.timedelta(days=1), now)
        assert chip["run_hours"] == Decimal("1.00")
        assert chip["downtime_hours"] == Decimal("0.50")
        assert chip["booked_hours"] == Decimal("1.50")
        assert chip["availability_pct"] == Decimal("66.67")
        assert chip["quantity_good"] == Decimal("8.0000")
        assert chip["quantity_scrapped"] == Decimal("2.0000")
        assert chip["quality_pct"] == Decimal("80.00")

    def test_an_empty_window_yields_a_zeroed_chip(self, work_center_a):
        from django.utils import timezone
        now = timezone.now()
        chip = work_center_a.oee_chip(now - datetime.timedelta(days=1), now)
        assert chip["availability_pct"] == Decimal("0")
        assert chip["quality_pct"] == Decimal("0")
        assert chip["booked_hours"] == Decimal("0.00")

    def test_nothing_about_load_is_a_stored_column(self):
        from apps.scm.models import WorkCenter
        stored = {field.name for field in WorkCenter._meta.fields}
        for derived in ("scheduled_hours", "actual_hours", "utilization_pct", "load_pct"):
            assert derived not in stored, derived


# ================================================================ ProductionTimeLog
class TestProductionTimeLog:
    def test_duration_is_derived_from_the_interval_never_typed(self, tenant_a,
                                                               released_work_order_a,
                                                               work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        log = ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            started_at=started, ended_at=started + datetime.timedelta(minutes=95),
            duration_minutes=99999)
        assert log.duration_minutes == 95   # the typed figure never survives save()
        assert log.duration_hours == Decimal("1.58")

    def test_an_open_ended_entry_books_zero_minutes(self, tenant_a, released_work_order_a,
                                                    work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        log = ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            started_at=timezone.now())
        assert log.duration_minutes == 0

    def test_the_derived_duration_rides_along_with_a_narrow_update_fields(self, time_log_a):
        """A caller passing update_fields=['ended_at'] must not persist a new interval and leave
        the stale duration behind."""
        time_log_a.ended_at = time_log_a.started_at + datetime.timedelta(hours=3)
        time_log_a.save(update_fields=["ended_at"])
        time_log_a.refresh_from_db()
        assert time_log_a.duration_minutes == 180

    def test_an_end_before_the_start_is_refused(self, tenant_a, released_work_order_a,
                                                work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        log = ProductionTimeLog(tenant=tenant_a, work_order=released_work_order_a,
                                work_center=work_center_a, started_at=started,
                                ended_at=started - datetime.timedelta(minutes=1))
        with pytest.raises(ValidationError) as exc:
            log.full_clean()
        assert "ended_at" in exc.value.error_dict

    def test_an_interval_longer_than_31_days_is_refused(self, tenant_a, released_work_order_a,
                                                        work_center_a):
        """duration_minutes is editable=False so it never sees form validation, and a
        1000-01-01 -> 9999-12-31 interval derives past what the column holds — a 500, not a
        rejection."""
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        log = ProductionTimeLog(tenant=tenant_a, work_order=released_work_order_a,
                                work_center=work_center_a, started_at=started,
                                ended_at=started + datetime.timedelta(days=32))
        with pytest.raises(ValidationError) as exc:
            log.full_clean()
        assert "ended_at" in exc.value.error_dict
        assert "31 days" in str(exc.value)

    def test_exactly_31_days_is_still_accepted(self, tenant_a, released_work_order_a,
                                               work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        ProductionTimeLog(tenant=tenant_a, work_order=released_work_order_a,
                          work_center=work_center_a, started_at=started,
                          ended_at=started + datetime.timedelta(days=31)).full_clean()

    def test_a_downtime_entry_needs_a_reason(self, tenant_a, released_work_order_a,
                                             work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        log = ProductionTimeLog(tenant=tenant_a, work_order=released_work_order_a,
                                work_center=work_center_a, entry_type="downtime",
                                started_at=timezone.now())
        with pytest.raises(ValidationError) as exc:
            log.full_clean()
        assert "downtime_reason" in exc.value.error_dict

    def test_only_a_downtime_entry_carries_a_reason(self, tenant_a, released_work_order_a,
                                                    work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        log = ProductionTimeLog(tenant=tenant_a, work_order=released_work_order_a,
                                work_center=work_center_a, entry_type="labor",
                                downtime_reason="breakdown", started_at=timezone.now())
        with pytest.raises(ValidationError) as exc:
            log.full_clean()
        assert "downtime_reason" in exc.value.error_dict

    def test_per_entry_costs_route_to_the_right_rate(self, tenant_a, released_work_order_a,
                                                     work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        rows = {}
        for entry_type in ("setup", "labor", "machine", "downtime"):
            rows[entry_type] = ProductionTimeLog.objects.create(
                tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
                entry_type=entry_type,
                downtime_reason="breakdown" if entry_type == "downtime" else "",
                started_at=started, ended_at=started + datetime.timedelta(hours=1))
        assert rows["setup"].labor_cost == Decimal("20.0000")
        assert rows["labor"].labor_cost == Decimal("20.0000")
        assert rows["labor"].machine_cost == Decimal("0")
        assert rows["machine"].machine_cost == Decimal("10.0000")
        assert rows["machine"].labor_cost == Decimal("0")
        assert rows["downtime"].labor_cost == Decimal("0")
        assert rows["downtime"].machine_cost == Decimal("0")

    def test_quantity_completed_never_rolls_up_into_the_run(self, released_work_order_a, tenant_a,
                                                            work_center_a):
        """Advisory progress. quantity_produced has exactly ONE writer — the report action that
        also posts the finished-goods StockMove."""
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        ProductionTimeLog.objects.create(
            tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
            started_at=timezone.now(), quantity_completed=Decimal("40"))
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")


# ================================================================ 4.8 residual branches
class TestManufacturingResidualBranches:
    def test_re_saving_the_EXISTING_default_recipe_is_not_a_clash_with_itself(self, bom_a):
        """clean() excludes the row's own pk — otherwise the one default per item rule would make
        an already-default BOM permanently un-editable."""
        bom_a.notes = "Touched"
        bom_a.full_clean()
        bom_a.save()
        bom_a.refresh_from_db()
        assert bom_a.is_default is True
        assert bom_a.notes == "Touched"

    def test_work_centre_actual_hours_is_zero_without_a_window(self, work_center_a, time_log_a):
        assert work_center_a.actual_hours(None, None) == Decimal("0")

    def test_utilization_re_aggregates_when_no_actual_is_supplied(self, work_center_a,
                                                                  time_log_a):
        from django.utils import timezone
        now = timezone.now()
        # 1 booked hour against 8 h/day x 100 % over 1 day.
        assert work_center_a.utilization_pct(now - datetime.timedelta(days=1), now,
                                             days=1) == Decimal("12.50")

    def test_a_lot_tracked_component_is_measured_against_ITS_OWN_lot(self, tenant_a, work_order_a,
                                                                     item_lot_a, lot_a,
                                                                     location_a):
        """Checking the item's tenant-wide total instead would hide a shortage in the very lot the
        line names."""
        from apps.scm.models import LotSerial, WorkOrderComponent
        from apps.scm.tests._helpers import seed_stock
        other_lot = LotSerial.objects.create(tenant=tenant_a, item=item_lot_a, kind="lot",
                                             number="LOT-0002")
        WorkOrderComponent.objects.create(work_order=work_order_a, sequence=10, item=item_lot_a,
                                          quantity_required=Decimal("10"), lot_serial=lot_a)
        seed_stock(tenant_a, item_lot_a, location_a, "3", "1.0000")          # into no lot at all
        move = seed_stock(tenant_a, item_lot_a, location_a, "50", "1.0000")  # into the WRONG lot
        move.lot_serial = other_lot
        move.save(update_fields=["lot_serial"])
        shortfalls = work_order_a.material_shortfalls()
        assert len(shortfalls) == 1
        assert shortfalls[0]["available"] == Decimal("0")   # LOT-0001 holds none of it
        assert shortfalls[0]["short"] == Decimal("10.0000")


# ================================================================================================
# SCM 4.9 Quality Management
# ================================================================================================

# ================================================================ Auto-numbering + uniqueness
class TestQualityAutoNumbering:
    def test_inspection_numbers_are_sequential_per_tenant(self, tenant_a, tenant_b, item_a,
                                                          item_b):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        today = timezone.localdate()
        a1 = QualityInspection.objects.create(tenant=tenant_a, item=item_a, inspected_on=today)
        a2 = QualityInspection.objects.create(tenant=tenant_a, item=item_a, inspected_on=today)
        b1 = QualityInspection.objects.create(tenant=tenant_b, item=item_b, inspected_on=today)
        assert (a1.number, a2.number) == ("QC-00001", "QC-00002")
        assert b1.number == "QC-00001"

    def test_nonconformance_numbers_are_prefixed_ncr(self, nonconformance_a):
        assert nonconformance_a.number == "NCR-00001"

    def test_capa_numbers_are_prefixed_capa(self, capa_action_a):
        assert capa_action_a.number == "CAPA-00001"

    def test_audit_numbers_are_prefixed_qa(self, quality_audit_a):
        assert quality_audit_a.number == "QA-00001"

    def test_inspection_number_is_unique_per_tenant(self, tenant_a, quality_inspection_a, item_a):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        with pytest.raises(IntegrityError):
            QualityInspection.objects.create(tenant=tenant_a, item=item_a,
                                             inspected_on=timezone.localdate(),
                                             number=quality_inspection_a.number)

    def test_nonconformance_number_is_unique_per_tenant(self, tenant_a, nonconformance_a, item_a):
        from django.utils import timezone
        from apps.scm.models import NonConformance
        with pytest.raises(IntegrityError):
            NonConformance.objects.create(tenant=tenant_a, item=item_a, title="Clash",
                                          description="Clash", detected_on=timezone.localdate(),
                                          number=nonconformance_a.number)

    def test_capa_number_is_unique_per_tenant(self, tenant_a, capa_action_a):
        from apps.scm.models import CapaAction
        with pytest.raises(IntegrityError):
            CapaAction.objects.create(tenant=tenant_a, title="Clash", problem_statement="Clash",
                                      number=capa_action_a.number)

    def test_audit_number_is_unique_per_tenant(self, tenant_a, quality_audit_a):
        from django.utils import timezone
        from apps.scm.models import QualityAudit
        with pytest.raises(IntegrityError):
            QualityAudit.objects.create(tenant=tenant_a, title="Clash",
                                        planned_date=timezone.localdate(),
                                        number=quality_audit_a.number)

    def test_a_plan_is_deliberately_NOT_numbered(self):
        """A plan is master data keyed by code+version — it must never grow a NUMBER_PREFIX."""
        from apps.scm.models import InspectionPlan
        assert "number" not in {f.name for f in InspectionPlan._meta.get_fields()}
        assert not hasattr(InspectionPlan, "NUMBER_PREFIX")

    def test_plan_code_and_version_are_unique_per_tenant(self, tenant_a, inspection_plan_a,
                                                         item_a):
        from apps.scm.models import InspectionPlan
        with pytest.raises(IntegrityError):
            InspectionPlan.objects.create(tenant=tenant_a, code=inspection_plan_a.code,
                                          version=inspection_plan_a.version, name="Clash",
                                          item=item_a)

    def test_the_same_plan_code_is_free_in_another_tenant(self, tenant_b, inspection_plan_a,
                                                          item_b):
        from apps.scm.models import InspectionPlan
        twin = InspectionPlan.objects.create(tenant=tenant_b, code=inspection_plan_a.code,
                                             version="1", name="Twin", item=item_b)
        assert twin.pk != inspection_plan_a.pk


# ================================================================ next_number on a LATE field
class TestCoaNumberAllocationOrder:
    """``coa_number`` is stamped long after the inspection row exists, so its rows are NOT in id
    order. ``next_number`` must order by the NUMBER FIELD — ordering by ``-id`` re-reads the
    highest-id certified row and mints a number already in use."""

    def _inspection(self, tenant, item):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        return QualityInspection.objects.create(tenant=tenant, item=item,
                                                inspection_type="outgoing",
                                                inspected_on=timezone.localdate())

    def test_next_coa_number_is_derived_from_the_highest_CERTIFICATE_not_the_highest_id(
        self, tenant_a, item_a,
    ):
        from apps.core.utils import next_number
        from apps.scm.models import QualityInspection
        first, second, third = (self._inspection(tenant_a, item_a) for _ in range(3))
        assert first.pk < second.pk < third.pk
        # Issued OUT of id order: the newest row got the FIRST certificate.
        QualityInspection.objects.filter(pk=third.pk).update(coa_number="COA-00001")
        QualityInspection.objects.filter(pk=first.pk).update(coa_number="COA-00002")
        assert next_number(QualityInspection, tenant_a, "COA",
                           field="coa_number") == "COA-00003"

    def test_the_coa_sequence_is_per_tenant(self, tenant_a, tenant_b, item_a, item_b):
        from apps.core.utils import next_number
        from apps.scm.models import QualityInspection
        mine = self._inspection(tenant_a, item_a)
        QualityInspection.objects.filter(pk=mine.pk).update(coa_number="COA-00007")
        assert next_number(QualityInspection, tenant_b, "COA", field="coa_number") == "COA-00001"

    def test_the_running_number_and_the_certificate_number_share_no_sequence(self, tenant_a,
                                                                             item_a):
        from apps.core.utils import next_number
        from apps.scm.models import QualityInspection
        for _ in range(3):
            self._inspection(tenant_a, item_a)
        assert next_number(QualityInspection, tenant_a, "QC") == "QC-00004"
        assert next_number(QualityInspection, tenant_a, "COA", field="coa_number") == "COA-00001"


# ================================================================ __str__ + defaults + CHOICES
class TestQualityStrAndDefaults:
    def test_plan_str(self, inspection_plan_a):
        assert str(inspection_plan_a) == "IQC-W1 v1 · Widget incoming check"

    def test_characteristic_str(self, inspection_plan_a):
        assert str(inspection_plan_a.characteristics.first()) == "Length"

    def test_inspection_str(self, quality_inspection_a, item_a):
        assert str(quality_inspection_a) == f"{quality_inspection_a.number} · {item_a.sku}"

    def test_inspection_result_str(self, outgoing_inspection_a):
        row = outgoing_inspection_a.results.first()
        assert str(row) == f"{row.characteristic_name} — {row.get_result_display()}"

    def test_nonconformance_str(self, nonconformance_a):
        assert str(nonconformance_a) == f"{nonconformance_a.number} · Widgets out of tolerance"

    def test_capa_str(self, capa_action_a):
        assert str(capa_action_a) == f"{capa_action_a.number} · {capa_action_a.title}"

    def test_capa_task_str(self, capa_action_a):
        assert str(capa_action_a.tasks.first()) == "Re-calibrate the gauge"

    def test_audit_str(self, quality_audit_a):
        assert str(quality_audit_a) == f"{quality_audit_a.number} · Q1 internal process audit"

    def test_a_new_inspection_defaults_to_draft_pending_none(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        obj = QualityInspection.objects.create(tenant=tenant_a, item=item_a,
                                               inspected_on=timezone.localdate())
        assert (obj.status, obj.usage_decision, obj.action_taken) == ("draft", "pending", "none")
        assert obj.inspection_type == "incoming"
        assert obj.coa_number == ""
        assert obj.coa_issued_on is None
        assert obj.coa_issued_to_id is None
        assert obj.quantity_inspected == Decimal("0")

    def test_a_new_nonconformance_defaults_to_open_pending(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import NonConformance
        obj = NonConformance.objects.create(tenant=tenant_a, item=item_a, title="T",
                                            description="D",
                                            detected_on=timezone.localdate())
        assert (obj.status, obj.disposition, obj.source) == ("open", "pending", "internal")
        assert obj.severity == "minor"
        assert obj.defect_category == "other"
        assert obj.quarantine_applied is False
        assert obj.closed_on is None
        assert obj.cost_of_quality == Decimal("0")

    def test_a_new_capa_defaults_to_open_corrective_normal(self, tenant_a):
        from apps.scm.models import CapaAction
        obj = CapaAction.objects.create(tenant=tenant_a, title="T", problem_statement="P")
        assert (obj.status, obj.action_type, obj.priority) == ("open", "corrective", "normal")
        assert obj.source == "internal_improvement"
        assert obj.effectiveness_result == "pending"
        assert obj.implemented_on is None
        assert obj.verified_by_id is None

    def test_a_new_audit_defaults_to_planned_internal_medium(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import QualityAudit
        obj = QualityAudit.objects.create(tenant=tenant_a, title="T",
                                          planned_date=timezone.localdate())
        assert (obj.status, obj.audit_type, obj.risk_level) == ("planned", "internal", "medium")
        assert obj.actual_start is None
        assert obj.actual_end is None

    def test_a_new_plan_defaults_to_an_active_100pct_every_event_incoming_plan(self, tenant_a,
                                                                               item_a):
        from apps.scm.models import InspectionPlan
        plan = InspectionPlan.objects.create(tenant=tenant_a, code="D1", name="Defaults",
                                             item=item_a)
        assert (plan.plan_type, plan.sampling_method, plan.frequency) == (
            "incoming_receipt", "all_100", "every")
        assert plan.version == "1"
        assert plan.is_active is True

    def test_every_choice_set_is_the_documented_one(self):
        from apps.scm.models import (CapaAction, CapaTask, InspectionCharacteristic,
                                     InspectionPlan, InspectionResult, NonConformance,
                                     QualityAudit, QualityInspection)
        assert [v for v, _ in QualityInspection.STATUS_CHOICES] == [
            "draft", "in_progress", "passed", "failed", "on_hold", "cancelled"]
        assert [v for v, _ in QualityInspection.INSPECTION_TYPE_CHOICES] == [
            "incoming", "in_process", "outgoing", "periodic_stock"]
        assert [v for v, _ in QualityInspection.USAGE_DECISION_CHOICES] == [
            "pending", "accept", "accept_with_deviation", "reject"]
        assert [v for v, _ in QualityInspection.ACTION_TAKEN_CHOICES] == [
            "none", "quarantined", "ncr_raised", "returned_to_vendor"]
        assert QualityInspection.EDITABLE_STATUSES == ("draft", "in_progress")
        assert QualityInspection.ACCEPTING_DECISIONS == ("accept", "accept_with_deviation")
        assert [v for v, _ in InspectionResult.RESULT_CHOICES] == [
            "pending", "pass", "fail", "not_applicable"]
        assert [v for v, _ in InspectionPlan.PLAN_TYPE_CHOICES] == [
            "incoming_receipt", "in_process", "outgoing_shipment", "periodic_stock",
            "audit_checklist"]
        assert [v for v, _ in InspectionCharacteristic.CHARACTERISTIC_TYPE_CHOICES] == [
            "measurement", "pass_fail", "visual", "instruction"]
        assert [v for v, _ in NonConformance.STATUS_CHOICES] == [
            "open", "investigating", "dispositioned", "closed", "cancelled"]
        assert [v for v, _ in NonConformance.DISPOSITION_CHOICES] == [
            "pending", "use_as_is", "rework", "repair", "scrap", "return_to_vendor", "regrade"]
        assert NonConformance.OPEN_STATUSES == ("open", "investigating", "dispositioned")
        assert [v for v, _ in CapaAction.STATUS_CHOICES] == [
            "open", "investigating", "in_progress", "pending_verification", "closed", "cancelled"]
        assert [v for v, _ in CapaTask.STATUS_CHOICES] == [
            "open", "in_progress", "done", "cancelled"]
        assert [v for v, _ in QualityAudit.STATUS_CHOICES] == [
            "planned", "in_progress", "reported", "closed", "cancelled"]
        assert QualityAudit.MAJOR_SEVERITIES == ("critical", "major")
        assert QualityAudit.OPEN_FINDING_STATUSES == ("open", "investigating", "dispositioned")
        assert QualityAudit.EDITABLE_STATUSES == ("planned", "in_progress")

    def test_a_customer_complaint_is_deliberately_NOT_an_ncr_source(self):
        """A complaint is a CRM Case — duplicating it here would give one customer two owners."""
        from apps.scm.models import NonConformance
        assert "customer_complaint" not in [v for v, _ in NonConformance.SOURCE_CHOICES]


# ================================================================ generate_results() — the SNAPSHOT
class TestGenerateResultsSnapshot:
    def test_it_copies_every_characteristic_onto_a_result_row(self, quality_inspection_a,
                                                              inspection_plan_a):
        created = quality_inspection_a.generate_results()
        assert created == 3
        assert quality_inspection_a.results.count() == 3
        rows = list(quality_inspection_a.results.order_by("sequence"))
        assert [r.sequence for r in rows] == [10, 20, 30]
        assert [r.characteristic_name for r in rows] == [
            "Length", "Visual check", "Photograph the label"]

    def test_the_whole_snapshot_block_is_copied_not_referenced(self, quality_inspection_a,
                                                               inspection_plan_a, uom_each_a):
        quality_inspection_a.generate_results()
        row = quality_inspection_a.results.get(sequence=10)
        source = inspection_plan_a.characteristics.get(sequence=10)
        assert row.characteristic_type == "measurement"
        assert row.uom_id == uom_each_a.pk
        assert (row.target_value, row.lower_limit, row.upper_limit) == (
            Decimal("100.0000"), Decimal("95.0000"), Decimal("105.0000"))
        assert row.test_method == "Vernier caliper"
        assert row.is_mandatory is True
        assert row.is_critical is False
        assert row.include_on_coa is False
        assert row.characteristic_id == source.pk    # traceability only

    def test_an_instruction_row_is_stamped_not_applicable_at_creation(self, quality_inspection_a):
        quality_inspection_a.generate_results()
        assert quality_inspection_a.results.get(sequence=30).result == "not_applicable"
        assert quality_inspection_a.results.get(sequence=10).result == "pending"

    def test_a_second_call_is_a_no_op(self, quality_inspection_a):
        assert quality_inspection_a.generate_results() == 3
        assert quality_inspection_a.generate_results() == 0
        assert quality_inspection_a.results.count() == 3

    def test_a_second_call_never_overwrites_a_hand_corrected_row(self, quality_inspection_a):
        quality_inspection_a.generate_results()
        row = quality_inspection_a.results.get(sequence=10)
        row.measured_value = Decimal("99")
        row.notes = "Measured twice"
        row.save()
        quality_inspection_a.generate_results()
        row.refresh_from_db()
        assert row.measured_value == Decimal("99.0000")
        assert row.notes == "Measured twice"
        assert quality_inspection_a.results.count() == 3

    def test_a_LATER_PLAN_EDIT_does_not_change_an_existing_result_row(self, quality_inspection_a,
                                                                      inspection_plan_a):
        """The whole reason the snapshot exists: a plan re-issued with tighter limits next quarter
        must not retro-actively rewrite what last quarter's certificate was measured against."""
        quality_inspection_a.generate_results()
        source = inspection_plan_a.characteristics.get(sequence=10)
        source.name = "Length (revised)"
        source.lower_limit = Decimal("99")
        source.upper_limit = Decimal("101")
        source.test_method = "Laser micrometer"
        source.include_on_coa = True
        source.save()
        row = quality_inspection_a.results.get(sequence=10)
        row.refresh_from_db()
        assert row.characteristic_name == "Length"
        assert (row.lower_limit, row.upper_limit) == (Decimal("95.0000"), Decimal("105.0000"))
        assert row.test_method == "Vernier caliper"
        assert row.include_on_coa is False

    def test_an_inspection_with_no_plan_generates_nothing(self, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        obj = QualityInspection.objects.create(tenant=tenant_a, item=item_a,
                                               inspected_on=timezone.localdate())
        assert obj.generate_results() == 0
        assert obj.results.count() == 0

    def test_generating_invalidates_the_instance_result_cache(self, quality_inspection_a):
        assert quality_inspection_a.evaluated_result == "pending"   # warms _result_cache on []
        quality_inspection_a.generate_results()
        assert len(quality_inspection_a._result_rows()) == 3

    def test_generating_invalidates_a_PREFETCHED_result_cache(self, tenant_a,
                                                              quality_inspection_a):
        from apps.scm.models import QualityInspection
        prefetched = QualityInspection.objects.filter(
            pk=quality_inspection_a.pk).prefetch_related("results").first()
        assert prefetched._result_rows() == []
        prefetched.generate_results()
        assert len(prefetched._result_rows()) == 3


# ================================================================ _evaluate() precedence
class TestInspectionResultEvaluation:
    def _row(self, inspection, **kwargs):
        from apps.scm.models import InspectionResult
        data = {"inspection": inspection, "characteristic_name": "X",
                "characteristic_type": "measurement"}
        data.update(kwargs)
        return InspectionResult.objects.create(**data)

    def test_an_instruction_is_always_not_applicable(self, quality_inspection_a):
        row = self._row(quality_inspection_a, characteristic_type="instruction", result="pass")
        assert row.result == "not_applicable"

    def test_a_measurement_inside_the_band_passes(self, quality_inspection_a):
        row = self._row(quality_inspection_a, lower_limit=Decimal("95"),
                        upper_limit=Decimal("105"), measured_value=Decimal("100"))
        assert row.result == "pass"

    def test_a_measurement_below_the_lower_limit_fails(self, quality_inspection_a):
        row = self._row(quality_inspection_a, lower_limit=Decimal("95"),
                        upper_limit=Decimal("105"), measured_value=Decimal("94.9999"))
        assert row.result == "fail"

    def test_a_measurement_above_the_upper_limit_fails(self, quality_inspection_a):
        row = self._row(quality_inspection_a, lower_limit=Decimal("95"),
                        upper_limit=Decimal("105"), measured_value=Decimal("105.0001"))
        assert row.result == "fail"

    def test_a_measurement_with_no_value_is_pending(self, quality_inspection_a):
        row = self._row(quality_inspection_a, lower_limit=Decimal("95"))
        assert row.result == "pending"

    def test_a_target_only_measurement_must_hit_it_exactly(self, quality_inspection_a):
        hit = self._row(quality_inspection_a, target_value=Decimal("16"),
                        measured_value=Decimal("16"))
        miss = self._row(quality_inspection_a, target_value=Decimal("16"),
                         measured_value=Decimal("16.0001"))
        assert (hit.result, miss.result) == ("pass", "fail")

    def test_a_measurement_OVERWRITES_a_posted_verdict(self, quality_inspection_a):
        """DERIVED from the snapshotted limits — an inspector cannot type 'pass' over a fail."""
        row = self._row(quality_inspection_a, lower_limit=Decimal("95"),
                        upper_limit=Decimal("105"), measured_value=Decimal("1"), result="pass")
        assert row.result == "fail"

    def test_a_pass_fail_row_keeps_the_inspectors_verdict(self, quality_inspection_a):
        row = self._row(quality_inspection_a, characteristic_type="pass_fail", result="fail",
                        text_value="Scratched")
        assert row.result == "fail"

    def test_a_pass_fail_row_with_no_verdict_stays_pending(self, quality_inspection_a):
        row = self._row(quality_inspection_a, characteristic_type="visual")
        assert row.result == "pending"

    def test_spec_text_renders_from_the_snapshot_alone(self, quality_inspection_a, uom_each_a):
        # Re-read: a page renders rows fetched from the DB, so the limits carry the column's own
        # 4dp shape rather than whatever Decimal literal the caller happened to hand in.
        def stored(**kwargs):
            row = self._row(quality_inspection_a, **kwargs)
            row.refresh_from_db()
            return row

        band = stored(lower_limit=Decimal("280"), upper_limit=Decimal("320"), uom=uom_each_a)
        upper = stored(upper_limit=Decimal("0.5"))
        lower = stored(lower_limit=Decimal("16"))
        target = stored(target_value=Decimal("16"))
        blank = stored()
        text = stored(characteristic_type="visual", text_value="No scratches")
        assert band.spec_text == "280.0000 – 320.0000 EA"
        assert upper.spec_text == "≤ 0.5000"
        assert lower.spec_text == "≥ 16.0000"
        assert target.spec_text == "= 16.0000"
        assert blank.spec_text == "—"
        assert text.spec_text == "No scratches"

    def test_is_out_of_spec_mirrors_the_verdict(self, quality_inspection_a):
        row = self._row(quality_inspection_a, upper_limit=Decimal("1"),
                        measured_value=Decimal("5"))
        assert row.is_out_of_spec is True


# ================================================================ evaluated_result + the counters
class TestInspectionDerivedVerdict:
    def _row(self, inspection, **kwargs):
        from apps.scm.models import InspectionResult
        data = {"inspection": inspection, "characteristic_name": "X",
                "characteristic_type": "pass_fail"}
        data.update(kwargs)
        row = InspectionResult.objects.create(**data)
        inspection.__dict__.pop("_result_cache", None)
        return row

    def test_no_rows_is_pending(self, quality_inspection_a):
        assert quality_inspection_a.evaluated_result == "pending"

    def test_all_pass_is_a_pass(self, quality_inspection_a):
        self._row(quality_inspection_a, result="pass")
        self._row(quality_inspection_a, result="pass")
        assert quality_inspection_a.evaluated_result == "pass"

    def test_a_failed_CRITICAL_row_fails_the_lot_whatever_the_rest_say(self,
                                                                       quality_inspection_a):
        self._row(quality_inspection_a, result="pass")
        self._row(quality_inspection_a, result="fail", is_critical=True, is_mandatory=False)
        assert quality_inspection_a.evaluated_result == "fail"
        assert quality_inspection_a.has_critical_failure is True

    def test_a_failed_MANDATORY_row_fails_the_lot_even_with_a_pending_mandatory_row(
        self, quality_inspection_a,
    ):
        self._row(quality_inspection_a, result="fail", is_mandatory=True)
        self._row(quality_inspection_a, result="pending", is_mandatory=True)
        assert quality_inspection_a.evaluated_result == "fail"

    def test_a_pending_mandatory_row_holds_the_verdict_open(self, quality_inspection_a):
        self._row(quality_inspection_a, result="pass")
        self._row(quality_inspection_a, result="pending", is_mandatory=True)
        assert quality_inspection_a.evaluated_result == "pending"

    def test_an_OPTIONAL_failure_still_fails_the_lot_once_the_mandatories_are_answered(
        self, quality_inspection_a,
    ):
        self._row(quality_inspection_a, result="pass", is_mandatory=True)
        self._row(quality_inspection_a, result="fail", is_mandatory=False)
        assert quality_inspection_a.evaluated_result == "fail"

    def test_an_optional_failure_cannot_pre_empt_an_unanswered_mandatory_row(self,
                                                                             quality_inspection_a):
        self._row(quality_inspection_a, result="pending", is_mandatory=True)
        self._row(quality_inspection_a, result="fail", is_mandatory=False)
        assert quality_inspection_a.evaluated_result == "pending"

    def test_the_three_counters_read_the_same_rows(self, quality_inspection_a):
        self._row(quality_inspection_a, result="fail", is_mandatory=True)
        self._row(quality_inspection_a, result="pending", is_mandatory=True)
        self._row(quality_inspection_a, result="pending", is_mandatory=False)
        assert quality_inspection_a.failed_count == 1
        assert quality_inspection_a.pending_count == 2
        assert quality_inspection_a.mandatory_pending_count == 1

    def test_result_rows_are_fetched_ONCE_per_instance(self, django_assert_max_num_queries,
                                                       outgoing_inspection_a):
        from apps.scm.models import QualityInspection
        obj = QualityInspection.objects.get(pk=outgoing_inspection_a.pk)
        with django_assert_max_num_queries(1):
            _ = (obj.evaluated_result, obj.failed_count, obj.pending_count,
                 obj.mandatory_pending_count, obj.has_critical_failure, obj.coa_results,
                 obj.coa_blockers())

    def test_a_supplied_prefetch_is_CONSUMED_rather_than_re_queried(self,
                                                                    django_assert_max_num_queries,
                                                                    outgoing_inspection_a):
        from apps.scm.models import QualityInspection
        obj = QualityInspection.objects.filter(
            pk=outgoing_inspection_a.pk).prefetch_related("results").first()
        with django_assert_max_num_queries(0):
            assert len(obj._result_rows()) == 2


# ================================================================ coa_blockers() — the seven rules
class TestCoaBlockers:
    def test_a_ready_inspection_has_no_blockers(self, outgoing_inspection_a):
        assert outgoing_inspection_a.coa_blockers() == []
        assert outgoing_inspection_a.coa_ready is True

    def test_rule_1_only_an_outgoing_inspection_may_certify(self, outgoing_inspection_a):
        outgoing_inspection_a.inspection_type = "incoming"
        assert any("Only an outgoing inspection" in b
                   for b in outgoing_inspection_a.coa_blockers())

    def test_rule_2_the_inspection_must_have_passed(self, outgoing_inspection_a):
        outgoing_inspection_a.status = "failed"
        assert any("has not passed" in b for b in outgoing_inspection_a.coa_blockers())

    def test_rule_3_a_usage_decision_must_have_accepted_the_lot(self, outgoing_inspection_a):
        outgoing_inspection_a.usage_decision = "reject"
        assert any("No usage decision has accepted" in b
                   for b in outgoing_inspection_a.coa_blockers())

    def test_rule_3_accept_with_deviation_also_certifies(self, outgoing_inspection_a):
        outgoing_inspection_a.usage_decision = "accept_with_deviation"
        assert outgoing_inspection_a.coa_blockers() == []

    def test_rule_4_an_out_of_spec_included_row_blocks_it(self, outgoing_inspection_a):
        row = outgoing_inspection_a.results.get(sequence=10)
        row.measured_value = Decimal("1")     # far outside 99.0 - 100.0
        row.save()
        outgoing_inspection_a.__dict__.pop("_result_cache", None)
        assert any("out of specification" in b for b in outgoing_inspection_a.coa_blockers())

    def test_rule_5_an_unrecorded_included_row_blocks_it(self, outgoing_inspection_a):
        row = outgoing_inspection_a.results.get(sequence=20)
        row.result = "pending"
        row.save()
        outgoing_inspection_a.__dict__.pop("_result_cache", None)
        assert any("no recorded value" in b for b in outgoing_inspection_a.coa_blockers())

    def test_rule_6_a_lot_tracked_item_must_name_its_batch(self, outgoing_inspection_a):
        outgoing_inspection_a.lot_serial = None
        assert any("lot/batch is required" in b for b in outgoing_inspection_a.coa_blockers())

    def test_rule_6_does_not_apply_to_an_untracked_item(self, outgoing_inspection_a, item_a):
        outgoing_inspection_a.lot_serial = None
        outgoing_inspection_a.item = item_a          # tracking="none"
        assert not any("lot/batch is required" in b
                       for b in outgoing_inspection_a.coa_blockers())

    def test_rule_7_nothing_flagged_for_the_certificate_blocks_it(self, outgoing_inspection_a):
        from apps.scm.models import InspectionResult
        InspectionResult.objects.filter(inspection=outgoing_inspection_a).update(
            include_on_coa=False)
        outgoing_inspection_a.__dict__.pop("_result_cache", None)
        assert outgoing_inspection_a.coa_results == []
        assert any("No characteristics are flagged" in b
                   for b in outgoing_inspection_a.coa_blockers())

    def test_coa_results_are_only_the_flagged_rows_in_sequence(self, outgoing_inspection_a):
        from apps.scm.models import InspectionResult
        InspectionResult.objects.filter(inspection=outgoing_inspection_a,
                                        sequence=20).update(include_on_coa=False)
        outgoing_inspection_a.__dict__.pop("_result_cache", None)
        assert [r.sequence for r in outgoing_inspection_a.coa_results] == [10]

    def test_is_coa_issued_reads_the_stamp(self, outgoing_inspection_a):
        assert outgoing_inspection_a.is_coa_issued is False
        outgoing_inspection_a.coa_number = "COA-00001"
        assert outgoing_inspection_a.is_coa_issued is True


# ================================================================ Model-level clean() guards
class TestQualityInspectionClean:
    def test_accepted_plus_rejected_may_not_exceed_the_inspected_quantity(self,
                                                                          quality_inspection_a):
        quality_inspection_a.quantity_accepted = Decimal("8")
        quality_inspection_a.quantity_rejected = Decimal("5")
        with pytest.raises(ValidationError) as exc:
            quality_inspection_a.full_clean()
        assert "quantity_accepted" in exc.value.error_dict

    def test_the_sample_may_not_be_larger_than_the_lot_inspected(self, quality_inspection_a):
        quality_inspection_a.sample_size = Decimal("99")
        with pytest.raises(ValidationError) as exc:
            quality_inspection_a.full_clean()
        assert "sample_size" in exc.value.error_dict

    def test_a_lot_belonging_to_another_item_is_refused(self, tenant_a, quality_inspection_a,
                                                        lot_a):
        """A crafted POST pairing item A with item B's lot would certify A's measurements under
        B's batch number."""
        quality_inspection_a.lot_serial = lot_a      # lot_a belongs to item_lot_a, not item_a
        with pytest.raises(ValidationError) as exc:
            quality_inspection_a.full_clean()
        assert "lot_serial" in exc.value.error_dict

    def test_the_matching_lot_is_accepted(self, outgoing_inspection_a):
        outgoing_inspection_a.full_clean()


class TestNonConformanceClean:
    def test_every_non_audit_source_must_name_an_item(self, tenant_a):
        from django.utils import timezone
        from apps.scm.models import NonConformance
        obj = NonConformance(tenant=tenant_a, source="production", title="T", description="D",
                             detected_on=timezone.localdate())
        with pytest.raises(ValidationError) as exc:
            obj.full_clean()
        assert "item" in exc.value.error_dict

    def test_an_AUDIT_finding_may_have_no_item(self, tenant_a, quality_audit_a):
        from django.utils import timezone
        from apps.scm.models import NonConformance
        obj = NonConformance(tenant=tenant_a, source="audit", audit=quality_audit_a,
                             title="Training records incomplete", description="D",
                             detected_on=timezone.localdate())
        obj.full_clean()

    def test_an_item_without_a_quantity_is_refused(self, nonconformance_a):
        nonconformance_a.quantity_affected = Decimal("0")
        with pytest.raises(ValidationError) as exc:
            nonconformance_a.full_clean()
        assert "quantity_affected" in exc.value.error_dict

    def test_a_due_date_before_the_detection_date_is_refused(self, nonconformance_a):
        nonconformance_a.due_date = nonconformance_a.detected_on - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            nonconformance_a.full_clean()
        assert "due_date" in exc.value.error_dict

    def test_a_lot_belonging_to_another_item_is_refused(self, nonconformance_a, lot_a):
        nonconformance_a.lot_serial = lot_a
        with pytest.raises(ValidationError) as exc:
            nonconformance_a.full_clean()
        assert "lot_serial" in exc.value.error_dict

    def test_posts_stock_is_true_only_for_a_from_stock_scrap(self, nonconformance_a):
        assert nonconformance_a.posts_stock is False        # disposition still pending
        nonconformance_a.disposition = "scrap"
        assert nonconformance_a.posts_stock is True
        nonconformance_a.source = "goods_receipt"
        assert nonconformance_a.posts_stock is False        # refused at the dock, never in stock
        nonconformance_a.source = "internal"
        nonconformance_a.location = None
        assert nonconformance_a.posts_stock is False
        nonconformance_a.location_id = 1
        nonconformance_a.item = None
        assert nonconformance_a.posts_stock is False        # an audit finding has no item
        nonconformance_a.item_id = 1
        nonconformance_a.disposition = "rework"
        assert nonconformance_a.posts_stock is False

    def test_is_overdue_uses_the_localdate_basis(self, nonconformance_a):
        from django.utils import timezone
        assert nonconformance_a.is_overdue is False
        nonconformance_a.due_date = timezone.localdate() - datetime.timedelta(days=1)
        assert nonconformance_a.is_overdue is True
        nonconformance_a.status = "closed"
        assert nonconformance_a.is_overdue is False

    def test_days_open_counts_to_today_then_freezes_at_closure(self, nonconformance_a):
        from django.utils import timezone
        nonconformance_a.detected_on = timezone.localdate() - datetime.timedelta(days=4)
        assert nonconformance_a.days_open == 4
        nonconformance_a.closed_on = timezone.now() - datetime.timedelta(days=2)
        assert nonconformance_a.days_open == 2

    def test_lot_history_is_empty_without_a_lot(self, nonconformance_a):
        assert list(nonconformance_a.lot_history()) == []

    def test_lot_history_returns_EVERY_move_for_the_batch(self, tenant_a, nonconformance_lot_a,
                                                          item_lot_a, location_a, lot_a):
        from apps.scm.tests._helpers import seed_stock
        move = seed_stock(tenant_a, item_lot_a, location_a, "20", "1.0000")
        move.lot_serial = lot_a
        move.save(update_fields=["lot_serial"])
        assert list(nonconformance_lot_a.lot_history()) == [move]


class TestCapaActionClean:
    def test_effectiveness_is_checked_after_the_action_is_due(self, capa_action_a):
        capa_action_a.effectiveness_due_date = capa_action_a.due_date - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            capa_action_a.full_clean()
        assert "effectiveness_due_date" in exc.value.error_dict

    def test_a_nonconformance_sourced_capa_must_name_one(self, capa_action_a):
        capa_action_a.source = "nonconformance"
        with pytest.raises(ValidationError) as exc:
            capa_action_a.full_clean()
        assert "nonconformance" in exc.value.error_dict

    def test_an_audit_sourced_capa_must_name_the_audit(self, capa_action_a):
        capa_action_a.source = "audit_finding"
        with pytest.raises(ValidationError) as exc:
            capa_action_a.full_clean()
        assert "audit" in exc.value.error_dict

    def test_a_SCAR_must_name_the_supplier(self, capa_action_a):
        capa_action_a.source = "supplier"
        with pytest.raises(ValidationError) as exc:
            capa_action_a.full_clean()
        assert "supplier" in exc.value.error_dict

    def test_open_task_count_is_DERIVED_not_stored(self, capa_action_a):
        from apps.scm.models import CapaTask
        assert capa_action_a.open_task_count == 1
        CapaTask.objects.create(capa=capa_action_a, sequence=20, description="Second",
                                status="done")
        assert capa_action_a.open_task_count == 1
        capa_action_a.tasks.update(status="done")
        assert capa_action_a.open_task_count == 0
        assert "open_task_count" not in {f.name for f in capa_action_a._meta.get_fields()}

    def test_verification_overdue_only_bites_while_awaiting_verification(self, capa_action_a):
        from django.utils import timezone
        capa_action_a.effectiveness_due_date = timezone.localdate() - datetime.timedelta(days=1)
        assert capa_action_a.verification_overdue is False      # still open
        capa_action_a.status = "pending_verification"
        assert capa_action_a.verification_overdue is True
        capa_action_a.effectiveness_result = "effective"
        assert capa_action_a.verification_overdue is False

    def test_a_task_is_overdue_only_while_it_is_live(self, capa_action_a):
        from django.utils import timezone
        task = capa_action_a.tasks.first()
        task.due_date = timezone.localdate() - datetime.timedelta(days=1)
        assert task.is_overdue is True
        task.status = "done"
        assert task.is_overdue is False


class TestQualityAuditClean:
    def test_an_audit_cannot_end_before_it_starts(self, reported_audit_a):
        reported_audit_a.actual_end = reported_audit_a.actual_start - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            reported_audit_a.full_clean()
        assert "actual_end" in exc.value.error_dict

    def test_a_supplier_audit_must_name_the_party(self, quality_audit_a):
        quality_audit_a.audit_type = "supplier"
        with pytest.raises(ValidationError) as exc:
            quality_audit_a.full_clean()
        assert "auditee_party" in exc.value.error_dict

    def test_an_internal_audit_must_name_the_department(self, quality_audit_a):
        quality_audit_a.auditee_org_unit = None
        with pytest.raises(ValidationError) as exc:
            quality_audit_a.full_clean()
        assert "auditee_org_unit" in exc.value.error_dict

    def test_only_an_audit_checklist_plan_may_be_the_checklist(self, quality_audit_a,
                                                               inspection_plan_a):
        quality_audit_a.checklist_plan = inspection_plan_a
        with pytest.raises(ValidationError) as exc:
            quality_audit_a.full_clean()
        assert "checklist_plan" in exc.value.error_dict

    def test_the_finding_roll_ups_are_DERIVED_not_columns(self, tenant_a, quality_audit_a):
        """4.7 shipped a stored counter, regretted it and fixed it — these must stay properties."""
        from django.utils import timezone
        from apps.scm.models import NonConformance
        for severity in ("critical", "major", "minor", "observation"):
            NonConformance.objects.create(tenant=tenant_a, source="audit", audit=quality_audit_a,
                                          severity=severity, title=severity, description="D",
                                          detected_on=timezone.localdate())
        assert quality_audit_a.finding_count == 4
        assert quality_audit_a.major_count == 2
        assert quality_audit_a.minor_count == 2
        assert quality_audit_a.open_finding_count == 4
        stored = {f.name for f in quality_audit_a._meta.get_fields()}
        for derived in ("finding_count", "major_count", "minor_count", "open_finding_count",
                        "duration_days"):
            assert derived not in stored, derived

    def test_editing_a_findings_severity_moves_the_roll_up_immediately(self, tenant_a,
                                                                       quality_audit_a):
        from django.utils import timezone
        from apps.scm.models import NonConformance
        finding = NonConformance.objects.create(tenant=tenant_a, source="audit",
                                                audit=quality_audit_a, severity="minor",
                                                title="T", description="D",
                                                detected_on=timezone.localdate())
        assert quality_audit_a.major_count == 0
        finding.severity = "critical"
        finding.save(update_fields=["severity"])
        assert quality_audit_a.major_count == 1

    def test_duration_days_is_inclusive_and_none_while_unfinished(self, reported_audit_a):
        assert reported_audit_a.duration_days == 2
        reported_audit_a.actual_end = None
        assert reported_audit_a.duration_days is None

    def test_an_audit_stays_editable_while_in_progress(self, quality_audit_a):
        """`complete` refuses a blank conclusion, and the conclusion is written AFTER the audit has
        been run — locking the header at `start` made the normal path unreachable."""
        quality_audit_a.status = "in_progress"
        assert quality_audit_a.is_editable is True
        quality_audit_a.status = "reported"
        assert quality_audit_a.is_editable is False


# ================================================================ InspectionPlan sampling + scope
class TestInspectionPlanRules:
    def test_percentage_sampling_needs_a_percentage(self, inspection_plan_a):
        inspection_plan_a.sampling_method = "percentage"
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "sample_percentage" in exc.value.error_dict

    def test_fixed_count_sampling_needs_a_size(self, inspection_plan_a):
        inspection_plan_a.sampling_method = "fixed_count"
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "sample_size" in exc.value.error_dict

    def test_aql_needs_both_numbers(self, inspection_plan_a):
        inspection_plan_a.sampling_method = "aql"
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "aql_accept_number" in exc.value.error_dict

    def test_the_aql_band_may_not_be_undefined(self, inspection_plan_a):
        inspection_plan_a.sampling_method = "aql"
        inspection_plan_a.aql_accept_number = 5
        inspection_plan_a.aql_reject_number = 5
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "aql_reject_number" in exc.value.error_dict

    def test_random_frequency_needs_a_percentage(self, inspection_plan_a):
        inspection_plan_a.frequency = "random_percent"
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "frequency_value" in exc.value.error_dict

    def test_a_scoped_plan_type_must_name_something(self, inspection_plan_a):
        inspection_plan_a.item = None
        with pytest.raises(ValidationError) as exc:
            inspection_plan_a.full_clean()
        assert "item" in exc.value.error_dict

    def test_an_audit_checklist_must_NOT_be_scoped(self, audit_checklist_plan_a, item_a):
        audit_checklist_plan_a.item = item_a
        with pytest.raises(ValidationError) as exc:
            audit_checklist_plan_a.full_clean()
        assert "plan_type" in exc.value.error_dict

    def test_sample_quantity_by_method(self, inspection_plan_a):
        inspection_plan_a.sampling_method = "all_100"
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("40.0000")
        inspection_plan_a.sampling_method = "percentage"
        inspection_plan_a.sample_percentage = Decimal("25")
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("10.0000")
        inspection_plan_a.sampling_method = "fixed_count"
        inspection_plan_a.sample_size = 100
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("40.0000")  # capped
        inspection_plan_a.sample_size = 5
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("5.0000")
        inspection_plan_a.sampling_method = "aql"
        inspection_plan_a.sample_size = None
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("40.0000")
        inspection_plan_a.sample_size = 8
        assert inspection_plan_a.sample_quantity(Decimal("40")) == Decimal("8.0000")

    def test_sample_quantity_of_an_empty_lot_is_zero(self, inspection_plan_a):
        assert inspection_plan_a.sample_quantity(Decimal("0")) == Decimal("0")
        assert inspection_plan_a.sample_quantity(Decimal("-5")) == Decimal("0")

    def test_is_effective_needs_active_and_the_date(self, inspection_plan_a):
        from django.utils import timezone
        today = timezone.localdate()
        assert inspection_plan_a.is_effective(today) is True
        inspection_plan_a.effective_from = today + datetime.timedelta(days=1)
        assert inspection_plan_a.is_effective(today) is False
        inspection_plan_a.effective_from = today
        assert inspection_plan_a.is_effective(today) is True
        inspection_plan_a.is_active = False
        assert inspection_plan_a.is_effective(today) is False

    def test_characteristic_count_is_derived(self, inspection_plan_a):
        assert inspection_plan_a.characteristic_count == 3
        inspection_plan_a.characteristics.filter(sequence=30).delete()
        assert inspection_plan_a.characteristic_count == 2

    def test_for_trigger_prefers_the_item_over_its_category(self, tenant_a, item_a,
                                                            inspection_plan_a, category_a):
        from apps.scm.models import InspectionPlan
        InspectionPlan.objects.create(tenant=tenant_a, code="CAT", name="Category-wide",
                                      plan_type="incoming_receipt", item_category=category_a)
        assert InspectionPlan.for_trigger(tenant_a, plan_type="incoming_receipt",
                                          item=item_a) == inspection_plan_a

    def test_for_trigger_falls_back_to_the_category_then_the_supplier(self, tenant_a, item_a,
                                                                      category_a, supplier_a):
        from apps.scm.models import InspectionPlan
        by_category = InspectionPlan.objects.create(
            tenant=tenant_a, code="CAT", name="Category-wide", plan_type="incoming_receipt",
            item_category=category_a)
        by_supplier = InspectionPlan.objects.create(
            tenant=tenant_a, code="SUP", name="Supplier-wide", plan_type="incoming_receipt",
            supplier=supplier_a)
        assert InspectionPlan.for_trigger(tenant_a, plan_type="incoming_receipt", item=item_a,
                                          supplier=supplier_a) == by_category
        by_category.is_active = False
        by_category.save(update_fields=["is_active"])
        assert InspectionPlan.for_trigger(tenant_a, plan_type="incoming_receipt", item=item_a,
                                          supplier=supplier_a) == by_supplier

    def test_for_trigger_returns_none_without_a_tenant(self, item_a):
        from apps.scm.models import InspectionPlan
        assert InspectionPlan.for_trigger(None, plan_type="incoming_receipt", item=item_a) is None

    def test_for_trigger_skips_a_plan_that_is_not_yet_effective(self, tenant_a, item_a,
                                                                inspection_plan_a):
        from django.utils import timezone
        from apps.scm.models import InspectionPlan
        inspection_plan_a.effective_from = timezone.localdate() + datetime.timedelta(days=30)
        inspection_plan_a.save(update_fields=["effective_from"])
        assert InspectionPlan.for_trigger(tenant_a, plan_type="incoming_receipt",
                                          item=item_a) is None

    def test_a_later_version_supersedes_an_earlier_one_on_a_tie(self, tenant_a, item_a,
                                                               inspection_plan_a):
        from apps.scm.models import InspectionPlan
        newer = InspectionPlan.objects.create(tenant=tenant_a, code="IQC-W1", name="Revised",
                                              version="2", plan_type="incoming_receipt",
                                              item=item_a)
        assert InspectionPlan.for_trigger(tenant_a, plan_type="incoming_receipt",
                                          item=item_a) == newer


class TestInspectionCharacteristicClean:
    def test_a_measurement_needs_at_least_one_figure(self, inspection_plan_a):
        from apps.scm.models import InspectionCharacteristic
        row = InspectionCharacteristic(plan=inspection_plan_a, name="X",
                                       characteristic_type="measurement")
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "target_value" in exc.value.error_dict

    def test_an_inverted_band_is_refused(self, inspection_plan_a):
        from apps.scm.models import InspectionCharacteristic
        row = InspectionCharacteristic(plan=inspection_plan_a, name="X",
                                       characteristic_type="measurement",
                                       lower_limit=Decimal("10"), upper_limit=Decimal("1"))
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "upper_limit" in exc.value.error_dict

    def test_limits_parked_on_a_NON_measurement_are_refused(self, inspection_plan_a):
        """The snapshot copies these columns, so a limit on a pass/fail row would be printed on a
        certificate as a specification nothing was ever measured against."""
        from apps.scm.models import InspectionCharacteristic
        row = InspectionCharacteristic(plan=inspection_plan_a, name="X",
                                       characteristic_type="pass_fail",
                                       upper_limit=Decimal("1"))
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "target_value" in exc.value.error_dict

    def test_only_a_measurement_or_pass_fail_may_be_certified(self, inspection_plan_a):
        from apps.scm.models import InspectionCharacteristic
        row = InspectionCharacteristic(plan=inspection_plan_a, name="X",
                                       characteristic_type="instruction", include_on_coa=True)
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "include_on_coa" in exc.value.error_dict


# ================================================================ Editability windows
class TestQualityEditableStatuses:
    def test_an_inspection_is_editable_only_while_draft_or_in_progress(self,
                                                                       quality_inspection_a):
        for status, editable in (("draft", True), ("in_progress", True), ("passed", False),
                                 ("failed", False), ("on_hold", False), ("cancelled", False)):
            quality_inspection_a.status = status
            assert quality_inspection_a.is_editable is editable, status

    def test_a_report_is_editable_only_while_open_or_investigating(self, nonconformance_a):
        for status, editable in (("open", True), ("investigating", True),
                                 ("dispositioned", False), ("closed", False),
                                 ("cancelled", False)):
            nonconformance_a.status = status
            assert nonconformance_a.is_editable is editable, status

    def test_a_capa_is_editable_up_to_pending_verification(self, capa_action_a):
        for status, editable in (("open", True), ("investigating", True), ("in_progress", True),
                                 ("pending_verification", False), ("closed", False),
                                 ("cancelled", False)):
            capa_action_a.status = status
            assert capa_action_a.is_editable is editable, status


# ================================================================================================
# SCM 4.10 Returns Management (Reverse Logistics)
#
# Every test below that is marked REGRESSION LOCK fails against the pre-review behaviour. They are
# not decoration: each one is a defect the review pass found in code that had already shipped.
# ================================================================================================
class TestReturnsAutoNumbering:
    def test_rma_numbers_are_sequential_per_tenant(self, tenant_a, tenant_b, customer_a,
                                                   customer_b):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        one = ReturnAuthorization.objects.create(tenant=tenant_a, customer=customer_a,
                                                 requested_on=timezone.localdate())
        two = ReturnAuthorization.objects.create(tenant=tenant_a, customer=customer_a,
                                                 requested_on=timezone.localdate())
        theirs = ReturnAuthorization.objects.create(tenant=tenant_b, customer=customer_b,
                                                    requested_on=timezone.localdate())
        assert (one.number, two.number) == ("RMA-00001", "RMA-00002")
        assert theirs.number == "RMA-00001"       # a separate per-tenant sequence

    def test_rma_number_is_unique_together_with_the_tenant(self, tenant_a, customer_a,
                                                           return_authorization_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        with pytest.raises(IntegrityError):
            ReturnAuthorization.objects.create(tenant=tenant_a, customer=customer_a,
                                               requested_on=timezone.localdate(),
                                               number=return_authorization_a.number)

    def test_warranty_claim_numbers_are_prefixed_wty(self, tenant_a, tenant_b, supplier_a,
                                                     supplier_b, item_a, item_b):
        from apps.scm.models import WarrantyClaim
        one = WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                           quantity_claimed=Decimal("1"))
        two = WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                           quantity_claimed=Decimal("1"))
        theirs = WarrantyClaim.objects.create(tenant=tenant_b, supplier=supplier_b, item=item_b,
                                              quantity_claimed=Decimal("1"))
        assert (one.number, two.number, theirs.number) == ("WTY-00001", "WTY-00002", "WTY-00001")

    def test_warranty_claim_number_is_unique_together_with_the_tenant(self, tenant_a, supplier_a,
                                                                     item_a, warranty_claim_a):
        from apps.scm.models import WarrantyClaim
        with pytest.raises(IntegrityError):
            WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                         quantity_claimed=Decimal("1"),
                                         number=warranty_claim_a.number)

    def test_the_bench_row_and_the_two_masters_carry_NO_number(self):
        """``ReturnDisposition``/``ReturnPolicy``/``ReturnReason`` are rows and configuration, not
        documents — the ``SalesOrderAllocation`` precedent."""
        from apps.scm.models import ReturnDisposition, ReturnPolicy, ReturnReason
        for model in (ReturnDisposition, ReturnPolicy, ReturnReason):
            assert not hasattr(model, "NUMBER_PREFIX") or model.NUMBER_PREFIX == ""
            assert "number" not in {f.name for f in model._meta.get_fields()}, model.__name__

    def test_the_reason_code_is_unique_per_tenant_and_reusable_across_tenants(self, tenant_a,
                                                                             tenant_b,
                                                                             return_reason_a,
                                                                             return_reason_b):
        from apps.scm.models import ReturnReason
        assert return_reason_a.code == return_reason_b.code    # same code, two tenants: fine
        with pytest.raises(IntegrityError):
            ReturnReason.objects.create(tenant=tenant_a, code=return_reason_a.code, name="Dup")


class TestReturnAuthorizationBasics:
    def test_defaults(self, tenant_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization.objects.create(tenant=tenant_a, customer=customer_a,
                                                 requested_on=timezone.localdate())
        assert rma.status == "draft"
        assert rma.return_type == "physical"
        assert rma.source == "csr"
        assert rma.resolution == "refund"
        assert rma.refund_method == "original_tender"
        assert rma.return_method == "mail_prepaid"
        assert rma.advance_refund is False
        assert rma.policy_snapshot == ""
        assert rma.credit_note_id is None
        assert rma.replacement_order_id is None
        for figure in (rma.refund_subtotal, rma.fee_total, rma.tax_total, rma.credit_total,
                       rma.label_cost):
            assert figure == Decimal("0")

    def test_str_is_the_number_and_the_customer(self, return_authorization_a, customer_a):
        assert str(return_authorization_a) == f"{return_authorization_a.number} · {customer_a.name}"

    def test_the_public_token_is_minted_once_from_the_CSPRNG(self, return_authorization_a):
        token = return_authorization_a.public_token
        assert token and len(token) >= 32
        return_authorization_a.notes = "touched"
        return_authorization_a.save()
        return_authorization_a.refresh_from_db()
        assert return_authorization_a.public_token == token   # never rotated on a later save

    def test_two_returns_never_share_a_token(self, tenant_a, tenant_b, customer_a, customer_b):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        tokens = {
            ReturnAuthorization.objects.create(tenant=tenant, customer=customer,
                                               requested_on=timezone.localdate()).public_token
            for tenant, customer in ((tenant_a, customer_a), (tenant_a, customer_a),
                                     (tenant_b, customer_b))
        }
        assert len(tokens) == 3

    def test_the_status_choice_ladder_is_exactly_the_documented_one(self):
        from apps.scm.models import ReturnAuthorization
        assert [c[0] for c in ReturnAuthorization.STATUS_CHOICES] == [
            "draft", "requested", "approved", "rejected", "awaiting_receipt",
            "partially_received", "received", "settled", "closed", "cancelled"]

    def test_the_status_bands_partition_the_ladder_the_way_the_views_assume(self):
        from apps.scm.models import ReturnAuthorization as R
        ladder = {c[0] for c in R.STATUS_CHOICES}
        assert set(R.EDITABLE_STATUSES) <= ladder
        assert set(R.OPEN_STATUSES) <= ladder
        assert set(R.TERMINAL_STATUSES) <= ladder
        assert set(R.PUBLIC_STATUSES) <= ladder
        assert set(R.LABEL_STATUSES) <= ladder
        assert set(R.SHIPPABLE_STATUSES) <= ladder
        assert set(R.NOTEABLE_STATUSES) <= ladder
        assert not set(R.OPEN_STATUSES) & set(R.TERMINAL_STATUSES)
        # The public page must never resolve a draft or a cancelled return.
        assert "draft" not in R.PUBLIC_STATUSES and "cancelled" not in R.PUBLIC_STATUSES
        # The anonymous "I've shipped it" write is NARROWER than what the page will render.
        assert set(R.SHIPPABLE_STATUSES) < set(R.PUBLIC_STATUSES)
        assert "requested" not in R.SHIPPABLE_STATUSES
        assert "settled" not in R.SHIPPABLE_STATUSES
        # A slip may only be printed for an authorised return.
        assert set(R.LABEL_STATUSES) <= set(R.PUBLIC_STATUSES)
        assert "requested" not in R.LABEL_STATUSES

    def test_is_editable_only_while_draft_or_requested(self, return_authorization_a):
        from apps.scm.models import ReturnAuthorization
        for status, _label in ReturnAuthorization.STATUS_CHOICES:
            return_authorization_a.status = status
            assert return_authorization_a.is_editable is (status in ("draft", "requested")), status

    def test_is_terminal_matches_the_declared_band(self, return_authorization_a):
        from apps.scm.models import ReturnAuthorization
        for status, _label in ReturnAuthorization.STATUS_CHOICES:
            return_authorization_a.status = status
            assert return_authorization_a.is_terminal is (
                status in ReturnAuthorization.TERMINAL_STATUSES), status


class TestReturnAuthorizationClean:
    def test_a_sales_order_belonging_to_another_customer_is_refused(self, tenant_a, customer_a,
                                                                    sales_order_b, item_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization(tenant=tenant_a, customer=customer_a, sales_order=sales_order_b,
                                  requested_on=timezone.localdate())
        with pytest.raises(ValidationError) as exc:
            rma.clean()
        assert "sales_order" in exc.value.error_dict

    def test_an_advance_refund_without_a_deadline_is_refused(self, tenant_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization(tenant=tenant_a, customer=customer_a, advance_refund=True,
                                  requested_on=timezone.localdate())
        with pytest.raises(ValidationError) as exc:
            rma.clean()
        assert "advance_refund_deadline" in exc.value.error_dict

    def test_a_credit_only_return_must_ask_for_nothing_back(self, tenant_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization(tenant=tenant_a, customer=customer_a,
                                  return_type="credit_only", return_method="mail_prepaid",
                                  requested_on=timezone.localdate())
        with pytest.raises(ValidationError) as exc:
            rma.clean()
        assert "return_method" in exc.value.error_dict
        rma.return_method = "keep_item"
        rma.clean()      # now consistent


class TestReturnAuthorizationDerivedQuantities:
    def test_the_three_quantity_roll_ups_are_derived_from_the_rows(self, rma_awaiting_receipt_a,
                                                                    disposition_a):
        rma = rma_awaiting_receipt_a
        assert rma.quantity_requested_total == Decimal("3.0000")
        assert rma.quantity_approved_total == Decimal("3.0000")
        assert rma.quantity_received_total == Decimal("3.0000")
        assert rma.is_fully_received is True

    def test_quantity_received_total_INCLUDES_rows_still_awaiting_a_decision(
        self, rma_awaiting_receipt_a, disposition_a,
    ):
        """REGRESSION LOCK (item 9). A unit on the bench with no decision yet physically came back;
        counting only decided rows would report an empty bench while it is full."""
        assert disposition_a.disposition == "received_pending"
        assert rma_awaiting_receipt_a.quantity_received_total == Decimal("3.0000")

    def test_nothing_received_leaves_the_roll_ups_at_zero(self, rma_awaiting_receipt_a):
        assert rma_awaiting_receipt_a.quantity_received_total == Decimal("0")
        assert rma_awaiting_receipt_a.is_fully_received is False

    def test_is_fully_received_needs_a_non_zero_approval(self, return_authorization_a):
        assert return_authorization_a.quantity_approved_total == Decimal("0")
        assert return_authorization_a.is_fully_received is False

    def test_days_open_counts_from_the_request_and_never_goes_negative(self, tenant_a,
                                                                       customer_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization(tenant=tenant_a, customer=customer_a,
                                  requested_on=timezone.localdate() - datetime.timedelta(days=7))
        assert rma.days_open == 7
        rma.requested_on = timezone.localdate() + datetime.timedelta(days=3)
        assert rma.days_open == 0

    def test_is_overdue_shipment_uses_the_policys_own_window_as_the_grace_period(
        self, rma_awaiting_receipt_a, return_policy_a,
    ):
        from django.utils import timezone
        rma = rma_awaiting_receipt_a
        rma.approved_on = timezone.localdate() - datetime.timedelta(days=10)
        assert rma.is_overdue_shipment is False              # inside the 30-day window
        rma.approved_on = timezone.localdate() - datetime.timedelta(days=31)
        assert rma.is_overdue_shipment is True
        return_policy_a.window_days = 90
        assert rma.is_overdue_shipment is False              # a 90-day policy chases later

    def test_is_overdue_shipment_is_false_once_the_customer_has_said_they_shipped(
        self, rma_awaiting_receipt_a,
    ):
        from django.utils import timezone
        rma = rma_awaiting_receipt_a
        rma.approved_on = timezone.localdate() - datetime.timedelta(days=60)
        rma.customer_shipped_on = timezone.localdate()
        assert rma.is_overdue_shipment is False

    def test_is_overdue_shipment_needs_an_approval_date_and_a_live_status(self,
                                                                          rma_awaiting_receipt_a):
        from django.utils import timezone
        rma = rma_awaiting_receipt_a
        rma.approved_on = None
        assert rma.is_overdue_shipment is False
        rma.approved_on = timezone.localdate() - datetime.timedelta(days=90)
        rma.status = "settled"
        assert rma.is_overdue_shipment is False

    def test_is_overdue_shipment_falls_back_to_30_days_without_a_policy(self, tenant_a,
                                                                        customer_a):
        from django.utils import timezone
        from apps.scm.models import ReturnAuthorization
        rma = ReturnAuthorization(tenant=tenant_a, customer=customer_a, policy=None,
                                  requested_on=timezone.localdate())
        rma.status = "approved"
        rma.approved_on = timezone.localdate() - datetime.timedelta(days=31)
        assert rma.is_overdue_shipment is True


class TestReturnAuthorizationSettlement:
    def test_is_settleable_is_false_before_anything_is_authorised(self, return_authorization_a):
        assert return_authorization_a.status == "draft"
        assert return_authorization_a.is_settleable is False

    def test_a_physical_return_is_settleable_only_once_a_credit_bearing_row_exists(
        self, tenant_a, rma_received_a, disposition_a,
    ):
        assert disposition_a.disposition == "received_pending"
        assert rma_received_a.is_settleable is False      # nothing decided yet
        disposition_a.disposition = "scrap"
        disposition_a.save(update_fields=["disposition"])
        rma_received_a.refresh_from_db()
        assert rma_received_a.is_settleable is True

    def test_repair_return_is_deliberately_NOT_credit_bearing(self, rma_received_a,
                                                              disposition_a):
        """The unit goes BACK to the customer repaired — they keep the goods, so they do not also
        keep the money."""
        from apps.scm.models import CREDIT_BEARING_DISPOSITIONS
        assert "repair_return" not in CREDIT_BEARING_DISPOSITIONS
        assert "received_pending" not in CREDIT_BEARING_DISPOSITIONS
        disposition_a.disposition = "repair_return"
        disposition_a.save(update_fields=["disposition"])
        rma_received_a.refresh_from_db()
        assert rma_received_a.is_settleable is False

    def test_a_credit_only_return_is_settleable_with_NO_bench_row_at_all(self, rma_credit_only_a):
        """REGRESSION LOCK (item 8) — the credit-only trap, on the model."""
        assert rma_credit_only_a.lines.first().dispositions.count() == 0
        assert rma_credit_only_a.is_settleable is True

    def test_settlement_figures_carry_the_tax_and_net_the_fee(self, tenant_a, rma_received_a,
                                                              disposition_a):
        disposition_a.disposition = "restock"
        disposition_a.save(update_fields=["disposition"])
        line = rma_received_a.lines.first()
        line.line_fee = Decimal("5.00")
        line.save(update_fields=["line_fee"])
        rma_received_a.refresh_from_db()
        subtotal, fee, tax, total = rma_received_a.settlement_figures
        assert subtotal == Decimal("45.00")               # 3 x 15.00
        assert fee == Decimal("5.00")
        assert tax == Decimal("9.00")                    # 20 % of 45.00
        assert total == Decimal("49.00")                 # 45 + 9 - 5

    def test_settlement_figures_are_zero_while_nothing_is_credit_bearing(self, rma_received_a,
                                                                        disposition_a):
        assert rma_received_a.settlement_figures == (Decimal("0.00"), Decimal("0.00"),
                                                     Decimal("0.00"), Decimal("0.00"))

    def test_the_four_settlement_columns_are_NOT_written_by_reading_the_property(
        self, rma_received_a, disposition_a,
    ):
        """The stored figures have exactly ONE writer — the draft-credit-note action. Reading the
        proposal must leave the record saying no credit was issued."""
        disposition_a.disposition = "restock"
        disposition_a.save(update_fields=["disposition"])
        rma_received_a.refresh_from_db()
        assert rma_received_a.settlement_figures[3] == Decimal("54.00")
        rma_received_a.refresh_from_db()
        assert rma_received_a.credit_total == Decimal("0")
        assert rma_received_a.refund_subtotal == Decimal("0")

    def test_snapshot_decodes_json_and_never_raises_on_rubbish(self, return_authorization_a):
        import json
        rma = return_authorization_a
        assert rma.snapshot == {}
        rma.policy_snapshot = json.dumps({"within_window": True})
        assert rma.snapshot == {"within_window": True}
        rma.policy_snapshot = "not json at all"
        assert rma.snapshot == {}
        rma.policy_snapshot = json.dumps([1, 2, 3])       # valid JSON, wrong shape
        assert rma.snapshot == {}


class TestReturnLineDerived:
    def test_str_is_the_sku_and_the_requested_quantity(self, return_line_a, item_a):
        assert str(return_line_a) == f"{item_a.sku} ×{return_line_a.quantity_requested}"

    def test_quantity_received_sums_every_row_pending_included(self, tenant_a, return_line_a,
                                                               location_a):
        """REGRESSION LOCK (item 9), at the line grain."""
        from django.utils import timezone
        from apps.scm.models import ReturnDisposition
        assert return_line_a.quantity_received == Decimal("0")
        ReturnDisposition.objects.create(tenant=tenant_a, return_line=return_line_a,
                                         quantity=Decimal("2"), received_on=timezone.localdate(),
                                         location=location_a, disposition="received_pending")
        assert return_line_a.quantity_received == Decimal("2.0000")

    def test_quantity_outstanding_never_goes_negative(self, tenant_a, return_line_a, location_a):
        from django.utils import timezone
        from apps.scm.models import ReturnDisposition
        assert return_line_a.quantity_outstanding == Decimal("3.0000")
        ReturnDisposition.objects.create(tenant=tenant_a, return_line=return_line_a,
                                         quantity=Decimal("3"), received_on=timezone.localdate(),
                                         location=location_a, disposition="received_pending")
        return_line_a.refresh_from_db()
        assert return_line_a.quantity_outstanding == Decimal("0")

    def test_quantity_outstanding_falls_back_to_the_requested_quantity(self,
                                                                       return_authorization_a):
        line = return_authorization_a.lines.first()
        assert line.quantity_approved == Decimal("0")
        assert line.quantity_outstanding == Decimal("3.0000")

    def test_credit_quantity_comes_from_the_DISPOSITION_rows_not_the_approval(self, rma_received_a,
                                                                              disposition_a):
        line = rma_received_a.lines.first()
        assert line.quantity_approved == Decimal("3.0000")
        assert line.credit_quantity == Decimal("0")       # nothing decided yet
        disposition_a.disposition = "restock"
        disposition_a.save(update_fields=["disposition"])
        line.refresh_from_db()
        assert line.credit_quantity == Decimal("3.0000")

    def test_credit_quantity_on_a_credit_only_return_IS_the_approved_quantity(self,
                                                                              rma_credit_only_a):
        line = rma_credit_only_a.lines.first()
        assert line.dispositions.count() == 0
        assert line.credit_quantity == Decimal("2.0000")

    def test_credit_quantity_mixes_a_partial_split(self, tenant_a, rma_received_a, disposition_a,
                                                   location_a):
        from django.utils import timezone
        from apps.scm.models import ReturnDisposition
        disposition_a.quantity = Decimal("2")
        disposition_a.disposition = "restock"
        disposition_a.save(update_fields=["quantity", "disposition"])
        ReturnDisposition.objects.create(tenant=tenant_a, return_line=disposition_a.return_line,
                                         quantity=Decimal("1"), received_on=timezone.localdate(),
                                         location=location_a, disposition="repair_return")
        line = rma_received_a.lines.first()
        line.refresh_from_db()
        assert line.credit_quantity == Decimal("2.0000")   # the repair_return is not credited

    def test_line_credit_and_line_tax(self, rma_received_a, disposition_a):
        disposition_a.disposition = "restock"
        disposition_a.save(update_fields=["disposition"])
        line = rma_received_a.lines.first()
        line.line_fee = Decimal("4.50")
        line.save(update_fields=["line_fee"])
        line.refresh_from_db()
        assert line.line_credit == Decimal("40.50")        # 45.00 - 4.50
        assert line.line_tax == Decimal("9.00")

    def test_a_line_without_a_tax_snapshot_credits_no_tax(self, rma_credit_only_a):
        line = rma_credit_only_a.lines.first()
        assert line.tax_pct == Decimal("0.00")
        assert line.line_tax == Decimal("0.00")
        assert line.line_credit == Decimal("50.00")


class TestReturnLineClean:
    def test_approving_more_than_was_asked_for_is_refused(self, return_line_a):
        return_line_a.quantity_approved = Decimal("4")
        with pytest.raises(ValidationError) as exc:
            return_line_a.full_clean()
        assert "quantity_approved" in exc.value.error_dict

    def test_a_lot_belonging_to_another_item_is_refused(self, return_line_a, lot_a):
        return_line_a.lot_serial = lot_a          # lot_a belongs to item_lot_a, not item_a
        with pytest.raises(ValidationError) as exc:
            return_line_a.clean()
        assert "lot_serial" in exc.value.error_dict

    def test_an_order_line_for_a_different_item_is_refused(self, return_line_a, tenant_a,
                                                           returns_sales_order_a, item_lot_a):
        from apps.scm.models import SalesOrderLine
        other = SalesOrderLine.objects.create(sales_order=returns_sales_order_a, item=item_lot_a,
                                              quantity_ordered=Decimal("1"))
        return_line_a.sales_order_line = other
        with pytest.raises(ValidationError) as exc:
            return_line_a.clean()
        assert "sales_order_line" in exc.value.error_dict

    def test_a_zero_requested_quantity_is_refused_by_the_validator(self, return_line_a):
        return_line_a.quantity_requested = Decimal("0")
        with pytest.raises(ValidationError) as exc:
            return_line_a.full_clean()
        assert "quantity_requested" in exc.value.error_dict


class TestReturnDispositionBasics:
    def test_defaults_and_str(self, disposition_a):
        assert disposition_a.disposition == "received_pending"
        assert disposition_a.condition_grade == "a"
        assert disposition_a.stock_posted is False
        assert disposition_a.stock_move_id is None
        assert disposition_a.refurbished_on is None
        assert disposition_a.decided_on is None
        disposition_a.refresh_from_db()
        assert str(disposition_a) == "Received — awaiting decision ×3.0000 (grade A)"

    def test_received_on_is_stamped_in_save_when_left_blank(self, tenant_a, return_line_a,
                                                            location_a):
        from django.utils import timezone
        from apps.scm.models import ReturnDisposition
        row = ReturnDisposition(tenant=tenant_a, return_line=return_line_a,
                                quantity=Decimal("1"), location=location_a)
        row.save()
        assert row.received_on == timezone.localdate()

    def test_the_disposition_ladder_is_the_shared_vocabulary(self):
        from apps.scm.models import (DECIDED_DISPOSITION_CHOICES, DISPOSITION_CHOICES,
                                     ReturnDisposition)
        assert ReturnDisposition.DISPOSITION_CHOICES is DISPOSITION_CHOICES
        assert ReturnDisposition.DECIDED_DISPOSITION_CHOICES is DECIDED_DISPOSITION_CHOICES
        assert [c[0] for c in DISPOSITION_CHOICES][0] == "received_pending"
        # received_pending is reached by RECEIVING, never by deciding.
        assert "received_pending" not in {c[0] for c in DECIDED_DISPOSITION_CHOICES}
        assert len(DECIDED_DISPOSITION_CHOICES) == len(DISPOSITION_CHOICES) - 1

    def test_the_write_off_band_and_the_consuming_band_agree(self):
        from apps.scm.models import ReturnDisposition
        assert ReturnDisposition.WRITE_OFF_DISPOSITIONS == ("scrap", "donate", "recycle",
                                                            "liquidate")
        assert ReturnDisposition.CONSUMING_DISPOSITIONS == \
            ReturnDisposition.WRITE_OFF_DISPOSITIONS

    def test_is_decided_flips_off_received_pending(self, disposition_a):
        assert disposition_a.is_decided is False
        disposition_a.disposition = "scrap"
        assert disposition_a.is_decided is True

    def test_recovery_variance_is_a_management_figure(self, disposition_a):
        disposition_a.recovery_value = Decimal("30.00")
        disposition_a.restock_unit_cost = Decimal("8.0000")
        assert disposition_a.recovery_variance == Decimal("6.00")     # 30 - 3 x 8


class TestReturnDispositionPostsStock:
    """The per-disposition ledger effect, as an EXECUTABLE table."""

    def test_intake_posts_nothing(self, disposition_a):
        assert disposition_a.posts_stock is False

    def test_a_restock_with_a_destination_posts_and_only_once(self, disposition_a, location_a2):
        disposition_a.disposition = "restock"
        disposition_a.restock_location = location_a2
        assert disposition_a.posts_stock is True
        disposition_a.stock_posted = True
        assert disposition_a.posts_stock is False

    def test_a_restock_with_NO_destination_never_claims_it_can_post(self, disposition_a):
        disposition_a.disposition = "restock"
        assert disposition_a.restock_location_id is None
        assert disposition_a.posts_stock is False

    def test_the_four_non_posting_decisions_post_nothing(self, disposition_a, location_a2):
        disposition_a.restock_location = location_a2
        for decision in ("return_to_vendor", "repair_return", "quarantine", "credit_only"):
            disposition_a.disposition = decision
            assert disposition_a.posts_stock is False, decision

    def test_a_write_off_straight_off_the_bench_posts_nothing(self, disposition_a, location_a2):
        from apps.scm.models import ReturnDisposition
        disposition_a.restock_location = location_a2
        for decision in ReturnDisposition.WRITE_OFF_DISPOSITIONS:
            disposition_a.disposition = decision
            disposition_a.stock_posted = False
            assert disposition_a.posts_stock is False, decision

    def test_a_write_off_of_a_unit_that_WAS_restocked_reverses_it(self, disposition_a,
                                                                  location_a2):
        from apps.scm.models import ReturnDisposition
        disposition_a.restock_location = location_a2
        disposition_a.stock_posted = True
        for decision in ReturnDisposition.WRITE_OFF_DISPOSITIONS:
            disposition_a.disposition = decision
            assert disposition_a.posts_stock is True, decision

    def test_a_write_off_with_no_location_refuses_rather_than_handing_None_onward(self,
                                                                                  disposition_a):
        """``_insufficient_stock`` would get ``location=None`` and raise an uncaught
        AttributeError — the caller only catches ValidationError."""
        disposition_a.disposition = "scrap"
        disposition_a.stock_posted = True
        assert disposition_a.restock_location_id is None
        assert disposition_a.posts_stock is False

    def test_a_row_with_no_line_or_no_item_posts_nothing(self, tenant_a):
        from apps.scm.models import ReturnDisposition
        assert ReturnDisposition(tenant=tenant_a, disposition="restock").posts_stock is False


class TestCanRestockAfterRefurbish:
    """REGRESSION LOCK (item 1). Without the ``restock_location_id`` clause a refurbished row with
    nowhere to go drew the Post button on two pages, and pressing it handed ``location=None`` to
    ``_post_stock_move`` — an IntegrityError inside the atomic block that the caller's
    ``except ValidationError`` does not catch. A hard 500 on 4.10's only ledger action."""

    def test_a_refurbished_row_with_NO_restock_location_is_not_postable(self, disposition_a):
        from django.utils import timezone
        disposition_a.disposition = "refurbish"
        disposition_a.refurbished_on = timezone.localdate()
        assert disposition_a.restock_location_id is None
        assert disposition_a.can_restock_after_refurbish is False
        assert disposition_a.posts_stock is False

    def test_a_refurbished_row_WITH_one_is_postable(self, disposition_a, location_a2):
        from django.utils import timezone
        disposition_a.disposition = "refurbish"
        disposition_a.refurbished_on = timezone.localdate()
        disposition_a.restock_location = location_a2
        assert disposition_a.can_restock_after_refurbish is True

    def test_an_unfinished_refurbishment_is_not_postable(self, disposition_a, location_a2):
        disposition_a.disposition = "refurbish"
        disposition_a.restock_location = location_a2
        assert disposition_a.refurbished_on is None
        assert disposition_a.can_restock_after_refurbish is False

    def test_an_already_posted_refurbishment_is_not_postable_again(self, disposition_a,
                                                                   location_a2):
        from django.utils import timezone
        disposition_a.disposition = "refurbish"
        disposition_a.refurbished_on = timezone.localdate()
        disposition_a.restock_location = location_a2
        disposition_a.stock_posted = True
        assert disposition_a.can_restock_after_refurbish is False

    def test_only_a_refurbish_row_qualifies(self, disposition_a, location_a2):
        from django.utils import timezone
        disposition_a.refurbished_on = timezone.localdate()
        disposition_a.restock_location = location_a2
        for decision in ("received_pending", "restock", "scrap", "quarantine"):
            disposition_a.disposition = decision
            assert disposition_a.can_restock_after_refurbish is False, decision


class TestIsSplittableKeysOnTheLedgerNotTheLatch:
    """REGRESSION LOCK (item 5). After a restock-then-write-off the latch is False again (correctly
    — the unit is no longer IN stock) but the row has written TWO real movements."""

    def test_an_undecided_unposted_row_is_splittable(self, disposition_a):
        assert disposition_a.is_splittable is True

    def test_a_decided_row_is_not(self, disposition_a):
        disposition_a.disposition = "restock"
        assert disposition_a.is_splittable is False

    def test_a_row_that_ever_touched_the_ledger_is_not_even_with_the_latch_off(
        self, tenant_a, disposition_a, item_a, location_a2,
    ):
        from django.utils import timezone
        from apps.scm.models import StockMove
        move = StockMove.objects.create(tenant=tenant_a, item=item_a, location=location_a2,
                                        quantity=Decimal("-3"), move_type="adjustment",
                                        moved_at=timezone.now())
        disposition_a.disposition = "received_pending"     # somebody re-opened it
        disposition_a.stock_posted = False                 # the latch says "not in stock"
        disposition_a.stock_move = move                    # but the ledger remembers
        assert disposition_a.is_splittable is False


class TestReturnDispositionClean:
    def test_a_tracked_item_needs_its_lot(self, tenant_a, rma_awaiting_receipt_a, item_lot_a,
                                          return_reason_a, location_a):
        from apps.scm.models import ReturnDisposition, ReturnLine
        line = ReturnLine.objects.create(
            return_authorization=rma_awaiting_receipt_a, item=item_lot_a,
            quantity_requested=Decimal("2"), quantity_approved=Decimal("2"),
            reason=return_reason_a)
        row = ReturnDisposition(tenant=tenant_a, return_line=line, quantity=Decimal("1"),
                                location=location_a)
        with pytest.raises(ValidationError) as exc:
            row.clean()
        assert "lot_serial" in exc.value.error_dict

    def test_a_lot_from_another_item_is_refused(self, tenant_a, disposition_a, lot_a):
        disposition_a.lot_serial = lot_a       # belongs to item_lot_a, the line is item_a
        with pytest.raises(ValidationError) as exc:
            disposition_a.clean()
        assert "lot_serial" in exc.value.error_dict

    def test_a_restock_needs_somewhere_to_go(self, disposition_a):
        disposition_a.disposition = "restock"
        with pytest.raises(ValidationError) as exc:
            disposition_a.clean()
        assert "restock_location" in exc.value.error_dict

    def test_a_restock_may_not_leave_the_unit_on_the_bench(self, disposition_a, location_a):
        disposition_a.disposition = "restock"
        disposition_a.restock_location = location_a          # the bench itself
        with pytest.raises(ValidationError) as exc:
            disposition_a.clean()
        assert "restock_location" in exc.value.error_dict

    def test_a_reason_that_blocks_restocking_refuses_it_on_the_model_too(
        self, tenant_a, rma_awaiting_receipt_a, return_reason_blocking_a, item_a, location_a,
        location_a2,
    ):
        from apps.scm.models import ReturnDisposition, ReturnLine
        line = ReturnLine.objects.create(
            return_authorization=rma_awaiting_receipt_a, item=item_a,
            quantity_requested=Decimal("1"), quantity_approved=Decimal("1"),
            reason=return_reason_blocking_a)
        row = ReturnDisposition(tenant=tenant_a, return_line=line, quantity=Decimal("1"),
                                location=location_a, disposition="restock",
                                restock_location=location_a2)
        with pytest.raises(ValidationError) as exc:
            row.clean()
        assert "disposition" in exc.value.error_dict

    def test_an_expired_lot_may_not_be_restocked(self, tenant_a, rma_awaiting_receipt_a,
                                                  item_lot_a, lot_a, return_reason_a, location_a,
                                                  location_a2):
        from apps.scm.models import ReturnDisposition, ReturnLine
        lot_a.status = "expired"
        lot_a.save(update_fields=["status"])
        line = ReturnLine.objects.create(
            return_authorization=rma_awaiting_receipt_a, item=item_lot_a,
            quantity_requested=Decimal("1"), quantity_approved=Decimal("1"),
            reason=return_reason_a)
        row = ReturnDisposition(tenant=tenant_a, return_line=line, quantity=Decimal("1"),
                                location=location_a, lot_serial=lot_a, disposition="restock",
                                restock_location=location_a2)
        with pytest.raises(ValidationError) as exc:
            row.clean()
        assert "disposition" in exc.value.error_dict

    def test_writing_off_a_restocked_unit_needs_the_location_it_went_into(self, disposition_a):
        disposition_a.disposition = "scrap"
        disposition_a.stock_posted = True
        with pytest.raises(ValidationError) as exc:
            disposition_a.clean()
        assert "restock_location" in exc.value.error_dict


class TestReturnDispositionAuthorisedQuantityCap:
    """REGRESSION LOCK (item 3). The cap used to live ONLY in the formset's ``clean()``, which left
    the single-row edit path free to raise a bench quantity to anything ``DecimalField(14, 4)``
    holds — and because the credit note is deliberately computed FROM the bench rows, that flowed
    straight into a real ``accounting.Invoice`` for more than was ever returned."""

    def test_a_single_row_edit_cannot_exceed_the_authorised_quantity(self, disposition_a):
        assert disposition_a.return_line.quantity_approved == Decimal("3.0000")
        disposition_a.quantity = Decimal("5")
        with pytest.raises(ValidationError) as exc:
            disposition_a.clean()
        assert "quantity" in exc.value.error_dict
        assert "3.0000 authorised" in str(exc.value)

    def test_the_cap_counts_the_SIBLING_rows_on_the_same_line(self, tenant_a, return_line_a,
                                                              disposition_a, location_a):
        from django.utils import timezone
        from apps.scm.models import ReturnDisposition
        second = ReturnDisposition(tenant=tenant_a, return_line=return_line_a,
                                   quantity=Decimal("1"), received_on=timezone.localdate(),
                                   location=location_a)
        with pytest.raises(ValidationError) as exc:
            second.clean()
        assert "quantity" in exc.value.error_dict

    def test_the_cap_excludes_the_row_being_edited(self, disposition_a):
        disposition_a.quantity = Decimal("3")
        disposition_a.clean()                 # unchanged at the ceiling — legal
        disposition_a.quantity = Decimal("1")
        disposition_a.clean()                 # reduced — legal

    def test_the_cap_falls_back_to_the_requested_quantity_when_nothing_is_approved(
        self, tenant_a, return_authorization_a, location_a,
    ):
        from apps.scm.models import ReturnDisposition
        line = return_authorization_a.lines.first()
        assert line.quantity_approved == Decimal("0")
        row = ReturnDisposition(tenant=tenant_a, return_line=line, quantity=Decimal("9"),
                                location=location_a)
        with pytest.raises(ValidationError) as exc:
            row.clean()
        assert "quantity" in exc.value.error_dict

    def test_the_cap_is_reached_through_full_clean_too(self, disposition_a):
        disposition_a.quantity = Decimal("4")
        with pytest.raises(ValidationError) as exc:
            disposition_a.full_clean()
        assert "quantity" in exc.value.error_dict


class TestReturnPolicyDerived:
    def test_str_and_defaults(self, tenant_a):
        from apps.scm.models import ReturnPolicy
        policy = ReturnPolicy.objects.create(tenant=tenant_a, name="Bare")
        assert str(policy) == "Bare"
        assert policy.is_active is True
        assert policy.is_default is False
        assert policy.priority == 100
        assert policy.window_basis == "delivery"
        assert (policy.window_days, policy.fallback_days) == (30, 45)
        assert policy.warranty_window_days == 365
        assert policy.refund_basis == "full"
        assert policy.refund_pct == Decimal("100.00")
        assert policy.restocking_fee_type == "none"
        assert policy.auto_approve is False
        assert policy.allow_keep_item is False

    def test_the_grade_ladder_is_a_real_curve(self, return_policy_a):
        assert return_policy_a.grade_cost_pct("a") == Decimal("100.00")
        assert return_policy_a.grade_cost_pct("B") == Decimal("75.00")
        assert return_policy_a.grade_cost_pct("c") == Decimal("40.00")
        assert return_policy_a.grade_cost_pct("d") == Decimal("0.00")

    def test_an_ungraded_unit_is_written_down_to_zero_not_up_to_full_cost(self, return_policy_a):
        """Falling back to 100 % would restock an ungraded unit at full cost — the expensive
        direction to be wrong in."""
        assert return_policy_a.grade_cost_pct("z") == Decimal("0")
        assert return_policy_a.grade_cost_pct("") == Decimal("0")
        assert return_policy_a.grade_cost_pct(None) == Decimal("0")

    def test_restock_cost_for_seeds_from_the_grade_and_the_average_cost(self, return_policy_a):
        assert return_policy_a.restock_cost_for("a", Decimal("10")) == Decimal("10.0000")
        assert return_policy_a.restock_cost_for("b", Decimal("10")) == Decimal("7.5000")
        assert return_policy_a.restock_cost_for("c", Decimal("10")) == Decimal("4.0000")
        assert return_policy_a.restock_cost_for("d", Decimal("10")) == Decimal("0.0000")
        assert return_policy_a.restock_cost_for("a", None) == Decimal("0.0000")

    def test_fee_for_handles_all_three_types(self, return_policy_a):
        assert return_policy_a.fee_for(Decimal("100")) == Decimal("0")
        return_policy_a.restocking_fee_type = "flat"
        return_policy_a.restocking_fee_value = Decimal("7.50")
        assert return_policy_a.fee_for(Decimal("100")) == Decimal("7.50")
        return_policy_a.restocking_fee_type = "percent_of_value"
        return_policy_a.restocking_fee_value = Decimal("15")
        assert return_policy_a.fee_for(Decimal("100")) == Decimal("15.00")

    def test_refund_for_handles_all_three_bases(self, return_policy_a):
        assert return_policy_a.refund_for(Decimal("80")) == Decimal("80.00")
        return_policy_a.refund_basis = "percentage"
        return_policy_a.refund_pct = Decimal("50")
        assert return_policy_a.refund_for(Decimal("80")) == Decimal("40.00")
        return_policy_a.refund_basis = "none"
        assert return_policy_a.refund_for(Decimal("80")) == Decimal("0")

    def test_allowed_resolutions_reflects_the_four_booleans(self, return_policy_a):
        assert return_policy_a.allowed_resolutions == ("refund", "store_credit", "exchange")
        return_policy_a.allow_keep_item = True
        return_policy_a.allow_store_credit = False
        assert return_policy_a.allowed_resolutions == ("refund", "exchange", "keep_item")


class TestReturnPolicyClean:
    def test_a_zero_percent_percentage_refund_is_refused(self, return_policy_a):
        return_policy_a.refund_basis = "percentage"
        return_policy_a.refund_pct = Decimal("0")
        with pytest.raises(ValidationError) as exc:
            return_policy_a.clean()
        assert "refund_pct" in exc.value.error_dict

    def test_a_configured_fee_with_no_value_is_refused(self, return_policy_a):
        return_policy_a.restocking_fee_type = "flat"
        with pytest.raises(ValidationError) as exc:
            return_policy_a.clean()
        assert "restocking_fee_value" in exc.value.error_dict

    def test_a_percentage_fee_over_100_is_refused(self, return_policy_a):
        return_policy_a.restocking_fee_type = "percent_of_value"
        return_policy_a.restocking_fee_value = Decimal("120")
        with pytest.raises(ValidationError) as exc:
            return_policy_a.clean()
        assert "restocking_fee_value" in exc.value.error_dict

    def test_a_policy_that_accepts_no_return_at_all_is_refused(self, return_policy_a):
        return_policy_a.window_days = 0
        return_policy_a.fallback_days = 0
        with pytest.raises(ValidationError) as exc:
            return_policy_a.clean()
        assert "window_days" in exc.value.error_dict


class TestReturnPolicyDayFieldCaps:
    """REGRESSION LOCK (item 13). All three fields are fed to ``datetime.timedelta(days=...)`` and
    a PositiveIntegerField accepts up to 4294967295 — an uncaught ``OverflowError`` (a 500), not a
    validation error. ONE saved value would permanently break the RMA list, every RMA detail page
    and the approve action for the whole tenant: a stored denial of service."""

    def test_each_of_the_three_day_fields_is_capped_at_3650(self, return_policy_a):
        for field in ("window_days", "fallback_days", "warranty_window_days"):
            fresh = type(return_policy_a).objects.get(pk=return_policy_a.pk)
            setattr(fresh, field, 3651)
            with pytest.raises(ValidationError) as exc:
                fresh.full_clean()
            assert field in exc.value.error_dict, field

    def test_exactly_3650_is_still_accepted(self, return_policy_a):
        return_policy_a.window_days = 3650
        return_policy_a.fallback_days = 3650
        return_policy_a.warranty_window_days = 3650
        return_policy_a.full_clean()

    def test_the_value_that_used_to_500_is_refused_at_the_model(self, return_policy_a):
        return_policy_a.window_days = 4294967295
        with pytest.raises(ValidationError) as exc:
            return_policy_a.full_clean()
        assert "window_days" in exc.value.error_dict


class TestSelectPolicy:
    def test_a_category_specific_policy_beats_the_blanket_one(self, tenant_a, item_a,
                                                              return_policy_a,
                                                              return_policy_fee_a):
        from apps.scm.models import select_policy
        assert select_policy(tenant_a, item_a) == return_policy_fee_a

    def test_an_item_in_no_matching_category_falls_back_to_the_default(self, tenant_a, item_lot_a,
                                                                       return_policy_a,
                                                                       return_policy_fee_a):
        from apps.scm.models import select_policy
        assert select_policy(tenant_a, item_lot_a) == return_policy_a

    def test_an_inactive_policy_is_never_selected(self, tenant_a, item_a, return_policy_a,
                                                  return_policy_fee_a):
        from apps.scm.models import select_policy
        return_policy_fee_a.is_active = False
        return_policy_fee_a.save(update_fields=["is_active"])
        assert select_policy(tenant_a, item_a) == return_policy_a

    def test_a_workspace_with_no_policies_returns_None(self, tenant_a, item_a):
        from apps.scm.models import select_policy
        assert select_policy(tenant_a, item_a) is None

    def test_no_tenant_returns_None(self, item_a):
        from apps.scm.models import select_policy
        assert select_policy(None, item_a) is None

    def test_another_tenants_policy_is_never_selected(self, tenant_a, item_a, return_policy_b):
        from apps.scm.models import select_policy
        assert select_policy(tenant_a, item_a) is None


class TestEvaluateReturnEligibility:
    def test_no_policy_at_all_blocks_with_a_named_reason(self, returns_sales_order_a, item_a,
                                                          return_reason_a):
        from apps.scm.models import evaluate_return_eligibility
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a, None)
        assert verdict["within_window"] is False
        assert verdict["basis_used"] == "none"
        assert verdict["allowed_resolutions"] == []
        assert any("No return policy is configured" in b for b in verdict["blockers"])
        assert verdict["reason"] == return_reason_a.code

    def test_an_order_with_no_delivery_stamp_falls_back_to_the_order_date(
        self, returns_sales_order_a, item_a, return_reason_a, return_policy_a,
    ):
        from apps.scm.models import evaluate_return_eligibility
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["basis_used"] == "fallback"
        assert verdict["basis_date_used"] == returns_sales_order_a.order_date.isoformat()
        assert verdict["within_window"] is True
        assert verdict["days_remaining"] == 45         # the FALLBACK window, not the 30-day one

    def test_a_delivered_order_uses_the_delivery_basis(self, returns_sales_order_a, item_a,
                                                        return_reason_a, return_policy_a):
        from django.utils import timezone
        from apps.scm.models import evaluate_return_eligibility
        returns_sales_order_a.delivered_notification_at = timezone.now()
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["basis_used"] == "delivery"
        assert verdict["days_remaining"] == 30

    def test_the_fulfilment_basis_reads_the_ship_stamp(self, returns_sales_order_a, item_a,
                                                       return_reason_a, return_policy_a):
        from django.utils import timezone
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.window_basis = "fulfilment"
        returns_sales_order_a.shipped_notification_at = timezone.now()
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["basis_used"] == "fulfilment"

    def test_the_order_date_basis_is_used_verbatim(self, returns_sales_order_a, item_a,
                                                    return_reason_a, return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.window_basis = "order_date"
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["basis_used"] == "order_date"
        assert verdict["days_remaining"] == 30

    def test_a_closed_window_blocks_and_names_the_date_it_ran_from(self, sales_order_a, item_a,
                                                                    return_reason_a,
                                                                    return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        verdict = evaluate_return_eligibility(sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["within_window"] is False
        assert any("Outside the 45-day window" in b for b in verdict["blockers"])
        assert verdict["basis_date_used"] == sales_order_a.order_date.isoformat()

    def test_a_blind_return_is_legitimate_but_needs_a_human(self, item_a, return_reason_a,
                                                             return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        verdict = evaluate_return_eligibility(None, item_a, return_reason_a, return_policy_a)
        assert verdict["basis_used"] == "none"
        assert verdict["deadline"] == ""
        assert any("approve this on judgement" in b for b in verdict["blockers"])

    def test_require_delivery_confirmation_blocks_an_unstamped_order(self, returns_sales_order_a,
                                                                      item_a, return_reason_a,
                                                                      return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.require_delivery_confirmation = True
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert any("requires a confirmed delivery" in b for b in verdict["blockers"])

    def test_a_cancelled_order_has_nothing_to_return_against(self, returns_sales_order_a, item_a,
                                                              return_reason_a, return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        returns_sales_order_a.status = "cancelled"
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert any("was cancelled" in b for b in verdict["blockers"])

    def test_an_inactive_policy_or_reason_blocks(self, returns_sales_order_a, item_a,
                                                 return_reason_a, return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.is_active = False
        return_reason_a.is_active = False
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert any("is inactive" in b for b in verdict["blockers"])

    def test_the_reason_NARROWS_the_policy_and_never_widens_it(self, returns_sales_order_a,
                                                               item_a, return_reason_a,
                                                               return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        return_reason_a.allows_exchange = False
        return_reason_a.allows_store_credit = False
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert verdict["allowed_resolutions"] == ["refund"]
        # A reason that allows a repair cannot unlock one the policy never offered.
        return_reason_a.allows_repair = True
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert "repair" not in verdict["allowed_resolutions"]

    def test_a_policy_and_a_reason_that_allow_nothing_together_block(self, returns_sales_order_a,
                                                                      item_a, return_reason_a,
                                                                      return_policy_a):
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.allow_refund = False
        return_policy_a.allow_store_credit = False
        return_policy_a.allow_exchange = False
        return_reason_a.allows_repair = True
        return_reason_a.allows_refund = False
        return_reason_a.allows_store_credit = False
        return_reason_a.allows_exchange = False
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a)
        assert any("allow no outcome at all" in b for b in verdict["blockers"])

    def test_the_money_is_the_policys_and_a_waiving_reason_suppresses_the_fee(
        self, returns_sales_order_a, item_a, return_reason_a, return_policy_a,
    ):
        from apps.scm.models import evaluate_return_eligibility
        return_policy_a.restocking_fee_type = "flat"
        return_policy_a.restocking_fee_value = Decimal("10.00")
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a, line_value=Decimal("45.00"))
        assert verdict["proposed_credit"] == "45.00"
        assert verdict["proposed_fee"] == "10.00"
        assert verdict["proposed_net"] == "35.00"
        return_reason_a.waives_return_fee = True
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a, line_value=Decimal("45.00"))
        assert verdict["proposed_fee"] == "0"
        assert verdict["proposed_net"] == "45.00"

    def test_the_verdict_is_json_round_trippable_because_it_is_STORED_as_text(
        self, returns_sales_order_a, item_a, return_reason_a, return_policy_a,
    ):
        import json
        from apps.scm.models import evaluate_return_eligibility
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a, line_value=Decimal("45.00"))
        assert json.loads(json.dumps(verdict)) == verdict

    def test_as_of_is_injectable_so_the_window_never_depends_on_the_wall_clock(
        self, returns_sales_order_a, item_a, return_reason_a, return_policy_a,
    ):
        from apps.scm.models import evaluate_return_eligibility
        far = returns_sales_order_a.order_date + datetime.timedelta(days=999)
        verdict = evaluate_return_eligibility(returns_sales_order_a, item_a, return_reason_a,
                                              return_policy_a, as_of=far)
        assert verdict["within_window"] is False


class TestReturnReason:
    def test_str_and_defaults(self, tenant_a):
        from apps.scm.models import ReturnReason
        reason = ReturnReason.objects.create(tenant=tenant_a, code="X", name="Something")
        assert str(reason) == "X · Something"
        assert reason.fault_party == "customer"
        assert reason.allows_refund is True
        assert reason.allows_repair is False
        assert reason.blocks_restock is False
        assert reason.requires_photo is False
        assert reason.raises_nonconformance is False
        assert reason.sort_order == 100
        assert reason.is_active is True

    def test_allowed_resolutions_reflects_the_four_booleans(self, return_reason_a):
        assert return_reason_a.allowed_resolutions == ("refund", "store_credit", "exchange")
        return_reason_a.allows_repair = True
        return_reason_a.allows_refund = False
        assert return_reason_a.allowed_resolutions == ("store_credit", "exchange", "repair")

    def test_a_reason_that_offers_nothing_is_refused(self, return_reason_a):
        return_reason_a.allows_refund = False
        return_reason_a.allows_store_credit = False
        return_reason_a.allows_exchange = False
        return_reason_a.allows_repair = False
        with pytest.raises(ValidationError) as exc:
            return_reason_a.clean()
        assert "allows_refund" in exc.value.error_dict

    def test_a_reason_cannot_block_and_suggest_a_restock_at_once(self, return_reason_a):
        return_reason_a.blocks_restock = True
        return_reason_a.suggested_disposition = "restock"
        with pytest.raises(ValidationError) as exc:
            return_reason_a.clean()
        assert "suggested_disposition" in exc.value.error_dict

    def test_the_suggested_disposition_choices_exclude_received_pending(self):
        from apps.scm.models import ReturnReason
        offered = {c[0] for c in ReturnReason._meta.get_field("suggested_disposition").choices}
        assert "received_pending" not in offered
        assert "restock" in offered


class TestWarrantyClaim:
    def test_str_and_defaults(self, tenant_a, supplier_a, item_a):
        from apps.scm.models import WarrantyClaim
        claim = WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                             quantity_claimed=Decimal("1"))
        assert str(claim) == f"{claim.number} · {item_a.sku}"
        assert claim.status == "draft"
        assert claim.defect_classification == "unknown"
        assert claim.submission_channel == "email"
        assert claim.amount_approved == Decimal("0")
        assert claim.amount_credited == Decimal("0")
        assert claim.credit_reference == ""
        assert claim.credit_received_on is None

    def test_is_editable_only_while_draft(self, warranty_claim_a):
        from apps.scm.models import WarrantyClaim
        for status, _label in WarrantyClaim.STATUS_CHOICES:
            warranty_claim_a.status = status
            assert warranty_claim_a.is_editable is (status == "draft"), status

    def test_the_amounts_are_derived_from_the_typed_cost_lines(self, warranty_claim_a):
        from apps.scm.models import WarrantyClaimCost
        assert warranty_claim_a.amount_claimed_total == Decimal("100.00")
        WarrantyClaimCost.objects.create(claim=warranty_claim_a, cost_type="labour",
                                          description="2 h fitting", quantity=Decimal("2"),
                                          unit_amount=Decimal("25.00"),
                                          amount_approved=Decimal("10.00"))
        fresh = type(warranty_claim_a).objects.get(pk=warranty_claim_a.pk)
        assert fresh.amount_claimed_total == Decimal("150.00")
        assert fresh.cost_approved_total == Decimal("10.00")

    def test_a_claim_with_no_cost_lines_totals_zero_and_never_divides_by_zero(self, tenant_a,
                                                                              supplier_a, item_a):
        from apps.scm.models import WarrantyClaim
        claim = WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                             quantity_claimed=Decimal("1"))
        assert claim.amount_claimed_total == Decimal("0.00")
        assert claim.recovery_rate_pct == Decimal("0")
        assert claim.recovery_variance == Decimal("0.00")

    def test_recovery_variance_and_rate(self, warranty_claim_approved_a):
        claim = warranty_claim_approved_a
        claim.amount_credited = Decimal("60.00")
        assert claim.recovery_variance == Decimal("40.00")
        assert claim.recovery_rate_pct == Decimal("60.00")

    def test_is_in_warranty_prefers_explicit_dates(self, warranty_claim_a):
        from django.utils import timezone
        claim = warranty_claim_a
        claim.warranty_start = timezone.localdate() - datetime.timedelta(days=30)
        claim.warranty_end = timezone.localdate() + datetime.timedelta(days=30)
        assert claim.is_in_warranty is True
        claim.warranty_end = timezone.localdate() - datetime.timedelta(days=1)
        assert claim.is_in_warranty is False
        claim.warranty_start = timezone.localdate() + datetime.timedelta(days=1)
        claim.warranty_end = timezone.localdate() + datetime.timedelta(days=30)
        assert claim.is_in_warranty is False        # it failed before cover began

    def test_is_in_warranty_derives_from_the_purchase_date_and_the_policy_window(
        self, warranty_claim_a, return_policy_a,
    ):
        from django.utils import timezone
        claim = warranty_claim_a
        assert claim.warranty_end is None
        assert claim.is_in_warranty is True                      # 10 days old, 365-day window
        return_policy_a.warranty_window_days = 5
        return_policy_a.save(update_fields=["warranty_window_days"])
        assert claim.is_in_warranty is False
        claim.purchase_date = None
        assert claim.is_in_warranty is False                     # nothing to derive from

    def test_is_overdue_needs_a_deadline_a_live_status_and_no_response(self, warranty_claim_a):
        from django.utils import timezone
        claim = warranty_claim_a
        claim.response_due_on = timezone.localdate() - datetime.timedelta(days=1)
        claim.status = "submitted"
        assert claim.is_overdue is True
        claim.responded_on = timezone.localdate()
        assert claim.is_overdue is False
        claim.responded_on = None
        claim.status = "rejected"                                 # terminal
        assert claim.is_overdue is False
        claim.status = "submitted"
        claim.response_due_on = None
        assert claim.is_overdue is False

    def test_days_open_counts_from_submission_or_creation(self, warranty_claim_a):
        from django.utils import timezone
        claim = warranty_claim_a
        assert claim.days_open >= 0
        claim.submitted_on = timezone.localdate() - datetime.timedelta(days=9)
        assert claim.days_open == 9
        claim.credit_received_on = timezone.localdate() - datetime.timedelta(days=4)
        assert claim.days_open == 5

    def test_is_possible_duplicate_is_advisory_and_scoped_to_the_supplier(self, tenant_a,
                                                                          supplier_a, vendor_a,
                                                                          item_a,
                                                                          warranty_claim_a):
        from apps.scm.models import WarrantyClaim
        warranty_claim_a.supplier_rma_number = "THEIR-1"
        warranty_claim_a.save(update_fields=["supplier_rma_number"])
        assert warranty_claim_a.is_possible_duplicate is False
        twin = WarrantyClaim.objects.create(tenant=tenant_a, supplier=supplier_a, item=item_a,
                                           quantity_claimed=Decimal("1"),
                                           supplier_rma_number="THEIR-1")
        warranty_claim_a.refresh_from_db()
        assert warranty_claim_a.is_possible_duplicate is True
        twin.status = "closed"
        twin.save(update_fields=["status"])
        assert warranty_claim_a.is_possible_duplicate is False    # closed claims do not count
        # A different supplier reusing the same reference is not a duplicate.
        twin.status = "submitted"
        twin.supplier = vendor_a
        twin.save(update_fields=["status", "supplier"])
        assert warranty_claim_a.is_possible_duplicate is False

    def test_is_possible_duplicate_is_false_without_a_reference(self, warranty_claim_a):
        assert warranty_claim_a.supplier_rma_number == ""
        assert warranty_claim_a.is_possible_duplicate is False

    def test_lot_history_is_empty_without_a_lot_and_reads_the_ledger_with_one(
        self, tenant_a, warranty_claim_a, item_lot_a, lot_a, location_a,
    ):
        from apps.scm.tests._helpers import seed_stock
        assert list(warranty_claim_a.lot_history()) == []
        warranty_claim_a.item = item_lot_a
        warranty_claim_a.lot_serial = lot_a
        warranty_claim_a.save(update_fields=["item", "lot_serial"])
        move = seed_stock(tenant_a, item_lot_a, location_a, "5", "1.0000")
        move.lot_serial = lot_a
        move.save(update_fields=["lot_serial"])
        assert list(warranty_claim_a.lot_history()) == [move]

    def test_clean_guards_the_three_impossible_date_and_lot_combinations(self, warranty_claim_a,
                                                                         lot_a):
        from django.utils import timezone
        claim = warranty_claim_a
        claim.lot_serial = lot_a           # belongs to item_lot_a, the claim is on item_a
        with pytest.raises(ValidationError) as exc:
            claim.clean()
        assert "lot_serial" in exc.value.error_dict
        claim.lot_serial = None
        claim.warranty_start = timezone.localdate()
        claim.warranty_end = timezone.localdate() - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            claim.clean()
        assert "warranty_end" in exc.value.error_dict
        claim.warranty_end = None
        claim.warranty_start = None
        claim.purchase_date = timezone.localdate()
        claim.failure_date = timezone.localdate() - datetime.timedelta(days=1)
        with pytest.raises(ValidationError) as exc:
            claim.clean()
        assert "failure_date" in exc.value.error_dict


class TestWarrantyClaimCost:
    def test_amount_claimed_is_COMPUTED_in_save_never_typed(self, warranty_claim_a):
        from apps.scm.models import WarrantyClaimCost
        row = WarrantyClaimCost.objects.create(
            claim=warranty_claim_a, cost_type="freight", description="Return freight",
            quantity=Decimal("3"), unit_amount=Decimal("12.50"),
            amount_claimed=Decimal("9999.99"))       # a crafted value is overwritten
        row.refresh_from_db()
        assert row.amount_claimed == Decimal("37.50")

    def test_amount_claimed_is_not_editable(self):
        from apps.scm.models import WarrantyClaimCost
        assert WarrantyClaimCost._meta.get_field("amount_claimed").editable is False

    def test_a_supplier_cannot_approve_more_than_was_claimed(self, warranty_claim_a):
        from apps.scm.models import WarrantyClaimCost
        row = WarrantyClaimCost(claim=warranty_claim_a, description="X", quantity=Decimal("1"),
                                unit_amount=Decimal("10.00"), amount_approved=Decimal("11.00"))
        with pytest.raises(ValidationError) as exc:
            row.clean()
        assert "amount_approved" in exc.value.error_dict

    def test_str_is_the_type_and_the_description(self, warranty_claim_a):
        row = warranty_claim_a.costs.first()
        assert str(row) == "Replacement part · Replacement gear"


class TestReturnsNothingIsStored:
    """Ledger-adjacent code: quantities and balances are DERIVED, never stored."""

    def test_the_bench_row_holds_no_quantity_received_column(self):
        from apps.scm.models import ReturnLine
        columns = {f.name for f in ReturnLine._meta.get_fields()}
        for derived in ("quantity_received", "quantity_outstanding", "credit_quantity",
                        "line_credit", "line_tax"):
            assert derived not in columns, derived

    def test_the_rma_holds_no_quantity_roll_up_columns(self):
        from apps.scm.models import ReturnAuthorization
        columns = {f.name for f in ReturnAuthorization._meta.get_fields()}
        for derived in ("quantity_requested_total", "quantity_approved_total",
                        "quantity_received_total", "is_fully_received", "days_open",
                        "is_settleable", "settlement_figures"):
            assert derived not in columns, derived

    def test_the_stored_settlement_columns_are_all_editable_False(self):
        from apps.scm.models import ReturnAuthorization
        for name in ("refund_subtotal", "fee_total", "tax_total", "credit_total", "status",
                     "policy_snapshot", "approved_on", "approved_by", "rejected_reason",
                     "customer_shipped_on", "public_token", "portal_note", "credit_note",
                     "replacement_order", "number"):
            assert ReturnAuthorization._meta.get_field(name).editable is False, name

    def test_the_bench_rows_stamped_columns_are_all_editable_False(self):
        from apps.scm.models import ReturnDisposition
        for name in ("received_on", "received_by", "refurbished_on", "stock_posted", "stock_move",
                     "decided_on", "decided_by"):
            assert ReturnDisposition._meta.get_field(name).editable is False, name

    def test_the_warranty_negotiation_columns_are_all_editable_False(self):
        from apps.scm.models import WarrantyClaim
        for name in ("number", "status", "submitted_on", "responded_on",
                     "supplier_response_notes", "amount_approved", "amount_credited",
                     "credit_reference", "credit_received_on"):
            assert WarrantyClaim._meta.get_field(name).editable is False, name

    def test_the_warranty_claim_total_is_an_aggregate_not_a_column(self, warranty_claim_a):
        from django.db.models import Sum
        from apps.scm.models import WarrantyClaimCost
        assert warranty_claim_a.amount_claimed_total == (
            WarrantyClaimCost.objects.filter(claim=warranty_claim_a)
            .aggregate(s=Sum("amount_claimed"))["s"])
        assert "amount_claimed_total" not in {f.name
                                              for f in type(warranty_claim_a)._meta.get_fields()}
