"""Model unit and invariant tests for Sub-module 11.8: Warranty & Insurance Management.

Covers all 4 models:
- AssetWarranty (AWAR-)
- AssetWarrantyClaim (AWCL-)
- AssetInsurancePolicy (AINS-)
- AssetInsuranceClaim (AICL-)
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    AssetWarranty,
    AssetWarrantyClaim,
    AssetInsurancePolicy,
    AssetInsuranceClaim,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Local 11.8 Fixtures & Helpers (Contract Aligned)
# ==============================================================================

@pytest.fixture
def warranty_a(db, tenant_a, fixed_asset_a, operational_asset_a, vendor_party_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetWarranty.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        warrantor_party=vendor_party_a,
        warranty_type="oem_standard",
        coverage_scope="comprehensive",
        title="Centrifugal Compressor OEM Factory Warranty",
        warranty_certificate_number="WARR-CERT-ACME-001",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=335),
        deductible_amount=Decimal("250.00"),
        contract_purchase_price=Decimal("1500.00"),
        currency=currency_usd,
        status="active",
        registered_by=admin_user,
        terms_and_conditions="Full parts and labor for manufacturing defects.",
    )


@pytest.fixture
def warranty_b(db, tenant_b, fixed_asset_b, operational_asset_b, vendor_party_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetWarranty.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        warrantor_party=vendor_party_b,
        warranty_type="oem_extended",
        coverage_scope="powertrain_major_components",
        title="Globex Generator Extended Powertrain Warranty",
        warranty_certificate_number="WARR-CERT-GLOBEX-002",
        start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=305),
        deductible_amount=Decimal("500.00"),
        contract_purchase_price=Decimal("2500.00"),
        currency=currency_usd,
        status="active",
        registered_by=admin_b,
        terms_and_conditions="Powertrain component defects and mechanical seizure.",
    )


@pytest.fixture
def warranty_claim_a(db, tenant_a, warranty_a, fixed_asset_a, operational_asset_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetWarrantyClaim.objects.create(
        tenant=tenant_a,
        warranty=warranty_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        title="Impeller Shaft Fatigue Fracture",
        defect_description="Fatigue crack detected on high-pressure impeller shaft stage 2.",
        incident_date=today - timedelta(days=10),
        claimed_amount=Decimal("3200.00"),
        approved_amount=Decimal("0.00"),
        deductible_applied=Decimal("250.00"),
        net_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="submitted",
        filed_by=admin_user,
    )


@pytest.fixture
def warranty_claim_b(db, tenant_b, warranty_b, fixed_asset_b, operational_asset_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetWarrantyClaim.objects.create(
        tenant=tenant_b,
        warranty=warranty_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        title="Rotor Core Insulation Breakdown",
        defect_description="Insulation resistance dropped below 1M ohm during routine run.",
        incident_date=today - timedelta(days=12),
        claimed_amount=Decimal("5500.00"),
        approved_amount=Decimal("0.00"),
        deductible_applied=Decimal("500.00"),
        net_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="submitted",
        filed_by=admin_b,
    )


@pytest.fixture
def insurance_policy_a(db, tenant_a, underwriter_party_a, broker_party_a, fixed_asset_a, operational_asset_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetInsurancePolicy.objects.create(
        tenant=tenant_a,
        policy_number="POL-2026-ACME-IND-01",
        title="Industrial Machinery Breakdown & All Risk Policy",
        policy_type="machinery_breakdown",
        underwriter_party=underwriter_party_a,
        broker_party=broker_party_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        effective_date=today - timedelta(days=60),
        expiration_date=today + timedelta(days=305),
        annual_premium=Decimal("12000.00"),
        premium_frequency="annual",
        total_insured_value=Decimal("250000.00"),
        deductible_retention=Decimal("5000.00"),
        valuation_basis="replacement_cost_value",
        currency=currency_usd,
        status="active",
        risk_manager=admin_user,
        coverage_terms="Covers sudden and accidental mechanical and electrical breakdown.",
    )


@pytest.fixture
def insurance_policy_b(db, tenant_b, underwriter_party_b, broker_party_b, fixed_asset_b, operational_asset_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetInsurancePolicy.objects.create(
        tenant=tenant_b,
        policy_number="POL-2026-GLOBEX-ENG-02",
        title="Globex Fleet & Heavy Equipment All Risk Policy",
        policy_type="comprehensive_all_risk",
        underwriter_party=underwriter_party_b,
        broker_party=broker_party_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        effective_date=today - timedelta(days=90),
        expiration_date=today + timedelta(days=275),
        annual_premium=Decimal("18500.00"),
        premium_frequency="semi_annual",
        total_insured_value=Decimal("400000.00"),
        deductible_retention=Decimal("7500.00"),
        valuation_basis="replacement_cost_value",
        currency=currency_usd,
        status="active",
        risk_manager=admin_b,
        coverage_terms="Property damage, fire, flood, and equipment collision.",
    )


@pytest.fixture
def insurance_claim_a(db, tenant_a, insurance_policy_a, fixed_asset_a, operational_asset_a, adjuster_party_a, currency_usd, admin_user):
    today = timezone.now().date()
    return AssetInsuranceClaim.objects.create(
        tenant=tenant_a,
        policy=insurance_policy_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        adjuster_party=adjuster_party_a,
        title="Stator Winding Arcing and Core Damage",
        incident_description="Grid power surge induced stator insulation flashover and thermal burn.",
        incident_location="Plant 1 - Main Compressor Bay",
        incident_date=today - timedelta(days=15),
        peril_type="electrical_arcing_surge",
        claimed_loss_amount=Decimal("28000.00"),
        deductible_applied=Decimal("5000.00"),
        settlement_payout_amount=Decimal("0.00"),
        salvage_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="proof_of_loss_filed",
        claims_officer=admin_user,
    )


@pytest.fixture
def insurance_claim_b(db, tenant_b, insurance_policy_b, fixed_asset_b, operational_asset_b, adjuster_party_b, currency_usd, admin_b):
    today = timezone.now().date()
    return AssetInsuranceClaim.objects.create(
        tenant=tenant_b,
        policy=insurance_policy_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        adjuster_party=adjuster_party_b,
        title="Cooling Tower Basin Hydraulic Rupture",
        incident_description="Freezing rupture on heat-exchanger supply piping and flooded sump.",
        incident_location="Yard 2 - Cooling Tower Cell B",
        incident_date=today - timedelta(days=20),
        peril_type="flood_water_damage",
        claimed_loss_amount=Decimal("35000.00"),
        deductible_applied=Decimal("7500.00"),
        settlement_payout_amount=Decimal("0.00"),
        salvage_recovery_amount=Decimal("0.00"),
        currency=currency_usd,
        claim_status="proof_of_loss_filed",
        claims_officer=admin_b,
    )


def _assetwarrantyinsurance_create_warranty(tenant, **kwargs):
    """Helper to provision test warranty with valid defaults."""
    today = timezone.now().date()
    defaults = {
        "title": "Default Test Warranty",
        "start_date": today,
        "end_date": today + timedelta(days=365),
    }
    defaults.update(kwargs)
    return AssetWarranty.objects.create(tenant=tenant, **defaults)


def _assetwarrantyinsurance_create_policy(tenant, **kwargs):
    """Helper to provision test insurance policy with valid defaults."""
    today = timezone.now().date()
    defaults = {
        "title": "Default Test Policy",
        "policy_number": "POL-TEST-001",
        "effective_date": today,
        "expiration_date": today + timedelta(days=365),
    }
    defaults.update(kwargs)
    return AssetInsurancePolicy.objects.create(tenant=tenant, **defaults)


# ==============================================================================
# 1. AssetWarranty Model Unit Tests
# ==============================================================================

def test_assetwarrantyinsurance_warranty_str_and_prefix(warranty_a):
    """Assert number prefix starts with AWAR- and __str__ matches format."""
    assert warranty_a.number.startswith("AWAR-")
    assert str(warranty_a) == f"{warranty_a.number} - {warranty_a.title}"


def test_assetwarrantyinsurance_warranty_defaults(tenant_a):
    """Assert model field defaults on AssetWarranty."""
    warranty = _assetwarrantyinsurance_create_warranty(tenant_a, title="Compressor OEM Plan")
    assert warranty.number.startswith("AWAR-")
    assert warranty.warranty_type == "oem_standard"
    assert warranty.coverage_scope == "comprehensive"
    assert warranty.meter_type == "none_calendar_only"
    assert warranty.meter_limit is None
    assert warranty.parts_coverage_percent == 100
    assert warranty.labor_coverage_percent == 100
    assert warranty.travel_dispatch_covered is True
    assert warranty.deductible_amount == Decimal("0.00")
    assert warranty.contract_purchase_price == Decimal("0.00")
    assert warranty.status == "active"
    assert warranty.warranty_certificate_number == ""
    assert warranty.terms_and_conditions == ""


def test_assetwarrantyinsurance_warranty_status_css_mapping(warranty_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badge classes."""
    for status_code, badge_class in AssetWarranty.STATUS_CSS.items():
        warranty_a.status = status_code
        assert warranty_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    # Unlisted status falls back to badge-slate
    warranty_a.status = "unknown_status"
    assert warranty_a.status_css == "badge-slate"


