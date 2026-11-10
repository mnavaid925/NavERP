"""Model unit and invariant tests for Sub-module 11.9: Asset Disposal & Retirement.

Covers all 4 models:
- AssetDisposalRequest (ADSP-)
- AssetResaleListing (ARSL-)
- AssetTradeIn (ATRD-)
- AssetScrapSalvage (ASCR-)
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import FixedAsset
from apps.assets.models import (
    AssetCategory,
    AssetDisposalRequest,
    AssetResaleListing,
    AssetTradeIn,
    AssetScrapSalvage,
)
from apps.scm.models import Asset

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (Contract Aligned)
# ==============================================================================

def _assetdisposal_create_request(tenant, fixed_asset, **kwargs):
    """Helper to provision test disposal request with valid defaults."""
    defaults = {
        "title": "Industrial CNC Mill Decommissioning Initiative",
        "disposal_method": "resale",
        "retirement_reason": "technological_obsolescence",
        "justification_notes": "Asset replaced by modern high-precision machining unit.",
        "acquisition_cost": Decimal("60000.00"),
        "accumulated_depreciation": Decimal("40000.00"),
        "net_book_value": Decimal("20000.00"),
        "estimated_residual_value": Decimal("22000.00"),
        "estimated_removal_cost": Decimal("1500.00"),
    }
    defaults.update(kwargs)
    return AssetDisposalRequest.objects.create(
        tenant=tenant,
        fixed_asset=fixed_asset,
        **defaults,
    )


def _assetdisposal_create_resale(tenant, disposal_request, fixed_asset, **kwargs):
    """Helper to provision test resale listing with valid defaults."""
    defaults = {
        "listing_channel": "public_auction",
        "listing_reference": "AUCT-LOT-2026-001",
        "listing_date": timezone.now().date(),
        "reserve_price": Decimal("18000.00"),
        "asking_price": Decimal("25000.00"),
        "gross_sale_proceeds": Decimal("22000.00"),
        "commission_rate_percent": Decimal("5.00"),
        "status": "draft",
        "payment_status": "pending",
    }
    defaults.update(kwargs)
    return AssetResaleListing.objects.create(
        tenant=tenant,
        disposal_request=disposal_request,
        fixed_asset=fixed_asset,
        **defaults,
    )


def _assetdisposal_create_trade_in(tenant, disposal_request, retired_fixed_asset, vendor, **kwargs):
    """Helper to provision test trade-in record with valid defaults."""
    defaults = {
        "agreement_number": "TRD-AGR-2026-X1",
        "agreement_date": timezone.now().date(),
        "trade_in_allowance": Decimal("12000.00"),
        "over_allowance_amount": Decimal("1000.00"),
        "status": "draft",
    }
    defaults.update(kwargs)
    return AssetTradeIn.objects.create(
        tenant=tenant,
        disposal_request=disposal_request,
        retired_fixed_asset=retired_fixed_asset,
        vendor=vendor,
        **defaults,
    )


def _assetdisposal_create_scrap(tenant, disposal_request, fixed_asset, **kwargs):
    """Helper to provision test scrap & salvage record with valid defaults."""
    defaults = {
        "scrap_method": "dismantling_parts_recovery",
        "total_scrap_weight_kg": Decimal("1500.00"),
        "salvage_proceeds": Decimal("3000.00"),
        "dismantling_cost": Decimal("600.00"),
        "status": "draft",
    }
    defaults.update(kwargs)
    return AssetScrapSalvage.objects.create(
        tenant=tenant,
        disposal_request=disposal_request,
        fixed_asset=fixed_asset,
        **defaults,
    )


# ==============================================================================
# 1. AssetDisposalRequest Model Unit Tests
# ==============================================================================

def test_assetdisposal_request_str_and_prefix(disposal_request_a):
    """Assert number prefix starts with ADSP- and __str__ matches number - title format."""
    assert disposal_request_a.number.startswith("ADSP-")
    assert str(disposal_request_a) == f"{disposal_request_a.number} — {disposal_request_a.title}"
    assert disposal_request_a.NUMBER_PREFIX == "ADSP"


def test_assetdisposal_request_defaults(tenant_a, fixed_asset_a):
    """Assert model field defaults on AssetDisposalRequest."""
    req = _assetdisposal_create_request(tenant_a, fixed_asset_a)
    assert req.number.startswith("ADSP-")
    assert req.disposal_method == "resale"
    assert req.retirement_reason == "technological_obsolescence"
    assert req.status == "draft"
    assert req.actual_gross_proceeds == Decimal("0.00")
    assert req.actual_removal_cost == Decimal("0.00")
    assert req.realized_gain_loss == Decimal("0.00")
    assert req.submitted_at is None
    assert req.approved_at is None
    assert req.completed_at is None
    assert req.rejection_reason == ""


def test_assetdisposal_request_status_choices():
    """Assert all expected STATUS_CHOICES are present on AssetDisposalRequest."""
    expected = [
        "draft",
        "submitted",
        "appraised",
        "approved",
        "in_progress",
        "completed",
        "rejected",
        "cancelled",
    ]
    actual = [code for code, _ in AssetDisposalRequest.STATUS_CHOICES]
    assert actual == expected


def test_assetdisposal_request_disposal_method_choices():
    """Assert all expected DISPOSAL_METHOD_CHOICES are present on AssetDisposalRequest."""
    expected = [
        "resale",
        "trade_in",
        "scrap_salvage",
        "donation",
        "write_off_loss",
    ]
    actual = [code for code, _ in AssetDisposalRequest.DISPOSAL_METHOD_CHOICES]
    assert actual == expected


def test_assetdisposal_request_retirement_reason_choices():
    """Assert all expected RETIREMENT_REASON_CHOICES are present on AssetDisposalRequest."""
    expected = [
        "end_of_life",
        "uneconomical_repair",
        "technological_obsolescence",
        "damaged_accident",
        "lease_expired",
        "redundant_surplus",
        "regulatory_compliance",
        "other",
    ]
    actual = [code for code, _ in AssetDisposalRequest.RETIREMENT_REASON_CHOICES]
    assert actual == expected


def test_assetdisposal_request_status_css_mapping(disposal_request_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badge classes."""
    for status_code, badge_class in AssetDisposalRequest.STATUS_CSS.items():
        disposal_request_a.status = status_code
        assert disposal_request_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    # Unlisted status falls back to badge-slate
    disposal_request_a.status = "unknown_status"
    assert disposal_request_a.status_css == "badge-slate"


