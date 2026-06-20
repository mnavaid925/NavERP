"""Seed Accounting & Finance (Module 2) demo data — a Chart of Accounts, fiscal periods,
payment terms, a bank account, vendor/customer profiles (reusing the core ``Party`` spine),
invoices, bills, payments + cash application, bank transactions, a reconciliation, and posted
journal entries — per tenant.

Idempotent: a tenant that already has a Chart of Accounts is skipped (the CoA is created first,
so a second run is a no-op). Currencies are global and use ``get_or_create``. Run after the core
spine seeders (``seed_core`` etc.) so ``Party`` rows exist to reuse.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole, Tenant
from apps.accounting.models_advanced import (
    Budget,
    BudgetLine,
    CostAllocation,
    FixedAsset,
    IntegrationConfig,
    IntercompanyTransaction,
    InternalControl,
    JobCostEntry,
    PayrollRun,
    Project,
    ScheduledReport,
    TaxCode,
    TaxReturn,
)
from apps.accounting.models import (
    BankAccount,
    BankTransaction,
    Bill,
    BillLine,
    Currency,
    CustomerProfile,
    ExchangeRate,
    FiscalPeriod,
    GLAccount,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Payment,
    PaymentAllocation,
    PaymentTerm,
    ReconciliationMatch,
    VendorProfile,
)

User = get_user_model()

CURRENCIES = [
    ("USD", "US Dollar", "$"),
    ("EUR", "Euro", "€"),
    ("GBP", "British Pound", "£"),
    ("CAD", "Canadian Dollar", "C$"),
]

# (code, name, account_type)
CHART = [
    ("1000", "Cash", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Prepaid Expenses", "asset"),
    ("1500", "Inventory", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("2100", "Accrued Liabilities", "liability"),
    ("2200", "Sales Tax Payable", "liability"),
    ("3000", "Owner's Equity", "equity"),
    ("3100", "Retained Earnings", "equity"),
    ("4000", "Sales Revenue", "income"),
    ("4100", "Service Revenue", "income"),
    ("5000", "Cost of Goods Sold", "expense"),
    ("6000", "Operating Expenses", "expense"),
    ("6100", "Salaries & Wages", "expense"),
    ("6200", "Rent Expense", "expense"),
    ("6300", "Utilities", "expense"),
    ("7000", "Interest Expense", "expense"),
    ("8000", "Income Tax Expense", "expense"),
]


class Command(BaseCommand):
    help = "Seed Accounting & Finance demo data — idempotent (skips a tenant that already has a CoA)."

    @transaction.atomic
    def handle(self, *args, **options):
        for code, name, symbol in CURRENCIES:
            Currency.objects.get_or_create(code=code, defaults={"name": name, "symbol": symbol})
        usd = Currency.objects.get(code="USD")

        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run `seed_core` first."))
            return

        for tenant in tenants:
            if GLAccount.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"{tenant.name}: base accounting data already exists — skipping base seed.")
            else:
                self._seed_tenant(tenant, usd)
            # Advanced sub-modules 2.6–2.15 — self-guarded so it runs once even when base data exists.
            self._seed_advanced(tenant, usd)

        self.stdout.write(self.style.SUCCESS("Accounting seed complete."))
        self.stdout.write("Log in as a tenant admin (e.g. admin_acme / password) to view accounting data.")
        self.stdout.write(self.style.WARNING(
            "Superuser 'admin' has no tenant — accounting pages show no data when logged in as admin."))

    def _admin(self, tenant):
        return (User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
                or User.objects.filter(tenant=tenant).first())

    def _party(self, tenant, name, kind, role):
        """Get-or-create a Party with the given role (reuse the core spine; never duplicate)."""
        party = (Party.objects.filter(tenant=tenant, roles__role=role).order_by("id").first())
        if party is None:
            party = Party.objects.create(tenant=tenant, kind=kind, name=name)
        PartyRole.objects.get_or_create(tenant=tenant, party=party, role=role,
                                        defaults={"status": "active", "start_date": timezone.localdate()})
        return party

    def _seed_tenant(self, tenant, usd):
        today = timezone.localdate()
        admin = self._admin(tenant)

        # --- Currencies (FX rates for non-USD) ----------------------------------
        for code, rate in (("EUR", "0.92"), ("GBP", "0.79"), ("CAD", "1.36")):
            cur = Currency.objects.get(code=code)
            ExchangeRate.objects.get_or_create(
                tenant=tenant, currency=cur, rate_date=today,
                defaults={"rate": Decimal(rate), "source": "manual"})

        # --- Chart of Accounts --------------------------------------------------
        accounts = {}
        for code, name, atype in CHART:
            accounts[code] = GLAccount.objects.create(
                tenant=tenant, code=code, name=name, account_type=atype)

        # --- Fiscal periods (previous closed, current open) ---------------------
        first_of_month = today.replace(day=1)
        prev_end = first_of_month - datetime.timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        FiscalPeriod.objects.create(
            tenant=tenant, name=prev_start.strftime("%b %Y"), period_type="month",
            start_date=prev_start, end_date=prev_end, status="closed",
            closed_by=admin, closed_at=timezone.now())
        open_period = FiscalPeriod.objects.create(
            tenant=tenant, name=today.strftime("%b %Y"), period_type="month",
            start_date=first_of_month, end_date=(first_of_month + datetime.timedelta(days=31)),
            status="open")

        # --- Payment terms ------------------------------------------------------
        net30 = PaymentTerm.objects.create(tenant=tenant, name="Net 30", days_due=30)
        early = PaymentTerm.objects.create(
            tenant=tenant, name="2/10 Net 30", days_due=30, discount_pct=Decimal("2"), discount_days=10)

        # --- Bank account -------------------------------------------------------
        bank = BankAccount.objects.create(
            tenant=tenant, name="Operating Account", account_number_last4="4821",
            bank_name="First National", currency=usd, gl_account=accounts["1000"],
            opening_balance=Decimal("50000"), opening_balance_date=first_of_month)

        # --- Vendor & customer profiles (reuse Party spine) ---------------------
        vendor = self._party(tenant, "Acme Office Supplies", "organization", "vendor")
        customer = self._party(tenant, "Globex Retail Group", "organization", "customer")
        VendorProfile.objects.get_or_create(
            party=vendor, defaults={"tenant": tenant, "payment_terms": net30,
                                    "default_expense_account": accounts["6000"], "currency": usd,
                                    "is_1099": True})
        CustomerProfile.objects.get_or_create(
            party=customer, defaults={"tenant": tenant, "payment_terms": early,
                                     "credit_limit": Decimal("25000"), "ar_account": accounts["1100"],
                                     "currency": usd})

        # --- AR invoices --------------------------------------------------------
        inv_sent = Invoice.objects.create(
            tenant=tenant, kind="invoice", party=customer, payment_terms=early,
            issue_date=today - datetime.timedelta(days=40), due_date=today - datetime.timedelta(days=10),
            status="partial", currency=usd)
        InvoiceLine.objects.create(invoice=inv_sent, description="Consulting — March",
                                   quantity=Decimal("10"), unit_price=Decimal("500"),
                                   tax_rate_pct=Decimal("8"), gl_account=accounts["4100"])
        InvoiceLine.objects.create(invoice=inv_sent, description="Onboarding setup",
                                   quantity=Decimal("1"), unit_price=Decimal("1500"),
                                   tax_rate_pct=Decimal("8"), gl_account=accounts["4000"])
        inv_sent.recalc_totals()

        inv_draft = Invoice.objects.create(
            tenant=tenant, kind="invoice", party=customer, payment_terms=net30,
            issue_date=today, due_date=today + datetime.timedelta(days=30), status="draft", currency=usd)
        InvoiceLine.objects.create(invoice=inv_draft, description="Monthly retainer",
                                   quantity=Decimal("1"), unit_price=Decimal("3000"),
                                   tax_rate_pct=Decimal("0"), gl_account=accounts["4100"])
        inv_draft.recalc_totals()

        # --- AP bills -----------------------------------------------------------
        bill_appr = Bill.objects.create(
            tenant=tenant, party=vendor, payment_terms=net30,
            bill_date=today - datetime.timedelta(days=20), due_date=today + datetime.timedelta(days=10),
            status="approved", currency=usd, approved_by=admin)
        BillLine.objects.create(bill=bill_appr, description="Office supplies",
                                quantity=Decimal("1"), unit_price=Decimal("850"),
                                tax_rate_pct=Decimal("8"), gl_account=accounts["6000"])
        BillLine.objects.create(bill=bill_appr, description="Printer toner",
                                quantity=Decimal("4"), unit_price=Decimal("120"),
                                tax_rate_pct=Decimal("8"), gl_account=accounts["6000"])
        bill_appr.recalc_totals()

        bill_draft = Bill.objects.create(
            tenant=tenant, party=vendor, payment_terms=net30, bill_date=today,
            due_date=today + datetime.timedelta(days=30), status="draft", currency=usd)
        BillLine.objects.create(bill=bill_draft, description="Q2 software licenses",
                                quantity=Decimal("1"), unit_price=Decimal("2400"),
                                tax_rate_pct=Decimal("0"), gl_account=accounts["6000"])
        bill_draft.recalc_totals()

        # --- Payment + cash application (partial on the sent invoice) -----------
        # A confirmed payment carries a balanced GL posting (Dr Cash / Cr AR), mirroring the
        # payment_confirm view so the demo ledger reflects the cash receipt.
        pay_je = self._posted_je(tenant, open_period, admin, today - datetime.timedelta(days=5),
                                 f"Receipt for {inv_sent.number}",
                                 [(accounts["1000"], Decimal("3000"), None),
                                  (accounts["1100"], None, Decimal("3000"))])
        payment = Payment.objects.create(
            tenant=tenant, direction="in", party=customer, bank_account=bank,
            payment_method="bank_transfer", payment_date=today - datetime.timedelta(days=5),
            amount=Decimal("3000"), currency=usd, status="confirmed", journal_entry=pay_je)
        PaymentAllocation.objects.create(payment=payment, invoice=inv_sent,
                                         allocated_amount=Decimal("3000"))

        # --- Posted journal entries (a small but balanced trial balance) --------
        self._posted_je(tenant, open_period, admin, today, "Opening cash investment",
                        [(accounts["1000"], Decimal("50000"), None),
                         (accounts["3000"], None, Decimal("50000"))])
        self._posted_je(tenant, open_period, admin, today, "Office rent — current month",
                        [(accounts["6200"], Decimal("2000"), None),
                         (accounts["1000"], None, Decimal("2000"))])
        self._posted_je(tenant, open_period, admin, today, "Service revenue accrual",
                        [(accounts["1100"], Decimal("3000"), None),
                         (accounts["4100"], None, Decimal("3000"))])

        # --- Bank transactions + reconciliation ---------------------------------
        txn1 = BankTransaction.objects.create(
            tenant=tenant, bank_account=bank, transaction_date=today - datetime.timedelta(days=5),
            description="Customer receipt — Globex", amount=Decimal("3000"), direction="credit",
            source="bank_feed", status="reconciled", external_ref="FEED-0001")
        BankTransaction.objects.create(
            tenant=tenant, bank_account=bank, transaction_date=today - datetime.timedelta(days=3),
            description="Rent payment", amount=Decimal("2000"), direction="debit",
            source="bank_feed", status="matched", external_ref="FEED-0002")
        BankTransaction.objects.create(
            tenant=tenant, bank_account=bank, transaction_date=today - datetime.timedelta(days=1),
            description="Bank service fee", amount=Decimal("35"), direction="debit",
            source="csv_import", status="unmatched", external_ref="FEED-0003")
        ReconciliationMatch.objects.create(
            tenant=tenant, bank_transaction=txn1, payment=payment, matched_by=admin, is_confirmed=True)

        self.stdout.write(self.style.SUCCESS(
            f"{tenant.name}: seeded CoA/periods/terms/bank/invoices/bills/payments/JEs/reconciliation"))

    def _posted_je(self, tenant, period, admin, date, description, legs):
        """Create a posted, balanced JournalEntry from (account, debit, credit) legs."""
        entry = JournalEntry.objects.create(
            tenant=tenant, entry_type="manual", status="posted", fiscal_period=period,
            entry_date=date, description=description, created_by=admin, approved_by=admin,
            posted_at=timezone.now())
        for account, debit, credit in legs:
            JournalLine.objects.create(
                entry=entry, gl_account=account, debit=debit or Decimal("0"),
                credit=credit or Decimal("0"), description=description)
        return entry

    # ------------------------------------------------ advanced sub-modules 2.6–2.15
    def _seed_advanced(self, tenant, usd):
        """Seed demo rows for 2.6–2.15. Idempotent: skips a tenant that already has a FixedAsset.
        Records are left in DRAFT so the user can exercise the post/run actions; the GL accounts
        they need are get_or_create'd so posting works out of the box."""
        if FixedAsset.objects.filter(tenant=tenant).exists():
            self.stdout.write(f"{tenant.name}: advanced accounting data already exists — skipping.")
            return
        today = timezone.localdate()
        admin = self._admin(tenant)

        def acct(code, name, atype):
            obj, _ = GLAccount.objects.get_or_create(
                tenant=tenant, code=code, defaults={"name": name, "account_type": atype})
            return obj

        cash = acct("1000", "Cash", "asset")
        ar = acct("1100", "Accounts Receivable", "asset")
        equipment = acct("1600", "Equipment", "asset")
        accum_dep = acct("1690", "Accumulated Depreciation", "asset")
        due_from = acct("1150", "Due from Affiliates", "asset")
        due_to = acct("2050", "Due to Affiliates", "liability")
        tax_payable = acct("2200", "Sales Tax Payable", "liability")
        ded_payable = acct("2100", "Accrued Liabilities", "liability")
        revenue = acct("4100", "Service Revenue", "income")
        opex = acct("6000", "Operating Expenses", "expense")
        dep_exp = acct("6400", "Depreciation Expense", "expense")
        wages_exp = acct("6100", "Salaries & Wages", "expense")

        org_units = list(OrgUnit.objects.filter(tenant=tenant).order_by("id")[:2])
        while len(org_units) < 2:
            org_units.append(OrgUnit.objects.create(
                tenant=tenant, kind="department", name=f"Division {len(org_units) + 1}"))
        org_a, org_b = org_units[0], org_units[1]
        custodian = self._party(tenant, "Operations Lead", "person", "employee")
        client = Party.objects.filter(tenant=tenant, roles__role="customer").first() \
            or self._party(tenant, "Project Client", "organization", "customer")

        # 2.6 Fixed Assets
        FixedAsset.objects.create(
            tenant=tenant, name="Delivery Van", category="Vehicles",
            acquisition_cost=Decimal("48000"), salvage_value=Decimal("6000"), useful_life_months=60,
            method="straight_line", in_service_date=today - datetime.timedelta(days=90), status="active",
            asset_account=equipment, accumulated_account=accum_dep, expense_account=dep_exp,
            custodian=custodian, location=org_a)
        FixedAsset.objects.create(
            tenant=tenant, name="Warehouse Racking", category="Equipment",
            acquisition_cost=Decimal("18000"), salvage_value=Decimal("0"), useful_life_months=84,
            method="declining_balance", status="cip", asset_account=equipment,
            accumulated_account=accum_dep, expense_account=dep_exp, location=org_b)

        # 2.7 Cost Allocation
        CostAllocation.objects.create(
            tenant=tenant, description="Allocate shared IT cost to Sales", allocation_date=today,
            amount=Decimal("1200"), source_account=opex, target_account=opex, target_org_unit=org_a)

        # 2.8 Payroll
        PayrollRun.objects.create(
            tenant=tenant, period_start=today.replace(day=1), period_end=today, pay_date=today,
            headcount=8, gross_wages=Decimal("32000"), employee_tax=Decimal("6400"),
            employer_tax=Decimal("2450"), benefits=Decimal("1800"), deductions=Decimal("950"))

        # 2.9 Project / Job costing
        project = Project.objects.create(
            tenant=tenant, name="Website Redesign", client=client, org_unit=org_a,
            billing_method="time_materials", budget_amount=Decimal("40000"),
            start_date=today - datetime.timedelta(days=30), status="active")
        JobCostEntry.objects.create(
            tenant=tenant, project=project, entry_date=today, kind="cost", amount=Decimal("5000"),
            gl_account=opex, description="Contractor hours")
        JobCostEntry.objects.create(
            tenant=tenant, project=project, entry_date=today, kind="revenue", amount=Decimal("12000"),
            gl_account=revenue, description="Progress billing")

        # 2.10 Multi-entity / Intercompany
        IntercompanyTransaction.objects.create(
            tenant=tenant, description="HQ funds Branch operations", transaction_date=today,
            amount=Decimal("15000"), from_org_unit=org_a, to_org_unit=org_b,
            due_from_account=due_from, due_to_account=due_to)

        # 2.11 Tax
        sales_tax = TaxCode.objects.create(
            tenant=tenant, name="State Sales Tax", jurisdiction="CA", tax_type="sales",
            rate_pct=Decimal("8.250"), payable_account=tax_payable)
        TaxCode.objects.create(
            tenant=tenant, name="VAT Standard", jurisdiction="EU", tax_type="vat",
            rate_pct=Decimal("20.000"), payable_account=tax_payable)
        TaxReturn.objects.create(
            tenant=tenant, tax_code=sales_tax, period_start=today.replace(day=1), period_end=today,
            taxable_amount=Decimal("40000"), tax_due=Decimal("3300"), status="draft",
            due_date=today + datetime.timedelta(days=20))

        # 2.12 Scheduled reports
        ScheduledReport.objects.create(
            tenant=tenant, name="Monthly Balance Sheet", report_type="balance_sheet",
            frequency="monthly", recipients="cfo@example.com", is_active=True)

        # 2.13 Budgeting
        period = FiscalPeriod.objects.filter(tenant=tenant, status="open").first()
        budget = Budget.objects.create(
            tenant=tenant, name="FY Operating Budget", fiscal_period=period, version="original",
            status="approved")
        BudgetLine.objects.create(tenant=tenant, budget=budget, gl_account=revenue, org_unit=org_a,
                                  amount=Decimal("120000"))
        BudgetLine.objects.create(tenant=tenant, budget=budget, gl_account=opex, org_unit=org_a,
                                  amount=Decimal("45000"))
        BudgetLine.objects.create(tenant=tenant, budget=budget, gl_account=wages_exp, org_unit=org_a,
                                  amount=Decimal("60000"))

        # 2.14 Audit & controls
        InternalControl.objects.create(
            tenant=tenant, code="CTRL-AP-01", name="Two-way invoice approval", control_type="preventive",
            frequency="transactional", risk_level="high", owner=custodian,
            last_tested_date=today - datetime.timedelta(days=15), last_result="pass", status="active",
            description="All vendor bills over $1,000 require a second approver.")
        InternalControl.objects.create(
            tenant=tenant, code="CTRL-GL-02", name="Monthly bank reconciliation", control_type="detective",
            frequency="monthly", risk_level="medium", owner=custodian, last_result="na", status="active",
            description="Reconcile every bank account within 5 business days of month-end.")

        # 2.15 Integration & API
        plaid = IntegrationConfig.objects.create(
            tenant=tenant, name="Plaid Bank Feed", provider="plaid", category="banking",
            status="connected", is_active=True, notes="Daily transaction sync.")
        plaid.set_secret(IntegrationConfig.generate_secret())
        plaid.save(update_fields=["api_key_prefix", "api_key_hash"])
        IntegrationConfig.objects.create(
            tenant=tenant, name="Avalara Tax", provider="avalara", category="tax",
            status="disconnected", is_active=False, notes="Sales-tax rate lookup (not yet connected).")

        self.stdout.write(self.style.SUCCESS(
            f"{tenant.name}: seeded advanced 2.6–2.15 (assets/cost/payroll/projects/intercompany/tax/budgets/controls/integrations)"))