def test_assetwarrantyinsurance_warranty_type_css_mapping(warranty_a):
    """Assert warranty_type_css maps all WARRANTY_TYPE_CHOICES to color badges."""
    for type_code, badge_class in AssetWarranty.WARRANTY_TYPE_CSS.items():
        warranty_a.warranty_type = type_code
        assert warranty_a.warranty_type_css == badge_class
        assert badge_class.startswith("badge-")

    warranty_a.warranty_type = "unknown_type"
    assert warranty_a.warranty_type_css == "badge-info"


def test_assetwarrantyinsurance_warranty_coverage_scope_css_mapping(warranty_a):
    """Assert coverage_scope_css maps all COVERAGE_SCOPE_CHOICES to color badges."""
    for scope_code, badge_class in AssetWarranty.COVERAGE_SCOPE_CSS.items():
        warranty_a.coverage_scope = scope_code
        assert warranty_a.coverage_scope_css == badge_class
        assert badge_class.startswith("badge-")

    warranty_a.coverage_scope = "unknown_scope"
    assert warranty_a.coverage_scope_css == "badge-green"


def test_assetwarrantyinsurance_warranty_is_currently_valid(tenant_a):
    """Assert is_currently_valid property logic against status and dates."""
    today = timezone.now().date()

    # Active and inside date window -> Valid
    w_active = _assetwarrantyinsurance_create_warranty(
        tenant_a,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=10),
        status="active",
    )
    assert w_active.is_currently_valid is True

    # Active but in the future -> Invalid
    w_future = _assetwarrantyinsurance_create_warranty(
        tenant_a,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=365),
        status="active",
    )
    assert w_future.is_currently_valid is False

    # Active but expired date -> Invalid
    w_past = _assetwarrantyinsurance_create_warranty(
        tenant_a,
        start_date=today - timedelta(days=365),
        end_date=today - timedelta(days=1),
        status="active",
    )
    assert w_past.is_currently_valid is False

    # In date window but voided or draft -> Invalid
    w_voided = _assetwarrantyinsurance_create_warranty(
        tenant_a,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=10),
        status="voided",
    )
    assert w_voided.is_currently_valid is False

    w_draft = _assetwarrantyinsurance_create_warranty(
        tenant_a,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=10),
        status="draft",
    )
    assert w_draft.is_currently_valid is False