def test_assetdisposal_request_disposal_method_css_mapping(disposal_request_a):
    """Assert disposal_method_css maps all DISPOSAL_METHOD_CHOICES to color-named badges."""
    for method_code, badge_class in AssetDisposalRequest.DISPOSAL_METHOD_CSS.items():
        disposal_request_a.disposal_method = method_code
        assert disposal_request_a.disposal_method_css == badge_class
        assert badge_class.startswith("badge-")

    disposal_request_a.disposal_method = "unknown_method"
    assert disposal_request_a.disposal_method_css == "badge-slate"


def test_assetdisposal_request_retirement_reason_css_mapping(disposal_request_a):
    """Assert retirement_reason_css maps all RETIREMENT_REASON_CHOICES to color-named badges."""
    for reason_code, badge_class in AssetDisposalRequest.RETIREMENT_REASON_CSS.items():
        disposal_request_a.retirement_reason = reason_code
        assert disposal_request_a.retirement_reason_css == badge_class
        assert badge_class.startswith("badge-")

    disposal_request_a.retirement_reason = "unknown_reason"
    assert disposal_request_a.retirement_reason_css == "badge-slate"


def test_assetdisposal_request_calculate_gain_loss_profit(disposal_request_a):
    """Assert positive gain calculation: Proceeds (38,000) - Removal (2,000) - NBV (30,000) = +6,000."""
    disposal_request_a.net_book_value = Decimal("30000.00")
    disposal_request_a.actual_gross_proceeds = Decimal("38000.00")
    disposal_request_a.actual_removal_cost = Decimal("2000.00")

    result = disposal_request_a.calculate_gain_loss()
    assert result == Decimal("6000.00")
    assert disposal_request_a.realized_gain_loss == Decimal("6000.00")


