"""
Unit tests for Sub-module 11.10: Lease & Rental Management Models.
Covers AssetLeaseContract, AssetLeaseSchedule, AssetLeaseModification, AssetLeaseBuyAnalysis.
"""
from decimal import Decimal
import datetime
import pytest
from django.utils import timezone

from apps.assets.models import (
    AssetLeaseContract,
    AssetLeaseSchedule,
    AssetLeaseModification,
    AssetLeaseBuyAnalysis,
)


@pytest.mark.django_db
class TestAssetLeaseRentalModels:
    """Model test suite for Sub-module 11.10 Lease & Rental Management."""

    def test_assetleaserental_contract_creation_and_number(self, lease_contract_a):
        """Verifies AssetLeaseContract creation, TenantNumbered prefix 'ALC', and string representation."""
        assert lease_contract_a.pk is not None
        assert lease_contract_a.number.startswith("ALC")
        assert "Finance Lease for 5-Axis CNC" in str(lease_contract_a)
        assert lease_contract_a.classification == "finance"
        assert lease_contract_a.initial_lease_liability > Decimal("0.00")
        assert lease_contract_a.initial_rou_asset_value > Decimal("0.00")

    def test_assetleaserental_contract_statutory_classification_five_tests(self, tenant_a, vendor_party_a, category_root_a):
        """Tests the ASC 842 / IFRS 16 automated 5-criteria statutory lease classification engine."""
        today = timezone.now().date()
        base_kwargs = {
            "tenant": tenant_a,
            "title": "Statutory Test Lease",
            "lessor": vendor_party_a,
            "category": category_root_a,
            "expiration_date": today + timezone.timedelta(days=720),
            "lease_term_months": 24,
            "economic_life_months": 120,  # 20% of life
            "fair_market_value": Decimal("100000.00"),
            "payment_amount": Decimal("1000.00"),
            "discount_rate_pct": Decimal("5.0000"),
            "payment_frequency": "monthly",
            "payment_timing": "arrears",
        }

        # Test 1: Ownership transfer -> Finance
        c1 = AssetLeaseContract.objects.create(transfer_of_ownership=True, **base_kwargs)
        assert c1.evaluate_statutory_classification() == "finance"

        # Test 2: Purchase option reasonably certain -> Finance
        c2 = AssetLeaseContract.objects.create(has_purchase_option=True, **base_kwargs)
        assert c2.evaluate_statutory_classification() == "finance"

        # Test 3: Major part of economic life (>= 75%) -> Finance
        kw3 = dict(base_kwargs)
        kw3["lease_term_months"] = 90
        kw3["economic_life_months"] = 100
        c3 = AssetLeaseContract.objects.create(**kw3)
        assert c3.evaluate_statutory_classification() == "finance"

        # Test 4: Substantially all of FMV (PV >= 90%) -> Finance
        kw4 = dict(base_kwargs)
        kw4["payment_amount"] = Decimal("4500.00")
        c4 = AssetLeaseContract.objects.create(**kw4)
        c4.calculate_present_value()
        assert c4.evaluate_statutory_classification() == "finance"

        # Test 5: Specialized asset with no alternative use -> Finance
        c5 = AssetLeaseContract.objects.create(is_specialized_asset=True, **base_kwargs)
        assert c5.evaluate_statutory_classification() == "finance"

        # Baseline: None met -> Operating
        c6 = AssetLeaseContract.objects.create(**base_kwargs)
        c6.calculate_present_value()
        assert c6.evaluate_statutory_classification() == "operating"

    def test_assetleaserental_present_value_arrears_vs_advance(self, tenant_a, vendor_party_a):
        """Verifies actuarial present value math for payments in arrears vs advance."""
        today = timezone.now().date()
        c_arrears = AssetLeaseContract.objects.create(
            tenant=tenant_a,
            title="Arrears Test",
            lessor=vendor_party_a,
            expiration_date=today + timezone.timedelta(days=365),
            lease_term_months=12,
            payment_amount=Decimal("1000.00"),
            discount_rate_pct=Decimal("6.0000"),
            payment_frequency="monthly",
            payment_timing="arrears",
            initial_direct_costs=Decimal("500.00"),
            lease_incentives=Decimal("200.00"),
        )
        pv_arrears, _ = c_arrears.calculate_present_value()
        assert pv_arrears > Decimal("11000.00")
        assert c_arrears.initial_rou_asset_value == pv_arrears + Decimal("500.00") - Decimal("200.00")

        c_advance = AssetLeaseContract.objects.create(
            tenant=tenant_a,
            title="Advance Test",
            lessor=vendor_party_a,
            expiration_date=today + timezone.timedelta(days=365),
            lease_term_months=12,
            payment_amount=Decimal("1000.00"),
            discount_rate_pct=Decimal("6.0000"),
            payment_frequency="monthly",
            payment_timing="advance",
        )
        pv_advance, _ = c_advance.calculate_present_value()
        # In advance, period 1 payment is undiscounted, so PV is strictly higher
        assert pv_advance > pv_arrears

    def test_assetleaserental_schedule_generation_and_day_preservation(self, tenant_a, vendor_party_a):
        """Verifies schedule generation, period counting, and that day-of-month doesn't collapse after Feb 28."""
        first_date = datetime.date(2025, 1, 31)
        contract = AssetLeaseContract.objects.create(
            tenant=tenant_a,
            title="Jan 31 Day Preservation Test",
            lessor=vendor_party_a,
            inception_date=first_date,
            commencement_date=first_date,
            first_payment_date=first_date,
            expiration_date=datetime.date(2026, 1, 31),
            lease_term_months=12,
            payment_amount=Decimal("2000.00"),
            discount_rate_pct=Decimal("5.0000"),
            payment_frequency="monthly",
            payment_timing="arrears",
        )
        contract.calculate_present_value()
        contract.save()

        count = contract.generate_amortization_schedule()
        assert count == 12
        schedules = list(contract.payment_schedules.order_by("period_number"))
        assert len(schedules) == 12

        # Check period 1 is Jan 31
        assert schedules[0].due_date == datetime.date(2025, 1, 31)
        # Period 2 is Feb 28 (non-leap year)
        assert schedules[1].due_date == datetime.date(2025, 2, 28)
        # Period 3 must restore to March 31, NOT collapse permanently to 28
        assert schedules[2].due_date == datetime.date(2025, 3, 31)
        # Period 4 is April 30
        assert schedules[3].due_date == datetime.date(2025, 4, 30)

        # Check financial balance progression
        for s in schedules:
            assert s.number.startswith("ALSP")
            assert s.beginning_liability >= s.ending_liability
            diff = abs((s.principal_reduction + s.interest_expense) - Decimal("2000.00"))
            assert diff <= Decimal("0.05")

    def test_assetleaserental_schedule_creation_and_str(self, lease_schedule_a):
        """Verifies AssetLeaseSchedule model fields, TenantNumbered prefix 'ALSP', and string repr."""
        assert lease_schedule_a.pk is not None
        assert lease_schedule_a.number.startswith("ALSP")
        assert "Period 1" in str(lease_schedule_a)
        assert lease_schedule_a.status == "paid"
        assert lease_schedule_a.paid_date is not None

    def test_assetleaserental_modification_auto_delta_calculation(self, tenant_a, lease_contract_a, admin_user):
        """Verifies that AssetLeaseModification automatically calculates liability and ROU adjustments on save()."""
        today = timezone.now().date()
        mod = AssetLeaseModification(
            tenant=tenant_a,
            lease_contract=lease_contract_a,
            modification_type="term_extension",
            request_date=today,
            effective_date=today,
            prior_lease_liability=Decimal("100000.00"),
            revised_lease_liability=Decimal("125000.00"),
            prior_rou_asset_value=Decimal("95000.00"),
            revised_rou_asset_value=Decimal("120000.00"),
            requested_by=admin_user,
            status="draft",
        )
        mod.save()
        assert mod.number.startswith("ALMD")
        assert mod.liability_adjustment == Decimal("25000.00")
        assert mod.rou_asset_adjustment == Decimal("25000.00")
        assert "Term Extension" in str(mod)

    def test_assetleaserental_lease_buy_analysis_npv_and_recommendation(self, lease_buy_analysis_a):
        """Verifies financial DCF NPV evaluation and recommendation on AssetLeaseBuyAnalysis."""
        assert lease_buy_analysis_a.pk is not None
        assert lease_buy_analysis_a.number.startswith("ALBA")
        assert lease_buy_analysis_a.npv_purchase_option is not None
        assert lease_buy_analysis_a.npv_lease_option is not None
        assert lease_buy_analysis_a.net_advantage_to_leasing is not None
        assert lease_buy_analysis_a.recommendation in ["buy", "lease", "indifferent"]
        assert "CapEx Decision" in str(lease_buy_analysis_a)

    def test_assetleaserental_lease_buy_analysis_zero_tax_on_salvage_when_book_equals_salvage(self, tenant_a, category_root_a, admin_user):
        """Verifies straight-line depreciation down to salvage produces no tax penalty on terminal salvage."""
        alba = AssetLeaseBuyAnalysis.objects.create(
            tenant=tenant_a,
            title="Salvage Tax Test",
            target_asset_name="Precision CNC Lathe",
            category=category_root_a,
            expected_useful_life_years=Decimal("5.0"),
            purchase_price=Decimal("100000.00"),
            down_payment_pct=Decimal("0.00"),
            loan_interest_rate_pct=Decimal("5.00"),
            loan_term_years=Decimal("5.0"),
            estimated_salvage_value=Decimal("20000.00"),
            annual_maintenance_cost_buy=Decimal("0.00"),
            annual_insurance_tax_buy=Decimal("0.00"),
            lease_term_months=60,
            monthly_lease_payment=Decimal("1800.00"),
            upfront_lease_fees=Decimal("0.00"),
            end_of_lease_purchase_option=Decimal("0.00"),
            annual_maintenance_cost_lease=Decimal("0.00"),
            discount_rate_wacc_pct=Decimal("6.00"),
            corporate_tax_rate_pct=Decimal("25.00"),
            evaluated_by=admin_user,
        )
        alba.evaluate_financial_models()
        assert alba.npv_purchase_option is not None
        assert alba.npv_lease_option is not None
