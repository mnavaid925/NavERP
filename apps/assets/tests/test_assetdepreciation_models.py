"""Asset Depreciation & Financial Management (11.4) — MODEL Invariants Test Suite.

Covers the 4 core models:
- AssetDepreciationSchedule [ADEP-]
- AssetRevaluation [AREV-]
- AssetTransfer [AXFR-]
- CapitalizationPolicy [ACTH-]

Invariants pinned:
1. String representations (__str__) for all 4 models.
2. Auto-number generation and collision-free prefixing (ADEP, AREV, AXFR, ACTH).
3. Status choices, method choices, and CSS badge mappings conforming to theme.css classes.
4. Depreciation calculations: straight-line, declining balance (150% & 200%), sum-of-years digits, units-of-production, and salvage-value capping.
5. Preservation of manual depreciation override unless force=True.
6. Depreciation GL posting (post_to_gl) creating balanced JournalEntry (Dr Expense / Cr Acc. Depr.) and updating FixedAsset.
7. Validation errors on post_to_gl (missing GL accounts, re-posting prevention, zero/negative charges).
8. Revaluation adjustment calculation (calculate_adjustment) for both upward step-up and impairment loss.
9. Revaluation execution (execute_revaluation) generating balanced GL entries and updating FixedAsset prospective params.
10. Validation errors on execute_revaluation (missing GL accounts, already approved guard).
11. Transfer lifecycle: capture_carrying_value, dispatch_transfer (in_transit), and complete_transfer updating FixedAsset and scm.Asset.
12. Capitalization policy evaluation (evaluate_asset): cost/life threshold compliance, de minimis safe harbor, and input guarding.
13. Model full_clean() validation and tenant isolation constraints.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import FixedAsset, GLAccount, JournalEntry
from apps.assets.models import (
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, Location


def _assetdepreciation_allowed_badge_classes():
    """Return the set of valid colour-named theme.css badge classes."""
    return {
        "badge-green",
        "badge-red",
        "badge-amber",
        "badge-info",
        "badge-muted",
        "badge-slate",
        "badge-purple",
    }


# ==============================================================================
# Local Fixture Overrides (exact schema alignment for 11.4 models)
# ==============================================================================


@pytest.fixture
def depreciation_schedule_a(db, tenant_a, fixed_asset_a, operational_asset_a, expense_account_a, accum_account_a):
    """Clean draft depreciation schedule for tenant_a."""
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        schedule_date=timezone.now().date(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        ending_book_value=Decimal("118200.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="draft",
    )


@pytest.fixture
def transfer_a(db, tenant_a, fixed_asset_a, operational_asset_a, location_a, location_a2, org_unit_a, vendor_party_a, admin_user):
    """Clean draft asset transfer order for tenant_a."""
    return AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Inter-Facility Transfer CNC Mill",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        transfer_type="inter_facility",
        transfer_date=timezone.now().date(),
        source_location=location_a,
        destination_location=location_a2,
        source_department=org_unit_a,
        source_custodian=vendor_party_a,
        transferred_by=admin_user,
        transportation_cost=Decimal("750.00"),
        status="draft",
    )


# ==============================================================================
# 1. String Representations (__str__)
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_schedule_str(depreciation_schedule_a):
    """AssetDepreciationSchedule __str__ format is '{number} - {fixed_asset.name} (FY{year} P{period})'."""
    expected = (
        f"{depreciation_schedule_a.number} - {depreciation_schedule_a.fixed_asset.name} "
        f"(FY{depreciation_schedule_a.fiscal_year} P{depreciation_schedule_a.period_number})"
    )
    assert str(depreciation_schedule_a) == expected
    assert depreciation_schedule_a.number in str(depreciation_schedule_a)
    assert depreciation_schedule_a.fixed_asset.name in str(depreciation_schedule_a)


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_str(revaluation_a):
    """AssetRevaluation __str__ format is '{number} - {title} ({event_type_display})'."""
    expected = f"{revaluation_a.number} - {revaluation_a.title} ({revaluation_a.get_event_type_display()})"
    assert str(revaluation_a) == expected
    assert revaluation_a.number in str(revaluation_a)
    assert revaluation_a.title in str(revaluation_a)


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_str(transfer_a):
    """AssetTransfer __str__ format is '{number} - {title} ({transfer_type_display})'."""
    expected = f"{transfer_a.number} - {transfer_a.title} ({transfer_a.get_transfer_type_display()})"
    assert str(transfer_a) == expected
    assert transfer_a.number in str(transfer_a)
    assert transfer_a.title in str(transfer_a)


@pytest.mark.django_db
def test_assetdepreciation_models_policy_str(capitalization_policy_a):
    """CapitalizationPolicy __str__ format is '{number} - {name} (${threshold:,.2f})'."""
    expected = f"{capitalization_policy_a.number} - {capitalization_policy_a.name} (${capitalization_policy_a.minimum_cost_threshold:,.2f})"
    assert str(capitalization_policy_a) == expected
    assert capitalization_policy_a.number in str(capitalization_policy_a)
    assert capitalization_policy_a.name in str(capitalization_policy_a)


# ==============================================================================
# 2. Number Sequence & Prefix Integrity
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_schedule_number_prefix_and_sequence(tenant_a, fixed_asset_a):
    """AssetDepreciationSchedule auto-generates sequential unique numbers prefixed with ADEP-."""
    s1 = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
    )
    s2 = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=2,
    )
    assert s1.number.startswith("ADEP-")
    assert s2.number.startswith("ADEP-")
    assert s1.number != s2.number


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_number_prefix_and_sequence(tenant_a, fixed_asset_a):
    """AssetRevaluation auto-generates sequential unique numbers prefixed with AREV-."""
    r1 = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Mid-Year Impairment Review 1",
        fixed_asset=fixed_asset_a,
    )
    r2 = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Mid-Year Impairment Review 2",
        fixed_asset=fixed_asset_a,
    )
    assert r1.number.startswith("AREV-")
    assert r2.number.startswith("AREV-")
    assert r1.number != r2.number


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_number_prefix_and_sequence(tenant_a, fixed_asset_a):
    """AssetTransfer auto-generates sequential unique numbers prefixed with AXFR-."""
    t1 = AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Plant Relocation Phase 1",
        fixed_asset=fixed_asset_a,
    )
    t2 = AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Plant Relocation Phase 2",
        fixed_asset=fixed_asset_a,
    )
    assert t1.number.startswith("AXFR-")
    assert t2.number.startswith("AXFR-")
    assert t1.number != t2.number


@pytest.mark.django_db
def test_assetdepreciation_models_policy_number_prefix_and_sequence(tenant_a):
    """CapitalizationPolicy auto-generates sequential unique numbers prefixed with ACTH-."""
    p1 = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Global CapEx Standard",
        policy_scope="global_default",
    )
    p2 = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Project Specific CapEx",
        policy_scope="project_capex",
    )
    assert p1.number.startswith("ACTH-")
    assert p2.number.startswith("ACTH-")
    assert p1.number != p2.number


# ==============================================================================
# 3. Choices & CSS Badge Mapping Invariants
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_schedule_status_and_method_choices_and_css(depreciation_schedule_a):
    """AssetDepreciationSchedule STATUS_CSS and METHOD_CSS map exclusively to valid theme.css classes."""
    valid_badges = _assetdepreciation_allowed_badge_classes()
    status_keys = {k for k, _ in AssetDepreciationSchedule.STATUS_CHOICES}
    assert status_keys == {"draft", "calculated", "posted", "superseded", "cancelled"}

    for status_key, badge_class in AssetDepreciationSchedule.STATUS_CSS.items():
        assert badge_class in valid_badges, f"Invalid CSS badge '{badge_class}' in STATUS_CSS"
        assert status_key in status_keys

    method_keys = {k for k, _ in AssetDepreciationSchedule.METHOD_CHOICES}
    assert method_keys == {
        "straight_line",
        "declining_balance_150",
        "declining_balance_200",
        "sum_of_years",
        "units_of_production",
    }

    for method_key, badge_class in AssetDepreciationSchedule.METHOD_CSS.items():
        assert badge_class in valid_badges, f"Invalid CSS badge '{badge_class}' in METHOD_CSS"
        assert method_key in method_keys

    depreciation_schedule_a.status = "posted"
    assert depreciation_schedule_a.status_css == "badge-green"

    depreciation_schedule_a.status = "unknown_status"
    assert depreciation_schedule_a.status_css == "badge-slate"

    depreciation_schedule_a.depreciation_method = "declining_balance_200"
    assert depreciation_schedule_a.method_css == "badge-slate"

    depreciation_schedule_a.depreciation_method = "unknown_method"
    assert depreciation_schedule_a.method_css == "badge-slate"


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_choices_and_css(revaluation_a):
    """AssetRevaluation STATUS_CSS and EVENT_TYPE_CSS map exclusively to valid theme.css classes."""
    valid_badges = _assetdepreciation_allowed_badge_classes()
    status_keys = {k for k, _ in AssetRevaluation.STATUS_CHOICES}
    assert status_keys == {"draft", "submitted", "approved", "rejected"}

    for status_key, badge_class in AssetRevaluation.STATUS_CSS.items():
        assert badge_class in valid_badges
        assert status_key in status_keys

    event_keys = {k for k, _ in AssetRevaluation.EVENT_TYPE_CHOICES}
    assert event_keys == {"impairment", "revaluation_up", "reversal_impairment", "salvage_revision"}

    for event_key, badge_class in AssetRevaluation.EVENT_TYPE_CSS.items():
        assert badge_class in valid_badges
        assert event_key in event_keys

    revaluation_a.status = "approved"
    assert revaluation_a.status_css == "badge-green"
    revaluation_a.status = "unknown"
    assert revaluation_a.status_css == "badge-slate"

    revaluation_a.event_type = "impairment"
    assert revaluation_a.event_type_css == "badge-red"
    revaluation_a.event_type = "unknown"
    assert revaluation_a.event_type_css == "badge-slate"


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_choices_and_css(transfer_a):
    """AssetTransfer STATUS_CSS and TRANSFER_TYPE_CSS map exclusively to valid theme.css classes."""
    valid_badges = _assetdepreciation_allowed_badge_classes()
    status_keys = {k for k, _ in AssetTransfer.STATUS_CHOICES}
    assert status_keys == {"draft", "in_transit", "completed", "rejected"}

    for status_key, badge_class in AssetTransfer.STATUS_CSS.items():
        assert badge_class in valid_badges
        assert status_key in status_keys

    type_keys = {k for k, _ in AssetTransfer.TRANSFER_TYPE_CHOICES}
    assert type_keys == {
        "cost_center",
        "inter_department",
        "inter_facility",
        "custodian_reassignment",
        "inter_company",
    }

    for type_key, badge_class in AssetTransfer.TRANSFER_TYPE_CSS.items():
        assert badge_class in valid_badges
        assert type_key in type_keys

    transfer_a.status = "in_transit"
    assert transfer_a.status_css == "badge-amber"
    transfer_a.status = "unknown"
    assert transfer_a.status_css == "badge-slate"

    transfer_a.transfer_type = "custodian_reassignment"
    assert transfer_a.transfer_type_css == "badge-amber"
    transfer_a.transfer_type = "unknown"
    assert transfer_a.transfer_type_css == "badge-slate"


@pytest.mark.django_db
def test_assetdepreciation_models_policy_choices_and_css(capitalization_policy_a):
    """CapitalizationPolicy STATUS_CSS and SCOPE_CSS map exclusively to valid theme.css classes."""
    valid_badges = _assetdepreciation_allowed_badge_classes()
    scope_keys = {k for k, _ in CapitalizationPolicy.POLICY_SCOPE_CHOICES}
    assert scope_keys == {"global_default", "category_override", "tax_book_safe_harbor", "project_capex"}

    for scope_key, badge_class in CapitalizationPolicy.SCOPE_CSS.items():
        assert badge_class in valid_badges
        assert scope_key in scope_keys

    capitalization_policy_a.is_active = True
    assert capitalization_policy_a.status_css == "badge-green"

    capitalization_policy_a.is_active = False
    assert capitalization_policy_a.status_css == "badge-muted"

    capitalization_policy_a.policy_scope = "tax_book_safe_harbor"
    assert capitalization_policy_a.scope_css == "badge-amber"

    capitalization_policy_a.policy_scope = "unknown"
    assert capitalization_policy_a.scope_css == "badge-slate"


# ==============================================================================
# 4. Depreciation Calculation Engine
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_straight_line_monthly(tenant_a, fixed_asset_a):
    """Straight-line monthly depreciation computes exact (cost - salvage) / life."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="straight_line",
        status="draft",
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("1800.00")
    assert sched.depreciation_amount == Decimal("1800.00")
    assert sched.starting_book_value == Decimal("120000.00")
    assert sched.accumulated_depreciation_after == Decimal("1800.00")
    assert sched.ending_book_value == Decimal("118200.00")
    assert sched.status == "calculated"


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_straight_line_frequencies(tenant_a, fixed_asset_a):
    """Straight-line computes quarterly (x3) and annual (x12) factors correctly."""
    sched_q = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="quarterly",
        depreciation_method="straight_line",
    )
    sched_q.calculate_depreciation()
    assert sched_q.depreciation_amount == Decimal("5400.00")

    sched_y = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="annual",
        depreciation_method="straight_line",
    )
    sched_y.calculate_depreciation()
    assert sched_y.depreciation_amount == Decimal("21600.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_declining_balance_150(tenant_a, fixed_asset_a):
    """150% Declining balance computes: starting_book_value * (1.5 / life_years) * (factor / 12)."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="declining_balance_150",
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("3000.00")
    assert sched.ending_book_value == Decimal("117000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_declining_balance_200(tenant_a, fixed_asset_a):
    """200% Double Declining balance computes: starting_book_value * (2.0 / life_years) * (factor / 12)."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="declining_balance_200",
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("4000.00")
    assert sched.ending_book_value == Decimal("116000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_sum_of_years(tenant_a, fixed_asset_a):
    """Sum-of-the-Years'-Digits (SYD) computes accelerated factor on depreciable base."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="sum_of_years",
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("3000.00")
    assert sched.ending_book_value == Decimal("117000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_units_of_production(tenant_a, fixed_asset_a):
    """Units-of-production computes: (depreciable_base / total_units) * units_produced."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="units_of_production",
        total_units_expected=Decimal("100000.00"),
        units_produced_period=Decimal("2500.00"),
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("2700.00")
    assert sched.ending_book_value == Decimal("117300.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_units_of_production_zero_units_guard(tenant_a, fixed_asset_a):
    """Units-of-production handles zero or None expected units safely without ZeroDivisionError."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="units_of_production",
        total_units_expected=Decimal("0.00"),
        units_produced_period=Decimal("100.00"),
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("0.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_salvage_value_capping(tenant_a, fixed_asset_a):
    """Depreciation charge is capped so ending book value does not breach salvage value."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=59,
        period_frequency="monthly",
        depreciation_method="straight_line",
        starting_book_value=Decimal("13000.00"),
    )
    amount = sched.calculate_depreciation()
    assert amount == Decimal("1000.00")
    assert sched.ending_book_value == Decimal("12000.00")

    sched_zero = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=60,
        period_frequency="monthly",
        depreciation_method="straight_line",
        starting_book_value=Decimal("12000.00"),
    )
    amount_zero = sched_zero.calculate_depreciation()
    assert amount_zero == Decimal("0.00")
    assert sched_zero.ending_book_value == Decimal("12000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_calculation_manual_override_preservation(tenant_a, fixed_asset_a):
    """calculate_depreciation preserves manual override unless force=True."""
    sched = AssetDepreciationSchedule(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="straight_line",
        depreciation_amount=Decimal("2500.00"),
    )
    res = sched.calculate_depreciation(force=False)
    assert res == Decimal("2500.00")
    assert sched.depreciation_amount == Decimal("2500.00")

    res_forced = sched.calculate_depreciation(force=True)
    assert res_forced == Decimal("1800.00")
    assert sched.depreciation_amount == Decimal("1800.00")


# ==============================================================================
# 5. Depreciation GL Posting (post_to_gl)
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_post_to_gl_success(
    depreciation_schedule_a, fixed_asset_a, expense_account_a, accum_account_a, org_unit_a, admin_user
):
    """post_to_gl generates a balanced JournalEntry and updates FixedAsset ledger."""
    depreciation_schedule_a.cost_center = org_unit_a
    depreciation_schedule_a.save()

    je = depreciation_schedule_a.post_to_gl(user=admin_user)

    assert isinstance(je, JournalEntry)
    assert je.status == "posted"
    assert je.entry_type == "recurring"
    assert je.tenant == depreciation_schedule_a.tenant
    assert je.reference == depreciation_schedule_a.number

    lines = list(je.lines.all())
    assert len(lines) == 2

    debit_line = next(l for l in lines if l.debit > 0)
    credit_line = next(l for l in lines if l.credit > 0)

    assert debit_line.gl_account == expense_account_a
    assert debit_line.debit == depreciation_schedule_a.depreciation_amount
    assert debit_line.org_unit == org_unit_a

    assert credit_line.gl_account == accum_account_a
    assert credit_line.credit == depreciation_schedule_a.depreciation_amount
    assert credit_line.org_unit == org_unit_a

    depreciation_schedule_a.refresh_from_db()
    assert depreciation_schedule_a.status == "posted"
    assert depreciation_schedule_a.posted_at is not None
    assert depreciation_schedule_a.posted_by == admin_user
    assert depreciation_schedule_a.journal_entry == je

    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.accumulated_depreciation == depreciation_schedule_a.accumulated_depreciation_after
    assert fixed_asset_a.last_depreciation_date == depreciation_schedule_a.schedule_date


@pytest.mark.django_db
def test_assetdepreciation_models_post_to_gl_fallback_to_fixed_asset_accounts(tenant_a, fixed_asset_a, admin_user):
    """post_to_gl falls back to FixedAsset accounts if not explicitly set on schedule."""
    sched = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=2,
        expense_account=None,
        accumulated_account=None,
    )
    je = sched.post_to_gl(user=admin_user)
    assert je.lines.filter(gl_account=fixed_asset_a.expense_account, debit__gt=0).exists()
    assert je.lines.filter(gl_account=fixed_asset_a.accumulated_account, credit__gt=0).exists()


@pytest.mark.django_db
def test_assetdepreciation_models_post_to_gl_missing_accounts_raises_validation_error(tenant_a, admin_user):
    """post_to_gl raises ValidationError when GL accounts are missing on both schedule and fixed asset."""
    fa = FixedAsset.objects.create(
        tenant=tenant_a,
        name="Asset without GL accounts",
        acquisition_cost=Decimal("50000.00"),
        useful_life_months=60,
    )
    sched = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fa,
        fiscal_year=2026,
        period_number=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        sched.post_to_gl(user=admin_user)
    assert "Both Depreciation Expense and Accumulated Depreciation GL accounts are required" in str(exc_info.value)


@pytest.mark.django_db
def test_assetdepreciation_models_post_to_gl_already_posted_guard(depreciation_schedule_a, admin_user):
    """post_to_gl raises ValidationError when schedule is already posted."""
    depreciation_schedule_a.status = "posted"
    depreciation_schedule_a.save()
    with pytest.raises(ValidationError) as exc_info:
        depreciation_schedule_a.post_to_gl(user=admin_user)
    assert "already posted to the General Ledger" in str(exc_info.value)


@pytest.mark.django_db
def test_assetdepreciation_models_post_to_gl_zero_amount_guard(tenant_a, fixed_asset_a, admin_user):
    """post_to_gl raises ValidationError when depreciation amount is zero or negative."""
    sched = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        starting_book_value=fixed_asset_a.salvage_value,
        depreciation_amount=Decimal("0.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        sched.post_to_gl(user=admin_user)
    assert "Cannot post a zero or negative depreciation charge" in str(exc_info.value)


# ==============================================================================
# 6. Asset Revaluation Workflow & GL Posting
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_calculate_adjustment_upward(revaluation_a, fixed_asset_a):
    """calculate_adjustment accurately calculates upward revaluation step-up amount."""
    fixed_asset_a.accumulated_depreciation = Decimal("20000.00")
    fixed_asset_a.save()

    revaluation_a.new_fair_market_value = Decimal("115000.00")
    adj = revaluation_a.calculate_adjustment()

    assert adj == Decimal("15000.00")
    assert revaluation_a.historical_cost == Decimal("120000.00")
    assert revaluation_a.accumulated_depreciation_before == Decimal("20000.00")
    assert revaluation_a.carrying_value_before == Decimal("100000.00")
    assert revaluation_a.revaluation_adjustment == Decimal("15000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_calculate_adjustment_impairment(revaluation_b, fixed_asset_b):
    """calculate_adjustment accurately calculates negative impairment adjustment."""
    fixed_asset_b.accumulated_depreciation = Decimal("10000.00")
    fixed_asset_b.save()

    revaluation_b.new_fair_market_value = Decimal("28000.00")
    adj = revaluation_b.calculate_adjustment()

    assert adj == Decimal("-7000.00")
    assert revaluation_b.carrying_value_before == Decimal("35000.00")
    assert revaluation_b.revaluation_adjustment == Decimal("-7000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_execute_upward_success(
    revaluation_a, fixed_asset_a, surplus_account_a, asset_account_a, admin_user
):
    """execute_revaluation for upward step-up posts Dr Asset Cost / Cr Revaluation Surplus."""
    fixed_asset_a.accumulated_depreciation = Decimal("20000.00")
    fixed_asset_a.save()

    revaluation_a.new_fair_market_value = Decimal("115000.00")
    revaluation_a.event_type = "revaluation_up"
    revaluation_a.revaluation_surplus_account = surplus_account_a
    revaluation_a.new_salvage_value = Decimal("15000.00")
    revaluation_a.remaining_useful_life_months = 48
    revaluation_a.save()

    je = revaluation_a.execute_revaluation(user=admin_user)

    assert isinstance(je, JournalEntry)
    assert je.status == "posted"

    lines = list(je.lines.all())
    assert len(lines) == 2

    debit_line = next(l for l in lines if l.debit > 0)
    credit_line = next(l for l in lines if l.credit > 0)

    assert debit_line.gl_account == asset_account_a
    assert debit_line.debit == Decimal("15000.00")

    assert credit_line.gl_account == surplus_account_a
    assert credit_line.credit == Decimal("15000.00")

    revaluation_a.refresh_from_db()
    assert revaluation_a.status == "approved"
    assert revaluation_a.approved_by == admin_user
    assert revaluation_a.approved_at is not None

    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.acquisition_cost == Decimal("135000.00")
    assert fixed_asset_a.salvage_value == Decimal("15000.00")
    assert fixed_asset_a.useful_life_months == 48


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_execute_impairment_success(
    tenant_a, fixed_asset_a, expense_account_a, accum_account_a, admin_user
):
    """execute_revaluation for impairment posts Dr Impairment Loss / Cr Accumulated Depreciation."""
    fixed_asset_a.accumulated_depreciation = Decimal("20000.00")
    fixed_asset_a.save()

    rev = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="CNC Crash Impairment",
        fixed_asset=fixed_asset_a,
        event_type="impairment",
        new_fair_market_value=Decimal("85000.00"),
        impairment_loss_account=expense_account_a,
        status="draft",
    )

    je = rev.execute_revaluation(user=admin_user)
    assert isinstance(je, JournalEntry)

    lines = list(je.lines.all())
    debit_line = next(l for l in lines if l.debit > 0)
    credit_line = next(l for l in lines if l.credit > 0)

    assert debit_line.gl_account == expense_account_a
    assert debit_line.debit == Decimal("15000.00")

    assert credit_line.gl_account == accum_account_a
    assert credit_line.credit == Decimal("15000.00")

    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.accumulated_depreciation == Decimal("35000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_execute_missing_accounts_validation(
    tenant_a, fixed_asset_a, admin_user
):
    """execute_revaluation raises ValidationError when accounts for impairment or surplus are absent."""
    rev_impair = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Impairment Missing Account",
        fixed_asset=fixed_asset_a,
        event_type="impairment",
        new_fair_market_value=Decimal("50000.00"),
        impairment_loss_account=None,
    )
    with pytest.raises(ValidationError) as exc_impair:
        rev_impair.execute_revaluation(user=admin_user)
    assert "Both Impairment Loss GL account and Fixed Asset accumulated depreciation account are required" in str(
        exc_impair.value
    )

    rev_up = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Surplus Missing Account",
        fixed_asset=fixed_asset_a,
        event_type="revaluation_up",
        new_fair_market_value=Decimal("150000.00"),
        revaluation_surplus_account=None,
    )
    with pytest.raises(ValidationError) as exc_up:
        rev_up.execute_revaluation(user=admin_user)
    assert "Both Revaluation Surplus GL account and Fixed Asset cost account are required" in str(exc_up.value)


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_execute_already_approved_guard(revaluation_a, admin_user):
    """execute_revaluation raises ValidationError if already approved."""
    revaluation_a.status = "approved"
    revaluation_a.save()
    with pytest.raises(ValidationError) as exc_info:
        revaluation_a.execute_revaluation(user=admin_user)
    assert "already been approved and executed" in str(exc_info.value)


