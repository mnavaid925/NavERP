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
