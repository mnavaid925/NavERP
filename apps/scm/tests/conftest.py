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