# ==============================================================================
# 7. Asset Transfer Lifecycle
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_capture_carrying_value(transfer_a, fixed_asset_a):
    """capture_carrying_value accurately captures cost minus accumulated depreciation."""
    fixed_asset_a.acquisition_cost = Decimal("120000.00")
    fixed_asset_a.accumulated_depreciation = Decimal("25000.00")
    fixed_asset_a.save()

    cv = transfer_a.capture_carrying_value()
    assert cv == Decimal("95000.00")
    assert transfer_a.carrying_value_at_transfer == Decimal("95000.00")


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_dispatch_workflow(transfer_a, fixed_asset_a):
    """dispatch_transfer captures carrying value and transitions status to in_transit."""
    assert transfer_a.status == "draft"
    transfer_a.dispatch_transfer()
    transfer_a.refresh_from_db()

    assert transfer_a.status == "in_transit"
    assert transfer_a.carrying_value_at_transfer == fixed_asset_a.acquisition_cost - fixed_asset_a.accumulated_depreciation


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_dispatch_non_draft_guard(transfer_a):
    """dispatch_transfer rejects orders that are not in draft status."""
    transfer_a.status = "in_transit"
    transfer_a.save()
    with pytest.raises(ValidationError) as exc_info:
        transfer_a.dispatch_transfer()
    assert "Only draft transfer orders can be dispatched" in str(exc_info.value)


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_complete_success(
    transfer_a, fixed_asset_a, operational_asset_a, location_a2, admin_user
):
    """complete_transfer updates FixedAsset and SCM Asset locations, custodians, and expense GL."""
    dept_target = OrgUnit.objects.create(tenant=transfer_a.tenant, name="Assembly Plant 2", kind="department")
    custodian_target = Party.objects.create(tenant=transfer_a.tenant, name="Lead Engineer Bob", kind="person")
    expense_acc = GLAccount.objects.create(
        tenant=transfer_a.tenant,
        code="6199-A",
        name="Transferred Depr Expense",
        account_type="expense",
        normal_balance="debit",
    )

    transfer_a.destination_department = dept_target
    transfer_a.destination_location = location_a2
    transfer_a.destination_custodian = custodian_target
    transfer_a.destination_expense_account = expense_acc
    transfer_a.status = "in_transit"
    transfer_a.save()

    transfer_a.complete_transfer(user=admin_user)

    transfer_a.refresh_from_db()
    assert transfer_a.status == "completed"
    assert transfer_a.received_by == admin_user
    assert transfer_a.completed_at is not None

    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.location == dept_target
    assert fixed_asset_a.custodian == custodian_target
    assert fixed_asset_a.expense_account == expense_acc

    operational_asset_a.refresh_from_db()
    assert operational_asset_a.location == location_a2
    assert operational_asset_a.custodian == custodian_target
    assert operational_asset_a.org_unit == dept_target


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_complete_already_completed_guard(transfer_a, admin_user):
    """complete_transfer raises ValidationError if already completed."""
    transfer_a.status = "completed"
    transfer_a.save()
    with pytest.raises(ValidationError) as exc_info:
        transfer_a.complete_transfer(user=admin_user)
    assert "already been completed" in str(exc_info.value)


