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
