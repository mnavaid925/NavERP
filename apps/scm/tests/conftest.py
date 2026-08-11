"""SCM app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b, client_a,
client_b, member_user, member_client) and adds SCM 4.1 Procurement Management records:
Currency/GLAccount/PaymentTerm/Budget (all ``apps.accounting``), supplier Parties (via
``core.PartyRole``, role ``supplier`` OR ``vendor``), and the PR -> RFQ -> quote -> PO ->
GRN chain itself.
"""
import datetime
from decimal import Decimal

import pytest


# ------------------------------------------------------------------ Currency / GL / PaymentTerm
@pytest.fixture
def usd(db):
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
    return obj


@pytest.fixture
def gl_expense(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="5000", name="Office Supplies Expense", account_type="expense"
    )


@pytest.fixture
def gl_expense_2(db, tenant_a):
    """A SECOND tenant_a expense account — used to prove budget_check() only counts
    committed spend on the SAME gl_account, not every requisition on the budget."""
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="5100", name="IT Equipment Expense", account_type="expense"
    )


@pytest.fixture
def gl_expense_b(db, tenant_b):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_b, code="5000", name="Globex Expense", account_type="expense"
    )


@pytest.fixture
def payment_terms_a(db, tenant_a):
    from apps.accounting.models import PaymentTerm
    return PaymentTerm.objects.create(tenant=tenant_a, name="Net 30", days_due=30)


# ------------------------------------------------------------------ Supplier parties
@pytest.fixture
def supplier_a(db, tenant_a):
    """A tenant_a Party tagged 'supplier' — the nominal SCM role."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Supplies Ltd", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="supplier")
    return party


@pytest.fixture
def vendor_a(db, tenant_a):
    """A SECOND tenant_a Party tagged 'vendor' (not 'supplier') — both spellings must be
    accepted as buy-from parties (apps/scm/forms/_common.py::_supplier_parties)."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Vendor Co", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="vendor")
    return party


@pytest.fixture
def non_supplier_party_a(db, tenant_a):
    """A tenant_a Party with NO supplier/vendor role — must never appear in a buy-from list."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Customer Only", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer")
    return party


@pytest.fixture
def supplier_b(db, tenant_b):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Supplies Ltd", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="supplier")
    return party


# ------------------------------------------------------------------ Org unit
@pytest.fixture
def org_unit_a(db, tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Operations", kind="department")


# ------------------------------------------------------------------ Budget (two GL accounts)
@pytest.fixture
def budget_a(db, tenant_a, gl_expense, gl_expense_2):
    from apps.accounting.models import Budget, BudgetLine
    budget = Budget.objects.create(tenant=tenant_a, name="FY2026 Opex", version="original", status="approved")
    BudgetLine.objects.create(tenant=tenant_a, budget=budget, gl_account=gl_expense, amount=Decimal("10000.00"))
    BudgetLine.objects.create(tenant=tenant_a, budget=budget, gl_account=gl_expense_2, amount=Decimal("5000.00"))
    return budget


# ------------------------------------------------------------------ Purchase Requisition
@pytest.fixture
def requisition_a(db, tenant_a, admin_user, org_unit_a, usd):
    """A draft requisition, tenant_a, one line (10 x $15.00 = $150.00)."""
    from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
    req = PurchaseRequisition.objects.create(
        tenant=tenant_a, title="Office supplies", requester=admin_user, org_unit=org_unit_a,
        currency=usd, status="draft",
    )
    PurchaseRequisitionLine.objects.create(
        requisition=req, item_description="Printer paper", quantity=Decimal("10"),
        estimated_unit_price=Decimal("15.00"),
    )
    req.recalc_totals()
    return req


@pytest.fixture
def requisition_pending_a(db, tenant_a, admin_user, org_unit_a, usd, budget_a, gl_expense):
    """A pending-approval requisition costed against gl_expense — ready for approve/reject."""
    from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine
    req = PurchaseRequisition.objects.create(
        tenant=tenant_a, title="New office chairs", requester=admin_user, org_unit=org_unit_a,
        currency=usd, budget=budget_a, status="pending_approval",
    )
    PurchaseRequisitionLine.objects.create(
        requisition=req, item_description="Ergonomic chairs", quantity=Decimal("4"),
        estimated_unit_price=Decimal("100.00"), gl_account=gl_expense,
    )
    req.recalc_totals()
    return req


@pytest.fixture
def requisition_b(db, tenant_b):
    from apps.scm.models import PurchaseRequisition
    return PurchaseRequisition.objects.create(tenant=tenant_b, title="Globex req", status="draft")


# ------------------------------------------------------------------ RFQ (+ quote)
@pytest.fixture
def rfq_a(db, tenant_a, usd):
    """A draft RFQ, tenant_a, one line (qty 10)."""
    from apps.scm.models import RFQ, RFQLine
    rfq = RFQ.objects.create(tenant=tenant_a, title="Paper RFQ", currency=usd, status="draft")
    RFQLine.objects.create(rfq=rfq, item_description="Printer paper", quantity=Decimal("10"))
    return rfq


@pytest.fixture
def rfq_sent_a(db, tenant_a, usd, supplier_a):
    """A sent RFQ, tenant_a, one line + one invited supplier — ready to be quoted/awarded."""
    from django.utils import timezone
    from apps.scm.models import RFQ, RFQLine, RFQVendor
    rfq = RFQ.objects.create(
        tenant=tenant_a, title="Paper RFQ", currency=usd, status="sent",
        issue_date=datetime.date(2026, 1, 1),
    )
    RFQLine.objects.create(rfq=rfq, item_description="Printer paper", quantity=Decimal("10"))
    RFQVendor.objects.create(tenant=tenant_a, rfq=rfq, party=supplier_a, invited_at=timezone.now())
    return rfq


@pytest.fixture
def quote_a(db, tenant_a, rfq_sent_a, supplier_a):
    """A received quote against rfq_sent_a, priced at $12.00/unit."""
    from apps.scm.models import RFQQuote, RFQQuoteLine
    quote = RFQQuote.objects.create(tenant=tenant_a, rfq=rfq_sent_a, party=supplier_a, status="received")
    line = rfq_sent_a.lines.first()
    RFQQuoteLine.objects.create(quote=quote, rfq_line=line, quantity=line.quantity, unit_price=Decimal("12.00"))
    quote.recalc_totals()
    return quote


@pytest.fixture
def rfq_b(db, tenant_b):
    from apps.scm.models import RFQ
    return RFQ.objects.create(tenant=tenant_b, title="Globex RFQ", status="draft")


@pytest.fixture
def quote_b(db, tenant_b, rfq_b, supplier_b):
    from apps.scm.models import RFQQuote
    return RFQQuote.objects.create(tenant=tenant_b, rfq=rfq_b, party=supplier_b, status="received")


# ------------------------------------------------------------------ Purchase Order (+ lines)
@pytest.fixture
def purchase_order_a(db, tenant_a, supplier_a, usd):
    """An approved order, tenant_a x supplier_a, one line (10 x $15.00 = $150.00)."""
    from apps.scm.models import PurchaseOrder, PurchaseOrderLine
    po = PurchaseOrder.objects.create(
        tenant=tenant_a, vendor=supplier_a, currency=usd,
        order_date=datetime.date(2026, 1, 5), status="approved",
    )
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Printer paper", quantity=Decimal("10"),
        unit_price=Decimal("15.00"),
    )
    po.recalc_totals()
    return po


@pytest.fixture
def purchase_order_b(db, tenant_b, supplier_b):
    from apps.scm.models import PurchaseOrder, PurchaseOrderLine
    po = PurchaseOrder.objects.create(
        tenant=tenant_b, vendor=supplier_b, order_date=datetime.date(2026, 1, 5), status="approved",
    )
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Globex widget", quantity=Decimal("5"), unit_price=Decimal("20.00"),
    )
    po.recalc_totals()
    return po


# ------------------------------------------------------------------ Goods Receipt Notes
@pytest.fixture
def goods_receipt_a(db, tenant_a, purchase_order_a):
    """A draft, fully-receiving GRN against purchase_order_a's single line."""
    from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
    line = purchase_order_a.lines.first()
    grn = GoodsReceiptNote.objects.create(
        tenant=tenant_a, purchase_order=purchase_order_a,
        receipt_date=datetime.date(2026, 1, 10), status="draft",
    )
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
    return grn


@pytest.fixture
def goods_receipt_b(db, tenant_b, purchase_order_b):
    from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine
    line = purchase_order_b.lines.first()
    grn = GoodsReceiptNote.objects.create(
        tenant=tenant_b, purchase_order=purchase_order_b,
        receipt_date=datetime.date(2026, 1, 10), status="draft",
    )
    GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)
    return grn


# ------------------------------------------------------------------ AP Bills (three-way match)
@pytest.fixture
def bill_a(db, tenant_a, supplier_a, usd):
    """A bill from purchase_order_a's own vendor, net value = $150.00 (matches the PO's line)."""
    from apps.accounting.models import Bill, BillLine
    bill = Bill.objects.create(
        tenant=tenant_a, party=supplier_a, bill_date=datetime.date(2026, 1, 12),
        status="approved", currency=usd,
    )
    BillLine.objects.create(
        bill=bill, description="Printer paper", quantity=Decimal("10"), unit_price=Decimal("15.00"),
    )
    bill.recalc_totals()
    return bill


@pytest.fixture
def bill_b(db, tenant_b, supplier_b, usd):
    from apps.accounting.models import Bill
    return Bill.objects.create(
        tenant=tenant_b, party=supplier_b, bill_date=datetime.date(2026, 1, 12),
        status="approved", currency=usd,
    )


# ------------------------------------------------------------------ SCM 4.2 Supplier Relationship Management
@pytest.fixture
def supplier_profile_a(db, tenant_a, supplier_a):
    """A draft SupplierProfile on supplier_a — the default onboarding entry point."""
    from apps.scm.models import SupplierProfile
    return SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a, onboarding_status="draft")


@pytest.fixture
def supplier_profile_b(db, tenant_b, supplier_b):
    from apps.scm.models import SupplierProfile
    return SupplierProfile.objects.create(tenant=tenant_b, party=supplier_b, onboarding_status="draft")


@pytest.fixture
def supplier_profile_dd_a(db, tenant_a, supplier_a):
    """A tenant_a SupplierProfile IN due_diligence review with the full DD checklist ticked —
    the one legal source state approve can act on."""
    from apps.scm.models import SupplierProfile
    return SupplierProfile.objects.create(
        tenant=tenant_a, party=supplier_a, onboarding_status="due_diligence",
        dd_financials_verified=True, dd_compliance_verified=True, dd_insurance_verified=True,
        dd_quality_cert_verified=True, dd_references_checked=True,
    )


@pytest.fixture
def scorecard_a(db, tenant_a, supplier_a):
    """A draft, unscored scorecard for supplier_a covering January 2026."""
    from apps.scm.models import SupplierScorecard
    return SupplierScorecard.objects.create(
        tenant=tenant_a, party=supplier_a,
        period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
    )


@pytest.fixture
def scorecard_b(db, tenant_b, supplier_b):
    from apps.scm.models import SupplierScorecard
    return SupplierScorecard.objects.create(
        tenant=tenant_b, party=supplier_b,
        period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
    )


@pytest.fixture
def contract_a(db, tenant_a, supplier_a):
    from apps.scm.models import SupplierContract
    return SupplierContract.objects.create(
        tenant=tenant_a, party=supplier_a, title="Master Supply Agreement", status="draft",
    )


@pytest.fixture
def contract_b(db, tenant_b, supplier_b):
    from apps.scm.models import SupplierContract
    return SupplierContract.objects.create(
        tenant=tenant_b, party=supplier_b, title="Globex Agreement", status="draft",
    )


@pytest.fixture
def catalog_a(db, tenant_a, supplier_a):
    from apps.scm.models import SupplierCatalog
    return SupplierCatalog.objects.create(tenant=tenant_a, party=supplier_a, name="2026 Price List")


@pytest.fixture
def catalog_b(db, tenant_b, supplier_b):
    from apps.scm.models import SupplierCatalog
    return SupplierCatalog.objects.create(tenant=tenant_b, party=supplier_b, name="Globex Price List")


@pytest.fixture
def risk_assessment_a(db, tenant_a, supplier_a):
    from apps.scm.models import SupplierRiskAssessment
    return SupplierRiskAssessment.objects.create(
        tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1),
    )


@pytest.fixture
def risk_assessment_b(db, tenant_b, supplier_b):
    from apps.scm.models import SupplierRiskAssessment
    return SupplierRiskAssessment.objects.create(
        tenant=tenant_b, party=supplier_b, assessment_date=datetime.date(2026, 1, 1),
    )


# ------------------------------------------------------------------ SCM 4.3 Inventory Management
@pytest.fixture
def uom_each_a(db, tenant_a):
    from apps.scm.models import UOM
    return UOM.objects.create(tenant=tenant_a, code="EA", name="Each")


@pytest.fixture
def uom_each_b(db, tenant_b):
    from apps.scm.models import UOM
    return UOM.objects.create(tenant=tenant_b, code="EA", name="Each")


@pytest.fixture
def category_a(db, tenant_a):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_a, name="Widgets")


@pytest.fixture
def category_b(db, tenant_b):
    from apps.scm.models import ItemCategory
    return ItemCategory.objects.create(tenant=tenant_b, name="Globex Widgets")


@pytest.fixture
def item_a(db, tenant_a, category_a, uom_each_a):
    """A weighted-average, untracked stock item, tenant_a. No stock posted yet."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_a, sku="WIDGET-1", name="Widget", category=category_a, uom=uom_each_a,
        item_type="stock", tracking="none", costing_method="weighted_avg",
        standard_cost=Decimal("8.00"), reorder_point=Decimal("10"),
    )


@pytest.fixture
def item_b(db, tenant_b, uom_each_b):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_b, sku="WIDGET-1", name="Globex Widget", uom=uom_each_b)


@pytest.fixture
def item_lot_a(db, tenant_a):
    """A lot-tracked stock item, tenant_a — for LotSerial tests and the lot/location guard regression."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="LOT-1", name="Lotted Widget", tracking="lot")