# ==============================================================================
# 8. Capitalization Policy Engine (evaluate_asset)
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_policy_evaluate_meets_both_criteria(capitalization_policy_a):
    """evaluate_asset returns 'capitalize' when both cost and life meet policy thresholds."""
    decision, reason = capitalization_policy_a.evaluate_asset(
        cost=Decimal("7500.00"),
        useful_life_months=24,
    )
    assert decision == "capitalize"
    assert "Meets capitalization threshold" in reason


@pytest.mark.django_db
def test_assetdepreciation_models_policy_evaluate_below_cost_threshold(capitalization_policy_a):
    """evaluate_asset returns default_classification when cost is below threshold."""
    decision, reason = capitalization_policy_a.evaluate_asset(
        cost=Decimal("3500.00"),
        useful_life_months=24,
    )
    assert decision == capitalization_policy_a.default_classification
    assert "is below minimum capitalization threshold" in reason


@pytest.mark.django_db
def test_assetdepreciation_models_policy_evaluate_below_life_threshold(capitalization_policy_a):
    """evaluate_asset returns default_classification when useful life is below minimum."""
    decision, reason = capitalization_policy_a.evaluate_asset(
        cost=Decimal("10000.00"),
        useful_life_months=6,
    )
    assert decision == capitalization_policy_a.default_classification
    assert "is below required minimum" in reason