def test_assetdisposal_request_calculate_gain_loss_loss(disposal_request_a):
    """Assert negative loss calculation: Proceeds (20,000) - Removal (2,500) - NBV (30,000) = -12,500."""
    disposal_request_a.net_book_value = Decimal("30000.00")
    disposal_request_a.actual_gross_proceeds = Decimal("20000.00")
    disposal_request_a.actual_removal_cost = Decimal("2500.00")

    result = disposal_request_a.calculate_gain_loss()
    assert result == Decimal("-12500.00")
    assert disposal_request_a.realized_gain_loss == Decimal("-12500.00")


def test_assetdisposal_request_calculate_gain_loss_zero_and_defaults(tenant_a, fixed_asset_a):
    """Assert gain/loss with zero actual proceeds results in negative carrying value loss."""
    req = _assetdisposal_create_request(
        tenant_a,
        fixed_asset_a,
        net_book_value=Decimal("15000.00"),
        actual_gross_proceeds=Decimal("0.00"),
        actual_removal_cost=Decimal("500.00"),
    )
    result = req.calculate_gain_loss()
    assert result == Decimal("-15500.00")
    assert req.realized_gain_loss == Decimal("-15500.00")


def test_assetdisposal_request_complete_disposal_logic(tenant_a, fixed_asset_a, operational_asset_a):
    """Assert complete_disposal() updates request, fixed_asset, and operational_asset statuses to 'disposed'."""
    # Setup initial active states
    fixed_asset_a.status = "active"
    fixed_asset_a.save()
    operational_asset_a.status = "in_service"
    operational_asset_a.save()

    req = _assetdisposal_create_request(
        tenant_a,
        fixed_asset_a,
        operational_asset=operational_asset_a,
        net_book_value=Decimal("25000.00"),
        actual_gross_proceeds=Decimal("30000.00"),
        actual_removal_cost=Decimal("1000.00"),
        status="approved",
    )

    req.complete_disposal()

    # Request state
    req.refresh_from_db()
    assert req.status == "completed"
    assert req.completed_at is not None
    assert req.realized_gain_loss == Decimal("4000.00")

    # Fixed asset status updated to disposed
    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.status == "disposed"

    # Operational asset status updated to disposed
    operational_asset_a.refresh_from_db()
    assert operational_asset_a.status == "disposed"


def test_assetdisposal_request_complete_without_operational_asset(tenant_a, fixed_asset_a):
    """Assert complete_disposal() safely completes when operational_asset is None."""
    fixed_asset_a.status = "active"
    fixed_asset_a.save()

    req = _assetdisposal_create_request(
        tenant_a,
        fixed_asset_a,
        operational_asset=None,
        status="approved",
    )
    req.complete_disposal()

    req.refresh_from_db()
    assert req.status == "completed"
    fixed_asset_a.refresh_from_db()
    assert fixed_asset_a.status == "disposed"


# ==============================================================================
# 2. AssetResaleListing Model Unit Tests
# ==============================================================================

def test_assetdisposal_resale_listing_str_and_prefix(resale_listing_a):
    """Assert number prefix starts with ARSL- and __str__ matches format."""
    assert resale_listing_a.number.startswith("ARSL-")
    assert resale_listing_a.NUMBER_PREFIX == "ARSL"
    expected_str = f"{resale_listing_a.number} — {resale_listing_a.fixed_asset.name} ({resale_listing_a.get_listing_channel_display()})"
    assert str(resale_listing_a) == expected_str


def test_assetdisposal_resale_listing_defaults(tenant_a, disposal_request_a, fixed_asset_a):
    """Assert default field values on AssetResaleListing."""
    listing = _assetdisposal_create_resale(tenant_a, disposal_request_a, fixed_asset_a)
    assert listing.number.startswith("ARSL-")
    assert listing.listing_channel == "public_auction"
    assert listing.status == "draft"
    assert listing.payment_status == "pending"
    assert listing.reserve_price == Decimal("18000.00")
    assert listing.highest_bid_amount == Decimal("0.00")
    assert listing.commission_amount == Decimal("0.00")
    assert listing.net_sale_proceeds == Decimal("0.00")
    assert listing.tax_amount == Decimal("0.00")
    assert listing.closing_date is None
    assert listing.payment_date is None
    assert listing.pickup_delivery_date is None


def test_assetdisposal_resale_listing_status_choices():
    """Assert all expected STATUS_CHOICES are present on AssetResaleListing."""
    expected = [
        "draft",
        "listed",
        "bid_received",
        "negotiation",
        "sold",
        "payment_received",
        "delivered",
        "unsold_withdrawn",
        "cancelled",
    ]
    actual = [code for code, _ in AssetResaleListing.STATUS_CHOICES]
    assert actual == expected