@pytest.fixture
def item_fifo_a(db, tenant_a):
    """A FIFO-costed stock item, tenant_a — for the FIFO-excludes-transfers valuation regression."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="FIFO-1", name="FIFO Widget", costing_method="fifo")


@pytest.fixture
def location_a(db, tenant_a):
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_a, code="WH1", name="Main Warehouse")


@pytest.fixture
def location_a2(db, tenant_a):
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_a, code="WH2", name="Overflow Warehouse")


@pytest.fixture
def location_b(db, tenant_b):
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_b, code="WH1", name="Globex Warehouse")


@pytest.fixture
def lot_a(db, tenant_a, item_lot_a):
    from apps.scm.models import LotSerial
    return LotSerial.objects.create(tenant=tenant_a, item=item_lot_a, kind="lot", number="LOT-0001")


@pytest.fixture
def lot_b(db, tenant_b, item_b):
    from apps.scm.models import LotSerial
    return LotSerial.objects.create(tenant=tenant_b, item=item_b, kind="lot", number="LOT-0001")


@pytest.fixture
def reorder_rule_a(db, tenant_a, item_a, location_a):
    from apps.scm.models import ReorderRule
    return ReorderRule.objects.create(
        tenant=tenant_a, item=item_a, location=location_a,
        reorder_point=Decimal("10"), safety_stock=Decimal("5"), reorder_quantity=Decimal("20"),
    )


@pytest.fixture
def reorder_rule_b(db, tenant_b, item_b, location_b):
    from apps.scm.models import ReorderRule
    return ReorderRule.objects.create(tenant=tenant_b, item=item_b, location=location_b)


@pytest.fixture
def stock_transfer_a(db, tenant_a, location_a, location_a2, item_a):
    """A draft transfer, tenant_a, one line moving 5 x item_a from WH1 to WH2."""
    from apps.scm.models import StockTransfer, StockTransferLine
    transfer = StockTransfer.objects.create(
        tenant=tenant_a, from_location=location_a, to_location=location_a2,
        transfer_date=datetime.date(2026, 1, 15),
    )
    StockTransferLine.objects.create(transfer=transfer, item=item_a, quantity=Decimal("5"))
    return transfer


@pytest.fixture
def stock_transfer_b(db, tenant_b, location_b, item_b):
    from apps.scm.models import Location, StockTransfer
    other = Location.objects.create(tenant=tenant_b, code="WH2", name="Globex Overflow")
    return StockTransfer.objects.create(
        tenant=tenant_b, from_location=location_b, to_location=other,
        transfer_date=datetime.date(2026, 1, 15),
    )


@pytest.fixture
def stock_adjustment_a(db, tenant_a, location_a, item_a):
    """A draft cycle-count adjustment, tenant_a, one line adding 10 x item_a at $8.00."""
    from apps.scm.models import StockAdjustment, StockAdjustmentLine
    adj = StockAdjustment.objects.create(
        tenant=tenant_a, location=location_a, reason="cycle_count",
        adjustment_date=datetime.date(2026, 1, 15),
    )
    StockAdjustmentLine.objects.create(
        adjustment=adj, item=item_a, quantity_delta=Decimal("10"), unit_cost=Decimal("8.00"),
    )
    return adj


@pytest.fixture
def stock_adjustment_b(db, tenant_b, location_b, item_b):
    from apps.scm.models import StockAdjustment
    return StockAdjustment.objects.create(
        tenant=tenant_b, location=location_b, reason="cycle_count",
        adjustment_date=datetime.date(2026, 1, 15),
    )


# ------------------------------------------------------------------ SCM 4.4 Warehouse Management
@pytest.fixture
def putawaytask_a(db, tenant_a, item_a, location_a, location_a2):
    """A pending putaway, tenant_a: 5 x item_a from staging (WH1) to bin (WH2). No stock posted
    yet — individual tests post the underlying receipt as needed."""
    from apps.scm.models import PutawayTask
    return PutawayTask.objects.create(
        tenant=tenant_a, item=item_a, from_location=location_a, to_location=location_a2,
        quantity=Decimal("5"),
    )


@pytest.fixture
def putawaytask_b(db, tenant_b, item_b, location_b):
    from apps.scm.models import Location, PutawayTask
    bin_b = Location.objects.create(tenant=tenant_b, code="BIN-B", name="Globex Bin")
    return PutawayTask.objects.create(
        tenant=tenant_b, item=item_b, from_location=location_b, to_location=bin_b,
        quantity=Decimal("5"),
    )


@pytest.fixture
def picktask_a(db, tenant_a, item_a, location_a):
    """A pending pick, tenant_a, one line requesting 5 x item_a from WH1 (nothing picked yet)."""
    from apps.scm.models import PickTask, PickTaskLine
    task = PickTask.objects.create(tenant=tenant_a)
    PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                quantity_requested=Decimal("5"))
    return task


@pytest.fixture
def picktask_b(db, tenant_b, item_b, location_b):
    from apps.scm.models import PickTask, PickTaskLine
    task = PickTask.objects.create(tenant=tenant_b)
    PickTaskLine.objects.create(pick_task=task, item=item_b, from_location=location_b,
                                quantity_requested=Decimal("5"))
    return task


@pytest.fixture
def cyclecounttask_a(db, tenant_a, location_a, item_a):
    """A scheduled count, tenant_a, location_a, one line on item_a (uncounted, unsnapshotted)."""
    from apps.scm.models import CycleCountTask, CycleCountTaskLine
    task = CycleCountTask.objects.create(tenant=tenant_a, location=location_a,
                                         scheduled_date=datetime.date(2026, 1, 20))
    CycleCountTaskLine.objects.create(cycle_count=task, item=item_a)
    return task


@pytest.fixture
def cyclecounttask_b(db, tenant_b, location_b, item_b):
    from apps.scm.models import CycleCountTask, CycleCountTaskLine
    task = CycleCountTask.objects.create(tenant=tenant_b, location=location_b,
                                         scheduled_date=datetime.date(2026, 1, 20))
    CycleCountTaskLine.objects.create(cycle_count=task, item=item_b)
    return task


@pytest.fixture
def yardvisit_a(db, tenant_a):
    from apps.scm.models import YardVisit
    return YardVisit.objects.create(tenant=tenant_a, carrier_name="Acme Haulage", direction="inbound")


@pytest.fixture
def yardvisit_b(db, tenant_b):
    from apps.scm.models import YardVisit
    return YardVisit.objects.create(tenant=tenant_b, carrier_name="Globex Haulage", direction="inbound")


# ------------------------------------------------------------------ SCM 4.5 Order Management System
@pytest.fixture
def customer_a(db, tenant_a):
    """A tenant_a Party tagged 'customer' — the 4.5 OMS sell-to party."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Retail Customer", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer", status="active",
                             start_date=datetime.date(2026, 1, 1))
    return party


@pytest.fixture
def customer_b(db, tenant_b):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Retail Customer", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="customer", status="active",
                             start_date=datetime.date(2026, 1, 1))
    return party


@pytest.fixture
def sales_order_a(db, tenant_a, customer_a, item_a):
    """A draft order, tenant_a, one line (10 x $15.00 = $150.00)."""
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                      order_date=datetime.date(2026, 1, 5))
    SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("10"),
                                  unit_price=Decimal("15.00"))
    order.recalc_totals()
    return order


@pytest.fixture
def sales_order_b(db, tenant_b, customer_b, item_b):
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(tenant=tenant_b, customer=customer_b,
                                      order_date=datetime.date(2026, 1, 5))
    SalesOrderLine.objects.create(sales_order=order, item=item_b, quantity_ordered=Decimal("5"),
                                  unit_price=Decimal("20.00"))
    order.recalc_totals()
    return order


@pytest.fixture
def sales_order_submitted_a(db, tenant_a, sales_order_a):
    """sales_order_a advanced straight to 'submitted' (bypassing the credit/fraud walk, which is
    exercised on its own in TestSalesOrderCreditFraudHold) — a ready base for allocation tests."""
    from django.utils import timezone
    sales_order_a.status = "submitted"
    sales_order_a.confirmation_sent_at = timezone.now()
    sales_order_a.save(update_fields=["status", "confirmation_sent_at", "updated_at"])
    return sales_order_a


@pytest.fixture
def sales_order_line_a(db, sales_order_submitted_a):
    return sales_order_submitted_a.lines.first()


@pytest.fixture
def sales_order_line_b(db, sales_order_b):
    return sales_order_b.lines.first()


@pytest.fixture
def allocation_a(db, tenant_a, sales_order_line_a, location_a):
    """A reserved allocation of 4 (of the 10 ordered) against sales_order_line_a at location_a."""
    from apps.scm.models import SalesOrderAllocation
    return SalesOrderAllocation.objects.create(
        tenant=tenant_a, sales_order_line=sales_order_line_a, location=location_a, quantity=Decimal("4"),
    )


@pytest.fixture
def allocation_b(db, tenant_b, sales_order_line_b, location_b):
    from apps.scm.models import SalesOrderAllocation
    return SalesOrderAllocation.objects.create(
        tenant=tenant_b, sales_order_line=sales_order_line_b, location=location_b, quantity=Decimal("2"),
    )


# ------------------------------------------------------------------ SCM 4.6 Transportation Management System
@pytest.fixture
def carrier_party_a(db, tenant_a):
    """A tenant_a Party tagged 'vendor' — a carrier is procured from like a supplier (4.6 TMS)."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Trucking Co", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="vendor")
    return party


@pytest.fixture
def carrier_party_b(db, tenant_b):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Freight Co", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="vendor")
    return party


@pytest.fixture
def carrier_a(db, tenant_a, carrier_party_a):
    """An active, truckload carrier, tenant_a, on carrier_party_a."""
    from apps.scm.models import Carrier
    return Carrier.objects.create(
        tenant=tenant_a, party=carrier_party_a, carrier_type="asset_based",
        primary_mode="truckload", service_level="standard", status="active",
    )


@pytest.fixture
def carrier_b(db, tenant_b, carrier_party_b):
    from apps.scm.models import Carrier
    return Carrier.objects.create(tenant=tenant_b, party=carrier_party_b)


@pytest.fixture
def load_a(db, tenant_a, carrier_a):
    """A planning-stage load, tenant_a, assigned to carrier_a."""
    from apps.scm.models import Load
    return Load.objects.create(
        tenant=tenant_a, carrier=carrier_a, origin_text="Chicago, IL", destination_text="Dallas, TX",
    )


@pytest.fixture
def load_b(db, tenant_b, carrier_b):
    from apps.scm.models import Load
    return Load.objects.create(
        tenant=tenant_b, carrier=carrier_b, origin_text="Metropolis", destination_text="Gotham",
    )


@pytest.fixture
def shipment_a(db, tenant_a, carrier_a):
    """A planned outbound shipment, tenant_a, executed by carrier_a."""
    from apps.scm.models import Shipment
    return Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, direction="outbound",
        origin_text="Chicago, IL", destination_text="Dallas, TX",
    )


@pytest.fixture
def shipment_b(db, tenant_b, carrier_b):
    from apps.scm.models import Shipment
    return Shipment.objects.create(tenant=tenant_b, carrier=carrier_b, direction="outbound")


@pytest.fixture
def freight_invoice_a(db, tenant_a, carrier_a):
    """A not-yet-audited freight invoice, tenant_a, from carrier_a (no lines yet)."""
    from apps.scm.models import FreightInvoice
    return FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)


@pytest.fixture
def freight_invoice_b(db, tenant_b, carrier_b):
    from apps.scm.models import FreightInvoice
    return FreightInvoice.objects.create(tenant=tenant_b, carrier=carrier_b)


# ------------------------------------------------------------------ SCM 4.7 Demand Planning & Forecasting
# Every horizon/window below is derived from ``timezone.localdate()`` — the SAME basis
# generate_periods / detect_order_surge / expire_stale_signals / calculate() read (lesson L16).
# Hard-coded 2026 dates would drift out of "covers today" the moment the clock passed them.
@pytest.fixture
def seasonality_profile_a(db, tenant_a, item_a):
    """An active, item-scoped MONTHLY seasonal curve on item_a: neutral all year, December x1.5."""
    from apps.scm.models import SeasonalityIndex, SeasonalityProfile
    profile = SeasonalityProfile.objects.create(
        tenant=tenant_a, name="Widget seasonality", profile_type="seasonal", bucket="month",
        scope="item", item=item_a,
    )
    for month in range(1, 13):
        SeasonalityIndex.objects.create(
            profile=profile, period_number=month,
            index_factor=Decimal("1.5000") if month == 12 else Decimal("1.0000"),
        )
    return profile


@pytest.fixture
def seasonality_profile_b(db, tenant_b, item_b):
    from apps.scm.models import SeasonalityProfile
    return SeasonalityProfile.objects.create(
        tenant=tenant_b, name="Globex seasonality", profile_type="seasonal", bucket="month",
        scope="item", item=item_b,
    )


@pytest.fixture
def promotion_profile_a(db, tenant_a, item_a):
    """A windowed promotion (+25 %) covering the CURRENT month — exercises WINDOWED_TYPES."""
    from django.utils import timezone
    from apps.scm.models import SeasonalityProfile
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return SeasonalityProfile.objects.create(
        tenant=tenant_a, name="Spring promo", profile_type="promotion", bucket="month",
        scope="item", item=item_a, event_start=start,
        event_end=add_months(start, 1) - datetime.timedelta(days=1),
        uplift_pct=Decimal("25.00"), promotion_mechanic="price_discount",
    )


@pytest.fixture
def category_profile_a(db, tenant_a, category_a):
    """A category-scoped seasonal profile with NO index rows yet — the derive action's input."""
    from apps.scm.models import SeasonalityProfile
    return SeasonalityProfile.objects.create(
        tenant=tenant_a, name="Widgets category curve", profile_type="seasonal", bucket="month",
        scope="category", category=category_a, derived_from_years=2,
    )


@pytest.fixture
def demand_history_a(db, tenant_a, customer_a, item_a):
    """12 consecutive monthly SUBMITTED sales orders of 100 x item_a, ending LAST month.

    The derived demand series every 4.7 consumer reads (there is no stored history table). Anchored
    on the current month so it always sits inside a default 24-month history window.
    """
    from django.utils import timezone
    from apps.scm.models import SalesOrder, SalesOrderLine
    from apps.scm.tests._helpers import add_months, month_start
    this_month = month_start(timezone.localdate())
    orders = []
    for back in range(12, 0, -1):
        order = SalesOrder.objects.create(
            tenant=tenant_a, customer=customer_a, order_date=add_months(this_month, -back),
            status="submitted",
        )
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("100"), unit_price=Decimal("15.00"))
        order.recalc_totals()
        orders.append(order)
    return orders


@pytest.fixture
def demand_forecast_a(db, tenant_a, item_a):
    """A DRAFT monthly forecast on item_a covering THIS month + the next two (3 periods)."""
    from django.utils import timezone
    from apps.scm.models import DemandForecast
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return DemandForecast.objects.create(
        tenant=tenant_a, name="Widget Q plan", item=item_a, bucket="month",
        horizon_start=start, horizon_end=add_months(start, 3) - datetime.timedelta(days=1),
        method="moving_average", method_parameter=Decimal("3"),
    )


@pytest.fixture
def demand_forecast_b(db, tenant_b, item_b):
    from django.utils import timezone
    from apps.scm.models import DemandForecast
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return DemandForecast.objects.create(
        tenant=tenant_b, name="Globex plan", item=item_b, bucket="month",
        horizon_start=start, horizon_end=add_months(start, 3) - datetime.timedelta(days=1),
    )


def _seed_baselines(forecast, baseline=Decimal("100")):
    """Give a generated grid a non-zero, flat baseline.

    ``generate_periods`` legitimately produces zeros when the item has no order history, and every
    pro-rata/consensus assertion needs a base to move. Written straight onto the period rows (not
    through a form) because ``baseline_quantity`` is the statistical output.
    """
    for row in forecast.periods.all():
        row.baseline_quantity = baseline
        row.final_quantity = baseline
        row.save(update_fields=["baseline_quantity", "final_quantity"])
    return forecast


@pytest.fixture
def forecast_with_periods_a(db, demand_forecast_a):
    """demand_forecast_a with its 3-period grid generated (status -> statistical), baselines 100."""
    demand_forecast_a.generate_periods()
    return _seed_baselines(demand_forecast_a)


@pytest.fixture
def forecast_with_periods_b(db, demand_forecast_b):
    demand_forecast_b.generate_periods()
    return _seed_baselines(demand_forecast_b)


@pytest.fixture
def forecast_period_a(db, forecast_with_periods_a):
    """The first bucket of forecast_with_periods_a's horizon (the current month)."""
    return forecast_with_periods_a.periods.first()


@pytest.fixture
def approved_forecast_a(db, forecast_with_periods_a):
    """forecast_with_periods_a promoted to the plan of record — what detect_order_surge reads."""
    forecast_with_periods_a.status = "approved"
    forecast_with_periods_a.save(update_fields=["status", "updated_at"])
    return forecast_with_periods_a


@pytest.fixture
def demand_signal_a(db, tenant_a, item_a):
    """A NEW order-surge signal on item_a worth +30 units across the current month."""
    from django.utils import timezone
    from apps.scm.models import DemandSignal
    from apps.scm.tests._helpers import add_months, month_start
    start = month_start(timezone.localdate())
    return DemandSignal.objects.create(
        tenant=tenant_a, signal_type="order_surge", source="internal_orders", item=item_a,
        observed_at=timezone.now(), effective_from=start,
        effective_to=add_months(start, 1) - datetime.timedelta(days=1),
        impact_direction="increase", impact_pct=Decimal("30.00"),
        impact_quantity=Decimal("30.0000"),
    )


@pytest.fixture
def demand_signal_b(db, tenant_b, item_b):
    from django.utils import timezone
    from apps.scm.models import DemandSignal
    return DemandSignal.objects.create(
        tenant=tenant_b, signal_type="order_surge", source="manual", item=item_b,
        observed_at=timezone.now(), impact_quantity=Decimal("10.0000"),
    )


@pytest.fixture
def forecast_adjustment_a(db, tenant_a, forecast_with_periods_a, forecast_period_a, admin_user):
    """A PROPOSED 'absolute 140' override from Sales on the forecast's first period."""
    from apps.scm.models import ForecastAdjustment
    return ForecastAdjustment.objects.create(
        tenant=tenant_a, forecast=forecast_with_periods_a, period=forecast_period_a,
        contributor_function="sales", submitted_by=admin_user, adjustment_type="absolute",
        proposed_quantity=Decimal("140"), reason_code="promotion",
        rationale="Spring campaign lands in this period.",
    )