def test_assetwarrantyinsurance_warranty_days_until_expiration_calculation(warranty_a):
    """Assert date arithmetic correctly computes remaining warranty days."""
    today = timezone.now().date()
    days_left = (warranty_a.end_date - today).days
    assert days_left > 0
    assert days_left == (warranty_a.end_date - today).days


def test_assetwarrantyinsurance_warranty_coverage_percentage_validators(tenant_a):
    """Assert parts and labor coverage percentage validators (0-100%)."""
    today = timezone.now().date()

    # Boundary: 0% and 100% valid
    w_valid = AssetWarranty(
        tenant=tenant_a,
        title="Valid Boundary Percentages",
        start_date=today,
        end_date=today + timedelta(days=30),
        parts_coverage_percent=0,
        labor_coverage_percent=100,
    )
    w_valid.full_clean()

    # Invalid: parts > 100
    w_invalid_parts = AssetWarranty(
        tenant=tenant_a,
        title="Invalid Parts Percent",
        start_date=today,
        end_date=today + timedelta(days=30),
        parts_coverage_percent=105,
    )
    with pytest.raises(ValidationError) as exc:
        w_invalid_parts.full_clean()
    assert "parts_coverage_percent" in exc.value.message_dict

    # Invalid: labor > 100
    w_invalid_labor = AssetWarranty(
        tenant=tenant_a,
        title="Invalid Labor Percent",
        start_date=today,
        end_date=today + timedelta(days=30),
        labor_coverage_percent=150,
    )
    with pytest.raises(ValidationError) as exc:
        w_invalid_labor.full_clean()
    assert "labor_coverage_percent" in exc.value.message_dict