@pytest.mark.django_db
def test_assetdepreciation_models_policy_evaluate_classification_options(tenant_a):
    """evaluate_asset adheres to different default classifications (expense_immediately, manual_review)."""
    p_expense = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Small Tooling Policy",
        minimum_cost_threshold=Decimal("2500.00"),
        minimum_useful_life_months=12,
        default_classification="expense_immediately",
    )
    decision1, _ = p_expense.evaluate_asset(cost=Decimal("1200.00"), useful_life_months=24)
    assert decision1 == "expense_immediately"

    p_review = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="IT Peripheral Review Policy",
        minimum_cost_threshold=Decimal("3000.00"),
        minimum_useful_life_months=12,
        default_classification="manual_review",
    )
    decision2, _ = p_review.evaluate_asset(cost=Decimal("1500.00"), useful_life_months=24)
    assert decision2 == "manual_review"


@pytest.mark.django_db
def test_assetdepreciation_models_policy_evaluate_invalid_inputs_guarded(capitalization_policy_a):
    """evaluate_asset guards against negative, infinite, and out-of-range inputs."""
    with pytest.raises(ValueError) as exc1:
        capitalization_policy_a.evaluate_asset(cost="-100.00", useful_life_months=24)
    assert "Invalid cost value" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        capitalization_policy_a.evaluate_asset(cost="1000000000000", useful_life_months=24)
    assert "Invalid cost value" in str(exc2.value)

    with pytest.raises(ValueError) as exc3:
        capitalization_policy_a.evaluate_asset(cost="invalid_cost", useful_life_months=24)
    assert "Invalid cost value" in str(exc3.value)

    with pytest.raises(ValueError) as exc4:
        capitalization_policy_a.evaluate_asset(cost="5000", useful_life_months=-5)
    assert "Invalid useful life" in str(exc4.value)

    with pytest.raises(ValueError) as exc5:
        capitalization_policy_a.evaluate_asset(cost="5000", useful_life_months=1500)
    assert "Invalid useful life" in str(exc5.value)

    with pytest.raises(ValueError) as exc6:
        capitalization_policy_a.evaluate_asset(cost="5000", useful_life_months="not_a_number")
    assert "Invalid useful life" in str(exc6.value)


