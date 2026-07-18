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