def test_assetwarrantyinsurance_warranty_unique_number_per_tenant(tenant_a, tenant_b, warranty_a):
    """Assert unique constraint on tenant and number."""
    today = timezone.now().date()

    # Duplicate within same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetWarranty.objects.create(
                tenant=tenant_a,
                number=warranty_a.number,
                title="Duplicate Number Within Tenant",
                start_date=today,
                end_date=today + timedelta(days=30),
            )

    # Identical number across different tenants is permitted
    w_other_tenant = AssetWarranty.objects.create(
        tenant=tenant_b,
        number=warranty_a.number,
        title="Same Number in Other Tenant",
        start_date=today,
        end_date=today + timedelta(days=30),
    )
    assert w_other_tenant.number == warranty_a.number
    assert w_other_tenant.tenant == tenant_b


def test_assetwarrantyinsurance_warranty_foreign_key_set_null(warranty_a, fixed_asset_a, operational_asset_a):
    """Assert SET_NULL cascading behavior for asset relations on warranty."""
    assert warranty_a.fixed_asset == fixed_asset_a
    assert warranty_a.operational_asset == operational_asset_a

    fixed_asset_a.delete()
    warranty_a.refresh_from_db()
    assert warranty_a.fixed_asset is None

    operational_asset_a.delete()
    warranty_a.refresh_from_db()
    assert warranty_a.operational_asset is None


# ==============================================================================
# 2. AssetWarrantyClaim Model Unit Tests
# ==============================================================================

def test_assetwarrantyinsurance_claim_str_and_prefix(warranty_claim_a):
    """Assert warranty claim auto-generated prefix starts with AWCL- and __str__."""
    assert warranty_claim_a.number.startswith("AWCL-")
    assert str(warranty_claim_a) == f"{warranty_claim_a.number} - {warranty_claim_a.title}"


def test_assetwarrantyinsurance_claim_defaults(tenant_a, warranty_a):
    """Assert defaults on AssetWarrantyClaim."""
    today = timezone.now().date()
    claim = AssetWarrantyClaim.objects.create(
        tenant=tenant_a,
        warranty=warranty_a,
        title="Spindle Seal Failure",
        incident_date=today,
        defect_description="High-speed coolant leak around seal ring.",
    )
    assert claim.number.startswith("AWCL-")
    assert claim.claim_status == "draft"
    assert claim.resolution_type == "pending_evaluation"
    assert claim.part_return_status == "not_required"
    assert claim.claimed_amount == Decimal("0.00")
    assert claim.approved_amount == Decimal("0.00")
    assert claim.deductible_applied == Decimal("0.00")
    assert claim.net_recovery_amount == Decimal("0.00")
    assert claim.operating_meter_at_failure is None
    assert claim.submission_date is None
    assert claim.settlement_date is None


def test_assetwarrantyinsurance_claim_status_css_mapping(warranty_claim_a):
    """Assert claim_status_css returns color badge for every CLAIM_STATUS_CHOICE."""
    for status_code, badge_class in AssetWarrantyClaim.CLAIM_STATUS_CSS.items():
        warranty_claim_a.claim_status = status_code
        assert warranty_claim_a.claim_status_css == badge_class
        assert badge_class.startswith("badge-")

    warranty_claim_a.claim_status = "unknown_claim_status"
    assert warranty_claim_a.claim_status_css == "badge-slate"


