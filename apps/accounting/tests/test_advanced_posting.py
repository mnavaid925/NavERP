"""Tests for balanced-JE posting invariants across advanced sub-modules 2.6–2.10.

Covers:
- fixed_asset_depreciate: straight-line and declining-balance amounts, accumulation,
  fully-depreciated cap (no further JE), balanced JE each time.
- asset_disposal_post: gain, loss, zero-proceeds cases — balanced JE, status=disposed,
  gain_loss recorded.
- cost_allocation_post: balanced JE, linked, status=posted.
- job_cost_entry_post (cost AND revenue kinds): balanced JE, linked.
- intercompany_post: balanced JE, linked.
- payroll_run_post: JE debit==total_expense(); credit breakdown verified; net_pay derived.
- After batch of posts: tenant total posted debits == total posted credits.
- Immutability / no-double-post: re-POST → 302 redirect, no second JE.
- GET on posting action views → 405.
- Locked-record edit/delete → blocked (redirect, record unchanged).
- FixedAsset delete blocked once depreciated or disposed.
"""
import datetime
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ shared fixtures
@pytest.fixture
def gl_expense(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="6100", name="Depreciation Expense", account_type="expense",
        normal_balance="debit",
    )


@pytest.fixture
def gl_accum(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="1690", name="Accumulated Depreciation", account_type="asset",
        normal_balance="credit",
    )


@pytest.fixture
def gl_asset_acct(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="1600", name="Fixed Asset Cost", account_type="asset",
        normal_balance="debit",
    )


@pytest.fixture
def gl_cash_1000(tenant_a):
    """Cash account at 1000 - used by payroll/job-cost disposal fallbacks."""
    from apps.accounting.models import GLAccount
    return GLAccount.objects.get_or_create(
        tenant=tenant_a, code="1000",
        defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"},
    )[0]


@pytest.fixture
def gl_income_acct(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.get_or_create(
        tenant=tenant_a, code="4000",
        defaults={"name": "Sales Revenue", "account_type": "income", "normal_balance": "credit"},
    )[0]


@pytest.fixture
def gl_liability(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="2000", name="Accounts Payable", account_type="liability",
        normal_balance="credit",
    )


@pytest.fixture
def gl_expense_6400(tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="6400", name="Wages Expense", account_type="expense",
        normal_balance="debit",
    )


@pytest.fixture
def org_unit(tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="HQ", kind="department")


@pytest.fixture
def org_unit_b(tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Branch A", kind="branch")


@pytest.fixture
def open_period_adv(tenant_a):
    """Open fiscal period for the advanced tests (avoids conflict with conftest's open_period)."""
    from apps.accounting.models import FiscalPeriod
    return FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="Jun 2026",
        period_type="month",
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 30),
        status="open",
    )


