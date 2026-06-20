"""Accounting app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b,
client_a, client_b, member_user, member_client) and adds Accounting-specific
records: GL accounts, a fiscal period, currency, party with roles, bank account.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client


# ------------------------------------------------------------------ Currency
@pytest.fixture
def usd(db):
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(code="USD", defaults={"name": "US Dollar", "symbol": "$"})
    return obj


# ------------------------------------------------------------------ GL Accounts
@pytest.fixture
def gl_cash(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="1000", name="Cash", account_type="asset"
    )


@pytest.fixture
def gl_ar(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="1100", name="Accounts Receivable", account_type="asset"
    )


@pytest.fixture
def gl_ap(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="2000", name="Accounts Payable", account_type="liability"
    )


@pytest.fixture
def gl_income(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="4000", name="Sales Revenue", account_type="income"
    )


# ------------------------------------------------------------------ GL Accounts for tenant_b (IDOR tests)
@pytest.fixture
def gl_cash_b(db, tenant_b):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_b, code="1000", name="Cash B", account_type="asset"
    )


# ------------------------------------------------------------------ Fiscal Period
@pytest.fixture
def open_period(db, tenant_a):
    from apps.accounting.models import FiscalPeriod
    return FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="Jan 2026",
        period_type="month",
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 1, 31),
        status="open",
    )


@pytest.fixture
def closed_period(db, tenant_a):
    from apps.accounting.models import FiscalPeriod
    return FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="Dec 2025",
        period_type="month",
        start_date=datetime.date(2025, 12, 1),
        end_date=datetime.date(2025, 12, 31),
        status="closed",
    )


# ------------------------------------------------------------------ Party (customer + vendor)
@pytest.fixture
def customer_party(db, tenant_a):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Customer", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="customer")
    return party


@pytest.fixture
def vendor_party(db, tenant_a):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Vendor", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="vendor")
    return party


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Customer", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="customer")
    return party


# ------------------------------------------------------------------ Bank account
@pytest.fixture
def bank_account(db, tenant_a, usd, gl_cash):
    from apps.accounting.models import BankAccount
    return BankAccount.objects.create(
        tenant=tenant_a,
        name="Main Checking",
        bank_name="First Bank",
        currency=usd,
        gl_account=gl_cash,
        opening_balance=Decimal("1000.00"),
    )


@pytest.fixture
def bank_account_b(db, tenant_b, usd, gl_cash_b):
    from apps.accounting.models import BankAccount
    return BankAccount.objects.create(
        tenant=tenant_b,
        name="Globex Checking",
        bank_name="Second Bank",
        currency=usd,
        gl_account=gl_cash_b,
        opening_balance=Decimal("500.00"),
    )


# ------------------------------------------------------------------ A balanced posted Journal Entry (for void tests)
@pytest.fixture
def posted_je(db, tenant_a, admin_user, open_period, gl_cash, gl_income):
    from django.utils import timezone
    from apps.accounting.models import JournalEntry, JournalLine
    je = JournalEntry.objects.create(
        tenant=tenant_a,
        entry_type="manual",
        status="posted",
        fiscal_period=open_period,
        entry_date=datetime.date(2026, 1, 15),
        description="Posted test entry",
        created_by=admin_user,
        approved_by=admin_user,
        posted_at=timezone.now(),
    )
    JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("500.00"), credit=Decimal("0.00"))
    JournalLine.objects.create(entry=je, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("500.00"))
    return je


# ------------------------------------------------------------------ Draft Journal Entry
@pytest.fixture
def draft_je(db, tenant_a, admin_user, open_period, gl_cash, gl_income):
    from apps.accounting.models import JournalEntry, JournalLine
    je = JournalEntry.objects.create(
        tenant=tenant_a,
        entry_type="manual",
        status="draft",
        fiscal_period=open_period,
        entry_date=datetime.date(2026, 1, 15),
        description="Draft test entry",
        created_by=admin_user,
    )
    JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("300.00"), credit=Decimal("0.00"))
    JournalLine.objects.create(entry=je, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("300.00"))
    return je


# ------------------------------------------------------------------ Invoice
@pytest.fixture
def draft_invoice(db, tenant_a, customer_party, usd):
    from apps.accounting.models import Invoice, InvoiceLine
    inv = Invoice.objects.create(
        tenant=tenant_a,
        party=customer_party,
        issue_date=datetime.date(2026, 1, 10),
        due_date=datetime.date(2026, 2, 10),
        status="draft",
        currency=usd,
    )
    InvoiceLine.objects.create(
        invoice=inv,
        description="Consulting",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
    )
    inv.recalc_totals()
    return inv


@pytest.fixture
def sent_invoice(db, tenant_a, admin_user, customer_party, open_period, gl_ar, gl_income, usd):
    """A sent invoice with a posted GL entry (total=500)."""
    from django.utils import timezone
    from apps.accounting.models import Invoice, InvoiceLine, JournalEntry, JournalLine
    inv = Invoice.objects.create(
        tenant=tenant_a,
        party=customer_party,
        issue_date=datetime.date(2026, 1, 10),
        due_date=datetime.date(2026, 2, 10),
        status="sent",
        currency=usd,
    )
    InvoiceLine.objects.create(
        invoice=inv,
        description="Service",
        quantity=Decimal("1"),
        unit_price=Decimal("500.00"),
    )
    inv.recalc_totals()
    return inv


@pytest.fixture
def invoice_b(db, tenant_b, party_b, usd):
    from apps.accounting.models import Invoice
    return Invoice.objects.create(
        tenant=tenant_b,
        party=party_b,
        issue_date=datetime.date(2026, 1, 10),
        due_date=datetime.date(2026, 2, 10),
        status="draft",
        currency=usd,
    )


# ------------------------------------------------------------------ Bill
@pytest.fixture
def draft_bill(db, tenant_a, vendor_party, usd):
    from apps.accounting.models import Bill, BillLine
    bill = Bill.objects.create(
        tenant=tenant_a,
        party=vendor_party,
        bill_date=datetime.date(2026, 1, 5),
        due_date=datetime.date(2026, 2, 5),
        status="draft",
        currency=usd,
    )
    BillLine.objects.create(
        bill=bill,
        description="Office Supplies",
        quantity=Decimal("1"),
        unit_price=Decimal("200.00"),
    )
    bill.recalc_totals()
    return bill


@pytest.fixture
def bill_b(db, tenant_b, party_b, usd):
    from apps.accounting.models import Bill
    return Bill.objects.create(
        tenant=tenant_b,
        party=party_b,
        bill_date=datetime.date(2026, 1, 5),
        status="draft",
        currency=usd,
    )


# ------------------------------------------------------------------ Payment
@pytest.fixture
def draft_payment(db, tenant_a, customer_party, bank_account, usd):
    from apps.accounting.models import Payment
    return Payment.objects.create(
        tenant=tenant_a,
        direction="in",
        party=customer_party,
        bank_account=bank_account,
        payment_method="bank_transfer",
        payment_date=datetime.date(2026, 1, 20),
        amount=Decimal("500.00"),
        currency=usd,
        status="draft",
    )


@pytest.fixture
def payment_b(db, tenant_b, party_b, bank_account_b, usd):
    from apps.accounting.models import Payment
    return Payment.objects.create(
        tenant=tenant_b,
        direction="in",
        party=party_b,
        bank_account=bank_account_b,
        payment_date=datetime.date(2026, 1, 20),
        amount=Decimal("100.00"),
        currency=usd,
        status="draft",
    )


# ------------------------------------------------------------------ JournalEntry for tenant_b (IDOR)
@pytest.fixture
def je_b(db, tenant_b, admin_b, gl_cash_b):
    """A draft JE belonging to tenant_b for IDOR tests."""
    from apps.accounting.models import JournalEntry
    return JournalEntry.objects.create(
        tenant=tenant_b,
        entry_type="manual",
        status="draft",
        entry_date=datetime.date(2026, 1, 1),
        description="Tenant B JE",
        created_by=admin_b,
    )
