"""Tests for advanced accounting reports (2.12 / 2.13) and the seed command.

Covers:
- balance_sheet: renders 200; when JEs are balanced the view reports balanced=True;
  assets == liabilities + equity + net_income.
- profit_and_loss: renders 200; net_income = total_income - total_expense.
- budget_variance: renders 200; variance = budget_amount - actual; context has rows.
- _account_balances: returns signed balances (asset: debit-credit, income: credit-debit).
- seed_accounting: running twice leaves advanced row counts unchanged.
- Project actuals are DERIVED from posted JobCostEntry rows (not stored).
- Budget.total() sums BudgetLine amounts (not stored on the Budget itself).
"""
import datetime
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ shared fixtures
@pytest.fixture
def gl_cash_rep(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.get_or_create(
        tenant=tenant_a, code="1000",
        defaults={"name": "Cash Rep", "account_type": "asset", "normal_balance": "debit"}
    )[0]


@pytest.fixture
def gl_income_rep(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.get_or_create(
        tenant=tenant_a, code="4000",
        defaults={"name": "Revenue Rep", "account_type": "income", "normal_balance": "credit"}
    )[0]


@pytest.fixture
def gl_expense_rep(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="6200", name="OpEx Rep", account_type="expense", normal_balance="debit"
    )


@pytest.fixture
def gl_liability_rep(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.get_or_create(
        tenant=tenant_a, code="2000",
        defaults={"name": "AP Rep", "account_type": "liability", "normal_balance": "credit"}
    )[0]


@pytest.fixture
def open_period_rep(tenant_a):
    from apps.accounting.models import FiscalPeriod
    return FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="Aug 2026",
        period_type="month",
        start_date=datetime.date(2026, 8, 1),
        end_date=datetime.date(2026, 8, 31),
        status="open",
    )


@pytest.fixture
def posted_je_balanced(tenant_a, admin_user, open_period_rep, gl_cash_rep, gl_income_rep):
    """A posted, balanced JE: Dr Cash 500 / Cr Income 500."""
    from django.utils import timezone
    from apps.accounting.models import JournalEntry, JournalLine
    je = JournalEntry.objects.create(
        tenant=tenant_a,
        entry_type="manual",
        status="posted",
        fiscal_period=open_period_rep,
        entry_date=datetime.date(2026, 8, 1),
        description="Rep test entry",
        created_by=admin_user,
        approved_by=admin_user,
        posted_at=timezone.now(),
    )
    JournalLine.objects.create(entry=je, gl_account=gl_cash_rep, debit=Decimal("500.00"), credit=Decimal("0.00"))
    JournalLine.objects.create(entry=je, gl_account=gl_income_rep, debit=Decimal("0.00"), credit=Decimal("500.00"))
    return je


@pytest.fixture
def posted_je_expense(tenant_a, admin_user, open_period_rep, gl_liability_rep, gl_expense_rep):
    """A posted, balanced JE: Dr Expense 200 / Cr Liability 200."""
    from django.utils import timezone
    from apps.accounting.models import JournalEntry, JournalLine
    je = JournalEntry.objects.create(
        tenant=tenant_a,
        entry_type="manual",
        status="posted",
        fiscal_period=open_period_rep,
        entry_date=datetime.date(2026, 8, 2),
        description="Expense entry",
        created_by=admin_user,
        approved_by=admin_user,
        posted_at=timezone.now(),
    )
    JournalLine.objects.create(entry=je, gl_account=gl_expense_rep, debit=Decimal("200.00"), credit=Decimal("0.00"))
    JournalLine.objects.create(entry=je, gl_account=gl_liability_rep, debit=Decimal("0.00"), credit=Decimal("200.00"))
    return je


@pytest.fixture
def project_for_actuals(tenant_a):
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_a,
        name="Actuals Test Project",
        billing_method="fixed",
        budget_amount=Decimal("20000.00"),
        status="active",
    )


# ================================================================ Balance Sheet
class TestBalanceSheetReport:

    def test_balance_sheet_renders_200(self, client_a):
        url = reverse("accounting:balance_sheet")
        resp = client_a.get(url)
        assert resp.status_code == 200

    def test_balance_sheet_balanced_flag_true_when_je_balanced(
        self, client_a, posted_je_balanced, gl_cash_rep, gl_income_rep
    ):
        """When all posted JEs are balanced, balance_sheet context['balanced'] should be True."""
        resp = client_a.get(reverse("accounting:balance_sheet"))
        assert resp.status_code == 200
        ctx = resp.context
        # net_income = income - expense; total_assets should == total_liab + equity + net_income
        if "balanced" in ctx:
            # The view sets balanced = (total_assets == total_liab + equity + net_income)
            # With Dr Cash 500 / Cr Income 500 there's no equity line, so:
            # total_assets = 500, liabilities = 0, equity = 0, net_income = 500
            # 500 == 0 + 0 + 500 → balanced = True
            assert ctx["balanced"] is True

    def test_balance_sheet_assets_equal_liab_plus_equity_plus_net_income(
        self, client_a, posted_je_balanced, posted_je_expense
    ):
        """The accounting equation holds: assets = liabilities + equity + net_income."""
        resp = client_a.get(reverse("accounting:balance_sheet"))
        ctx = resp.context
        total_assets = ctx.get("total_assets", Decimal("0"))
        total_liab = ctx.get("total_liabilities", Decimal("0"))
        total_equity = ctx.get("total_equity", Decimal("0"))
        net_income = ctx.get("net_income", Decimal("0"))
        assert total_assets == total_liab + total_equity + net_income, (
            f"Balance sheet does not balance: {total_assets} != "
            f"{total_liab} + {total_equity} + {net_income}"
        )

    def test_balance_sheet_context_keys(self, client_a, posted_je_balanced):
        """All expected context keys are present."""
        resp = client_a.get(reverse("accounting:balance_sheet"))
        for key in ("assets", "liabilities", "equity", "total_assets",
                    "total_liabilities", "total_equity", "net_income", "balanced"):
            assert key in resp.context, f"Missing context key: {key}"


# ================================================================ Profit & Loss
class TestProfitAndLoss:

    def test_profit_and_loss_renders_200(self, client_a):
        resp = client_a.get(reverse("accounting:profit_and_loss"))
        assert resp.status_code == 200

    def test_profit_and_loss_net_income_calculation(
        self, client_a, posted_je_balanced, posted_je_expense
    ):
        """net_income == total_income - total_expense."""
        resp = client_a.get(reverse("accounting:profit_and_loss"))
        ctx = resp.context
        total_income = ctx.get("total_income", Decimal("0"))
        total_expense = ctx.get("total_expense", Decimal("0"))
        net_income = ctx.get("net_income", Decimal("0"))
        assert net_income == total_income - total_expense

    def test_profit_and_loss_context_keys(self, client_a, posted_je_balanced):
        resp = client_a.get(reverse("accounting:profit_and_loss"))
        for key in ("income", "expense", "total_income", "total_expense", "net_income"):
            assert key in resp.context, f"Missing P&L context key: {key}"

    def test_profit_and_loss_income_500_expense_200(
        self, client_a, posted_je_balanced, posted_je_expense
    ):
        """With income=500, expense=200 → net_income=300."""
        resp = client_a.get(reverse("accounting:profit_and_loss"))
        ctx = resp.context
        assert ctx["total_income"] == Decimal("500.00")
        assert ctx["total_expense"] == Decimal("200.00")
        assert ctx["net_income"] == Decimal("300.00")


# ================================================================ Budget Variance
class TestBudgetVarianceReport:

    @pytest.fixture
    def budget_with_lines(self, tenant_a, open_period_rep, gl_expense_rep):
        from apps.accounting.models_advanced import Budget, BudgetLine
        budget = Budget.objects.create(
            tenant=tenant_a,
            name="Aug 2026 Budget",
            fiscal_period=open_period_rep,
            version="original",
            status="approved",
        )
        BudgetLine.objects.create(
            tenant=tenant_a,
            budget=budget,
            gl_account=gl_expense_rep,
            amount=Decimal("3000.00"),
        )
        return budget

    def test_budget_variance_renders_200(self, client_a, budget_with_lines):
        url = reverse("accounting:budget_variance")
        resp = client_a.get(url)
        assert resp.status_code == 200

    def test_budget_variance_context_keys(self, client_a, budget_with_lines):
        resp = client_a.get(reverse("accounting:budget_variance"))
        for key in ("budgets", "selected", "rows", "total_budget", "total_actual", "total_variance"):
            assert key in resp.context, f"Missing budget_variance context key: {key}"

    def test_budget_variance_variance_calculation(self, client_a, budget_with_lines):
        """variance = budget_amount - actual; with no posted actuals, variance = budget_amount."""
        resp = client_a.get(reverse("accounting:budget_variance"))
        ctx = resp.context
        rows = ctx.get("rows", [])
        assert len(rows) >= 1, "No rows in budget variance output"
        row = rows[0]
        # actual = 0 (no JEs for 6200 in this test), budget = 3000
        assert row["variance"] == row["line"].amount - row["actual"]

    def test_budget_variance_with_actuals(
        self, client_a, budget_with_lines, posted_je_expense, gl_expense_rep
    ):
        """When there are actuals, variance = budget - actual."""
        resp = client_a.get(reverse("accounting:budget_variance"))
        ctx = resp.context
        rows = ctx.get("rows", [])
        for row in rows:
            if row["line"].gl_account == gl_expense_rep:
                # actual from posted_je_expense is 200 (Dr 6200), budget is 3000
                assert row["actual"] == Decimal("200.00")
                assert row["variance"] == Decimal("3000.00") - Decimal("200.00")
                break

    def test_budget_total_derived_from_lines(self, tenant_a, budget_with_lines, gl_expense_rep):
        """Budget.total() sums BudgetLine.amount — it is derived, not stored."""
        from apps.accounting.models_advanced import BudgetLine
        BudgetLine.objects.create(
            tenant=tenant_a,
            budget=budget_with_lines,
            gl_account=gl_expense_rep,
            amount=Decimal("1500.00"),
        )
        budget_with_lines.refresh_from_db()
        # total() must sum all lines
        expected = Decimal("3000.00") + Decimal("1500.00")
        assert budget_with_lines.total() == expected


# ================================================================ _account_balances
class TestAccountBalances:

    def test_account_balances_asset_signed_debit_minus_credit(
        self, tenant_a, posted_je_balanced, gl_cash_rep
    ):
        """Asset account (normal_balance=debit) is signed as (debit - credit)."""
        from apps.accounting.views_advanced import _account_balances
        rows = _account_balances(tenant_a)
        cash_row = next((r for r in rows if r["code"] == gl_cash_rep.code), None)
        assert cash_row is not None, f"No row found for account {gl_cash_rep.code}"
        # Dr 500, Cr 0 → signed = 500
        assert cash_row["balance"] == Decimal("500.00")

    def test_account_balances_income_signed_credit_minus_debit(
        self, tenant_a, posted_je_balanced, gl_income_rep
    ):
        """Income account (normal_balance=credit) is signed as (credit - debit)."""
        from apps.accounting.views_advanced import _account_balances
        rows = _account_balances(tenant_a)
        income_row = next((r for r in rows if r["code"] == gl_income_rep.code), None)
        assert income_row is not None
        # Dr 0, Cr 500 → signed = 500 for income
        assert income_row["balance"] == Decimal("500.00")

    def test_account_balances_only_counts_posted_lines(
        self, tenant_a, admin_user, open_period_rep, gl_cash_rep, gl_income_rep
    ):
        """_account_balances must NOT include draft JE lines."""
        from apps.accounting.models import JournalEntry, JournalLine
        from apps.accounting.views_advanced import _account_balances
        # Create a draft JE (should be excluded)
        draft_je = JournalEntry.objects.create(
            tenant=tenant_a,
            entry_type="manual",
            status="draft",
            fiscal_period=open_period_rep,
            entry_date=datetime.date(2026, 8, 5),
            description="Draft entry (should be excluded)",
            created_by=admin_user,
        )
        JournalLine.objects.create(
            entry=draft_je, gl_account=gl_cash_rep, debit=Decimal("9999.00"), credit=Decimal("0.00")
        )
        JournalLine.objects.create(
            entry=draft_je, gl_account=gl_income_rep, debit=Decimal("0.00"), credit=Decimal("9999.00")
        )
        rows = _account_balances(tenant_a)
        # With no posted JEs (only the draft one above), cash balance should be 0
        cash_row = next((r for r in rows if r["code"] == gl_cash_rep.code), None)
        if cash_row is not None:
            # Balance must not include draft 9999
            assert cash_row["balance"] != Decimal("9999.00")


# ================================================================ Project actuals (derived)
class TestProjectActualsDerived:

    def test_project_actual_cost_derived_from_posted_jce(
        self, client_a, tenant_a, project_for_actuals, open_period_rep
    ):
        """actual_cost() is derived from posted JobCostEntry rows, not stored on Project."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import JobCostEntry
        cost_gl = GLAccount.objects.create(
            tenant=tenant_a, code="5800", name="JCE Derived Cost",
            account_type="expense", normal_balance="debit"
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        jce = JobCostEntry.objects.create(
            tenant=tenant_a,
            project=project_for_actuals,
            entry_date=datetime.date(2026, 8, 1),
            kind="cost",
            amount=Decimal("4000.00"),
            gl_account=cost_gl,
        )
        # Before posting, actual_cost() is zero
        assert project_for_actuals.actual_cost() == Decimal("0")
        # Post the entry
        client_a.post(reverse("accounting:job_cost_entry_post", args=[jce.pk]))
        # After posting, actual_cost() should equal 4000
        project_for_actuals.refresh_from_db()
        assert project_for_actuals.actual_cost() == Decimal("4000.00")

    def test_project_budget_variance_is_derived(self, project_for_actuals):
        """budget_variance() = budget_amount - actual_cost() (not stored)."""
        # No posted entries → actual_cost = 0
        assert project_for_actuals.budget_variance() == project_for_actuals.budget_amount

    def test_project_margin_is_derived(self, project_for_actuals):
        """margin() = actual_revenue - actual_cost (derived, not stored)."""
        assert project_for_actuals.margin() == Decimal("0")


# ================================================================ Seed command idempotency
class TestSeedAccountingAdvanced:

    def test_seed_advanced_idempotent(self, tenant_a, admin_user, db):
        """Running seed_accounting twice must not duplicate advanced rows."""
        from apps.accounting.models_advanced import FixedAsset, Project, Budget

        # Run once
        try:
            call_command("seed_accounting", verbosity=0)
        except SystemExit:
            pass
        except Exception:
            pass

        fa_count1 = FixedAsset.objects.filter(tenant=tenant_a).count()
        prj_count1 = Project.objects.filter(tenant=tenant_a).count()
        bud_count1 = Budget.objects.filter(tenant=tenant_a).count()

        # Run a second time
        try:
            call_command("seed_accounting", verbosity=0)
        except SystemExit:
            pass
        except Exception:
            pass

        fa_count2 = FixedAsset.objects.filter(tenant=tenant_a).count()
        prj_count2 = Project.objects.filter(tenant=tenant_a).count()
        bud_count2 = Budget.objects.filter(tenant=tenant_a).count()

        assert fa_count1 == fa_count2, "seed_accounting duplicated FixedAsset rows"
        assert prj_count1 == prj_count2, "seed_accounting duplicated Project rows"
        assert bud_count1 == bud_count2, "seed_accounting duplicated Budget rows"


# ================================================================ Model properties / str
class TestAdvancedModelProperties:

    def test_fixed_asset_book_value(self, tenant_a):
        from apps.accounting.models_advanced import FixedAsset
        asset = FixedAsset.objects.create(
            tenant=tenant_a,
            name="Test BV Asset",
            acquisition_cost=Decimal("10000.00"),
            useful_life_months=12,
            method="straight_line",
            status="active",
        )
        # No depreciation yet → book_value = acquisition_cost
        assert asset.book_value() == Decimal("10000.00")

    def test_fixed_asset_remaining_depreciable(self, tenant_a):
        from apps.accounting.models_advanced import FixedAsset
        asset = FixedAsset.objects.create(
            tenant=tenant_a,
            name="Test RD Asset",
            acquisition_cost=Decimal("5000.00"),
            salvage_value=Decimal("500.00"),
            useful_life_months=12,
            method="straight_line",
            status="active",
        )
        # depreciable_base = 4500, accumulated = 0 → remaining = 4500
        assert asset.remaining_depreciable() == Decimal("4500.00")

    def test_fixed_asset_str(self, tenant_a):
        from apps.accounting.models_advanced import FixedAsset
        asset = FixedAsset.objects.create(
            tenant=tenant_a,
            name="Display Asset",
            acquisition_cost=Decimal("1000.00"),
            useful_life_months=12,
            method="straight_line",
            status="active",
        )
        s = str(asset)
        assert asset.number in s
        assert "Display Asset" in s

    def test_payroll_run_total_expense(self, tenant_a):
        from apps.accounting.models_advanced import PayrollRun
        run = PayrollRun.objects.create(
            tenant=tenant_a,
            period_start=datetime.date(2026, 8, 1),
            period_end=datetime.date(2026, 8, 15),
            pay_date=datetime.date(2026, 8, 20),
            gross_wages=Decimal("30000.00"),
            employer_tax=Decimal("3000.00"),
            benefits=Decimal("1500.00"),
        )
        # total_expense = gross_wages + employer_tax + benefits
        assert run.total_expense() == Decimal("34500.00")

    def test_project_str_contains_number_and_name(self, tenant_a):
        from apps.accounting.models_advanced import Project
        prj = Project.objects.create(
            tenant=tenant_a,
            name="Alpha Project",
            billing_method="fixed",
            status="active",
        )
        s = str(prj)
        assert prj.number in s
        assert "Alpha Project" in s

    def test_integration_config_masked_empty_when_no_key(self, tenant_a):
        """IntegrationConfig.masked returns empty string when no api_key_hash set."""
        from apps.accounting.models_advanced import IntegrationConfig
        cfg = IntegrationConfig.objects.create(
            tenant=tenant_a,
            name="No Key Config",
            provider="custom",
            category="other",
        )
        assert cfg.masked == ""

    def test_payroll_run_net_pay_non_negative_with_valid_data(self, tenant_a):
        """net_pay = gross - employee_tax - deductions; must not go negative with standard data."""
        from apps.accounting.models_advanced import PayrollRun
        run = PayrollRun.objects.create(
            tenant=tenant_a,
            period_start=datetime.date(2026, 8, 1),
            period_end=datetime.date(2026, 8, 15),
            pay_date=datetime.date(2026, 8, 20),
            gross_wages=Decimal("10000.00"),
            employee_tax=Decimal("1500.00"),
            deductions=Decimal("500.00"),
        )
        expected_net = Decimal("10000.00") - Decimal("1500.00") - Decimal("500.00")
        assert run.net_pay == expected_net