@pytest.mark.django_db
def test_assetdepreciation_models_policy_de_minimis_and_standards(capitalization_policy_b):
    """CapitalizationPolicy fields adhere to de minimis safe harbor and GAAP standard defaults."""
    assert capitalization_policy_b.de_minimis_safe_harbor is True
    assert capitalization_policy_b.applicable_gaap_standard == "US GAAP / IFRS IAS 16"
    assert capitalization_policy_b.policy_scope == "tax_book_safe_harbor"


# ==============================================================================
# 9. Tenant Isolation & Model Validation Constraints
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_models_schedule_tenant_isolation(
    tenant_a, tenant_b, fixed_asset_a, fixed_asset_b
):
    """AssetDepreciationSchedule enforces tenant isolation and compound number uniqueness."""
    s_a = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
    )
    s_b = AssetDepreciationSchedule.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        fiscal_year=2026,
        period_number=1,
    )

    # Scoped filtering verifies tenant isolation
    assert list(AssetDepreciationSchedule.objects.filter(tenant=tenant_a)) == [s_a]
    assert list(AssetDepreciationSchedule.objects.filter(tenant=tenant_b)) == [s_b]

    # Duplicate number within the SAME tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup = AssetDepreciationSchedule(
                tenant=tenant_a,
                fixed_asset=fixed_asset_a,
                fiscal_year=2026,
                period_number=2,
            )
            dup.number = s_a.number
            dup.save()

    # Different tenants can legitimately hold the same sequential number without collision
    assert s_a.number == s_b.number
    assert s_a.tenant != s_b.tenant
    assert AssetDepreciationSchedule.objects.filter(number=s_a.number).count() == 2


