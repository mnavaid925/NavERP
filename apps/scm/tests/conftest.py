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