@pytest.fixture
def forecast_adjustment_b(db, tenant_b, forecast_with_periods_b):
    from apps.scm.models import ForecastAdjustment
    return ForecastAdjustment.objects.create(
        tenant=tenant_b, forecast=forecast_with_periods_b, adjustment_type="delta",
        proposed_quantity=Decimal("10"), rationale="Globex proposal.",
    )


@pytest.fixture
def reorder_rule_service_level_a(db, tenant_a, item_a, location_a2):
    """A tenant_a rule on the SERVICE-LEVEL safety-stock policy — the calculator's main branch.

    Sited at WH2 so it can co-exist with ``reorder_rule_a`` (same item, WH1) — the pair shares an
    item deliberately, since ``demand_series`` ignores location for the ``sales_orders`` source.
    """
    from apps.scm.models import ReorderRule
    return ReorderRule.objects.create(
        tenant=tenant_a, item=item_a, location=location_a2,
        reorder_point=Decimal("10"), safety_stock=Decimal("5"), reorder_quantity=Decimal("20"),
        safety_stock_method="service_level", service_level_pct=Decimal("95"),
        lead_time_days=10, lead_time_variability_days=Decimal("2"),
    )


# ------------------------------------------------------------------ SCM 4.8 Manufacturing
# The costing fixtures below are deliberately EXACT so the unabsorbed-pool arithmetic can be
# asserted to the last quantum:
#
#   BOM-A  makes 1 x item_a from  2 x BOLT-1 (@ 2.0000)  +  1 x PLATE-1 (@ 5.0000)
#   WO     plans 5 x item_a  ->  10 x BOLT (20.00)  +  5 x PLATE (25.00)   = 45.0000 material
#   logs   2 machine hours @ 10.0000  +  1 labour hour @ 20.0000           = 40.0000 conversion
#                                                                    pool  = 85.0000
#
# A 3-then-2 split therefore posts 3 x 28.3333 = 84.9999 and then 2 x 0.0000, i.e. never more than
# the 85.0000 actually incurred. The formula this replaced banked 3 x (85/3) + 2 x (85/5) = 119.00,
# 140 % of real cost — see WorkOrder.computed_unit_cost's docstring.
@pytest.fixture
def employee_party_a(db, tenant_a):
    """A tenant_a Party holding the 'employee' role — the only kind a work-centre supervisor or a
    time-log operator may be (``_employee_parties``)."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Dana Operator", kind="person")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="employee")
    return party


@pytest.fixture
def work_center_a(db, tenant_a, location_a):
    """An active machining cell, tenant_a — 8 h/day at 100 %, 10.00 machine + 20.00 labour."""
    from apps.scm.models import WorkCenter
    return WorkCenter.objects.create(
        tenant=tenant_a, code="WC-CNC", name="CNC Cell", center_type="machine",
        location=location_a, capacity_hours_per_day=Decimal("8"), efficiency_pct=Decimal("100"),
        machine_cost_per_hour=Decimal("10.0000"), labor_cost_per_hour=Decimal("20.0000"),
    )


@pytest.fixture
def work_center_a2(db, tenant_a):
    """A SECOND tenant_a centre — proves the load board and the list filters separate them."""
    from apps.scm.models import WorkCenter
    return WorkCenter.objects.create(
        tenant=tenant_a, code="WC-ASM", name="Assembly Bench", center_type="assembly",
        capacity_hours_per_day=Decimal("8"), efficiency_pct=Decimal("100"),
    )


@pytest.fixture
def work_center_b(db, tenant_b):
    from apps.scm.models import WorkCenter
    return WorkCenter.objects.create(tenant=tenant_b, code="WC-GBX", name="Globex Cell")


@pytest.fixture
def component_bolt_a(db, tenant_a, uom_each_a):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="BOLT-1", name="Bolt", uom=uom_each_a,
                               standard_cost=Decimal("2.0000"))


@pytest.fixture
def component_plate_a(db, tenant_a, uom_each_a):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_a, sku="PLATE-1", name="Steel Plate", uom=uom_each_a,
                               standard_cost=Decimal("5.0000"))


@pytest.fixture
def bom_a(db, tenant_a, item_a, component_bolt_a, component_plate_a, work_center_a, uom_each_a):
    """The ACTIVE default recipe for item_a: 2 bolts + 1 plate per unit, both manually issued."""
    from apps.scm.models import BillOfMaterials, BOMLine
    bom = BillOfMaterials.objects.create(
        tenant=tenant_a, item=item_a, name="Widget recipe", version="1", bom_type="manufacture",
        output_quantity=Decimal("1"), uom=uom_each_a, lead_time_days=3,
        default_work_center=work_center_a, status="active", is_default=True,
    )
    BOMLine.objects.create(bom=bom, sequence=10, component=component_bolt_a,
                           quantity_per=Decimal("2"), uom=uom_each_a)
    BOMLine.objects.create(bom=bom, sequence=20, component=component_plate_a,
                           quantity_per=Decimal("1"), uom=uom_each_a)
    return bom


@pytest.fixture
def bom_draft_a(db, tenant_a, item_lot_a, component_bolt_a):
    """A DRAFT single-line recipe on a different item — the editable/deletable one."""
    from apps.scm.models import BillOfMaterials, BOMLine
    bom = BillOfMaterials.objects.create(
        tenant=tenant_a, item=item_lot_a, name="Lotted widget recipe", version="1",
        output_quantity=Decimal("1"), status="draft",
    )
    BOMLine.objects.create(bom=bom, component=component_bolt_a, quantity_per=Decimal("1"))
    return bom


@pytest.fixture
def bom_b(db, tenant_b, item_b):
    from apps.scm.models import BillOfMaterials, BOMLine
    bom = BillOfMaterials.objects.create(
        tenant=tenant_b, item=item_b, name="Globex recipe", version="1", status="active",
    )
    BOMLine.objects.create(bom=bom, component=item_b, quantity_per=Decimal("1"))
    return bom


@pytest.fixture
def work_order_a(db, tenant_a, item_a, bom_a, work_center_a, location_a, location_a2, uom_each_a):
    """A DRAFT run for 5 x item_a with no components exploded yet — the create/edit fixture."""
    from apps.scm.models import WorkOrder
    return WorkOrder.objects.create(
        tenant=tenant_a, item=item_a, uom=uom_each_a, bom=bom_a,
        quantity_planned=Decimal("5"), work_center=work_center_a,
        component_location=location_a, output_location=location_a2, priority="normal",
    )


@pytest.fixture
def work_order_b(db, tenant_b, item_b, work_center_b, location_b):
    from apps.scm.models import WorkOrder
    return WorkOrder.objects.create(
        tenant=tenant_b, item=item_b, quantity_planned=Decimal("5"),
        work_center=work_center_b, component_location=location_b, output_location=location_b,
    )


@pytest.fixture
def stocked_work_order_a(db, work_order_a, component_bolt_a, component_plate_a, location_a):
    """work_order_a with its BOM exploded onto components AND the material physically on hand.

    Still DRAFT — the tests drive release / issue / report through the real POST routes so the
    guards and the ``select_for_update`` re-read are exercised, not bypassed.
    """
    from apps.scm.tests._helpers import seed_stock
    work_order_a.explode_components()
    seed_stock(work_order_a.tenant, component_bolt_a, location_a, "100", "2.0000")
    seed_stock(work_order_a.tenant, component_plate_a, location_a, "100", "5.0000")
    return work_order_a


@pytest.fixture
def released_work_order_a(db, stocked_work_order_a, admin_user):
    """stocked_work_order_a moved to RELEASED — the state the postings legally act from."""
    stocked_work_order_a.status = "released"
    stocked_work_order_a.released_by = admin_user
    stocked_work_order_a.save(update_fields=["status", "released_by", "updated_at"])
    return stocked_work_order_a


@pytest.fixture
def time_log_a(db, tenant_a, released_work_order_a, work_center_a, employee_party_a):
    """One booked MACHINE hour against the live run (60 minutes, derived — never typed)."""
    from django.utils import timezone
    from apps.scm.models import ProductionTimeLog
    started = timezone.now() - datetime.timedelta(hours=2)
    return ProductionTimeLog.objects.create(
        tenant=tenant_a, work_order=released_work_order_a, work_center=work_center_a,
        entry_type="machine", operator=employee_party_a, operation="Mill",
        started_at=started, ended_at=started + datetime.timedelta(hours=1),
    )


@pytest.fixture
def time_log_b(db, tenant_b, work_order_b, work_center_b):
    from django.utils import timezone
    from apps.scm.models import ProductionTimeLog
    started = timezone.now() - datetime.timedelta(hours=2)
    return ProductionTimeLog.objects.create(
        tenant=tenant_b, work_order=work_order_b, work_center=work_center_b,
        entry_type="labor", started_at=started, ended_at=started + datetime.timedelta(hours=1),
    )


# ------------------------------------------------------------------ SCM 4.9 Quality Management
# Every reference date below is derived from ``timezone.localdate()`` — the SAME basis
# ``qualityaudit_start``, ``capaaction_implement``, ``NonConformance.is_overdue`` and
# ``InspectionPlan.is_effective`` use (lesson L16). A literal ``datetime.date.today()`` here would
# flake for the hours around local midnight on a USE_TZ=True project.
#
# The two plans are deliberately different shapes because the CoA rules need both:
#
#   inspection_plan_a  incoming_receipt / item_a (untracked)  3 characteristics, NONE on the CoA
#                      -> measurement + visual + instruction, i.e. one row of each verdict rule
#   outgoing_plan_a    outgoing_shipment / item_lot_a (LOT-tracked)  2 characteristics, BOTH on
#                      the CoA -> the only shape that can ever reach `coa_ready`
@pytest.fixture
def inspection_plan_a(db, tenant_a, item_a, uom_each_a):
    """An active incoming-receipt plan for item_a with one characteristic of each judged type.

    The ``instruction`` row is load-bearing: ``generate_results()`` must stamp it
    ``not_applicable`` at creation, or a plan full of instructions would block ``complete`` on rows
    nobody can ever answer.
    """
    from apps.scm.models import InspectionCharacteristic, InspectionPlan
    plan = InspectionPlan.objects.create(
        tenant=tenant_a, code="IQC-W1", name="Widget incoming check", version="1",
        plan_type="incoming_receipt", item=item_a, sampling_method="all_100", frequency="every",
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=10, name="Length", characteristic_type="measurement", uom=uom_each_a,
        target_value=Decimal("100"), lower_limit=Decimal("95"), upper_limit=Decimal("105"),
        test_method="Vernier caliper", is_mandatory=True,
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=20, name="Visual check", characteristic_type="visual",
        expected_text="No scratches", is_mandatory=False,
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=30, name="Photograph the label", characteristic_type="instruction",
        is_mandatory=True,
    )
    return plan


@pytest.fixture
def outgoing_plan_a(db, tenant_a, item_lot_a, uom_each_a):
    """An active outgoing-shipment plan for the LOT-tracked item — both rows print on the CoA."""
    from apps.scm.models import InspectionCharacteristic, InspectionPlan
    plan = InspectionPlan.objects.create(
        tenant=tenant_a, code="OQC-L1", name="Lotted widget release", version="1",
        plan_type="outgoing_shipment", item=item_lot_a, sampling_method="fixed_count",
        sample_size=2, frequency="every",
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=10, name="Purity", characteristic_type="measurement", uom=uom_each_a,
        target_value=Decimal("99.5"), lower_limit=Decimal("99.0"), upper_limit=Decimal("100.0"),
        test_method="HPLC", is_critical=True, is_mandatory=True, include_on_coa=True,
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=20, name="Appearance", characteristic_type="pass_fail",
        expected_text="Clear, colourless", is_mandatory=True, include_on_coa=True,
    )
    return plan


@pytest.fixture
def audit_checklist_plan_a(db, tenant_a):
    """An UNSCOPED audit checklist — the only plan_type a QualityAudit may point at."""
    from apps.scm.models import InspectionCharacteristic, InspectionPlan
    plan = InspectionPlan.objects.create(
        tenant=tenant_a, code="AUD-ISO9K", name="ISO 9001 process audit", version="1",
        plan_type="audit_checklist",
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=10, name="Are training records current?",
        characteristic_type="pass_fail", is_mandatory=True)
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=20, name="Is the calibration log complete?",
        characteristic_type="visual", is_mandatory=True)
    return plan


@pytest.fixture
def inspection_plan_b(db, tenant_b, item_b):
    from apps.scm.models import InspectionCharacteristic, InspectionPlan
    plan = InspectionPlan.objects.create(
        tenant=tenant_b, code="IQC-W1", name="Globex incoming check", version="1",
        plan_type="incoming_receipt", item=item_b,
    )
    InspectionCharacteristic.objects.create(
        plan=plan, sequence=10, name="Globex length", characteristic_type="measurement",
        target_value=Decimal("10"))
    return plan


@pytest.fixture
def quality_inspection_a(db, tenant_a, item_a, location_a, supplier_a, employee_party_a,
                        inspection_plan_a):
    """A DRAFT incoming inspection with NO result rows yet — the generate_results() fixture."""
    from django.utils import timezone
    from apps.scm.models import QualityInspection
    return QualityInspection.objects.create(
        tenant=tenant_a, plan=inspection_plan_a, inspection_type="incoming", item=item_a,
        location=location_a, supplier=supplier_a, inspector=employee_party_a,
        quantity_inspected=Decimal("10"), sample_size=Decimal("10"),
        quantity_accepted=Decimal("10"), inspected_on=timezone.localdate(),
    )


@pytest.fixture
def quality_inspection_b(db, tenant_b, item_b, location_b, inspection_plan_b):
    from django.utils import timezone
    from apps.scm.models import QualityInspection
    return QualityInspection.objects.create(
        tenant=tenant_b, plan=inspection_plan_b, inspection_type="incoming", item=item_b,
        location=location_b, quantity_inspected=Decimal("5"), inspected_on=timezone.localdate(),
    )


def _fill_results(inspection, *, measurement="99.6", verdict="pass"):
    """Answer every generated result row so the lot reaches a real verdict.

    ``InspectionResult.save()`` is the ONE writer of ``result`` — a measurement is re-derived from
    the snapshotted limits whatever is posted, a pass/fail keeps the inspector's verdict.
    """
    for row in inspection.results.all():
        if row.characteristic_type == "measurement":
            row.measured_value = Decimal(measurement)
        else:
            row.text_value = "Clear, colourless"
            row.result = verdict
        row.save()
    inspection.__dict__.pop("_result_cache", None)


@pytest.fixture
def outgoing_inspection_a(db, tenant_a, item_lot_a, lot_a, location_a, shipment_a,
                          employee_party_a, outgoing_plan_a):
    """A CoA-READY outgoing inspection: passed, accepted, both CoA rows answered, lot named.

    This is the ONE fixture every ``coa_blockers()`` test starts from — each test breaks exactly
    one of the seven rules on it and proves that rule alone refuses the certificate.
    """
    from django.utils import timezone
    from apps.scm.models import QualityInspection
    inspection = QualityInspection.objects.create(
        tenant=tenant_a, plan=outgoing_plan_a, inspection_type="outgoing", item=item_lot_a,
        lot_serial=lot_a, location=location_a, shipment=shipment_a, inspector=employee_party_a,
        quantity_inspected=Decimal("10"), sample_size=Decimal("2"),
        quantity_accepted=Decimal("10"), inspected_on=timezone.localdate(),
    )
    inspection.generate_results()
    _fill_results(inspection)
    inspection.status = "passed"
    inspection.usage_decision = "accept"
    inspection.save(update_fields=["status", "usage_decision", "updated_at"])
    inspection.__dict__.pop("_result_cache", None)
    return inspection


@pytest.fixture
def nonconformance_a(db, tenant_a, item_a, location_a, supplier_a, employee_party_a, uom_each_a):
    """An OPEN report against 5 units of the untracked item, sitting at location_a.

    No stock is seeded — the scrap tests call ``seed_stock`` themselves so the shortfall guard and
    the happy path are both reachable from the same fixture.
    """
    from django.utils import timezone
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_a, source="internal", item=item_a, location=location_a, uom=uom_each_a,
        supplier=supplier_a, quantity_affected=Decimal("5"), defect_category="dimensional",
        severity="major", title="Widgets out of tolerance",
        description="Five units measured outside the length band.",
        detected_by=employee_party_a, detected_on=timezone.localdate(),
        cost_of_quality=Decimal("40.00"),
    )


@pytest.fixture
def nonconformance_lot_a(db, tenant_a, item_lot_a, lot_a, location_a, employee_party_a):
    """An OPEN report against a LOT — the quarantine / release fixture (posts NO StockMove)."""
    from django.utils import timezone
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_a, source="production", item=item_lot_a, lot_serial=lot_a,
        location=location_a, quantity_affected=Decimal("4"), defect_category="contamination",
        severity="critical", title="Batch contamination suspected",
        description="Visible particulate in the batch.", detected_by=employee_party_a,
        detected_on=timezone.localdate(),
    )


@pytest.fixture
def nonconformance_b(db, tenant_b, item_b, location_b):
    from django.utils import timezone
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_b, source="internal", item=item_b, location=location_b,
        quantity_affected=Decimal("2"), title="Globex defect",
        description="Globex description.", detected_on=timezone.localdate(),
    )


@pytest.fixture
def capa_action_a(db, tenant_a, item_a, employee_party_a):
    """An OPEN corrective action with one OPEN task — the implement-guard fixture."""
    from django.utils import timezone
    from apps.scm.models import CapaAction, CapaTask
    capa = CapaAction.objects.create(
        tenant=tenant_a, action_type="corrective", source="internal_improvement",
        title="Tighten the length gauge procedure", item=item_a,
        problem_statement="Length drifts out of band on the second shift.",
        owner=employee_party_a, priority="high",
        due_date=timezone.localdate() + datetime.timedelta(days=14),
        effectiveness_due_date=timezone.localdate() + datetime.timedelta(days=45),
    )
    CapaTask.objects.create(capa=capa, sequence=10, description="Re-calibrate the gauge",
                            owner=employee_party_a,
                            due_date=timezone.localdate() + datetime.timedelta(days=7))
    return capa


@pytest.fixture
def capa_in_progress_a(db, capa_action_a):
    """capa_action_a moved to IN PROGRESS with a root cause recorded — one open task remains."""
    capa_action_a.status = "in_progress"
    capa_action_a.root_cause = "The gauge was never re-zeroed after the shift change."
    capa_action_a.save(update_fields=["status", "root_cause", "updated_at"])
    return capa_action_a


@pytest.fixture
def capa_action_b(db, tenant_b):
    from apps.scm.models import CapaAction
    return CapaAction.objects.create(
        tenant=tenant_b, title="Globex corrective action",
        problem_statement="Globex problem statement.")


@pytest.fixture
def quality_audit_a(db, tenant_a, org_unit_a, employee_party_a, audit_checklist_plan_a):
    """A PLANNED internal audit against the checklist plan."""
    from django.utils import timezone
    from apps.scm.models import QualityAudit
    return QualityAudit.objects.create(
        tenant=tenant_a, audit_type="internal", title="Q1 internal process audit",
        standard="ISO 9001:2015", scope="Goods-in and inspection",
        auditee_org_unit=org_unit_a, checklist_plan=audit_checklist_plan_a,
        lead_auditor=employee_party_a, planned_date=timezone.localdate(), risk_level="medium",
    )


@pytest.fixture
def reported_audit_a(db, quality_audit_a):
    """quality_audit_a run and REPORTED — the close-guard fixture (add a finding to block it)."""
    from django.utils import timezone
    quality_audit_a.status = "reported"
    quality_audit_a.actual_start = timezone.localdate() - datetime.timedelta(days=1)
    quality_audit_a.actual_end = timezone.localdate()
    quality_audit_a.conclusion = "Two minor findings; the process is otherwise conforming."
    quality_audit_a.save(update_fields=["status", "actual_start", "actual_end", "conclusion",
                                        "updated_at"])
    return quality_audit_a


@pytest.fixture
def quality_audit_b(db, tenant_b):
    from django.utils import timezone
    from apps.scm.models import QualityAudit
    return QualityAudit.objects.create(
        tenant=tenant_b, audit_type="internal", title="Globex audit",
        planned_date=timezone.localdate())


# ------------------------------------------------------------------ SCM 4.10 Returns Management
# Every reference date below is derived from ``timezone.localdate()`` — the SAME basis
# ``evaluate_return_eligibility``, ``ReturnAuthorization.is_overdue_shipment``,
# ``ReturnDisposition.save()`` and ``WarrantyClaim.is_in_warranty`` read (lesson L16). A literal
# ``datetime.date.today()`` here would flake for the hours around local midnight on USE_TZ=True.
#
# The money is deliberately EXACT so the credit-note arithmetic can be asserted to the penny:
#
#   returns_sales_order_a   10 x item_a @ 15.00, tax 20 %              (ordered TODAY)
#   return_authorization_a   3 x item_a @ 15.00, tax 20 %, cost 8.0000
#                            -> subtotal 45.00, tax 9.00, fee 0.00, credit 54.00
#   return_policy_a          grade ladder 100 / 75 / 40 / 0 %, no restocking fee
#
# ``unit_price`` (15.00) and ``unit_cost`` (8.0000) are deliberately DIFFERENT so a restock posted
# at the sale price is detectable — that is the one cost trap the whole bench is built around.
@pytest.fixture
def return_reason_a(db, tenant_a):
    """An ordinary customer-fault reason that permits a restock."""
    from apps.scm.models import ReturnReason
    return ReturnReason.objects.create(
        tenant=tenant_a, code="WRONG-SIZE", name="Wrong size ordered", fault_party="customer",
        allows_refund=True, allows_store_credit=True, allows_exchange=True,
        suggested_disposition="restock", sort_order=10,
    )


@pytest.fixture
def return_reason_blocking_a(db, tenant_a):
    """A reason whose unit can NEVER go back into sellable stock — the blocks_restock gate."""
    from apps.scm.models import ReturnReason
    return ReturnReason.objects.create(
        tenant=tenant_a, code="CONTAM", name="Contaminated", fault_party="supplier",
        allows_refund=True, allows_store_credit=False, allows_exchange=False,
        waives_return_fee=True, blocks_restock=True, raises_nonconformance=True,
        suggested_disposition="scrap", sort_order=20,
    )


@pytest.fixture
def return_reason_photo_a(db, tenant_a):
    """A reason that REQUIRES a photo on the line before approval."""
    from apps.scm.models import ReturnReason
    return ReturnReason.objects.create(
        tenant=tenant_a, code="DAMAGED", name="Arrived damaged", fault_party="carrier",
        allows_refund=True, requires_photo=True, sort_order=30,
    )


@pytest.fixture
def return_reason_b(db, tenant_b):
    from apps.scm.models import ReturnReason
    return ReturnReason.objects.create(
        tenant=tenant_b, code="WRONG-SIZE", name="Globex wrong size", allows_refund=True,
    )


@pytest.fixture
def return_policy_a(db, tenant_a):
    """The tenant_a catch-all promise: 30-day window, full refund, no fee, real grade ladder."""
    from apps.scm.models import ReturnPolicy
    return ReturnPolicy.objects.create(
        tenant=tenant_a, name="Standard 30-day", is_active=True, is_default=True, priority=100,
        window_basis="delivery", window_days=30, fallback_days=45,
        allow_refund=True, allow_store_credit=True, allow_exchange=True, allow_keep_item=False,
        refund_basis="full", restocking_fee_type="none", return_shipping_paid_by="customer",
        grade_a_cost_pct=Decimal("100"), grade_b_cost_pct=Decimal("75"),
        grade_c_cost_pct=Decimal("40"), grade_d_cost_pct=Decimal("0"),
        warranty_window_days=365, return_to_address="Acme Returns, Unit 4, Springfield",
        portal_instructions="Pack it in the original box.",
    )


@pytest.fixture
def return_policy_fee_a(db, tenant_a, category_a):
    """A category-specific policy charging a FLAT 10.00 restocking fee — beats the default."""
    from apps.scm.models import ReturnPolicy
    return ReturnPolicy.objects.create(
        tenant=tenant_a, name="Widgets 14-day", is_active=True, priority=10,
        item_category=category_a, window_basis="order_date", window_days=14, fallback_days=14,
        refund_basis="full", restocking_fee_type="flat", restocking_fee_value=Decimal("10.00"),
        auto_approve=True,
    )


@pytest.fixture
def return_policy_b(db, tenant_b):
    from apps.scm.models import ReturnPolicy
    return ReturnPolicy.objects.create(tenant=tenant_b, name="Globex 30-day", is_default=True)


@pytest.fixture
def returns_sales_order_a(db, tenant_a, customer_a, item_a, usd):
    """A SUBMITTED order dated TODAY — so a return raised against it sits inside every window.

    ``sales_order_a`` is anchored on a fixed 2026-01-05 for the 4.5 tests; a return dated from it
    would fall outside a 30/45-day policy window and every approval assertion would then be
    measuring the override path instead of the happy one.
    """
    from django.utils import timezone
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(
        tenant=tenant_a, customer=customer_a, order_date=timezone.localdate(), currency=usd,
        status="submitted",
    )
    SalesOrderLine.objects.create(
        sales_order=order, item=item_a, description="Widget", quantity_ordered=Decimal("10"),
        unit_price=Decimal("15.00"), tax_pct=Decimal("20.00"),
    )
    order.recalc_totals()
    return order


def _build_draft_rma(tenant, customer, sales_order, policy, reason, item, currency):
    """Create a DRAFT physical RMA: 3 x item @ 15.00 (20 % tax, 8.0000 cost), no fee.

    A plain function rather than a fixture so ``return_authorization_a`` and
    ``rma_awaiting_receipt_a`` can each own a SEPARATE row. Chaining them — the latter taking the
    former and mutating it in place — made pytest's per-test fixture cache hand BOTH names the same
    ReturnAuthorization, so a test asking for a draft return AND an authorised one silently got one
    row in the later state. That is not a state any real workspace can be in, and it quietly
    disarmed every "this forbidden POST left the draft alone" assertion in test_security.py.
    """
    from django.utils import timezone
    from apps.scm.models import ReturnAuthorization, ReturnLine
    rma = ReturnAuthorization.objects.create(
        tenant=tenant, customer=customer, sales_order=sales_order,
        return_type="physical", source="csr", policy=policy,
        requested_on=timezone.localdate(), resolution="refund",
        refund_method="original_tender", return_method="mail_prepaid", currency=currency,
    )
    ReturnLine.objects.create(
        return_authorization=rma, sales_order_line=sales_order.lines.first(),
        item=item, description="Widget", quantity_requested=Decimal("3"),
        reason=reason, unit_price=Decimal("15.00"), tax_pct=Decimal("20.00"),
        unit_cost=Decimal("8.0000"),
    )
    return rma


@pytest.fixture
def return_authorization_a(db, tenant_a, customer_a, returns_sales_order_a, return_policy_a,
                           return_reason_a, item_a, usd):
    """A DRAFT physical RMA: 3 x item_a @ 15.00 (20 % tax, 8.0000 cost), no fee."""
    return _build_draft_rma(tenant_a, customer_a, returns_sales_order_a, return_policy_a,
                            return_reason_a, item_a, usd)


@pytest.fixture
def rma_awaiting_receipt_a(db, tenant_a, customer_a, returns_sales_order_a, return_policy_a,
                           return_reason_a, item_a, usd):
    """A SECOND, INDEPENDENT authorised RMA: every line approved in full, awaiting_receipt.

    Deliberately NOT built on ``return_authorization_a``: a test that asks for both wants a draft
    return AND an authorised one, and mutating the draft in place handed it the same row twice.

    Written straight onto the row rather than through ``returnauthorization_approve`` so the bench
    tests start from a known state; the approve action itself is driven through its real POST route
    in its own test class.
    """
    from django.utils import timezone
    rma = _build_draft_rma(tenant_a, customer_a, returns_sales_order_a, return_policy_a,
                           return_reason_a, item_a, usd)
    for line in rma.lines.all():
        line.quantity_approved = line.quantity_requested
        line.save(update_fields=["quantity_approved"])
    rma.status = "awaiting_receipt"
    rma.approved_on = timezone.localdate()
    rma.save(update_fields=["status", "approved_on", "updated_at"])
    return rma


@pytest.fixture
def return_line_a(db, rma_awaiting_receipt_a):
    """The single approved line of rma_awaiting_receipt_a (3 approved of 3 requested)."""
    return rma_awaiting_receipt_a.lines.first()


@pytest.fixture
def disposition_a(db, tenant_a, return_line_a, location_a):
    """A ``received_pending`` bench row: 3 units on the WH1 bench at grade A, cost 8.0000.

    Nothing is posted — the bench is deliberately off-ledger (see the ReturnDisposition module
    docstring), which is exactly what the intake tests assert.
    """
    from django.utils import timezone
    from apps.scm.models import ReturnDisposition
    return ReturnDisposition.objects.create(
        tenant=tenant_a, return_line=return_line_a, quantity=Decimal("3"),
        received_on=timezone.localdate(), location=location_a, condition_grade="a",
        disposition="received_pending", restock_unit_cost=Decimal("8.0000"),
    )


@pytest.fixture
def rma_received_a(db, disposition_a, rma_awaiting_receipt_a):
    """rma_awaiting_receipt_a with its goods physically on the bench (status ``received``)."""
    rma_awaiting_receipt_a.status = "received"
    rma_awaiting_receipt_a.save(update_fields=["status", "updated_at"])
    return rma_awaiting_receipt_a


@pytest.fixture
def rma_credit_only_a(db, tenant_a, customer_a, return_policy_a, return_reason_a, item_a, usd):
    """A SETTLED credit-only RMA — 2 x 25.00, no tax, and NO bench row, ever.

    §7.11's trap made a fixture: this record never produces a ``ReturnDisposition``, so any queue
    keyed on "has received goods" drops it silently.
    """
    from django.utils import timezone
    from apps.scm.models import ReturnAuthorization, ReturnLine
    rma = ReturnAuthorization.objects.create(
        tenant=tenant_a, customer=customer_a, return_type="credit_only", source="csr",
        policy=return_policy_a, requested_on=timezone.localdate(), resolution="refund",
        refund_method="original_tender", return_method="keep_item", currency=usd,
    )
    ReturnLine.objects.create(
        return_authorization=rma, item=item_a, description="Widget kept by the customer",
        quantity_requested=Decimal("2"), quantity_approved=Decimal("2"), reason=return_reason_a,
        unit_price=Decimal("25.00"), unit_cost=Decimal("8.0000"),
    )
    rma.status = "settled"
    rma.approved_on = timezone.localdate()
    rma.save(update_fields=["status", "approved_on", "updated_at"])
    return rma


@pytest.fixture
def rma_advance_refund_a(db, tenant_a, customer_a, return_policy_a, return_reason_a, item_a, usd):
    """An advance-refunded RMA whose deadline has PASSED and whose goods never shipped."""
    from django.utils import timezone
    from apps.scm.models import ReturnAuthorization, ReturnLine
    rma = ReturnAuthorization.objects.create(
        tenant=tenant_a, customer=customer_a, return_type="physical", source="portal",
        policy=return_policy_a, requested_on=timezone.localdate() - datetime.timedelta(days=40),
        resolution="refund", return_method="mail_prepaid", currency=usd,
        advance_refund=True,
        advance_refund_deadline=timezone.localdate() - datetime.timedelta(days=5),
    )
    ReturnLine.objects.create(
        return_authorization=rma, item=item_a, quantity_requested=Decimal("1"),
        quantity_approved=Decimal("1"), reason=return_reason_a, unit_price=Decimal("30.00"),
        unit_cost=Decimal("8.0000"),
    )
    rma.status = "awaiting_receipt"
    rma.approved_on = timezone.localdate() - datetime.timedelta(days=39)
    rma.save(update_fields=["status", "approved_on", "updated_at"])
    return rma


@pytest.fixture
def return_authorization_b(db, tenant_b, customer_b, return_policy_b, return_reason_b, item_b):
    """The tenant_b RMA every cross-tenant IDOR assertion points at."""
    from django.utils import timezone
    from apps.scm.models import ReturnAuthorization, ReturnLine
    rma = ReturnAuthorization.objects.create(
        tenant=tenant_b, customer=customer_b, return_type="physical", policy=return_policy_b,
        requested_on=timezone.localdate(), resolution="refund",
    )
    ReturnLine.objects.create(
        return_authorization=rma, item=item_b, quantity_requested=Decimal("2"),
        quantity_approved=Decimal("2"), reason=return_reason_b, unit_price=Decimal("20.00"),
    )
    rma.status = "awaiting_receipt"
    rma.approved_on = timezone.localdate()
    rma.save(update_fields=["status", "approved_on", "updated_at"])
    return rma


@pytest.fixture
def return_line_b(db, return_authorization_b):
    return return_authorization_b.lines.first()


@pytest.fixture
def disposition_b(db, tenant_b, return_line_b, location_b):
    from django.utils import timezone
    from apps.scm.models import ReturnDisposition
    return ReturnDisposition.objects.create(
        tenant=tenant_b, return_line=return_line_b, quantity=Decimal("2"),
        received_on=timezone.localdate(), location=location_b, condition_grade="a",
        disposition="received_pending",
    )


@pytest.fixture
def warranty_claim_a(db, tenant_a, supplier_a, item_a, return_policy_a):
    """A DRAFT claim on supplier_a: 1 unit, one 100.00 part cost line, inside its warranty."""
    from django.utils import timezone
    from apps.scm.models import WarrantyClaim, WarrantyClaimCost
    claim = WarrantyClaim.objects.create(
        tenant=tenant_a, supplier=supplier_a, item=item_a, quantity_claimed=Decimal("1"),
        purchase_date=timezone.localdate() - datetime.timedelta(days=10),
        failure_date=timezone.localdate(), defect_classification="manufacturing",
        submission_channel="email", description="Gear sheared under normal load.",
        response_due_on=timezone.localdate() + datetime.timedelta(days=30),
    )
    WarrantyClaimCost.objects.create(
        claim=claim, cost_type="part", description="Replacement gear", quantity=Decimal("1"),
        unit_amount=Decimal("100.00"),
    )
    return claim


@pytest.fixture
def warranty_claim_submitted_a(db, warranty_claim_a):
    """warranty_claim_a sent to the supplier — the record-response fixture."""
    from django.utils import timezone
    warranty_claim_a.status = "submitted"
    warranty_claim_a.submitted_on = timezone.localdate()
    warranty_claim_a.save(update_fields=["status", "submitted_on", "updated_at"])
    return warranty_claim_a


@pytest.fixture
def warranty_claim_approved_a(db, warranty_claim_submitted_a):
    """The supplier accepted 80.00 of the 100.00 claimed — the record-credit fixture."""
    from django.utils import timezone
    claim = warranty_claim_submitted_a
    claim.status = "partially_approved"
    claim.amount_approved = Decimal("80.00")
    claim.responded_on = timezone.localdate()
    claim.save(update_fields=["status", "amount_approved", "responded_on", "updated_at"])
    return claim


@pytest.fixture
def warranty_claim_b(db, tenant_b, supplier_b, item_b):
    from apps.scm.models import WarrantyClaim, WarrantyClaimCost
    claim = WarrantyClaim.objects.create(
        tenant=tenant_b, supplier=supplier_b, item=item_b, quantity_claimed=Decimal("1"),
    )
    WarrantyClaimCost.objects.create(claim=claim, cost_type="part", description="Globex part",
                                     quantity=Decimal("1"), unit_amount=Decimal("50.00"))
    return claim


# --- the CRM portal binding the customer-facing request form is built on ------------------------
@pytest.fixture
def portal_user_a(db, tenant_a):
    from apps.accounts.models import User
    return User.objects.create_user(
        email="shopper@acme.com", username="shopper_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )


@pytest.fixture
def portal_access_a(db, tenant_a, customer_a, portal_user_a):
    """An ACTIVE ``crm.CustomerPortalAccess`` binding portal_user_a to customer_a."""
    from apps.crm.models import CustomerPortalAccess
    return CustomerPortalAccess.objects.create(
        tenant=tenant_a, customer_party=customer_a, portal_user=portal_user_a, is_active=True,
    )


@pytest.fixture
def portal_client_a(db, portal_access_a, portal_user_a):
    from django.test import Client
    c = Client()
    c.force_login(portal_user_a)
    return c


# ------------------------------------------------------------------ SCM 4.11 Supply Chain Analytics
# EVERY window below is derived from ``timezone.localdate()`` / ``timezone.now()`` — the SAME basis
# ``analytics.range_bounds``, ``period_windows`` and every resolver read (lesson L16). The five report
# pages open on ``last_90`` and a ``KpiTarget`` defaults to ``last_30``, so a literal 2026 date would
# drift out of both windows the moment the clock passed it and every tile would quietly go blank.
#
# The three 4.11 tables are: KpiTarget (the ONE row a human authors), KpiSnapshot (system-written by
# ``capture_snapshots``) and SupplyChainAlert (system-written by ``detect_alerts``, plus a hand-raise
# form). ``analytics_history_a`` below is the 4.1-4.10 SIGNAL the resolvers read — nothing in 4.11
# stores a measurement of its own.
def _days_ago(days):
    """A date ``days`` before today, on the tz-aware basis the resolvers window against."""
    from django.utils import timezone
    return timezone.localdate() - datetime.timedelta(days=days)


def _moments_ago(days):
    """A tz-aware datetime ``days`` before now — for the DateTimeField windows (moved_at, event_at)."""
    from django.utils import timezone
    return timezone.now() - datetime.timedelta(days=days)


@pytest.fixture
def kpi_target_a(db, tenant_a):
    """A NETWORK-scope turnover target with both bands set and alerting OFF.

    ``inv_turnover`` is ``higher_is_better`` in the registry, so ``clean()`` requires the bands to
    run target >= warning >= critical (6 >= 4 >= 2).
    """
    from apps.scm.models import KpiTarget
    return KpiTarget.objects.create(
        tenant=tenant_a, metric="inv_turnover", name="Turnover goal", scope="all",
        period_grain="month", date_range="last_90",
        target_value=Decimal("6.00"), warning_threshold=Decimal("4.00"),
        critical_threshold=Decimal("2.00"),
    )


@pytest.fixture
def kpi_target_b(db, tenant_b):
    """The tenant_b target every cross-tenant IDOR assertion points at."""
    from apps.scm.models import KpiTarget
    return KpiTarget.objects.create(
        tenant=tenant_b, metric="inv_turnover", name="Globex turnover goal", scope="all",
        date_range="last_90", target_value=Decimal("6.00"), warning_threshold=Decimal("4.00"),
    )


@pytest.fixture
def alerting_target_a(db, tenant_a):
    """An OTD target with an impact FLOOR and thresholds a 0 % on-time reading crosses.

    This is the fixture behind the "``_impact_of`` returns None, not ZERO" regression:
    ``_r_otd_pct`` emits no money figure at all, so a ``min_impact_value`` floor must NOT be able to
    mute it. ``otd_pct`` is higher_is_better, so the bands run 98 >= 95 >= 90 and a 0 % reading has
    crossed the critical one.
    """
    from apps.scm.models import KpiTarget
    return KpiTarget.objects.create(
        tenant=tenant_a, metric="otd_pct", name="Carrier on-time delivery", scope="all",
        period_grain="month", date_range="last_90",
        target_value=Decimal("98.00"), warning_threshold=Decimal("95.00"),
        critical_threshold=Decimal("90.00"),
        is_alerting=True, min_impact_value=Decimal("1.00"), severity="warning",
    )


@pytest.fixture
def late_shipment_a(db, tenant_a, carrier_a):
    """One shipment DELIVERED LATE inside the last-90 window — the OTD breach the alert tests use.

    ``status`` / ``actual_delivery_at`` / ``actual_pickup_at`` are ``editable=False`` (4.6 moves them
    through its own actions), so they are written straight onto the row here: the point of this
    fixture is the analytics READING, and 4.6's own transitions have their own tests.
    """
    from apps.scm.models import Shipment
    ship = Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, direction="outbound",
        origin_text="Chicago, IL", destination_text="Dallas, TX",
        planned_delivery_date=_days_ago(20), carrier_tracking_number="TRK-LATE-1",
        weight_kg=Decimal("1000.00"), volume_cbm=Decimal("4.000"), package_count=10,
    )
    ship.status = "delivered"
    ship.actual_pickup_at = _moments_ago(13)
    ship.actual_delivery_at = _moments_ago(10)
    ship.save(update_fields=["status", "actual_pickup_at", "actual_delivery_at", "updated_at"])
    return ship


@pytest.fixture
def kpi_snapshot_a(db, tenant_a, kpi_target_a):
    """One frozen point for kpi_target_a — the roll-up dimension (``dimension_key=""``)."""
    from apps.scm.models import KpiSnapshot
    return KpiSnapshot.objects.create(
        tenant=tenant_a, kpi_target=kpi_target_a, metric=kpi_target_a.metric,
        period_start=_days_ago(30), period_end=_days_ago(1),
        value=Decimal("3.5000"), target_value_at_time=Decimal("6.00"), status_band="warning",
        breakdown={"cost_issued": 100.0, "rows": [{"sku": "WIDGET-1", "cost_issued": 100.0}]},
    )


@pytest.fixture
def kpi_snapshot_b(db, tenant_b, kpi_target_b):
    from apps.scm.models import KpiSnapshot
    return KpiSnapshot.objects.create(
        tenant=tenant_b, kpi_target=kpi_target_b, metric=kpi_target_b.metric,
        period_start=_days_ago(30), period_end=_days_ago(1),
        value=Decimal("2.0000"), status_band="critical",
    )


@pytest.fixture
def alert_a(db, tenant_a, item_a):
    """An OPEN, detector-shaped exception for tenant_a — the triage fixture."""
    from apps.scm.models import SupplyChainAlert
    return SupplyChainAlert.objects.create(
        tenant=tenant_a, alert_type="dead_stock", title="Dead stock: WIDGET-1",
        severity="warning", item=item_a, impact_value=Decimal("800.00"),
        dimension_key=f"item:{item_a.pk}", dimension_label="Widget",
        dedupe_key=f"dead_stock:item:{item_a.pk}",
    )


@pytest.fixture
def alert_b(db, tenant_b, item_b):
    from apps.scm.models import SupplyChainAlert
    return SupplyChainAlert.objects.create(
        tenant=tenant_b, alert_type="dead_stock", title="Globex dead stock",
        severity="warning", item=item_b, impact_value=Decimal("100.00"),
        dedupe_key=f"dead_stock:item:{item_b.pk}",
    )


@pytest.fixture
def analytics_history_a(db, tenant_a, usd, supplier_a, vendor_a, customer_a, carrier_a,
                        item_a, category_a, location_a, location_a2, rfq_sent_a, quote_a,
                        employee_party_a):
    """The 4.1-4.10 SIGNAL every 4.11 resolver reads, on ONE tenant, inside the last-90 window.

    4.11 stores no measurement of its own — a report page with nothing behind it renders its empty
    state, which is correct and is tested separately. This fixture is what lets the supporting TABLES
    on the five pages have real rows, which is the only way the row-key contract (the resolver's keys
    vs the template's) can be asserted at all: a status-code assertion cannot tell a populated table
    from a grid of em-dashes.

    Returns a dict of the rows other tests need to point at.
    """
    from django.utils import timezone
    from apps.scm.models import (CapaAction, FreightInvoice, FreightInvoiceLine, GoodsReceiptLine,
                                 GoodsReceiptNote, Load, NonConformance, PurchaseOrder,
                                 PurchaseOrderLine, ReorderRule, RFQQuote, RFQQuoteLine,
                                 SalesOrder, SalesOrderAllocation, SalesOrderLine, Shipment,
                                 SupplierContract, SupplierRiskAssessment, SupplierScorecard,
                                 TrackingEvent, YardVisit)
    from apps.scm.tests._helpers import seed_stock
    from apps.scm.views._helpers import _post_stock_move

    today = timezone.localdate()

    # --- 4.1 procurement: two suppliers, one on time and clean, one late and rejecting -----------
    po_on_time = PurchaseOrder.objects.create(
        tenant=tenant_a, vendor=supplier_a, currency=usd, order_date=_days_ago(45),
        expected_date=_days_ago(35), status="received")
    po_on_time.acknowledged_at = _moments_ago(44)
    po_on_time.save(update_fields=["acknowledged_at", "updated_at"])
    PurchaseOrderLine.objects.create(
        purchase_order=po_on_time, item_description="Printer paper", sku_hint=item_a.sku,
        quantity=Decimal("10"), unit_price=Decimal("15.00"))
    po_on_time.recalc_totals()

    po_late = PurchaseOrder.objects.create(
        tenant=tenant_a, vendor=vendor_a, currency=usd, order_date=_days_ago(40),
        expected_date=_days_ago(30), status="received")
    PurchaseOrderLine.objects.create(
        purchase_order=po_late, item_description="Printer paper", sku_hint=item_a.sku,
        quantity=Decimal("10"), unit_price=Decimal("18.00"))
    po_late.recalc_totals()

    grn_on_time = GoodsReceiptNote.objects.create(
        tenant=tenant_a, purchase_order=po_on_time, receipt_date=_days_ago(36), status="received")
    GoodsReceiptLine.objects.create(
        goods_receipt=grn_on_time, po_line=po_on_time.lines.first(),
        quantity_received=Decimal("10"), quantity_rejected=Decimal("0"))
    grn_late = GoodsReceiptNote.objects.create(
        tenant=tenant_a, purchase_order=po_late, receipt_date=_days_ago(20), status="received")
    GoodsReceiptLine.objects.create(
        goods_receipt=grn_late, po_line=po_late.lines.first(),
        quantity_received=Decimal("8"), quantity_rejected=Decimal("2"))

    # A SECOND quote on the seeded RFQ, so `savings_negotiated` has a competing price to take the
    # median of — an award with no competition is skipped rather than scored as zero savings.
    rival = RFQQuote.objects.create(tenant=tenant_a, rfq=rfq_sent_a, party=vendor_a,
                                    status="received")
    RFQQuoteLine.objects.create(quote=rival, rfq_line=rfq_sent_a.lines.first(),
                                quantity=Decimal("10"), unit_price=Decimal("18.00"))
    rival.recalc_totals()
    po_awarded = PurchaseOrder.objects.create(
        tenant=tenant_a, vendor=supplier_a, currency=usd, order_date=_days_ago(25),
        expected_date=_days_ago(10), status="approved", quote=quote_a)
    PurchaseOrderLine.objects.create(
        purchase_order=po_awarded, item_description="Printer paper", sku_hint=item_a.sku,
        quantity=Decimal("5"), unit_price=Decimal("12.00"))
    po_awarded.recalc_totals()

    # --- 4.2 supplier relationship: contract cover, a published scorecard, a risk assessment -----
    contract = SupplierContract.objects.create(
        tenant=tenant_a, party=supplier_a, title="Master Supply Agreement", status="active",
        start_date=_days_ago(200), end_date=today + datetime.timedelta(days=30))
    scorecard = SupplierScorecard.objects.create(
        tenant=tenant_a, party=supplier_a, period_start=_days_ago(60), period_end=_days_ago(10),
        status="published", delivery_score=Decimal("90.00"), quality_score=Decimal("95.00"),
        price_score=Decimal("80.00"), responsiveness_score=Decimal("85.00"))
    scorecard.recompute_overall()
    assessment = SupplierRiskAssessment.objects.create(
        tenant=tenant_a, party=supplier_a, assessment_date=_days_ago(15), status="submitted",
        financial_score=3, geopolitical_score=2, compliance_score=3, operational_score=4)
    assessment.recompute_risk_level()

    # --- 4.3 inventory: real on-hand, real issues, one dead line ---------------------------------
    seed_stock(tenant_a, item_a, location_a, "200", "8.0000")
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-40"),
                     move_type="issue", unit_cost=Decimal("8.0000"), reference="SO-00001",
                     moved_at=_moments_ago(45))
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-30"),
                     move_type="issue", unit_cost=Decimal("8.0000"), reference="SO-00002",
                     moved_at=_moments_ago(3))
    # A returned-to-stock receipt, so the NETTED demand series has something to net.
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                     move_type="receipt", unit_cost=Decimal("8.0000"), reference="RMA-00001",
                     moved_at=_moments_ago(2))
    # A quality write-off — a NEGATIVE 'adjustment' carrying the NCR number, which is the ONLY thing
    # that lets `scrap_value` split the loss by what caused it.
    _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-2"),
                     move_type="adjustment", unit_cost=Decimal("8.0000"), reference="NCR-00001",
                     moved_at=_moments_ago(18))

    rule = ReorderRule.objects.create(
        tenant=tenant_a, item=item_a, location=location_a2, reorder_point=Decimal("50"),
        safety_stock=Decimal("10"), reorder_quantity=Decimal("100"), lead_time_days=14)
    # avg_daily_demand is editable=False and written only by 4.7's calculate — set here so the
    # projected-stockout resolver has a runway to measure (a rule without one is REPORTED as
    # unmeasurable, which is its own regression test).
    rule.avg_daily_demand = Decimal("5.0000")
    rule.save(update_fields=["avg_daily_demand"])

    # --- 4.5/4.6 order + transport: one on-time delivery, one late, one silent in flight ---------
    order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, currency=usd,
                                      order_date=_days_ago(30), status="submitted")
    line = SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                         quantity_ordered=Decimal("10"),
                                         unit_price=Decimal("25.00"))
    order.recalc_totals()
    SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line,
                                        location=location_a, quantity=Decimal("6"))

    load = Load.objects.create(
        tenant=tenant_a, carrier=carrier_a, origin_text="Chicago, IL",
        destination_text="Dallas, TX", distance_km=Decimal("1500.00"),
        planned_departure=_moments_ago(34), planned_arrival=_moments_ago(31),
        equipment_capacity_weight_kg=Decimal("20000.00"),
        equipment_capacity_volume_cbm=Decimal("80.000"))
    on_time = Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, load=load, sales_order=order, direction="outbound",
        origin_text="Chicago, IL", destination_text="Dallas, TX",
        planned_delivery_date=_days_ago(30), weight_kg=Decimal("8000.00"),
        volume_cbm=Decimal("30.000"), package_count=40, carrier_tracking_number="TRK-1")
    on_time.status = "delivered"
    on_time.actual_pickup_at = _moments_ago(34)
    on_time.actual_delivery_at = _moments_ago(31)
    on_time.save(update_fields=["status", "actual_pickup_at", "actual_delivery_at", "updated_at"])
    TrackingEvent.objects.create(shipment=on_time, event_type="delivered",
                                 event_at=_moments_ago(31), location_text="Dallas, TX")

    in_flight = Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, direction="outbound", origin_text="Chicago, IL",
        destination_text="Denver, CO", planned_delivery_date=_days_ago(2),
        carrier_tracking_number="TRK-SILENT")
    in_flight.status = "in_transit"
    in_flight.eta = _moments_ago(-3)
    in_flight.save(update_fields=["status", "eta", "updated_at"])

    invoice = FreightInvoice.objects.create(
        tenant=tenant_a, carrier=carrier_a, shipment=on_time, load=load, currency=usd,
        carrier_invoice_number="CI-001", invoice_date=_days_ago(28))
    FreightInvoiceLine.objects.create(freight_invoice=invoice, charge_type="linehaul",
                                      description="Linehaul", billed_amount=Decimal("2200.00"),
                                      contract_amount=Decimal("2000.00"))
    invoice.recalc_amounts()
    invoice.match_status = "price_variance"
    invoice.save(update_fields=["match_status", "updated_at"])

    yard = YardVisit.objects.create(tenant=tenant_a, carrier_name=carrier_a.party.name,
                                    direction="inbound", dock_door=location_a, status="departed")
    yard.arrived_at = _moments_ago(20)
    yard.docked_at = _moments_ago(20) + datetime.timedelta(hours=1)
    yard.departed_at = _moments_ago(20) + datetime.timedelta(hours=4)
    yard.save(update_fields=["arrived_at", "docked_at", "departed_at", "updated_at"])

    # --- 4.9 quality: one nonconformance and one open corrective action against a supplier -------
    ncr = NonConformance.objects.create(
        tenant=tenant_a, source="goods_receipt", item=item_a, location=location_a, supplier=vendor_a,
        quantity_affected=Decimal("2"), defect_category="dimensional", severity="major",
        title="Two units out of tolerance", description="Rejected at goods-in.",
        detected_by=employee_party_a, detected_on=_days_ago(19),
        cost_of_quality=Decimal("40.00"))
    capa = CapaAction.objects.create(
        tenant=tenant_a, action_type="corrective", source="supplier",
        title="Supplier to re-qualify the gauge", supplier=vendor_a,
        problem_statement="Two units rejected at goods-in.", owner=employee_party_a,
        due_date=today + datetime.timedelta(days=10))

    # 4.6 STORES the carrier's on-time percentage; 4.11 trends that column and never restates it, so
    # the carrier scorecard table is empty until the stored figure exists.
    carrier_a.recompute_scorecard()

    return {
        "po_on_time": po_on_time, "po_late": po_late, "po_awarded": po_awarded,
        "grn_on_time": grn_on_time, "grn_late": grn_late, "rival_quote": rival,
        "contract": contract, "scorecard": scorecard, "assessment": assessment,
        "rule": rule, "sales_order": order, "sales_order_line": line, "load": load,
        "shipment_on_time": on_time, "shipment_in_flight": in_flight, "freight_invoice": invoice,
        "yard_visit": yard, "nonconformance": ncr, "capa": capa,
    }


@pytest.fixture
def dead_stock_item_a(db, tenant_a, category_a, uom_each_a, location_a):
    """A tenant_a item received 120 days ago and NEVER issued — the inventory page's two aged tables.

    ``analytics_history_a`` deliberately keeps ``item_a`` moving (its newest issue is three days
    old), so both the dead-stock table and the FIFO age table are legitimately EMPTY on it and the
    row-key contract there cannot be asserted at all: an empty table and a table of em-dashes render
    identically. One dormant layer fills both — dead (nothing outbound inside the 90-day tail) and
    aged (a remaining FIFO layer 120 days old, i.e. the ``91-180`` bucket).
    """
    from apps.scm.models import Item
    from apps.scm.views._helpers import _post_stock_move
    item = Item.objects.create(
        tenant=tenant_a, sku="DORMANT-1", name="Dormant Widget", category=category_a,
        uom=uom_each_a, item_type="stock", tracking="none", costing_method="weighted_avg",
        standard_cost=Decimal("12.00"),
    )
    _post_stock_move(tenant_a, item=item, location=location_a, quantity=Decimal("20"),
                     move_type="receipt", unit_cost=Decimal("12.0000"),
                     reference="OPENING", moved_at=_moments_ago(120))
    return item


@pytest.fixture
def snoozed_alert_a(db, alert_a):
    """``alert_a`` with a LIVE suppression window — the state the no-op guards are asserted against.

    ``status`` / ``snoozed_until`` are ``editable=False`` and move only through ``snooze()``, so the
    model's own method is what puts the row here rather than a hand write.
    """
    alert_a.snooze(14)
    return alert_a


@pytest.fixture
def resolved_alert_a(db, alert_a, admin_user):
    """A CLOSED alert carrying its original resolver and note — the re-resolve no-op fixture."""
    alert_a.resolve(admin_user, "Wrote the stock off against the quarantine bin.")
    return alert_a


# ------------------------------------------------------------------ SCM 4.12 Contract & Compliance
# Four registers, one report. Every date below is derived from ``timezone.localdate()`` — the SAME
# basis ``TradeLicense.days_to_expiry``, ``ComplianceRequirement.refresh_status`` and the carbon
# report's window all read (lesson L16). A literal 2026 date would drift out of the renewal window
# and out of the report's default last-365-days window the moment the clock passed it.
#
# Nothing here TYPES a workflow status the app moves through a verb: ``TradeLicense.status`` and
# ``TradeDocument.status`` are both ``editable=False``, so the licence fixtures walk
# draft -> applied -> active exactly as ``tradelicense_submit`` / ``tradelicense_approve`` do, and a
# document is issued through the same ``can_charge()`` gate ``tradedocument_issue`` uses. A hand-set
# status would let a test assert a state the product cannot actually reach.
def _compliance_date(days):
    """A date ``days`` from today on the tz-aware basis every 4.12 date reader uses."""
    from django.utils import timezone
    return timezone.localdate() + datetime.timedelta(days=days)


@pytest.fixture
def org_unit_b(db, tenant_b):
    """The tenant_b org unit the ``scope="org_unit"`` isolation assertions point at.

    4.1 shipped ``org_unit_a`` alone because nothing before 4.12 pointed an FK at an org unit from a
    screen a crafted POST could reach; the obligation register does, so the foreign row it has to
    fail against has to exist.
    """
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, name="Globex Operations", kind="department")


@pytest.fixture
def evidence_document_a(db, tenant_a):
    """A tenant_a ``core.Document`` — 4.12 attaches evidence through the generic attachment, never
    a FileField of its own (Module 13 owns file storage)."""
    from apps.core.models import Document
    return Document.objects.create(tenant=tenant_a, name="COI 2026.pdf", file="documents/coi.pdf")


@pytest.fixture
def evidence_document_b(db, tenant_b):
    """The tenant_b attachment every cross-tenant evidence assertion points at."""
    from apps.core.models import Document
    return Document.objects.create(tenant=tenant_b, name="Globex COI.pdf",
                                   file="documents/globex.pdf")


@pytest.fixture
def trade_license_a(db, tenant_a, usd, supplier_a):
    """An IN-FORCE export licence capped in BOTH dimensions — 10 000.00 value, 500.0000 units.

    Driven through the real application ladder (draft -> applied -> active) rather than created at
    ``status="active"``: the column is ``editable=False`` and only the verbs move it, so a hand-set
    value would be a state no button in the product can produce.
    """
    from apps.scm.models import TradeLicense
    lic = TradeLicense.objects.create(
        tenant=tenant_a, license_number="BIS-2026-000111",
        title="Export licence - workstation hardware", license_type="export_license",
        issuing_authority="US Bureau of Industry and Security", issuing_country="United States",
        holder_party=supplier_a, application_date=_compliance_date(-120),
        issue_date=_compliance_date(-110), expiry_date=_compliance_date(300),
        renewal_notice_days=60, authorized_value=Decimal("10000.00"),
        authorized_quantity=Decimal("500.0000"), currency=usd,
        commodity_scope="Laptop workstations and monitors.",
        eccn_or_hs="EAR99 / HS 8471.30", destination_countries="Canada",
    )
    lic.status = "applied"
    lic.save(update_fields=["status", "updated_at"])
    lic.status = "active"
    lic.save(update_fields=["status", "updated_at"])
    lic.refresh_status()
    return lic


@pytest.fixture
def uncapped_license_a(db, tenant_a):
    """An in-force licence with NO ceiling in either dimension.

    ``authorized_value`` / ``authorized_quantity`` are nullable and that nullability carries meaning:
    unlimited, not exhausted. This is the fixture behind every "``remaining_*`` and
    ``utilization_pct`` answer ``None``, never ``0``" assertion.
    """
    from apps.scm.models import TradeLicense
    lic = TradeLicense.objects.create(
        tenant=tenant_a, license_number="GEN-AUTH-000222", title="General authorization - spares",
        license_type="general_authorization", issuing_authority="US Customs and Border Protection",
        issue_date=_compliance_date(-30), expiry_date=_compliance_date(400),
    )
    lic.status = "active"
    lic.save(update_fields=["status", "updated_at"])
    return lic


@pytest.fixture
def expiring_license_a(db, tenant_a):
    """An in-force licence 21 days from lapsing against a 60-day notice window — amber."""
    from apps.scm.models import TradeLicense
    lic = TradeLicense.objects.create(
        tenant=tenant_a, license_number="CBP-IMP-000333", title="Import permit - lithium cells",
        license_type="import_permit", issuing_authority="US Customs and Border Protection",
        # Shares ``issuing_country`` with ``trade_license_a`` deliberately: the list's country
        # dropdown is built with DISTINCT over a values_list, and DISTINCT over a queryset carrying
        # an unrelated ORDER BY column returns duplicates — two rows on one country is what proves
        # the explicit ``order_by`` on that dropdown is doing its job.
        issuing_country="United States",
        application_date=_compliance_date(-400), issue_date=_compliance_date(-390),
        expiry_date=_compliance_date(21), renewal_notice_days=60,
        authorized_quantity=Decimal("10000.0000"),
    )
    lic.status = "active"
    lic.save(update_fields=["status", "updated_at"])
    lic.refresh_status()
    return lic


@pytest.fixture
def draft_license_a(db, tenant_a):
    """A licence still at ``draft`` — the submit/approve ladder's starting point, and the one state
    ``can_charge()`` refuses on the status alone."""
    from apps.scm.models import TradeLicense
    return TradeLicense.objects.create(
        tenant=tenant_a, license_number="DRAFT-000444", title="Draft export licence",
        issuing_authority="BIS", expiry_date=_compliance_date(200),
    )


@pytest.fixture
def trade_license_b(db, tenant_b):
    """The tenant_b licence every cross-tenant IDOR assertion points at."""
    from apps.scm.models import TradeLicense
    lic = TradeLicense.objects.create(
        tenant=tenant_b, license_number="GLOBEX-LIC-1", title="Globex export licence",
        issuing_authority="Globex Authority", expiry_date=_compliance_date(300),
        authorized_value=Decimal("5000.00"),
    )
    lic.status = "active"
    lic.save(update_fields=["status", "updated_at"])
    return lic


@pytest.fixture
def trade_document_a(db, tenant_a, usd, customer_a, shipment_a, trade_license_a, item_a,
                     uom_each_a):
    """A DRAFT commercial invoice charged to ``trade_license_a``, with TWO declared lines.

    The two lines are the whole point: ``declared_value`` is 1 200.00 and the lines multiply out to
    the same 1 200.00 (200 + 1 000), so a ``recompute_usage()`` that summed both grains in ONE
    aggregate would fan the document row out per line and charge the licence 2 400.00 — twice its
    face value, silently. The line quantities total 7.0000.
    """
    from apps.scm.models import TradeDocument, TradeDocumentLine
    doc = TradeDocument.objects.create(
        tenant=tenant_a, doc_type="commercial_invoice", direction="export",
        document_number="INV-EXP-0001", issue_date=_compliance_date(-2), shipment=shipment_a,
        license=trade_license_a, consignee_party=customer_a, country_of_origin="United States",
        country_of_destination="Canada", currency=usd, declared_value=Decimal("1200.00"),
        incoterm="DAP", gross_weight_kg=Decimal("900.00"), net_weight_kg=Decimal("850.00"),
        package_count=12, port_of_loading="Chicago, IL", port_of_discharge="Toronto, ON",
    )
    TradeDocumentLine.objects.create(
        document=doc, item=item_a, description="Laptop workstation", hs_code="8471.30",
        country_of_origin="United States", uom_text="each", uom=uom_each_a,
        quantity=Decimal("2.0000"), unit_value=Decimal("100.00"))
    TradeDocumentLine.objects.create(
        document=doc, description="Monitor, 27-inch", hs_code="8528.52",
        country_of_origin="United States", uom_text="each",
        quantity=Decimal("5.0000"), unit_value=Decimal("200.00"))
    return doc


@pytest.fixture
def issued_document_a(db, trade_document_a, trade_license_a, admin_user):
    """``trade_document_a`` put through the issue verb's own arithmetic — refused, never clamped.

    ``status`` is ``editable=False`` and only ``tradedocument_issue`` moves it, so this mirrors that
    route exactly: ``can_charge()`` first, then the stamps, then ``recompute_usage()`` on the licence
    (re-derived from the documents, never incremented).
    """
    from django.db.models import Sum
    from django.utils import timezone
    from apps.scm.models._base import q2, q4
    value = q2(trade_document_a.declared_value)
    quantity = q4(trade_document_a.lines.aggregate(total=Sum("quantity"))["total"])
    allowed, reason = trade_license_a.can_charge(value, quantity)
    assert allowed, reason
    trade_document_a.status = "issued"
    trade_document_a.issued_at = timezone.now()
    trade_document_a.issued_by = admin_user
    trade_document_a.save(update_fields=["status", "issued_at", "issued_by", "updated_at"])
    trade_license_a.recompute_usage()
    return trade_document_a


@pytest.fixture
def trade_document_b(db, tenant_b, trade_license_b, supplier_b):
    """The tenant_b document every cross-tenant IDOR assertion points at."""
    from apps.scm.models import TradeDocument, TradeDocumentLine
    doc = TradeDocument.objects.create(
        tenant=tenant_b, doc_type="customs_declaration", direction="import",
        document_number="GLOBEX-ENT-1", license=trade_license_b, shipper_party=supplier_b,
        declared_value=Decimal("500.00"))
    TradeDocumentLine.objects.create(document=doc, description="Globex widget",
                                     quantity=Decimal("1.0000"), unit_value=Decimal("500.00"))
    return doc


@pytest.fixture
def compliance_requirement_a(db, tenant_a, admin_user, supplier_a, contract_a):
    """An open, QUARTERLY contract obligation due in 10 days, scoped to a supplier.

    ``source="contract"`` with the contract named, because ``clean()`` rule (c) refuses a link-out
    that links nowhere, and ``next_due_date`` is set because rule (d) refuses a scheduled obligation
    with no first due date.
    """
    from apps.scm.models import ComplianceRequirement
    return ComplianceRequirement.objects.create(
        tenant=tenant_a, title="Certificate of insurance on file and current",
        description="Evidence the supplier's cover annually.", source="contract",
        contract=contract_a, source_reference=f"{contract_a.number}, clause 11.2",
        framework="insurance_coi", obligation_category="insurance", jurisdiction="United States",
        scope="party", party=supplier_a, owner=admin_user, frequency="quarterly",
        next_due_date=_compliance_date(10), notice_days=30, criticality="high",
    )


@pytest.fixture
def overdue_requirement_a(db, tenant_a, item_a):
    """An ANNUAL obligation whose due date is already 12 days past — still sitting at ``applicable``.

    Left un-rolled on purpose: ``refresh_status()`` moving it to ``overdue`` is what the list roll
    and the detail page are asserted to do, so the fixture has to hand them a row that has crossed
    the boundary but not yet been caught up.
    """
    from apps.scm.models import ComplianceRequirement
    return ComplianceRequirement.objects.create(
        tenant=tenant_a, title="Lithium cells classified to UN3481", source="regulation",
        source_reference="49 CFR 173.185", framework="hazmat_dot_iata_imdg",
        jurisdiction="United States", scope="item", item=item_a, frequency="annual",
        next_due_date=_compliance_date(-12), notice_days=30, criticality="critical",
    )


@pytest.fixture
def one_time_requirement_a(db, tenant_a):
    """A ``one_time`` obligation — the cadence with NO next cycle, so a pass clears the due date
    rather than inventing one."""
    from apps.scm.models import ComplianceRequirement
    return ComplianceRequirement.objects.create(
        tenant=tenant_a, title="GDPR processor terms reviewed once", source="internal_policy",
        framework="data_privacy_gdpr", scope="tenant", frequency="one_time",
        next_due_date=_compliance_date(5), notice_days=30, criticality="low",
    )


@pytest.fixture
def compliance_requirement_b(db, tenant_b):
    """The tenant_b obligation every cross-tenant IDOR assertion points at."""
    from apps.scm.models import ComplianceRequirement
    return ComplianceRequirement.objects.create(
        tenant=tenant_b, title="Globex REACH declaration", source="regulation",
        framework="reach", scope="tenant", frequency="annual",
        next_due_date=_compliance_date(30), criticality="medium",
    )


@pytest.fixture
def compliance_check_a(db, compliance_requirement_a, admin_user):
    """One PARTIAL proof cycle folded into its parent through ``record_check()``.

    Partial rather than pass: it moves the parent to ``in_progress`` and leaves ``next_due_date``
    alone, so the fixture does not silently consume the cycle the advance tests are about.
    """
    from apps.scm.models import ComplianceCheck
    check = ComplianceCheck.objects.create(
        requirement=compliance_requirement_a, result="partial",
        due_date=compliance_requirement_a.next_due_date, performed_on=_compliance_date(-3),
        performed_by=admin_user,
        finding="Cargo cover evidenced; liability certificate outstanding.",
    )
    compliance_requirement_a.record_check(check)
    return check


@pytest.fixture
def compliance_check_b(db, compliance_requirement_b):
    """A tenant-LESS child of the tenant_b requirement.

    It carries no ``tenant`` column, so every view must resolve it as
    ``requirement__tenant=request.tenant`` — a bare pk lookup is a cross-tenant read, and this is
    the row that proves whether one is happening.
    """
    from apps.scm.models import ComplianceCheck
    return ComplianceCheck.objects.create(
        requirement=compliance_requirement_b, result="pass",
        due_date=compliance_requirement_b.next_due_date, performed_on=_compliance_date(-1),
    )


@pytest.fixture
def sustainability_assessment_a(db, tenant_a, supplier_a, admin_user):
    """A full four-theme EcoVadis-shaped scorecard — 72/68/75/61 means 69, i.e. gold.

    ``overall_score`` and ``rating`` are NOT passed: they are ``editable=False`` and
    ``recompute_rating()`` (which ``save()`` calls on every path) is their only writer, which is
    exactly what these tests assert.
    """
    from apps.scm.models import SustainabilityAssessment
    return SustainabilityAssessment.objects.create(
        tenant=tenant_a, party=supplier_a, assessment_date=_compliance_date(-60),
        valid_until=_compliance_date(305), source="third_party_rating", provider="EcoVadis",
        status="validated", environment_score=72, labor_human_rights_score=68, ethics_score=75,
        sustainable_procurement_score=61, carbon_score=58, assessed_by=admin_user,
        reach_declared=True, rohs_declared=True, conflict_minerals_declared=True,
        code_of_conduct_signed=True,
        scope1_tco2e=Decimal("1240.500"), scope2_tco2e=Decimal("3180.250"),
        scope3_tco2e=Decimal("18640.000"), carbon_reporting_year=2025,
    )


@pytest.fixture
def unscored_assessment_a(db, tenant_a, vendor_a):
    """A scorecard with NOT ONE theme answered — ``overall_score`` must be ``None``, never 0.

    "Assessed, terrible" and "not assessed" are different facts, and a blanket 0 states the first
    when the truth is the second.
    """
    from apps.scm.models import SustainabilityAssessment
    return SustainabilityAssessment.objects.create(
        tenant=tenant_a, party=vendor_a, assessment_date=_compliance_date(-10),
        source="self_assessment", status="draft",
    )


@pytest.fixture
def sustainability_assessment_b(db, tenant_b, supplier_b):
    """The tenant_b scorecard every cross-tenant IDOR assertion points at."""
    from apps.scm.models import SustainabilityAssessment
    return SustainabilityAssessment.objects.create(
        tenant=tenant_b, party=supplier_b, assessment_date=_compliance_date(-20),
        source="desk_review", environment_score=30, scope1_tco2e=Decimal("99.000"),
        carbon_reporting_year=2025,
    )


@pytest.fixture
def carbon_shipment_a(db, tenant_a, carrier_a):
    """One MEASURABLE movement inside the report's default window: 2 000 kg over 500 km by truck.

    2.0 tonnes x 500 km = 1 000 tonne-km, times the truckload factor (62 gCO2e/tonne-km) = 62 000 g
    = 0.06 tCO2e. Every assertion recomputes that from ``EMISSION_FACTORS`` rather than typing 0.06,
    so a test cannot pass by agreeing with itself after a factor changes.
    """
    from django.utils import timezone
    from apps.scm.models import Load, Shipment
    load = Load.objects.create(tenant=tenant_a, carrier=carrier_a, mode="truckload",
                               origin_text="Chicago, IL", destination_text="Dallas, TX",
                               distance_km=Decimal("500.00"))
    ship = Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, load=load, direction="outbound", mode="truckload",
        origin_text="Chicago, IL", destination_text="Dallas, TX",
        planned_pickup_date=_compliance_date(-12), planned_delivery_date=_compliance_date(-10),
        weight_kg=Decimal("2000.00"), package_count=20,
    )
    ship.status = "delivered"
    ship.actual_delivery_at = timezone.now() - datetime.timedelta(days=10)
    ship.save(update_fields=["status", "actual_delivery_at", "updated_at"])
    return ship


@pytest.fixture
def unmeasurable_shipment_a(db, tenant_a, carrier_a):
    """A movement with a distance but NO weight — it cannot be scored, so the report must count it
    as an EXCLUSION rather than fold it in as a carbon-free zero."""
    from django.utils import timezone
    from apps.scm.models import Load, Shipment
    load = Load.objects.create(tenant=tenant_a, carrier=carrier_a, mode="air",
                               distance_km=Decimal("3000.00"))
    ship = Shipment.objects.create(
        tenant=tenant_a, carrier=carrier_a, load=load, direction="outbound", mode="air",
        origin_text="Chicago, IL", destination_text="London, UK",
        planned_pickup_date=_compliance_date(-8), weight_kg=None,
    )
    ship.status = "delivered"
    ship.actual_delivery_at = timezone.now() - datetime.timedelta(days=6)
    ship.save(update_fields=["status", "actual_delivery_at", "updated_at"])
    return ship


# ------------------------------------------------------------------ SCM 4.13 Asset Management
# One plant register (``Asset`` + ``AssetSparePart``), one PM programme (``MaintenancePlan`` +
# ``MaintenancePlanTask``), one job ladder (``MaintenanceWorkOrder`` + its parts and checklist
# children) and one append-only meter log (``MeterReading``).
#
# Every date below is derived from ``timezone.localdate()`` / ``timezone.now()`` — the SAME basis
# ``Asset.days_to_warranty_expiry``, ``Asset._observed_hours``, ``MaintenancePlan.days_until_due``,
# ``MaintenancePlan.advance`` and ``MeterReading.clean`` all read (L16). A literal 2026 date would
# drift out of the warranty notice band and out of the PM forecast horizon the moment the clock
# passed it, and a hard-coded ``read_at`` would eventually trip the model's no-future-dates rule.
#
# ``MaintenanceWorkOrder.status`` is ``editable=False`` and moved ONLY by the ten verbs, so the
# ladder fixtures walk it exactly as the verbs do (assign + a narrow ``save(update_fields=...)``) —
# the ``trade_license_a`` posture. A status typed straight into ``objects.create()`` would let a
# test assert a state no button in the product can actually produce.
def _asset_date(days):
    """A date ``days`` from today on the tz-aware basis every 4.13 date reader uses."""
    from django.utils import timezone
    return timezone.localdate() + datetime.timedelta(days=days)


def _asset_moment(hours):
    """An aware datetime ``hours`` from now — the basis downtime windows and ``read_at`` use."""
    from django.utils import timezone
    return timezone.now() + datetime.timedelta(hours=hours)


@pytest.fixture
def fixed_asset_a(db, tenant_a):
    """The ``accounting.FixedAsset`` 4.13 POINTS AT and never writes (L29).

    48 000.00 acquired, 8 000.00 accumulated -> 40 000.00 book value, which is what the
    repair-vs-replace ratio on the depreciation report divides by.
    """
    from apps.accounting.models import FixedAsset
    asset = FixedAsset.objects.create(
        tenant=tenant_a, name="CNC lathe (capitalised)", category="Machinery",
        acquisition_cost=Decimal("48000.00"), salvage_value=Decimal("3000.00"),
        useful_life_months=120, status="active", in_service_date=_asset_date(-365),
    )
    # ``accumulated_depreciation`` is editable=False and advanced by accounting's own depreciation
    # run — set through a narrow save() rather than create(), for the same reason the status
    # fixtures do: the column has exactly one writer in the product.
    asset.accumulated_depreciation = Decimal("8000.00")
    asset.save(update_fields=["accumulated_depreciation", "updated_at"])
    return asset


@pytest.fixture
def fixed_asset_b(db, tenant_b):
    """The tenant_b book record every cross-workspace ``fixed_asset`` assertion points at."""
    from apps.accounting.models import FixedAsset
    return FixedAsset.objects.create(
        tenant=tenant_b, name="Globex press (capitalised)",
        acquisition_cost=Decimal("10000.00"), status="active")


@pytest.fixture
def asset_a(db, tenant_a, location_a, work_center_a, org_unit_a, employee_party_a, supplier_a):
    """The 360-degree fixture: every FK populated, a meter declared, a warranty still in force.

    ``commissioned_on`` is 365 days back because it is what ``_observed_hours`` measures the
    reliability window from — an asset with no commissioning date falls back to ``created_at``,
    which in a test is microseconds old and makes every availability figure meaningless.
    """
    from apps.scm.models import Asset
    return Asset.objects.create(
        tenant=tenant_a, code="CNC-1", name="CNC Lathe", asset_type="machine",
        status="in_service", criticality="critical", category="Machining",
        manufacturer="Haas", model_number="ST-20", serial_number="SN-0001", tag_code="QR-CNC-1",
        specifications="3-axis, 20 kW spindle",
        location=location_a, org_unit=org_unit_a, work_center=work_center_a,
        custodian=employee_party_a, supplier=supplier_a, service_vendor=supplier_a,
        purchase_date=_asset_date(-400), commissioned_on=_asset_date(-365),
        warranty_expires_on=_asset_date(300), purchase_cost=Decimal("48000.00"),
        meter_name="Running Hours", meter_unit="h",
    )


@pytest.fixture
def asset_a2(db, tenant_a, location_a2):
    """A SECOND tenant_a asset — no meter, no tag, no warranty date.

    Three absences that each carry meaning: a blank ``meter_name`` is what makes a meter plan on it
    a validation error and a completion capture unfileable, a blank ``tag_code`` is what proves the
    uniqueness rule allows MANY untagged assets, and a null ``warranty_expires_on`` is the muted
    "Not recorded" chip that must never read green.
    """
    from apps.scm.models import Asset
    return Asset.objects.create(
        tenant=tenant_a, code="FORK-2", name="Forklift", asset_type="forklift",
        status="standby", criticality="low", location=location_a2,
        commissioned_on=_asset_date(-200),
    )


@pytest.fixture
def asset_b(db, tenant_b, location_b):
    """The tenant_b asset every cross-tenant IDOR assertion points at."""
    from apps.scm.models import Asset
    return Asset.objects.create(
        tenant=tenant_b, code="GBX-1", name="Globex Press", asset_type="machine",
        location=location_b, meter_name="Cycles", meter_unit="cycles",
        commissioned_on=_asset_date(-100), tag_code="QR-GBX-1",
    )


@pytest.fixture
def child_asset_a(db, tenant_a, asset_a, location_a):
    """A component of ``asset_a`` — the hierarchy fixture behind the cycle guard and the orphan
    message on delete (``Asset.parent`` is SET_NULL, so children survive their assembly)."""
    from apps.scm.models import Asset
    return Asset.objects.create(
        tenant=tenant_a, code="CNC-1-SPINDLE", name="Spindle assembly", asset_type="machine",
        parent=asset_a, location=location_a, criticality="high",
    )


@pytest.fixture
def spare_item_a(db, tenant_a, category_a, uom_each_a, location_a):
    """An MRO item flagged ``is_spare_part`` with REAL on-hand: 10 @ 25.0000 at ``location_a``.

    Stock is posted through ``_post_stock_move`` (via the suite's ``seed_stock``) rather than
    written as a bare ``StockMove`` row, so the item's cached ``average_cost`` is rolled forward
    exactly as production would — the issue verb stamps ``unit_cost`` from that cache, and a
    hand-written ledger row would leave the two disagreeing.
    """
    from apps.scm.models import Item
    from apps.scm.tests._helpers import seed_stock
    item = Item.objects.create(
        tenant=tenant_a, sku="BRG-6205", name="Bearing 6205", category=category_a, uom=uom_each_a,
        item_type="stock", tracking="none", costing_method="weighted_avg",
        standard_cost=Decimal("20.0000"), reorder_point=Decimal("4"), is_spare_part=True,
    )
    seed_stock(tenant_a, item, location_a, quantity="10", unit_cost="25.0000", reference="OPEN-BRG")
    item.refresh_from_db()
    return item


@pytest.fixture
def spare_item_b(db, tenant_b, uom_each_b):
    """The tenant_b spare every cross-workspace parts-line assertion points at."""
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant_b, sku="GBX-BRG", name="Globex bearing",
                               uom=uom_each_b, is_spare_part=True)


@pytest.fixture
def asset_spare_part_a(db, asset_a, spare_item_a):
    """One line of ``asset_a``'s parts list. Tenant-less child, reached through ``asset__tenant``."""
    from apps.scm.models import AssetSparePart
    return AssetSparePart.objects.create(
        asset=asset_a, item=spare_item_a, quantity_per_service=Decimal("2"), is_critical=True,
        notes="Front bearing")


@pytest.fixture
def maintenance_plan_a(db, tenant_a, asset_a, employee_party_a, location_a):
    """A CALENDAR plan on a FLOATING basis, due in 10 days, with a two-step job plan.

    ``lead_time_days=7`` against a due date 10 days out puts it deliberately OUTSIDE its own call
    horizon, so ``due_status()`` reads ``scheduled`` — the state the due filter, the forecast board
    and ``is_due`` are all measured against.
    """
    from apps.scm.models import MaintenancePlan, MaintenancePlanTask
    plan = MaintenancePlan.objects.create(
        tenant=tenant_a, name="Quarterly service", asset=asset_a,
        instructions="Grease the ways, check the coolant, log the hour meter.",
        trigger_type="calendar", schedule_basis="floating", interval_days=90, lead_time_days=7,
        next_due_on=_asset_date(10), priority="high", work_type="preventive",
        estimated_hours=Decimal("2.50"), assigned_to=employee_party_a, parts_location=location_a,
    )
    MaintenancePlanTask.objects.create(plan=plan, sequence=10, description="Isolate and lock out",
                                       expected_result="Isolator padlocked", is_safety_step=True)
    MaintenancePlanTask.objects.create(plan=plan, sequence=20, description="Grease the ways",
                                       expected_result="Two shots per nipple")
    return plan


@pytest.fixture
def plan_task_a(db, maintenance_plan_a):
    """``maintenance_plan_a``'s first job-plan step — a tenant-less child reached via
    ``plan__tenant``."""
    return maintenance_plan_a.tasks.order_by("sequence").first()


@pytest.fixture
def meter_plan_a(db, tenant_a, asset_a):
    """A PURE METER plan: every 250 running hours, next owed at 1500, no calendar axis at all.

    This is the fixture behind "a correctly configured meter plan reads ``scheduled``, not
    ``not_scheduled``" — the muted chip that says "nobody is watching this machine" must be reserved
    for plans that genuinely cannot fire.
    """
    from apps.scm.models import MaintenancePlan
    return MaintenancePlan.objects.create(
        tenant=tenant_a, name="500-hour service", asset=asset_a, trigger_type="meter",
        schedule_basis="floating", meter_interval=Decimal("250"),
        next_due_reading=Decimal("1500"), lead_time_days=7, work_type="preventive",
    )


@pytest.fixture
def maintenance_plan_b(db, tenant_b, asset_b):
    """The tenant_b plan every cross-tenant IDOR assertion points at."""
    from apps.scm.models import MaintenancePlan, MaintenancePlanTask
    plan = MaintenancePlan.objects.create(
        tenant=tenant_b, name="Globex weekly check", asset=asset_b, trigger_type="calendar",
        interval_days=7, next_due_on=_asset_date(3),
    )
    MaintenancePlanTask.objects.create(plan=plan, sequence=10, description="Globex step")
    return plan


@pytest.fixture
def plan_task_b(db, maintenance_plan_b):
    """The tenant_b job-plan step — proves the plan formset resolves through ``plan__tenant``."""
    return maintenance_plan_b.tasks.first()


@pytest.fixture
def maintenance_order_a(db, tenant_a, asset_a, location_a, employee_party_a):
    """A tenant_a job at the intake state ``requested`` — the bottom rung of the ladder.

    ``parts_location`` is set because the issue verb refuses outright without a storeroom; the
    absent-storeroom case is tested by CLEARING it rather than by a second fixture nobody reads.
    """
    from apps.scm.models import MaintenanceWorkOrder
    return MaintenanceWorkOrder.objects.create(
        tenant=tenant_a, title="Spindle noise", asset=asset_a, work_type="corrective",
        priority="high", source="request", description="Whine above 4 000 rpm.",
        reported_by=employee_party_a, assigned_to=employee_party_a, parts_location=location_a,
        labour_hours=Decimal("2.00"), labour_rate=Decimal("40.0000"),
        external_cost=Decimal("100.00"),
    )


@pytest.fixture
def approved_order_a(db, maintenance_order_a):
    """``maintenance_order_a`` one rung up — the state ``schedule`` and ``start`` both accept."""
    maintenance_order_a.status = "approved"
    maintenance_order_a.save(update_fields=["status", "updated_at"])
    return maintenance_order_a


@pytest.fixture
def in_progress_order_a(db, approved_order_a):
    """The only state ``complete`` accepts, with ``started_at`` stamped as ``start`` stamps it."""
    from django.utils import timezone
    approved_order_a.status = "in_progress"
    approved_order_a.started_at = timezone.now() - datetime.timedelta(hours=3)
    approved_order_a.save(update_fields=["status", "started_at", "updated_at"])
    return approved_order_a


@pytest.fixture
def completed_order_a(db, in_progress_order_a):
    """A terminal job — no longer editable, no longer cancellable, and the only state ``close``
    accepts."""
    from django.utils import timezone
    in_progress_order_a.status = "completed"
    in_progress_order_a.completed_at = timezone.now()
    in_progress_order_a.save(update_fields=["status", "completed_at", "updated_at"])
    return in_progress_order_a


@pytest.fixture
def maintenance_order_b(db, tenant_b, asset_b, location_b):
    """The tenant_b job every cross-tenant IDOR assertion points at."""
    from apps.scm.models import MaintenanceWorkOrder
    return MaintenanceWorkOrder.objects.create(
        tenant=tenant_b, title="Globex press jam", asset=asset_b, work_type="breakdown",
        parts_location=location_b)


@pytest.fixture
def part_line_a(db, maintenance_order_a, spare_item_a):
    """One PLANNED (not issued) part line: 2 x the stocked bearing. ``unit_cost`` is still 0.0000 —
    it is stamped only when the issue verb posts the negative ``maintenance`` StockMove."""
    from apps.scm.models import MaintenanceWorkOrderPart
    return MaintenanceWorkOrderPart.objects.create(
        work_order=maintenance_order_a, item=spare_item_a, quantity=Decimal("2"))


@pytest.fixture
def issued_part_line_a(db, part_line_a, maintenance_order_a, spare_item_a, location_a, tenant_a):
    """A line already drawn from stock, with its ledger move actually posted.

    The ``StockMove`` is REAL rather than implied: the cancel and delete guards refuse on
    ``is_issued``, and the whole point of the refusal is that a movement exists which would
    otherwise be left orphaned in an append-only ledger.
    """
    from django.utils import timezone
    from apps.scm.views._helpers import _post_stock_move
    _post_stock_move(tenant_a, item=spare_item_a, location=location_a, quantity=Decimal("-2"),
                     move_type="maintenance", unit_cost=Decimal("25.0000"),
                     reference=maintenance_order_a.number, reason="Maintenance issue")
    part_line_a.unit_cost = Decimal("25.0000")
    part_line_a.is_issued = True
    part_line_a.issued_at = timezone.now()
    part_line_a.save(update_fields=["unit_cost", "is_issued", "issued_at"])
    return part_line_a


@pytest.fixture
def job_task_a(db, maintenance_order_a):
    """One checklist step on a tenant_a job — the tenant-less child reached via
    ``work_order__tenant``."""
    from apps.scm.models import MaintenanceWorkOrderTask
    return MaintenanceWorkOrderTask.objects.create(
        work_order=maintenance_order_a, sequence=10, description="Isolate and lock out",
        expected_result="Isolator padlocked", is_safety_step=True)


@pytest.fixture
def job_task_b(db, maintenance_order_b):
    """The tenant_b checklist step every ``work_order__tenant`` isolation assertion points at."""
    from apps.scm.models import MaintenanceWorkOrderTask
    return MaintenanceWorkOrderTask.objects.create(
        work_order=maintenance_order_b, sequence=10, description="Globex step")


@pytest.fixture
def meter_reading_a(db, tenant_a, asset_a, employee_party_a):
    """The asset's current running-hours value: 1 218.5 h, read yesterday.

    Deliberately BELOW ``meter_plan_a``'s 1 500 h target, so the meter axis is not yet due — the
    plan reads ``scheduled``, and a completion capture is what actually moves it.
    """
    from apps.scm.models import MeterReading
    return MeterReading.objects.create(
        tenant=tenant_a, asset=asset_a, recorded_by=employee_party_a,
        meter_name="Running Hours", unit="h", reading=Decimal("1218.5"),
        read_at=_asset_moment(-24), source="manual")


@pytest.fixture
def meter_reading_b(db, tenant_b, asset_b):
    """The tenant_b reading every cross-tenant IDOR assertion points at."""
    from apps.scm.models import MeterReading
    return MeterReading.objects.create(
        tenant=tenant_b, asset=asset_b, meter_name="Cycles", unit="cycles",
        reading=Decimal("900"), read_at=_asset_moment(-24))


# ------------------------------------------------------------------ SCM 4.14 Labor Management
# L16 — EVERY reference date and time below is derived from ``timezone.now()`` /
# ``timezone.localdate()``, never ``datetime.date.today()`` and never a literal. Two model rules make
# that load-bearing rather than stylistic: ``LaborSession.clean()`` pins ``work_date`` to the LOCAL
# date of ``clock_in``, and ``LaborActivity.clean()`` refuses an interval that falls outside its
# shift's clock window. A literal date would therefore rot the day the calendar moved past it, and a
# ``date.today()`` basis would disagree with the views for the hours after local midnight.
def _labor_moment(hours_ago=0, minutes_ago=0):
    """An aware datetime that far in the past, TRUNCATED to the minute.

    Truncated because the ``datetime-local`` widget round-trips whole minutes: a fixture carrying
    seconds would hold a value nothing in the product can actually write, and every edit-form
    round-trip assertion would be measuring the fixture rather than the form.
    """
    from django.utils import timezone
    return (timezone.now() - datetime.timedelta(hours=hours_ago, minutes=minutes_ago)
            ).replace(second=0, microsecond=0)


def _labor_workday(moment):
    """The LOCAL date a shift starting at ``moment`` belongs to — ``LaborSession.clean()``'s rule (c).

    Read through ``timezone.localdate`` rather than ``moment.date()`` so a fixture built at 23:30 UTC
    under a non-UTC project timezone lands on the day the model would insist on.
    """
    from django.utils import timezone
    return timezone.localdate(moment)


def _labor_date(days=0):
    """Today (or days from it) on the basis every 4.14 date reader uses."""
    from django.utils import timezone
    return timezone.localdate() + datetime.timedelta(days=days)


@pytest.fixture
def employee_party_a2(db, tenant_a):
    """A SECOND tenant_a employee.

    Needed twice over: a worker may hold only ONE open session (``LaborSession.clean()`` rule (e)),
    so the gap-filter shifts cannot all belong to one person, and the payroll export's "a member
    sees only their own rows" assertion needs a colleague whose name must be ABSENT.
    """
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Rowan Picker", kind="person")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="employee")
    return party


@pytest.fixture
def employee_party_b(db, tenant_b):
    """The tenant_b worker every cross-tenant labour assertion points at."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Operator", kind="person")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="employee")
    return party


@pytest.fixture
def labor_standard_a(db, tenant_a):
    """An ACTIVE, network-wide picking standard, in force since a month ago and open-ended.

    3 fixed minutes (2 setup + 1 travel) + 0.5 per unit, inflated by a 10% PF&D allowance — so
    100 units earn ``(3 + 50) x 1.10 = 58.3000`` minutes. Every performance assertion in the 4.14
    suite is built on that one figure, deliberately, so a change to the arithmetic shows up once.
    """
    from apps.scm.models import LaborStandard
    return LaborStandard.objects.create(
        tenant=tenant_a, name="Case picking", activity="pick", basis="per_unit",
        source="engineered", minutes_per_unit=Decimal("0.5000"),
        setup_minutes=Decimal("2.0000"), travel_minutes=Decimal("1.0000"),
        allowance_pct=Decimal("10.00"), labour_rate=Decimal("24.0000"),
        status="active", effective_from=_labor_date(-30))


@pytest.fixture
def draft_standard_a(db, tenant_a):
    """A DRAFT packing standard — the activate verb's subject, and a row select_standard must SKIP."""
    from apps.scm.models import LaborStandard
    return LaborStandard.objects.create(
        tenant=tenant_a, name="Carton packing", activity="pack", basis="per_case",
        minutes_per_unit=Decimal("1.2500"), setup_minutes=Decimal("0.5000"),
        status="draft", effective_from=_labor_date(-10))


@pytest.fixture
def labor_standard_b(db, tenant_b):
    """The tenant_b standard every cross-tenant IDOR assertion points at."""
    from apps.scm.models import LaborStandard
    return LaborStandard.objects.create(
        tenant=tenant_b, name="Globex picking", activity="pick",
        minutes_per_unit=Decimal("0.8000"), status="active", effective_from=_labor_date(-30))


@pytest.fixture
def labor_session_a(db, tenant_a, employee_party_a, location_a):
    """An OPEN shift that started four hours ago and has NOT been clocked out.

    Open because that is the only writable status — ``LaborActivity.clean()`` refuses to write into
    anything else — so it is the state every booking test has to start from.
    """
    from apps.scm.models import LaborSession
    started = _labor_moment(hours_ago=4)
    return LaborSession.objects.create(
        tenant=tenant_a, worker=employee_party_a, location=location_a,
        work_date=_labor_workday(started), shift_label="Early", clock_in=started)


@pytest.fixture
def labor_session_b(db, tenant_b, employee_party_b, location_b):
    """The tenant_b shift every cross-tenant IDOR assertion points at."""
    from apps.scm.models import LaborSession
    started = _labor_moment(hours_ago=4)
    return LaborSession.objects.create(
        tenant=tenant_b, worker=employee_party_b, location=location_b,
        work_date=_labor_workday(started), clock_in=started)


@pytest.fixture
def labor_activity_a(db, tenant_a, labor_session_a, labor_standard_a):
    """One COMPLETED 60-minute pick of 100 units (2 of them wrong), measured against the standard.

    The three input snapshots are written exactly as ``_stamp_standard`` writes them, so the row is
    indistinguishable from one the create view filed: earned = 58.3000, performance = 97.17%.
    """
    from apps.scm.models import LaborActivity
    started = labor_session_a.clock_in
    return LaborActivity.objects.create(
        tenant=tenant_a, session=labor_session_a, activity_type="pick",
        started_at=started, ended_at=started + datetime.timedelta(minutes=60),
        quantity=Decimal("100"), error_quantity=Decimal("2"),
        standard=labor_standard_a,
        standard_fixed_snapshot=Decimal("3.0000"),
        standard_rate_snapshot=Decimal("0.5000"),
        standard_allowance_snapshot=Decimal("10.00"))


@pytest.fixture
def labor_activity_b(db, tenant_b, labor_session_b):
    """The tenant_b booking every ``session__tenant`` isolation assertion points at."""
    from apps.scm.models import LaborActivity
    started = labor_session_b.clock_in
    return LaborActivity.objects.create(
        tenant=tenant_b, session=labor_session_b, activity_type="pick",
        started_at=started, ended_at=started + datetime.timedelta(minutes=30),
        quantity=Decimal("40"))


@pytest.fixture
def labor_plan_a(db, tenant_a, location_a):
    """A DRAFT daily plan over the next three days at location_a, sourced from the stock ledger."""
    from apps.scm.models import LaborPlan
    return LaborPlan.objects.create(
        tenant=tenant_a, name="Next three days", location=location_a,
        period_start=_labor_date(1), period_end=_labor_date(3), bucket="day",
        volume_source="stock_moves", method="moving_average", history_days=28,
        hours_per_shift=Decimal("8.00"), productivity_pct=Decimal("100.00"))


@pytest.fixture
def labor_plan_b(db, tenant_b, location_b):
    """The tenant_b plan every cross-tenant IDOR assertion points at."""
    from apps.scm.models import LaborPlan
    return LaborPlan.objects.create(
        tenant=tenant_b, name="Globex plan", location=location_b,
        period_start=_labor_date(1), period_end=_labor_date(2), bucket="day",
        volume_source="manual", method="manual")


@pytest.fixture
def labor_plan_line_a(db, labor_plan_a, labor_standard_a):
    """One generated bucket of labor_plan_a's grid — the only row a planner may edit, and only
    through ``planned_headcount``."""
    from apps.scm.models import LaborPlanLine
    return LaborPlanLine.objects.create(
        plan=labor_plan_a, period_start=labor_plan_a.period_start, activity="pick",
        forecast_volume=Decimal("100.0000"), standard=labor_standard_a,
        standard_minutes_snapshot=Decimal("58.3000"),
        required_minutes=Decimal("58.30"), required_headcount=Decimal("0.12"),
        planned_headcount=Decimal("1.00"))


@pytest.fixture
def labor_plan_line_b(db, labor_plan_b):
    """The tenant-LESS child that can only be reached through ``plan__tenant`` — tenant_b's."""
    from apps.scm.models import LaborPlanLine
    return LaborPlanLine.objects.create(
        plan=labor_plan_b, period_start=labor_plan_b.period_start, activity="pick",
        required_headcount=Decimal("2.00"), planned_headcount=Decimal("1.00"))