@pytest.mark.django_db
def test_assetdepreciation_models_revaluation_tenant_isolation(
    tenant_a, tenant_b, fixed_asset_a, fixed_asset_b
):
    """AssetRevaluation enforces tenant isolation and compound number uniqueness."""
    r_a = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Appraisal A",
        fixed_asset=fixed_asset_a,
    )
    r_b = AssetRevaluation.objects.create(
        tenant=tenant_b,
        title="Appraisal B",
        fixed_asset=fixed_asset_b,
    )

    assert list(AssetRevaluation.objects.filter(tenant=tenant_a)) == [r_a]
    assert list(AssetRevaluation.objects.filter(tenant=tenant_b)) == [r_b]

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup = AssetRevaluation(
                tenant=tenant_a,
                title="Dup A",
                fixed_asset=fixed_asset_a,
            )
            dup.number = r_a.number
            dup.save()

    assert r_a.number == r_b.number
    assert r_a.tenant != r_b.tenant
    assert AssetRevaluation.objects.filter(number=r_a.number).count() == 2


@pytest.mark.django_db
def test_assetdepreciation_models_transfer_tenant_isolation(
    tenant_a, tenant_b, fixed_asset_a, fixed_asset_b
):
    """AssetTransfer enforces tenant isolation and compound number uniqueness."""
    t_a = AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Relocation A",
        fixed_asset=fixed_asset_a,
    )
    t_b = AssetTransfer.objects.create(
        tenant=tenant_b,
        title="Relocation B",
        fixed_asset=fixed_asset_b,
    )

    assert list(AssetTransfer.objects.filter(tenant=tenant_a)) == [t_a]
    assert list(AssetTransfer.objects.filter(tenant=tenant_b)) == [t_b]

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup = AssetTransfer(
                tenant=tenant_a,
                title="Dup Transfer",
                fixed_asset=fixed_asset_a,
            )
            dup.number = t_a.number
            dup.save()

    assert t_a.number == t_b.number
    assert t_a.tenant != t_b.tenant
    assert AssetTransfer.objects.filter(number=t_a.number).count() == 2


@pytest.mark.django_db
def test_assetdepreciation_models_policy_tenant_isolation(tenant_a, tenant_b):
    """CapitalizationPolicy enforces tenant isolation and compound number uniqueness."""
    p_a = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Policy A",
    )
    p_b = CapitalizationPolicy.objects.create(
        tenant=tenant_b,
        name="Policy B",
    )

    assert list(CapitalizationPolicy.objects.filter(tenant=tenant_a)) == [p_a]
    assert list(CapitalizationPolicy.objects.filter(tenant=tenant_b)) == [p_b]

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup = CapitalizationPolicy(
                tenant=tenant_a,
                name="Dup Policy",
            )
            dup.number = p_a.number
            dup.save()

    assert p_a.number == p_b.number
    assert p_a.tenant != p_b.tenant
    assert CapitalizationPolicy.objects.filter(number=p_a.number).count() == 2


@pytest.mark.django_db
def test_assetdepreciation_models_full_clean_validation(
    depreciation_schedule_a, revaluation_a, transfer_a, capitalization_policy_a
):
    """All 4 models execute full_clean() cleanly without validation errors."""
    depreciation_schedule_a.full_clean()
    revaluation_a.full_clean()
    transfer_a.full_clean()
    capitalization_policy_a.full_clean()