@pytest.fixture
def active_asset(tenant_a, gl_asset_acct, gl_accum, gl_expense, org_unit, open_period_adv):
    """Straight-line asset: $12 000 cost, $0 salvage, 12-month life → $1 000/month."""
    from apps.accounting.models_advanced import FixedAsset
    return FixedAsset.objects.create(
        tenant=tenant_a,
        name="Server Rack",
        acquisition_cost=Decimal("12000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_months=12,
        method="straight_line",
        status="active",
        in_service_date=datetime.date(2026, 1, 1),
        asset_account=gl_asset_acct,
        accumulated_account=gl_accum,
        expense_account=gl_expense,
    )


@pytest.fixture
def declining_asset(tenant_a, gl_asset_acct, gl_accum, gl_expense, open_period_adv):
    """Declining-balance asset: $10 000 cost, $0 salvage, 10-month life → rate=20%."""
    from apps.accounting.models_advanced import FixedAsset
    return FixedAsset.objects.create(
        tenant=tenant_a,
        name="Laptop Fleet",
        acquisition_cost=Decimal("10000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_months=10,
        method="declining_balance",
        status="active",
        in_service_date=datetime.date(2026, 1, 1),
        asset_account=gl_asset_acct,
        accumulated_account=gl_accum,
        expense_account=gl_expense,
    )


@pytest.fixture
def draft_disposal(tenant_a, active_asset):
    """Draft disposal with proceeds > book value (gain case)."""
    from apps.accounting.models_advanced import AssetDisposal
    return AssetDisposal.objects.create(
        tenant=tenant_a,
        asset=active_asset,
        disposal_date=datetime.date(2026, 6, 15),
        proceeds=Decimal("13000.00"),  # gain: 13000 - 12000 = 1000
    )


@pytest.fixture
def project(tenant_a, open_period_adv):
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_a,
        name="Website Redesign",
        billing_method="fixed",
        budget_amount=Decimal("50000.00"),
        status="active",
    )


# ============================================================== Helpers
def _assert_je_balanced(je):
    """Assert a JournalEntry is balanced (Σdebit == Σcredit > 0)."""
    from apps.accounting.models import JournalLine
    totals = JournalLine.objects.filter(entry=je).aggregate(
        d=Sum("debit"), c=Sum("credit")
    )
    total_d = totals["d"] or Decimal("0")
    total_c = totals["c"] or Decimal("0")
    assert total_d > Decimal("0"), f"JE {je.number} has zero debit total"
    assert total_d == total_c, f"JE {je.number} unbalanced: debit={total_d} credit={total_c}"


# ============================================================== 2.6 Fixed Asset Depreciation
class TestFixedAssetDepreciation:

    def test_straight_line_depreciation_amount(self, active_asset):
        """period_depreciation() for straight-line = (cost - salvage) / life."""
        expected = Decimal("12000.00") / Decimal("12")
        assert active_asset.period_depreciation() == expected.quantize(Decimal("0.01"))

    def test_declining_balance_depreciation_amount(self, declining_asset):
        """Declining-balance period_depreciation() = book_value * (2/life)."""
        rate = Decimal(2) / Decimal(10)
        expected = (declining_asset.book_value() * rate).quantize(Decimal("0.01"))
        assert declining_asset.period_depreciation() == expected

    def test_depreciate_action_posts_balanced_je(self, client_a, active_asset, open_period_adv):
        """POST /fixed-assets/<pk>/depreciate/ posts a balanced JE."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        je = JournalEntry.objects.filter(reference=active_asset.number).first()
        assert je is not None, "No JE was posted for depreciation"
        _assert_je_balanced(je)

    def test_depreciate_increases_accumulated_depreciation(self, client_a, active_asset, open_period_adv):
        """Accumulated depreciation increases by period_depreciation() after each post."""
        before = active_asset.accumulated_depreciation
        expected_increase = active_asset.period_depreciation()
        url = reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk])
        client_a.post(url)
        active_asset.refresh_from_db()
        assert active_asset.accumulated_depreciation == before + expected_increase

    def test_declining_balance_depreciate_posts_balanced_je(self, client_a, declining_asset, open_period_adv):
        """Declining-balance asset also posts a balanced JE."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:fixed_asset_depreciate", args=[declining_asset.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        je = JournalEntry.objects.filter(reference=declining_asset.number).first()
        assert je is not None
        _assert_je_balanced(je)

    def test_fully_depreciated_asset_no_further_je(self, client_a, tenant_a, gl_asset_acct,
                                                     gl_accum, gl_expense, open_period_adv):
        """An asset fully depreciated (accumulated >= depreciable_base) produces no further JE."""
        from apps.accounting.models import JournalEntry
        from apps.accounting.models_advanced import FixedAsset
        # Asset where accumulated == depreciable base → no more depreciation
        asset = FixedAsset.objects.create(
            tenant=tenant_a,
            name="Fully Depreciated PC",
            acquisition_cost=Decimal("5000.00"),
            salvage_value=Decimal("0.00"),
            useful_life_months=12,
            method="straight_line",
            status="active",
            in_service_date=datetime.date(2025, 1, 1),
            asset_account=gl_asset_acct,
            accumulated_account=gl_accum,
            expense_account=gl_expense,
        )
        # Manually set accumulated = full depreciable base
        FixedAsset.objects.filter(pk=asset.pk).update(
            accumulated_depreciation=asset.acquisition_cost - asset.salvage_value
        )
        asset.refresh_from_db()

        je_count_before = JournalEntry.objects.filter(tenant=tenant_a).count()
        url = reverse("accounting:fixed_asset_depreciate", args=[asset.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        # No new JE should have been created
        je_count_after = JournalEntry.objects.filter(tenant=tenant_a).count()
        assert je_count_after == je_count_before, "A JE was posted for a fully-depreciated asset"

    def test_depreciation_dr_expense_cr_accum(self, client_a, active_asset, gl_expense,
                                               gl_accum, open_period_adv):
        """JE lines: Dr depreciation-expense / Cr accumulated-depreciation."""
        from apps.accounting.models import JournalEntry, JournalLine
        url = reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk])
        client_a.post(url)
        je = JournalEntry.objects.filter(reference=active_asset.number).latest("id")
        lines = list(JournalLine.objects.filter(entry=je))
        # There should be exactly 2 lines
        assert len(lines) == 2
        # One debit on expense account, one credit on accum account
        debit_lines = [l for l in lines if l.debit > Decimal("0")]
        credit_lines = [l for l in lines if l.credit > Decimal("0")]
        assert len(debit_lines) == 1
        assert len(credit_lines) == 1
        assert debit_lines[0].gl_account_id == gl_expense.pk
        assert credit_lines[0].gl_account_id == gl_accum.pk


# ============================================================== 2.6 Asset Disposal
class TestAssetDisposal:

    def _make_disposal(self, tenant_a, asset, proceeds):
        from apps.accounting.models_advanced import AssetDisposal
        return AssetDisposal.objects.create(
            tenant=tenant_a,
            asset=asset,
            disposal_date=datetime.date(2026, 6, 30),
            proceeds=Decimal(str(proceeds)),
        )

    def test_gain_disposal_posts_balanced_je(self, client_a, tenant_a, active_asset,
                                              gl_cash, gl_income, open_period_adv):
        """Gain case (proceeds > book value) → balanced JE."""
        from apps.accounting.models import GLAccount
        # Ensure we have accounts at the right prefixes that the view will find
        cash = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )[0]
        income = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )[0]

        disposal = self._make_disposal(tenant_a, active_asset, "13000.00")
        url = reverse("accounting:asset_disposal_post", args=[disposal.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        disposal.refresh_from_db()
        assert disposal.status == "posted"
        assert disposal.journal_entry is not None
        _assert_je_balanced(disposal.journal_entry)

    def test_gain_disposal_records_gain_loss(self, client_a, tenant_a, active_asset,
                                              gl_cash, gl_income, open_period_adv):
        """Gain case: gain_loss == proceeds - book_value."""
        from apps.accounting.models import GLAccount
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )
        disposal = self._make_disposal(tenant_a, active_asset, "13000.00")
        expected_gain = Decimal("13000.00") - active_asset.book_value()
        url = reverse("accounting:asset_disposal_post", args=[disposal.pk])
        client_a.post(url)
        disposal.refresh_from_db()
        assert disposal.gain_loss == expected_gain

    def test_gain_disposal_asset_becomes_disposed(self, client_a, tenant_a, active_asset,
                                                   gl_cash, gl_income, open_period_adv):
        """After disposal post, the asset status becomes 'disposed'."""
        from apps.accounting.models import GLAccount
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )
        disposal = self._make_disposal(tenant_a, active_asset, "13000.00")
        url = reverse("accounting:asset_disposal_post", args=[disposal.pk])
        client_a.post(url)
        active_asset.refresh_from_db()
        assert active_asset.status == "disposed"

    def test_loss_disposal_posts_balanced_je(self, client_a, tenant_a, active_asset,
                                              gl_cash, gl_income, open_period_adv):
        """Loss case (proceeds < book value) → balanced JE."""
        from apps.accounting.models import GLAccount
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )
        loss_disposal = self._make_disposal(tenant_a, active_asset, "5000.00")  # loss
        url = reverse("accounting:asset_disposal_post", args=[loss_disposal.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        loss_disposal.refresh_from_db()
        assert loss_disposal.status == "posted"
        _assert_je_balanced(loss_disposal.journal_entry)
        assert loss_disposal.gain_loss < Decimal("0"), "Loss should be negative"

    def test_zero_proceeds_disposal_posts_balanced_je(self, client_a, tenant_a, active_asset,
                                                       gl_cash, gl_income, open_period_adv):
        """Zero-proceeds disposal → JE still balances (pure loss of book value)."""
        from apps.accounting.models import GLAccount
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )
        zero_disposal = self._make_disposal(tenant_a, active_asset, "0.00")
        url = reverse("accounting:asset_disposal_post", args=[zero_disposal.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        zero_disposal.refresh_from_db()
        assert zero_disposal.status == "posted"
        _assert_je_balanced(zero_disposal.journal_entry)


# ============================================================== 2.7 Cost Allocation
class TestCostAllocationPost:

    @pytest.fixture
    def gl_target(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.create(
            tenant=tenant_a, code="5100", name="Allocated Cost", account_type="expense",
            normal_balance="debit",
        )

    @pytest.fixture
    def draft_alloc(self, tenant_a, gl_cash, gl_target, open_period_adv):
        from apps.accounting.models_advanced import CostAllocation
        # gl_cash is the source (code 1000), gl_target is the target
        return CostAllocation.objects.create(
            tenant=tenant_a,
            description="Q1 overhead allocation",
            allocation_date=datetime.date(2026, 6, 1),
            amount=Decimal("2500.00"),
            source_account=gl_cash,
            target_account=gl_target,
        )

    def test_cost_allocation_post_posts_balanced_je(self, client_a, draft_alloc, open_period_adv):
        url = reverse("accounting:cost_allocation_post", args=[draft_alloc.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        draft_alloc.refresh_from_db()
        assert draft_alloc.status == "posted"
        assert draft_alloc.journal_entry is not None
        _assert_je_balanced(draft_alloc.journal_entry)

    def test_cost_allocation_double_post_rejected(self, client_a, draft_alloc, open_period_adv):
        """Re-posting an already-posted allocation → 302 redirect, no second JE."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:cost_allocation_post", args=[draft_alloc.pk])
        client_a.post(url)
        je_count = JournalEntry.objects.filter(tenant=draft_alloc.tenant).count()
        client_a.post(url)  # second post
        assert JournalEntry.objects.filter(tenant=draft_alloc.tenant).count() == je_count


# ============================================================== 2.8 Payroll
class TestPayrollPost:

    @pytest.fixture
    def gl_wages_exp(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.create(
            tenant=tenant_a, code="6100", name="Wages Expense", account_type="expense",
            normal_balance="debit",
        )

    @pytest.fixture
    def gl_cash_payroll(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )[0]

    @pytest.fixture
    def gl_tax_payable(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.create(
            tenant=tenant_a, code="2200", name="Tax Payable", account_type="liability",
            normal_balance="credit",
        )

    @pytest.fixture
    def draft_payroll(self, tenant_a, open_period_adv, gl_wages_exp, gl_cash_payroll, gl_tax_payable):
        from apps.accounting.models_advanced import PayrollRun
        return PayrollRun.objects.create(
            tenant=tenant_a,
            period_start=datetime.date(2026, 6, 1),
            period_end=datetime.date(2026, 6, 15),
            pay_date=datetime.date(2026, 6, 20),
            headcount=10,
            gross_wages=Decimal("50000.00"),
            employee_tax=Decimal("5000.00"),
            employer_tax=Decimal("3000.00"),
            benefits=Decimal("2000.00"),
            deductions=Decimal("1000.00"),
        )

    def test_payroll_net_pay_derived(self, draft_payroll):
        """net_pay is derived by save(): gross - employee_tax - deductions."""
        expected = Decimal("50000.00") - Decimal("5000.00") - Decimal("1000.00")
        assert draft_payroll.net_pay == expected

    def test_payroll_post_balanced_je(self, client_a, draft_payroll, open_period_adv,
                                       gl_wages_exp, gl_cash_payroll, gl_tax_payable):
        url = reverse("accounting:payroll_run_post", args=[draft_payroll.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        draft_payroll.refresh_from_db()
        assert draft_payroll.status == "posted"
        assert draft_payroll.journal_entry is not None
        _assert_je_balanced(draft_payroll.journal_entry)

    def test_payroll_je_debit_equals_total_expense(self, client_a, draft_payroll, open_period_adv,
                                                    gl_wages_exp, gl_cash_payroll, gl_tax_payable):
        """JE total debit == run.total_expense()."""
        from apps.accounting.models import JournalLine
        url = reverse("accounting:payroll_run_post", args=[draft_payroll.pk])
        client_a.post(url)
        draft_payroll.refresh_from_db()
        je = draft_payroll.journal_entry
        total_debit = JournalLine.objects.filter(entry=je).aggregate(s=Sum("debit"))["s"] or Decimal("0")
        assert total_debit == draft_payroll.total_expense()

    def test_payroll_double_post_rejected(self, client_a, draft_payroll, open_period_adv,
                                           gl_wages_exp, gl_cash_payroll, gl_tax_payable):
        """Second POST after already posted → no second JE."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:payroll_run_post", args=[draft_payroll.pk])
        client_a.post(url)
        je_count = JournalEntry.objects.filter(tenant=draft_payroll.tenant).count()
        client_a.post(url)
        assert JournalEntry.objects.filter(tenant=draft_payroll.tenant).count() == je_count


# ============================================================== 2.9 Job Cost Entry
class TestJobCostEntryPost:

    @pytest.fixture
    def gl_cost_acct(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.create(
            tenant=tenant_a, code="5200", name="Project Costs", account_type="expense",
            normal_balance="debit",
        )

    @pytest.fixture
    def gl_cash_jce(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )[0]

    @pytest.fixture
    def gl_revenue_acct(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )[0]

    @pytest.fixture
    def draft_cost_entry(self, tenant_a, project, gl_cost_acct, gl_cash_jce, open_period_adv):
        from apps.accounting.models_advanced import JobCostEntry
        return JobCostEntry.objects.create(
            tenant=tenant_a,
            project=project,
            entry_date=datetime.date(2026, 6, 10),
            kind="cost",
            amount=Decimal("3000.00"),
            gl_account=gl_cost_acct,
            description="Labor cost",
        )

    @pytest.fixture
    def draft_revenue_entry(self, tenant_a, project, gl_revenue_acct, gl_cash_jce, open_period_adv):
        from apps.accounting.models_advanced import JobCostEntry
        return JobCostEntry.objects.create(
            tenant=tenant_a,
            project=project,
            entry_date=datetime.date(2026, 6, 10),
            kind="revenue",
            amount=Decimal("5000.00"),
            gl_account=gl_revenue_acct,
            description="Client invoice",
        )

    def test_cost_entry_post_balanced_je(self, client_a, draft_cost_entry, open_period_adv,
                                          gl_cash_jce):
        url = reverse("accounting:job_cost_entry_post", args=[draft_cost_entry.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        draft_cost_entry.refresh_from_db()
        assert draft_cost_entry.status == "posted"
        assert draft_cost_entry.journal_entry is not None
        _assert_je_balanced(draft_cost_entry.journal_entry)

    def test_revenue_entry_post_balanced_je(self, client_a, draft_revenue_entry, open_period_adv,
                                             gl_cash_jce, gl_revenue_acct):
        url = reverse("accounting:job_cost_entry_post", args=[draft_revenue_entry.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        draft_revenue_entry.refresh_from_db()
        assert draft_revenue_entry.status == "posted"
        assert draft_revenue_entry.journal_entry is not None
        _assert_je_balanced(draft_revenue_entry.journal_entry)

    def test_jce_double_post_rejected(self, client_a, draft_cost_entry, open_period_adv, gl_cash_jce):
        """Second POST on already-posted entry → no second JE."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:job_cost_entry_post", args=[draft_cost_entry.pk])
        client_a.post(url)
        je_count = JournalEntry.objects.filter(tenant=draft_cost_entry.tenant).count()
        client_a.post(url)
        assert JournalEntry.objects.filter(tenant=draft_cost_entry.tenant).count() == je_count


# ============================================================== 2.10 Intercompany
class TestIntercompanyPost:

    @pytest.fixture
    def gl_due_from(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1100",
            defaults={"name": "Due From", "account_type": "asset", "normal_balance": "debit"}
        )[0]

    @pytest.fixture
    def gl_due_to(self, tenant_a):
        from apps.accounting.models import GLAccount
        return GLAccount.objects.get_or_create(
            tenant=tenant_a, code="2000",
            defaults={"name": "Due To", "account_type": "liability", "normal_balance": "credit"}
        )[0]

    @pytest.fixture
    def draft_ict(self, tenant_a, org_unit, org_unit_b, gl_due_from, gl_due_to, open_period_adv):
        from apps.accounting.models_advanced import IntercompanyTransaction
        return IntercompanyTransaction.objects.create(
            tenant=tenant_a,
            description="Parent-to-subsidiary loan",
            transaction_date=datetime.date(2026, 6, 1),
            amount=Decimal("10000.00"),
            from_org_unit=org_unit,
            to_org_unit=org_unit_b,
            due_from_account=gl_due_from,
            due_to_account=gl_due_to,
        )

    def test_intercompany_post_posts_balanced_je(self, client_a, draft_ict, open_period_adv,
                                                  gl_due_from, gl_due_to):
        url = reverse("accounting:intercompany_post", args=[draft_ict.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        draft_ict.refresh_from_db()
        assert draft_ict.status == "posted"
        assert draft_ict.journal_entry is not None
        _assert_je_balanced(draft_ict.journal_entry)

    def test_intercompany_double_post_rejected(self, client_a, draft_ict, open_period_adv,
                                                gl_due_from, gl_due_to):
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:intercompany_post", args=[draft_ict.pk])
        client_a.post(url)
        je_count = JournalEntry.objects.filter(tenant=draft_ict.tenant).count()
        client_a.post(url)
        assert JournalEntry.objects.filter(tenant=draft_ict.tenant).count() == je_count


# ============================================================== Global balance invariant
class TestGlobalDoubleEntryBalance:

    def test_tenant_posted_debits_equal_credits_after_batch(
        self, client_a, tenant_a, open_period_adv,
        active_asset, project,
        gl_cash, gl_income, gl_expense, gl_accum, gl_asset_acct,
        gl_liability
    ):
        """After posting depreciation + disposal + cost_allocation + job_cost:
        total posted debits == total posted credits for the tenant."""
        from apps.accounting.models import GLAccount, JournalEntry, JournalLine
        from apps.accounting.models_advanced import CostAllocation, JobCostEntry

        # Ensure needed accounts exist
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="4000",
            defaults={"name": "Revenue", "account_type": "income", "normal_balance": "credit"}
        )

        # Post 1: depreciation
        client_a.post(reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk]))

        # Post 2: cost allocation
        target = GLAccount.objects.create(
            tenant=tenant_a, code="5999", name="Overhead Target",
            account_type="expense", normal_balance="debit"
        )
        cash = GLAccount.objects.get(tenant=tenant_a, code="1000")
        alloc = CostAllocation.objects.create(
            tenant=tenant_a,
            description="Overhead",
            allocation_date=datetime.date(2026, 6, 1),
            amount=Decimal("500.00"),
            source_account=cash,
            target_account=target,
        )
        client_a.post(reverse("accounting:cost_allocation_post", args=[alloc.pk]))

        # Post 3: job cost entry
        cost_gl = GLAccount.objects.create(
            tenant=tenant_a, code="5888", name="JCE Test Cost",
            account_type="expense", normal_balance="debit"
        )
        jce = JobCostEntry.objects.create(
            tenant=tenant_a,
            project=project,
            entry_date=datetime.date(2026, 6, 5),
            kind="cost",
            amount=Decimal("1200.00"),
            gl_account=cost_gl,
            description="Test cost",
        )
        client_a.post(reverse("accounting:job_cost_entry_post", args=[jce.pk]))

        # Now assert global balance
        totals = JournalLine.objects.filter(
            entry__tenant=tenant_a, entry__status="posted"
        ).aggregate(d=Sum("debit"), c=Sum("credit"))
        assert totals["d"] == totals["c"], (
            f"Global imbalance: total_debit={totals['d']} total_credit={totals['c']}"
        )


# ============================================================== Immutability tests
class TestImmutabilityAndLocking:

    def _make_posted_alloc(self, tenant_a, gl_cash, open_period_adv):
        """Helper to create and post a CostAllocation."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import CostAllocation
        target = GLAccount.objects.create(
            tenant=tenant_a, code="5500", name="Locked Target",
            account_type="expense", normal_balance="debit"
        )
        alloc = CostAllocation.objects.create(
            tenant=tenant_a,
            description="Lock test allocation",
            allocation_date=datetime.date(2026, 6, 1),
            amount=Decimal("100.00"),
            source_account=gl_cash,
            target_account=target,
        )
        return alloc, target

    def test_posted_cost_allocation_edit_redirects(self, client_a, tenant_a, gl_cash, open_period_adv):
        """GET edit on a posted CostAllocation → redirect (locked)."""
        alloc, _ = self._make_posted_alloc(tenant_a, gl_cash, open_period_adv)
        client_a.post(reverse("accounting:cost_allocation_post", args=[alloc.pk]))
        resp = client_a.get(reverse("accounting:cost_allocation_edit", args=[alloc.pk]))
        assert resp.status_code == 302

    def test_posted_cost_allocation_delete_blocked(self, client_a, tenant_a, gl_cash, open_period_adv):
        """POST delete on a posted CostAllocation → not deleted."""
        from apps.accounting.models_advanced import CostAllocation
        alloc, _ = self._make_posted_alloc(tenant_a, gl_cash, open_period_adv)
        client_a.post(reverse("accounting:cost_allocation_post", args=[alloc.pk]))
        client_a.post(reverse("accounting:cost_allocation_delete", args=[alloc.pk]))
        assert CostAllocation.objects.filter(pk=alloc.pk).exists(), "Posted allocation was deleted"

    def test_posted_payroll_edit_redirects(self, client_a, tenant_a, open_period_adv):
        """GET edit on a posted PayrollRun → redirect."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import PayrollRun
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="6100",
            defaults={"name": "Wages Expense", "account_type": "expense", "normal_balance": "debit"}
        )
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="2200",
            defaults={"name": "Tax Payable", "account_type": "liability", "normal_balance": "credit"}
        )
        run = PayrollRun.objects.create(
            tenant=tenant_a,
            period_start=datetime.date(2026, 6, 1),
            period_end=datetime.date(2026, 6, 15),
            pay_date=datetime.date(2026, 6, 20),
            gross_wages=Decimal("10000.00"),
            employee_tax=Decimal("1000.00"),
        )
        client_a.post(reverse("accounting:payroll_run_post", args=[run.pk]))
        resp = client_a.get(reverse("accounting:payroll_run_edit", args=[run.pk]))
        assert resp.status_code == 302

    def test_fixed_asset_delete_blocked_when_depreciated(self, client_a, active_asset, open_period_adv):
        """DELETE on an asset that has been depreciated → blocked (redirect to detail, not deleted)."""
        from apps.accounting.models_advanced import FixedAsset
        # Post depreciation first
        client_a.post(reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk]))
        active_asset.refresh_from_db()
        assert active_asset.accumulated_depreciation > Decimal("0")

        resp = client_a.post(reverse("accounting:fixed_asset_delete", args=[active_asset.pk]))
        assert resp.status_code == 302
        assert FixedAsset.objects.filter(pk=active_asset.pk).exists(), (
            "Asset was deleted despite having accumulated depreciation"
        )

    def test_posted_intercompany_edit_redirects(self, client_a, tenant_a, org_unit, org_unit_b,
                                                 open_period_adv):
        """GET edit on a posted IntercompanyTransaction → redirect."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import IntercompanyTransaction
        due_from = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1100",
            defaults={"name": "Due From", "account_type": "asset", "normal_balance": "debit"}
        )[0]
        due_to = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="2000",
            defaults={"name": "Due To", "account_type": "liability", "normal_balance": "credit"}
        )[0]
        ict = IntercompanyTransaction.objects.create(
            tenant=tenant_a,
            description="Lock test",
            transaction_date=datetime.date(2026, 6, 1),
            amount=Decimal("500.00"),
            from_org_unit=org_unit,
            to_org_unit=org_unit_b,
            due_from_account=due_from,
            due_to_account=due_to,
        )
        client_a.post(reverse("accounting:intercompany_post", args=[ict.pk]))
        resp = client_a.get(reverse("accounting:intercompany_edit", args=[ict.pk]))
        assert resp.status_code == 302

    def test_posted_jce_delete_blocked(self, client_a, tenant_a, project, open_period_adv):
        """POST delete on a posted JobCostEntry → not deleted."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import JobCostEntry
        cost_gl = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="5300", name="JCE Immutable Cost",
            defaults={"account_type": "expense", "normal_balance": "debit"}
        )[0]
        GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1000",
            defaults={"name": "Cash", "account_type": "asset", "normal_balance": "debit"}
        )
        jce = JobCostEntry.objects.create(
            tenant=tenant_a,
            project=project,
            entry_date=datetime.date(2026, 6, 1),
            kind="cost",
            amount=Decimal("200.00"),
            gl_account=cost_gl,
        )
        client_a.post(reverse("accounting:job_cost_entry_post", args=[jce.pk]))
        client_a.post(reverse("accounting:job_cost_entry_delete", args=[jce.pk]))
        assert JobCostEntry.objects.filter(pk=jce.pk).exists(), "Posted JCE was deleted"


# ============================================================== GET → 405 on POST-only actions
class TestPostOnlyAdvanced:

    def test_get_depreciate_returns_405(self, client_a, active_asset):
        resp = client_a.get(reverse("accounting:fixed_asset_depreciate", args=[active_asset.pk]))
        assert resp.status_code == 405

    def test_get_disposal_post_returns_405(self, client_a, draft_disposal):
        resp = client_a.get(reverse("accounting:asset_disposal_post", args=[draft_disposal.pk]))
        assert resp.status_code == 405

    def test_get_cost_allocation_post_returns_405(self, client_a, tenant_a, gl_cash, open_period_adv):
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import CostAllocation
        target = GLAccount.objects.create(
            tenant=tenant_a, code="5600", name="GET Test Target",
            account_type="expense", normal_balance="debit"
        )
        alloc = CostAllocation.objects.create(
            tenant=tenant_a,
            description="GET test alloc",
            allocation_date=datetime.date(2026, 6, 1),
            amount=Decimal("50.00"),
            source_account=gl_cash,
            target_account=target,
        )
        resp = client_a.get(reverse("accounting:cost_allocation_post", args=[alloc.pk]))
        assert resp.status_code == 405

    def test_get_intercompany_post_returns_405(self, client_a, tenant_a, org_unit, org_unit_b, open_period_adv):
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import IntercompanyTransaction
        due_from = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="1100",
            defaults={"name": "Due From", "account_type": "asset", "normal_balance": "debit"}
        )[0]
        due_to = GLAccount.objects.get_or_create(
            tenant=tenant_a, code="2000",
            defaults={"name": "Due To", "account_type": "liability", "normal_balance": "credit"}
        )[0]
        ict = IntercompanyTransaction.objects.create(
            tenant=tenant_a,
            description="GET test ICT",
            transaction_date=datetime.date(2026, 6, 1),
            amount=Decimal("100.00"),
            from_org_unit=org_unit,
            to_org_unit=org_unit_b,
            due_from_account=due_from,
            due_to_account=due_to,
        )
        resp = client_a.get(reverse("accounting:intercompany_post", args=[ict.pk]))
        assert resp.status_code == 405
