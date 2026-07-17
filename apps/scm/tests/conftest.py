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