def test_assetwarrantyinsurance_claim_resolution_type_css_mapping(warranty_claim_a):
    """Assert resolution_type_css returns color badge for every choice."""
    for type_code, badge_class in AssetWarrantyClaim.RESOLUTION_TYPE_CSS.items():
        warranty_claim_a.resolution_type = type_code
        assert warranty_claim_a.resolution_type_css == badge_class
        assert badge_class.startswith("badge-")

    warranty_claim_a.resolution_type = "unknown_resolution"
    assert warranty_claim_a.resolution_type_css == "badge-slate"


def test_assetwarrantyinsurance_claim_part_return_status_css_mapping(warranty_claim_a):
    """Assert part_return_status_css returns color badge for every choice."""
    for return_code, badge_class in AssetWarrantyClaim.PART_RETURN_STATUS_CSS.items():
        warranty_claim_a.part_return_status = return_code
        assert warranty_claim_a.part_return_status_css == badge_class
        assert badge_class.startswith("badge-")

    warranty_claim_a.part_return_status = "unknown_part_status"
    assert warranty_claim_a.part_return_status_css == "badge-slate"


def test_assetwarrantyinsurance_claim_net_financial_recovery_calculation(tenant_a, warranty_a):
    """Assert net recovery calculation (approved_amount - deductible_applied)."""
    today = timezone.now().date()
    claim = AssetWarrantyClaim.objects.create(
        tenant=tenant_a,
        warranty=warranty_a,
        title="Compressor Vane Overhaul Claim",
        incident_date=today,
        defect_description="Overhauled worn guide vanes.",
        claimed_amount=Decimal("4500.00"),
        approved_amount=Decimal("4200.00"),
        deductible_applied=Decimal("250.00"),
        net_recovery_amount=Decimal("3950.00"),
    )
    # Check invariant: net_recovery == approved - deductible
    expected_net = claim.approved_amount - claim.deductible_applied
    assert claim.net_recovery_amount == expected_net
    assert claim.net_recovery_amount == Decimal("3950.00")


def test_assetwarrantyinsurance_claim_cascade_on_warranty_deletion(tenant_a, warranty_a, warranty_claim_a):
    """Assert CASCADE deletion: deleting parent AssetWarranty deletes child claims."""
    claim_id = warranty_claim_a.pk
    assert AssetWarrantyClaim.objects.filter(pk=claim_id).exists() is True

    warranty_a.delete()
    assert AssetWarrantyClaim.objects.filter(pk=claim_id).exists() is False


def test_assetwarrantyinsurance_claim_unique_number_per_tenant(tenant_a, tenant_b, warranty_claim_a, warranty_b):
    """Assert unique constraint on tenant and number for warranty claims."""
    today = timezone.now().date()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetWarrantyClaim.objects.create(
                tenant=tenant_a,
                warranty=warranty_claim_a.warranty,
                number=warranty_claim_a.number,
                title="Duplicate Claim Number",
                incident_date=today,
                defect_description="Collision test.",
            )

    claim_tenant_b = AssetWarrantyClaim.objects.create(
        tenant=tenant_b,
        warranty=warranty_b,
        number=warranty_claim_a.number,
        title="Same Number Other Tenant",
        incident_date=today,
        defect_description="Allowed cross-tenant collision.",
    )
    assert claim_tenant_b.number == warranty_claim_a.number
    assert claim_tenant_b.tenant == tenant_b


# ==============================================================================
# 3. AssetInsurancePolicy Model Unit Tests
# ==============================================================================

def test_assetwarrantyinsurance_policy_str_and_prefix(insurance_policy_a):
    """Assert policy number prefix starts with AINS- and __str__ format."""
    assert insurance_policy_a.number.startswith("AINS-")
    expected_str = f"{insurance_policy_a.number} ({insurance_policy_a.policy_number}) - {insurance_policy_a.title}"
    assert str(insurance_policy_a) == expected_str


def test_assetwarrantyinsurance_policy_defaults(tenant_a):
    """Assert defaults on AssetInsurancePolicy."""
    policy = _assetwarrantyinsurance_create_policy(tenant_a, title="Boiler Schedule")
    assert policy.number.startswith("AINS-")
    assert policy.policy_type == "machinery_breakdown"
    assert policy.valuation_basis == "replacement_cost_value"
    assert policy.premium_frequency == "annual"
    assert policy.coinsurance_percentage == 100
    assert policy.total_insured_value == Decimal("0.00")
    assert policy.deductible_retention == Decimal("0.00")
    assert policy.annual_premium == Decimal("0.00")
    assert policy.status == "active"
    assert policy.coverage_terms == ""