def test_assetdisposal_resale_listing_channel_choices():
    """Assert all expected LISTING_CHANNEL_CHOICES are present on AssetResaleListing."""
    expected = [
        "public_auction",
        "private_treaty",
        "online_marketplace",
        "employee_sale",
        "dealer_wholesale",
    ]
    actual = [code for code, _ in AssetResaleListing.LISTING_CHANNEL_CHOICES]
    assert actual == expected


def test_assetdisposal_resale_listing_payment_status_choices():
    """Assert all expected PAYMENT_STATUS_CHOICES are present on AssetResaleListing."""
    expected = [
        "pending",
        "partial",
        "paid",
        "waived",
    ]
    actual = [code for code, _ in AssetResaleListing.PAYMENT_STATUS_CHOICES]
    assert actual == expected


def test_assetdisposal_resale_listing_status_css_mapping(resale_listing_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badge classes."""
    for status_code, badge_class in AssetResaleListing.STATUS_CSS.items():
        resale_listing_a.status = status_code
        assert resale_listing_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    resale_listing_a.status = "unknown_status"
    assert resale_listing_a.status_css == "badge-slate"


def test_assetdisposal_resale_listing_channel_css_mapping(resale_listing_a):
    """Assert listing_channel_css maps all channels to color-named badge classes."""
    for channel_code, badge_class in AssetResaleListing.LISTING_CHANNEL_CSS.items():
        resale_listing_a.listing_channel = channel_code
        assert resale_listing_a.listing_channel_css == badge_class
        assert badge_class.startswith("badge-")

    resale_listing_a.listing_channel = "unknown_channel"
    assert resale_listing_a.listing_channel_css == "badge-slate"


def test_assetdisposal_resale_listing_payment_status_css_mapping(resale_listing_a):
    """Assert payment_status_css maps all payment statuses to color-named badges."""
    for pstatus_code, badge_class in AssetResaleListing.PAYMENT_STATUS_CSS.items():
        resale_listing_a.payment_status = pstatus_code
        assert resale_listing_a.payment_status_css == badge_class
        assert badge_class.startswith("badge-")

    resale_listing_a.payment_status = "unknown_pstatus"
    assert resale_listing_a.payment_status_css == "badge-slate"


def test_assetdisposal_resale_listing_calculate_settlement_with_commission(resale_listing_a):
    """Assert settlement calculation: Gross (36,500) @ 5% Commission (1,825) = Net (34,675)."""
    resale_listing_a.gross_sale_proceeds = Decimal("36500.00")
    resale_listing_a.commission_rate_percent = Decimal("5.00")

    net = resale_listing_a.calculate_settlement()
    assert resale_listing_a.commission_amount == Decimal("1825.00")
    assert net == Decimal("34675.00")
    assert resale_listing_a.net_sale_proceeds == Decimal("34675.00")


def test_assetdisposal_resale_listing_calculate_settlement_zero_commission(tenant_a, disposal_request_a, fixed_asset_a):
    """Assert settlement calculation with 0% commission yields gross equal to net."""
    listing = _assetdisposal_create_resale(
        tenant_a,
        disposal_request_a,
        fixed_asset_a,
        gross_sale_proceeds=Decimal("50000.00"),
        commission_rate_percent=Decimal("0.00"),
    )
    net = listing.calculate_settlement()
    assert listing.commission_amount == Decimal("0.00")
    assert net == Decimal("50000.00")
    assert listing.net_sale_proceeds == Decimal("50000.00")


def test_assetdisposal_resale_listing_calculate_settlement_empty_proceeds(tenant_a, disposal_request_a, fixed_asset_a):
    """Assert settlement calculation with zero proceeds yields zero net."""
    listing = _assetdisposal_create_resale(
        tenant_a,
        disposal_request_a,
        fixed_asset_a,
        gross_sale_proceeds=Decimal("0.00"),
        commission_rate_percent=Decimal("10.00"),
    )
    net = listing.calculate_settlement()
    assert listing.commission_amount == Decimal("0.00")
    assert net == Decimal("0.00")


# ==============================================================================
# 3. AssetTradeIn Model Unit Tests
# ==============================================================================

def test_assetdisposal_trade_in_str_and_prefix(trade_in_a):
    """Assert number prefix starts with ATRD- and __str__ matches format."""
    assert trade_in_a.number.startswith("ATRD-")
    assert trade_in_a.NUMBER_PREFIX == "ATRD"
    expected = f"{trade_in_a.number} — {trade_in_a.retired_fixed_asset.name} trade to {trade_in_a.vendor.name}"
    assert str(trade_in_a) == expected


def test_assetdisposal_trade_in_defaults(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a):
    """Assert model field defaults on AssetTradeIn."""
    trd = _assetdisposal_create_trade_in(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a)
    assert trd.number.startswith("ATRD-")
    assert trd.status == "draft"
    assert trd.dealer_appraised_value == Decimal("0.00")
    assert trd.trade_in_allowance == Decimal("12000.00")
    assert trd.over_allowance_amount == Decimal("1000.00")
    assert trd.net_credit_applied == Decimal("0.00")
    assert trd.replacement_asset_cost == Decimal("0.00")
    assert trd.net_cash_outflow == Decimal("0.00")
    assert trd.like_kind_exchange is False
    assert trd.gain_loss_deferred == Decimal("0.00")
    assert trd.surrendered_at is None
    assert trd.settled_at is None


def test_assetdisposal_trade_in_status_choices():
    """Assert all expected STATUS_CHOICES are present on AssetTradeIn."""
    expected = [
        "draft",
        "proposed",
        "negotiated",
        "accepted",
        "equipment_surrendered",
        "credit_settled",
        "rejected",
        "cancelled",
    ]
    actual = [code for code, _ in AssetTradeIn.STATUS_CHOICES]
    assert actual == expected


def test_assetdisposal_trade_in_status_css_mapping(trade_in_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badge classes."""
    for status_code, badge_class in AssetTradeIn.STATUS_CSS.items():
        trade_in_a.status = status_code
        assert trade_in_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    trade_in_a.status = "unknown_status"
    assert trade_in_a.status_css == "badge-slate"


def test_assetdisposal_trade_in_calculate_trade_credit_with_cash_outflow(trade_in_a):
    """Assert credit and cash outflow: Allowance (15,000) + Over (2,000) against Replacement (50,000) = 33,000 Outflow."""
    trade_in_a.trade_in_allowance = Decimal("15000.00")
    trade_in_a.over_allowance_amount = Decimal("2000.00")
    trade_in_a.replacement_asset_cost = Decimal("50000.00")

    credit = trade_in_a.calculate_trade_credit()
    assert credit == Decimal("17000.00")
    assert trade_in_a.net_credit_applied == Decimal("17000.00")
    assert trade_in_a.net_cash_outflow == Decimal("33000.00")


def test_assetdisposal_trade_in_calculate_trade_credit_full_coverage(trade_in_a):
    """Assert cash outflow does not go below zero when credit exceeds replacement cost."""
    trade_in_a.trade_in_allowance = Decimal("25000.00")
    trade_in_a.over_allowance_amount = Decimal("5000.00")
    trade_in_a.replacement_asset_cost = Decimal("28000.00")

    credit = trade_in_a.calculate_trade_credit()
    assert credit == Decimal("30000.00")
    assert trade_in_a.net_credit_applied == Decimal("30000.00")
    assert trade_in_a.net_cash_outflow == Decimal("0.00")


def test_assetdisposal_trade_in_calculate_trade_credit_zero_replacement_cost(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a):
    """Assert calculate_trade_credit() handles zero replacement cost gracefully."""
    trd = _assetdisposal_create_trade_in(
        tenant_a,
        disposal_request_a,
        fixed_asset_a,
        vendor_party_a,
        trade_in_allowance=Decimal("10000.00"),
        over_allowance_amount=Decimal("0.00"),
        replacement_asset_cost=Decimal("0.00"),
    )
    credit = trd.calculate_trade_credit()
    assert credit == Decimal("10000.00")
    assert trd.net_cash_outflow == Decimal("0.00")


def test_assetdisposal_trade_in_like_kind_exchange_flags(trade_in_a):
    """Assert IRC Sec 1031 like-kind exchange flag and deferred gain/loss persistence."""
    trade_in_a.like_kind_exchange = True
    trade_in_a.gain_loss_deferred = Decimal("4500.00")
    trade_in_a.save()

    trade_in_a.refresh_from_db()
    assert trade_in_a.like_kind_exchange is True
    assert trade_in_a.gain_loss_deferred == Decimal("4500.00")


# ==============================================================================
# 4. AssetScrapSalvage Model Unit Tests
# ==============================================================================

def test_assetdisposal_scrap_salvage_str_and_prefix(scrap_salvage_a):
    """Assert number prefix starts with ASCR- and __str__ matches format."""
    assert scrap_salvage_a.number.startswith("ASCR-")
    assert scrap_salvage_a.NUMBER_PREFIX == "ASCR"
    expected = f"{scrap_salvage_a.number} — {scrap_salvage_a.fixed_asset.name} ({scrap_salvage_a.get_scrap_method_display()})"
    assert str(scrap_salvage_a) == expected


def test_assetdisposal_scrap_salvage_defaults(tenant_a, disposal_request_a, fixed_asset_a):
    """Assert model field defaults on AssetScrapSalvage."""
    scrap = _assetdisposal_create_scrap(tenant_a, disposal_request_a, fixed_asset_a)
    assert scrap.number.startswith("ASCR-")
    assert scrap.scrap_method == "dismantling_parts_recovery"
    assert scrap.status == "draft"
    assert scrap.sanitization_method == "none"
    assert scrap.total_scrap_weight_kg == Decimal("1500.00")
    assert scrap.ferrous_weight_kg == Decimal("0.00")
    assert scrap.non_ferrous_weight_kg == Decimal("0.00")
    assert scrap.e_waste_weight_kg == Decimal("0.00")
    assert scrap.net_salvage_recovery == Decimal("0.00")
    assert scrap.has_hazardous_materials is False
    assert scrap.abatement_certified is False
    assert scrap.data_sanitized is False
    assert scrap.completion_date is None
    assert scrap.abatement_date is None
    assert scrap.cod_issue_date is None


def test_assetdisposal_scrap_salvage_scrap_method_choices():
    """Assert all expected SCRAP_METHOD_CHOICES are present on AssetScrapSalvage."""
    expected = [
        "physical_destruction",
        "dismantling_parts_recovery",
        "shredding_recycling",
        "e_waste_itad",
        "hazardous_waste_abatement",
    ]
    actual = [code for code, _ in AssetScrapSalvage.SCRAP_METHOD_CHOICES]
    assert actual == expected


def test_assetdisposal_scrap_salvage_status_choices():
    """Assert all expected STATUS_CHOICES are present on AssetScrapSalvage."""
    expected = [
        "draft",
        "dismantling",
        "abatement_in_progress",
        "scrap_transferred",
        "certified_destroyed",
        "settled",
        "cancelled",
    ]
    actual = [code for code, _ in AssetScrapSalvage.STATUS_CHOICES]
    assert actual == expected


def test_assetdisposal_scrap_salvage_sanitization_method_choices():
    """Assert all expected SANITIZATION_METHOD_CHOICES are present on AssetScrapSalvage."""
    expected = [
        "none",
        "nist_clear",
        "nist_purge",
        "dod_5220_wipe",
        "physical_shredding",
        "crypto_erase",
    ]
    actual = [code for code, _ in AssetScrapSalvage.SANITIZATION_METHOD_CHOICES]
    assert actual == expected


def test_assetdisposal_scrap_salvage_status_css_mapping(scrap_salvage_a):
    """Assert status_css maps all STATUS_CHOICES to color-named badge classes."""
    for status_code, badge_class in AssetScrapSalvage.STATUS_CSS.items():
        scrap_salvage_a.status = status_code
        assert scrap_salvage_a.status_css == badge_class
        assert badge_class.startswith("badge-")

    scrap_salvage_a.status = "unknown_status"
    assert scrap_salvage_a.status_css == "badge-slate"


def test_assetdisposal_scrap_salvage_scrap_method_css_mapping(scrap_salvage_a):
    """Assert scrap_method_css maps all methods to color-named badge classes."""
    for method_code, badge_class in AssetScrapSalvage.SCRAP_METHOD_CSS.items():
        scrap_salvage_a.scrap_method = method_code
        assert scrap_salvage_a.scrap_method_css == badge_class
        assert badge_class.startswith("badge-")

    scrap_salvage_a.scrap_method = "unknown_method"
    assert scrap_salvage_a.scrap_method_css == "badge-slate"


def test_assetdisposal_scrap_salvage_sanitization_method_css_mapping(scrap_salvage_a):
    """Assert sanitization_method_css maps all sanitization methods to color-named badges."""
    for sanit_code, badge_class in AssetScrapSalvage.SANITIZATION_METHOD_CSS.items():
        scrap_salvage_a.sanitization_method = sanit_code
        assert scrap_salvage_a.sanitization_method_css == badge_class
        assert badge_class.startswith("badge-")

    scrap_salvage_a.sanitization_method = "unknown_sanit"
    assert scrap_salvage_a.sanitization_method_css == "badge-slate"


def test_assetdisposal_scrap_salvage_calculate_net_recovery_positive(scrap_salvage_a):
    """Assert net recovery calculation: Proceeds (2,500) - Dismantling Cost (450) = +2,050."""
    scrap_salvage_a.salvage_proceeds = Decimal("2500.00")
    scrap_salvage_a.dismantling_cost = Decimal("450.00")

    recovery = scrap_salvage_a.calculate_net_recovery()
    assert recovery == Decimal("2050.00")
    assert scrap_salvage_a.net_salvage_recovery == Decimal("2050.00")


def test_assetdisposal_scrap_salvage_calculate_net_recovery_negative(tenant_a, disposal_request_a, fixed_asset_a):
    """Assert net recovery calculation when dismantling cost exceeds salvage proceeds (net cost)."""
    scrap = _assetdisposal_create_scrap(
        tenant_a,
        disposal_request_a,
        fixed_asset_a,
        salvage_proceeds=Decimal("800.00"),
        dismantling_cost=Decimal("1500.00"),
    )
    recovery = scrap.calculate_net_recovery()
    assert recovery == Decimal("-700.00")
    assert scrap.net_salvage_recovery == Decimal("-700.00")


def test_assetdisposal_scrap_salvage_hazardous_waste_compliance(scrap_salvage_a):
    """Assert hazardous waste flags and manifest identification tracking."""
    scrap_salvage_a.has_hazardous_materials = True
    scrap_salvage_a.hazardous_waste_class = "EPA-RCRA-D008"
    scrap_salvage_a.epa_manifest_number = "EPA-MNF-2026-9081"
    scrap_salvage_a.abatement_certified = True
    scrap_salvage_a.abatement_date = timezone.now().date()
    scrap_salvage_a.save()

    scrap_salvage_a.refresh_from_db()
    assert scrap_salvage_a.has_hazardous_materials is True
    assert scrap_salvage_a.hazardous_waste_class == "EPA-RCRA-D008"
    assert scrap_salvage_a.epa_manifest_number == "EPA-MNF-2026-9081"
    assert scrap_salvage_a.abatement_certified is True
    assert scrap_salvage_a.abatement_date is not None


def test_assetdisposal_scrap_salvage_data_sanitization_clearance(scrap_salvage_a):
    """Assert electronic media data sanitization clearance and DoD multi-pass certification."""
    scrap_salvage_a.data_sanitized = True
    scrap_salvage_a.sanitization_method = "dod_5220_wipe"
    scrap_salvage_a.sanitization_verified_by = "SecOps Lead J. Mercer (CISSP)"
    scrap_salvage_a.cod_number = "COD-ITAD-2026-881"
    scrap_salvage_a.cod_issue_date = timezone.now().date()
    scrap_salvage_a.cod_issuing_agency = "Apex Certified Destruction Ltd"
    scrap_salvage_a.save()

    scrap_salvage_a.refresh_from_db()
    assert scrap_salvage_a.data_sanitized is True
    assert scrap_salvage_a.sanitization_method == "dod_5220_wipe"
    assert scrap_salvage_a.cod_number == "COD-ITAD-2026-881"


# ==============================================================================
# 5. Invariants (Auto-numbering, Tenant Scoping, Unique Constraints)
# ==============================================================================

def test_assetdisposal_auto_numbering_sequential(tenant_a, fixed_asset_a):
    """Assert TenantNumbered automatically issues sequential document numbers per model."""
    req1 = _assetdisposal_create_request(tenant_a, fixed_asset_a, title="Decommission Plan 1")
    req2 = _assetdisposal_create_request(tenant_a, fixed_asset_a, title="Decommission Plan 2")

    assert req1.number.startswith("ADSP-")
    assert req2.number.startswith("ADSP-")
    assert req1.number != req2.number

    num1 = int(req1.number.split("-")[-1])
    num2 = int(req2.number.split("-")[-1])
    assert num2 == num1 + 1


def test_assetdisposal_tenant_scoping_isolation(
    disposal_request_a,
    disposal_request_b,
    resale_listing_a,
    resale_listing_b,
    trade_in_a,
    trade_in_b,
    scrap_salvage_a,
    scrap_salvage_b,
):
    """Assert models strictly isolate queries per tenant and do not leak cross-tenant rows."""
    tenant_a = disposal_request_a.tenant
    tenant_b = disposal_request_b.tenant

    # Disposal Requests
    assert AssetDisposalRequest.objects.filter(tenant=tenant_a).filter(pk=disposal_request_b.pk).exists() is False
    assert AssetDisposalRequest.objects.filter(tenant=tenant_b).filter(pk=disposal_request_a.pk).exists() is False

    # Resale Listings
    assert AssetResaleListing.objects.filter(tenant=tenant_a).filter(pk=resale_listing_b.pk).exists() is False
    assert AssetResaleListing.objects.filter(tenant=tenant_b).filter(pk=resale_listing_a.pk).exists() is False

    # Trade-ins
    assert AssetTradeIn.objects.filter(tenant=tenant_a).filter(pk=trade_in_b.pk).exists() is False
    assert AssetTradeIn.objects.filter(tenant=tenant_b).filter(pk=trade_in_a.pk).exists() is False

    # Scrap Salvages
    assert AssetScrapSalvage.objects.filter(tenant=tenant_a).filter(pk=scrap_salvage_b.pk).exists() is False
    assert AssetScrapSalvage.objects.filter(tenant=tenant_b).filter(pk=scrap_salvage_a.pk).exists() is False


def test_assetdisposal_unique_constraint_same_tenant_raises_error(tenant_a, fixed_asset_a, vendor_party_a, disposal_request_a):
    """Assert unique constraint on ['tenant', 'number'] raises IntegrityError on collision."""
    # AssetDisposalRequest duplicate number
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetDisposalRequest.objects.create(
                tenant=tenant_a,
                number=disposal_request_a.number,
                fixed_asset=fixed_asset_a,
                title="Duplicate ADSP Number",
            )

    # AssetResaleListing duplicate number
    resale = _assetdisposal_create_resale(tenant_a, disposal_request_a, fixed_asset_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetResaleListing.objects.create(
                tenant=tenant_a,
                number=resale.number,
                disposal_request=disposal_request_a,
                fixed_asset=fixed_asset_a,
            )

    # AssetTradeIn duplicate number
    trade = _assetdisposal_create_trade_in(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetTradeIn.objects.create(
                tenant=tenant_a,
                number=trade.number,
                disposal_request=disposal_request_a,
                retired_fixed_asset=fixed_asset_a,
                vendor=vendor_party_a,
            )

    # AssetScrapSalvage duplicate number
    scrap = _assetdisposal_create_scrap(tenant_a, disposal_request_a, fixed_asset_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetScrapSalvage.objects.create(
                tenant=tenant_a,
                number=scrap.number,
                disposal_request=disposal_request_a,
                fixed_asset=fixed_asset_a,
            )


def test_assetdisposal_unique_number_cross_tenant_allowed(tenant_a, tenant_b, fixed_asset_a, fixed_asset_b):
    """Assert that the same document number is allowed across different tenants."""
    shared_number = "ADSP-SHARED-001"
    req_a = AssetDisposalRequest.objects.create(
        tenant=tenant_a,
        number=shared_number,
        fixed_asset=fixed_asset_a,
        title="Tenant A Disposal",
    )
    req_b = AssetDisposalRequest.objects.create(
        tenant=tenant_b,
        number=shared_number,
        fixed_asset=fixed_asset_b,
        title="Tenant B Disposal",
    )
    assert req_a.number == req_b.number
    assert req_a.tenant != req_b.tenant