def test_assetwarrantyinsurance_policy_status_css_mapping(insurance_policy_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badges."""
    for status_code, badge_class in AssetInsurancePolicy.STATUS_CSS.items():
        insurance_policy_a.status = status_code
        assert insurance_policy_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_policy_a.status = "unknown_policy_status"
    assert insurance_policy_a.status_css == "badge-slate"


def test_assetwarrantyinsurance_policy_type_css_mapping(insurance_policy_a):
    """Assert policy_type_css maps all POLICY_TYPE_CHOICES to color badges."""
    for type_code, badge_class in AssetInsurancePolicy.POLICY_TYPE_CSS.items():
        insurance_policy_a.policy_type = type_code
        assert insurance_policy_a.policy_type_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_policy_a.policy_type = "unknown_policy_type"
    assert insurance_policy_a.policy_type_css == "badge-info"


def test_assetwarrantyinsurance_policy_valuation_basis_css_mapping(insurance_policy_a):
    """Assert valuation_basis_css maps all VALUATION_BASIS_CHOICES to color badges."""
    for basis_code, badge_class in AssetInsurancePolicy.VALUATION_BASIS_CSS.items():
        insurance_policy_a.valuation_basis = basis_code
        assert insurance_policy_a.valuation_basis_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_policy_a.valuation_basis = "unknown_basis"
    assert insurance_policy_a.valuation_basis_css == "badge-green"


def test_assetwarrantyinsurance_policy_is_currently_in_force(tenant_a):
    """Assert is_currently_in_force property logic against status and dates."""
    today = timezone.now().date()

    # Active and inside date window -> In force
    p_active = _assetwarrantyinsurance_create_policy(
        tenant_a,
        effective_date=today - timedelta(days=30),
        expiration_date=today + timedelta(days=30),
        status="active",
    )
    assert p_active.is_currently_in_force is True

    # Active but not yet effective -> False
    p_future = _assetwarrantyinsurance_create_policy(
        tenant_a,
        effective_date=today + timedelta(days=1),
        expiration_date=today + timedelta(days=365),
        status="active",
    )
    assert p_future.is_currently_in_force is False

    # Active but expired -> False
    p_past = _assetwarrantyinsurance_create_policy(
        tenant_a,
        effective_date=today - timedelta(days=365),
        expiration_date=today - timedelta(days=1),
        status="active",
    )
    assert p_past.is_currently_in_force is False

    # Inside window but cancelled or draft -> False
    p_cancelled = _assetwarrantyinsurance_create_policy(
        tenant_a,
        effective_date=today - timedelta(days=30),
        expiration_date=today + timedelta(days=30),
        status="cancelled",
    )
    assert p_cancelled.is_currently_in_force is False

    p_draft = _assetwarrantyinsurance_create_policy(
        tenant_a,
        effective_date=today - timedelta(days=30),
        expiration_date=today + timedelta(days=30),
        status="draft",
    )
    assert p_draft.is_currently_in_force is False


def test_assetwarrantyinsurance_policy_days_until_expiration(insurance_policy_a):
    """Assert policy remaining days calculation."""
    today = timezone.now().date()
    remaining = (insurance_policy_a.expiration_date - today).days
    assert remaining > 0


def test_assetwarrantyinsurance_policy_coinsurance_validators(tenant_a):
    """Assert coinsurance_percentage range validators (0-100%)."""
    today = timezone.now().date()

    # Valid boundaries: 0 and 100
    p_valid = AssetInsurancePolicy(
        tenant=tenant_a,
        title="Boundary Coinsurance",
        policy_number="POL-BOUND-01",
        effective_date=today,
        expiration_date=today + timedelta(days=365),
        coinsurance_percentage=80,
    )
    p_valid.full_clean()

    # Invalid: coinsurance > 100
    p_invalid = AssetInsurancePolicy(
        tenant=tenant_a,
        title="Invalid Coinsurance High",
        policy_number="POL-HIGH-01",
        effective_date=today,
        expiration_date=today + timedelta(days=365),
        coinsurance_percentage=105,
    )
    with pytest.raises(ValidationError) as exc:
        p_invalid.full_clean()
    assert "coinsurance_percentage" in exc.value.message_dict


def test_assetwarrantyinsurance_policy_unique_number_per_tenant(tenant_a, tenant_b, insurance_policy_a):
    """Assert unique constraint on tenant and number for insurance policies."""
    today = timezone.now().date()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetInsurancePolicy.objects.create(
                tenant=tenant_a,
                number=insurance_policy_a.number,
                title="Duplicate Policy Number",
                policy_number="POL-DUP-01",
                effective_date=today,
                expiration_date=today + timedelta(days=365),
            )

    pol_tenant_b = AssetInsurancePolicy.objects.create(
        tenant=tenant_b,
        number=insurance_policy_a.number,
        title="Same Number in Other Tenant",
        policy_number="POL-DUP-02",
        effective_date=today,
        expiration_date=today + timedelta(days=365),
    )
    assert pol_tenant_b.number == insurance_policy_a.number
    assert pol_tenant_b.tenant == tenant_b


def test_assetwarrantyinsurance_policy_set_null_on_parties(insurance_policy_a, underwriter_party_a, broker_party_a):
    """Assert SET_NULL cascading behavior for underwriter and broker relations."""
    assert insurance_policy_a.underwriter_party == underwriter_party_a
    assert insurance_policy_a.broker_party == broker_party_a

    underwriter_party_a.delete()
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.underwriter_party is None

    broker_party_a.delete()
    insurance_policy_a.refresh_from_db()
    assert insurance_policy_a.broker_party is None


# ==============================================================================
# 4. AssetInsuranceClaim Model Unit Tests
# ==============================================================================

def test_assetwarrantyinsurance_insurance_claim_str_and_prefix(insurance_claim_a):
    """Assert insurance claim prefix starts with AICL- and __str__ format."""
    assert insurance_claim_a.number.startswith("AICL-")
    assert str(insurance_claim_a) == f"{insurance_claim_a.number} - {insurance_claim_a.title}"


def test_assetwarrantyinsurance_insurance_claim_defaults(tenant_a, insurance_policy_a):
    """Assert field defaults on AssetInsuranceClaim."""
    today = timezone.now().date()
    claim = AssetInsuranceClaim.objects.create(
        tenant=tenant_a,
        policy=insurance_policy_a,
        title="Switchgear Fire Loss",
        incident_date=today,
        incident_description="Thermal failure on main switchgear bussing.",
        incident_location="Substation 3B",
    )
    assert claim.number.startswith("AICL-")
    assert claim.claim_status == "incident_reported"
    assert claim.peril_type == "mechanical_breakdown"
    assert claim.settlement_method == "direct_indemnity_check"
    assert claim.claimed_loss_amount == Decimal("0.00")
    assert claim.deductible_applied == Decimal("0.00")
    assert claim.salvage_recovery_amount == Decimal("0.00")
    assert claim.settlement_payout_amount == Decimal("0.00")
    assert claim.carrier_claim_number == ""
    assert claim.adjuster_name == ""
    assert claim.date_reported_to_carrier is None
    assert claim.proof_of_loss_date is None
    assert claim.settlement_date is None


def test_assetwarrantyinsurance_insurance_claim_status_css_mapping(insurance_claim_a):
    """Assert claim_status_css returns color badge for every choice."""
    for status_code, badge_class in AssetInsuranceClaim.CLAIM_STATUS_CSS.items():
        insurance_claim_a.claim_status = status_code
        assert insurance_claim_a.claim_status_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_claim_a.claim_status = "unknown_status"
    assert insurance_claim_a.claim_status_css == "badge-slate"


def test_assetwarrantyinsurance_insurance_claim_peril_type_css_mapping(insurance_claim_a):
    """Assert peril_type_css returns color badge for every choice."""
    for peril_code, badge_class in AssetInsuranceClaim.PERIL_TYPE_CSS.items():
        insurance_claim_a.peril_type = peril_code
        assert insurance_claim_a.peril_type_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_claim_a.peril_type = "unknown_peril"
    assert insurance_claim_a.peril_type_css == "badge-slate"


def test_assetwarrantyinsurance_insurance_claim_settlement_method_css_mapping(insurance_claim_a):
    """Assert settlement_method_css returns color badge for every choice."""
    for method_code, badge_class in AssetInsuranceClaim.SETTLEMENT_METHOD_CSS.items():
        insurance_claim_a.settlement_method = method_code
        assert insurance_claim_a.settlement_method_css == badge_class
        assert badge_class.startswith("badge-")

    insurance_claim_a.settlement_method = "unknown_method"
    assert insurance_claim_a.settlement_method_css == "badge-slate"


def test_assetwarrantyinsurance_insurance_claim_financial_recovery_calculations(tenant_a, insurance_policy_a):
    """Assert net claim payable and net carrier recovery calculations."""
    today = timezone.now().date()
    claim = AssetInsuranceClaim.objects.create(
        tenant=tenant_a,
        policy=insurance_policy_a,
        title="Submerged Turbine Auxiliary Motor",
        incident_date=today,
        incident_description="Basement flooded after pump trip.",
        incident_location="Turbine Hall Basement",
        peril_type="flood_water_damage",
        claimed_loss_amount=Decimal("50000.00"),
        deductible_applied=Decimal("5000.00"),
        settlement_payout_amount=Decimal("42000.00"),
        salvage_recovery_amount=Decimal("3000.00"),
    )
    # Gross claim less deductible
    net_claim_expected = claim.claimed_loss_amount - claim.deductible_applied
    assert net_claim_expected == Decimal("45000.00")

    # Total financial indemnification = carrier payout + salvage scrap sale
    total_recovery = claim.settlement_payout_amount + claim.salvage_recovery_amount
    assert total_recovery == Decimal("45000.00")


def test_assetwarrantyinsurance_insurance_claim_cascade_on_policy_deletion(tenant_a, insurance_policy_a, insurance_claim_a):
    """Assert CASCADE deletion: deleting AssetInsurancePolicy deletes child claims."""
    claim_id = insurance_claim_a.pk
    assert AssetInsuranceClaim.objects.filter(pk=claim_id).exists() is True

    insurance_policy_a.delete()
    assert AssetInsuranceClaim.objects.filter(pk=claim_id).exists() is False


def test_assetwarrantyinsurance_insurance_claim_unique_number_per_tenant(tenant_a, tenant_b, insurance_claim_a, insurance_policy_b):
    """Assert unique constraint on tenant and number for insurance claims."""
    today = timezone.now().date()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetInsuranceClaim.objects.create(
                tenant=tenant_a,
                policy=insurance_claim_a.policy,
                number=insurance_claim_a.number,
                title="Duplicate Number Collision",
                incident_date=today,
                incident_description="Collision test.",
                incident_location="Bay 1",
            )

    claim_tenant_b = AssetInsuranceClaim.objects.create(
        tenant=tenant_b,
        policy=insurance_policy_b,
        number=insurance_claim_a.number,
        title="Same Number in Other Tenant",
        incident_date=today,
        incident_description="Allowed collision.",
        incident_location="Bay 2",
    )
    assert claim_tenant_b.number == insurance_claim_a.number
    assert claim_tenant_b.tenant == tenant_b


# ==============================================================================
# 5. Multi-Tenant Query Isolation Tests
# ==============================================================================

def test_assetwarrantyinsurance_tenant_isolation_filter(
    tenant_a,
    tenant_b,
    warranty_a,
    warranty_b,
    insurance_policy_a,
    insurance_policy_b,
):
    """Assert tenant isolation queries never cross-leak records."""
    # Tenant A warranties
    warranties_a = AssetWarranty.objects.filter(tenant=tenant_a)
    assert warranty_a in warranties_a
    assert warranty_b not in warranties_a

    # Tenant B warranties
    warranties_b = AssetWarranty.objects.filter(tenant=tenant_b)
    assert warranty_b in warranties_b
    assert warranty_a not in warranties_b

    # Tenant A policies
    policies_a = AssetInsurancePolicy.objects.filter(tenant=tenant_a)
    assert insurance_policy_a in policies_a
    assert insurance_policy_b not in policies_a

    # Tenant B policies
    policies_b = AssetInsurancePolicy.objects.filter(tenant=tenant_b)
    assert insurance_policy_b in policies_b
    assert insurance_policy_a not in policies_b
