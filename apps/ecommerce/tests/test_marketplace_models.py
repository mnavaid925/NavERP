"""Unit and invariant tests for eCommerce 9.11 Marketplace & Multi-Vendor models.

Covers:
- MarketplaceVendor
- VendorProductListing
- VendorSubOrder
- VendorPayout

Naming conventions enforced:
- Test functions: test_marketplace_*
- Module-level helpers: _marketplace_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.ecommerce.models import (
    MarketplaceVendor,
    VendorProductListing,
    VendorSubOrder,
    VendorPayout,
)
from apps.ecommerce.tests.conftest import (
    _marketplace_party,
    _marketplace_vendor,
    _marketplace_listing,
    _marketplace_suborder,
    _marketplace_payout,
    _productcatalog_product,
    _productcatalog_variant,
    _ordermanagement_order,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# MarketplaceVendor Model Tests
# ==============================================================================

def test_marketplace_vendor_creation_and_auto_number(tenant_a):
    vendor = _marketplace_vendor(tenant_a, store_name="Starlight Crafts")
    assert vendor.pk is not None
    assert vendor.number.startswith("EMKV-")
    assert vendor.store_name == "Starlight Crafts"
    assert vendor.status == "approved"
    assert vendor.kyc_status == "verified"
    assert str(vendor) == f"{vendor.store_name} ({vendor.number})"


def test_marketplace_vendor_clean_negative_commission_rejected(tenant_a):
    vendor = _marketplace_vendor(tenant_a, store_name="Invalid Commission Store")
    vendor.commission_rate = Decimal("-5.00")
    with pytest.raises(ValidationError) as exc_info:
        vendor.clean()
    assert "commission_rate" in exc_info.value.message_dict

    vendor.commission_rate = Decimal("10.00")
    vendor.fixed_fee_per_order = Decimal("-1.00")
    with pytest.raises(ValidationError) as exc_info:
        vendor.clean()
    assert "fixed_fee_per_order" in exc_info.value.message_dict

    vendor.fixed_fee_per_order = Decimal("1.00")
    vendor.min_payout_amount = Decimal("-10.00")
    with pytest.raises(ValidationError) as exc_info:
        vendor.clean()
    assert "min_payout_amount" in exc_info.value.message_dict


def test_marketplace_vendor_rating_aggregation(tenant_a):
    vendor = _marketplace_vendor(tenant_a, store_name="Review Star Store")
    order = _ordermanagement_order(tenant_a)

    sub1 = _marketplace_suborder(tenant_a, vendor=vendor, order=order, customer_rating=5)
    sub2 = _marketplace_suborder(tenant_a, vendor=vendor, order=order, customer_rating=4)

    vendor.update_rating()
    vendor.refresh_from_db()
    assert vendor.rating_count == 2
    assert vendor.rating_average == Decimal("4.50")


# ==============================================================================
# VendorProductListing Model Tests
# ==============================================================================

def test_marketplace_listing_creation_and_auto_number(tenant_a, ecom_vendor_a, ecom_product_a):
    listing = _marketplace_listing(tenant_a, vendor=ecom_vendor_a, product=ecom_product_a)
    assert listing.pk is not None
    assert listing.number.startswith("EVPL-")
    assert listing.condition == "new"
    assert listing.moderation_status == "approved"
    assert str(listing) == f"{ecom_product_a.name} [{listing.seller_sku}] — {ecom_vendor_a.store_name} ({listing.number})"


def test_marketplace_listing_clean_negative_values_rejected(tenant_a, ecom_vendor_a, ecom_product_a):
    listing = _marketplace_listing(tenant_a, vendor=ecom_vendor_a, product=ecom_product_a)
    listing.asking_price = Decimal("-1.00")
    with pytest.raises(ValidationError) as exc_info:
        listing.clean()
    assert "asking_price" in exc_info.value.message_dict

    listing.asking_price = Decimal("20.00")
    listing.compare_at_price = Decimal("-5.00")
    with pytest.raises(ValidationError) as exc_info:
        listing.clean()
    assert "compare_at_price" in exc_info.value.message_dict

    listing.compare_at_price = Decimal("25.00")
    listing.cost_price = Decimal("-2.00")
    with pytest.raises(ValidationError) as exc_info:
        listing.clean()
    assert "cost_price" in exc_info.value.message_dict


def test_marketplace_listing_clean_variant_product_mismatch(tenant_a, ecom_vendor_a, ecom_product_a):
    unrelated_product = _productcatalog_product(tenant_a, name="Unrelated Gadget")
    unrelated_variant = _productcatalog_variant(tenant_a, product=unrelated_product, sku="UNREL-VAR-01")

    listing = _marketplace_listing(
        tenant_a,
        vendor=ecom_vendor_a,
        product=ecom_product_a,
        variant=unrelated_variant,
    )
    with pytest.raises(ValidationError) as exc_info:
        listing.clean()
    assert "variant" in exc_info.value.message_dict


# ==============================================================================
# VendorSubOrder Model Tests
# ==============================================================================

def test_marketplace_suborder_creation_and_auto_number(tenant_a, ecom_vendor_a):
    sub_order = _marketplace_suborder(tenant_a, vendor=ecom_vendor_a)
    assert sub_order.pk is not None
    assert sub_order.number.startswith("EVSO-")
    assert sub_order.fulfillment_status == "unfulfilled"
    assert sub_order.payout_status == "accrued"
    assert str(sub_order) == f"{sub_order.number} (Order {sub_order.order.number} • {ecom_vendor_a.store_name})"


def test_marketplace_suborder_payout_vendor_alignment_validation(tenant_a, ecom_vendor_a):
    other_vendor = _marketplace_vendor(tenant_a, store_name="Other Vendor")
    mismatched_payout = _marketplace_payout(tenant_a, vendor=other_vendor)

    sub_order = _marketplace_suborder(tenant_a, vendor=ecom_vendor_a)
    sub_order.payout = mismatched_payout
    with pytest.raises(ValidationError) as exc_info:
        sub_order.clean()
    assert "payout" in exc_info.value.message_dict


def test_marketplace_suborder_calculate_financials_percentage(tenant_a):
    vendor = _marketplace_vendor(
        tenant_a,
        commission_type="percentage",
        commission_rate=Decimal("10.00"),
        fixed_fee_per_order=Decimal("5.00"),
    )
    sub_order = _marketplace_suborder(
        tenant_a,
        vendor=vendor,
        commission_rate=Decimal("10.00"),
        subtotal_amount=Decimal("200.00"),
        shipping_amount=Decimal("15.00"),
    )
    sub_order.calculate_financials()
    # 10% of 200 = 20.00
    assert sub_order.commission_amount == Decimal("20.00")
    # net = (200.00 + 15.00) - 20.00 = 195.00
    assert sub_order.net_vendor_amount == Decimal("195.00")


def test_marketplace_suborder_calculate_financials_fixed(tenant_a):
    vendor = _marketplace_vendor(
        tenant_a,
        commission_type="fixed",
        commission_rate=Decimal("20.00"),
        fixed_fee_per_order=Decimal("7.50"),
    )
    sub_order = _marketplace_suborder(
        tenant_a,
        vendor=vendor,
        subtotal_amount=Decimal("100.00"),
        shipping_amount=Decimal("0.00"),
    )
    sub_order.calculate_financials()
    assert sub_order.commission_amount == Decimal("7.50")
    assert sub_order.net_vendor_amount == Decimal("92.50")


def test_marketplace_suborder_calculate_financials_combined(tenant_a):
    vendor = _marketplace_vendor(
        tenant_a,
        commission_type="combined",
        commission_rate=Decimal("10.00"),
        fixed_fee_per_order=Decimal("2.00"),
    )
    sub_order = _marketplace_suborder(
        tenant_a,
        vendor=vendor,
        commission_rate=Decimal("10.00"),
        subtotal_amount=Decimal("100.00"),
        shipping_amount=Decimal("5.00"),
    )
    sub_order.calculate_financials()
    # 10% of 100 = 10.00 + 2.00 = 12.00
    assert sub_order.commission_amount == Decimal("12.00")
    # net = (100 + 5) - 12 = 93.00
    assert sub_order.net_vendor_amount == Decimal("93.00")


def test_marketplace_suborder_sla_status_on_time_and_breached(tenant_a, ecom_vendor_a):
    now = timezone.now()
    sub_order = _marketplace_suborder(
        tenant_a,
        vendor=ecom_vendor_a,
        promised_dispatch_date=now.date(),
        dispatched_at=now - timedelta(days=1),
        fulfillment_status="shipped",
    )
    sub_order.evaluate_sla()
    assert sub_order.sla_status == "on_time"

    # Dispatched after promised dispatch date
    sub_order.dispatched_at = now + timedelta(days=2)
    sub_order.evaluate_sla()
    assert sub_order.sla_status == "breached"


# ==============================================================================
# VendorPayout Model Tests
# ==============================================================================

def test_marketplace_payout_creation_and_auto_number(tenant_a, ecom_vendor_a):
    payout = _marketplace_payout(tenant_a, vendor=ecom_vendor_a)
    assert payout.pk is not None
    assert payout.number.startswith("EVPO-")
    assert payout.payout_status == "draft"
    assert str(payout) == f"{payout.number} ({ecom_vendor_a.store_name} • ${payout.net_payout_amount})"


def test_marketplace_payout_clean_negative_volume_rejected(tenant_a, ecom_vendor_a):
    payout = _marketplace_payout(tenant_a, vendor=ecom_vendor_a)
    payout.gross_sales_amount = Decimal("-100.00")
    with pytest.raises(ValidationError) as exc_info:
        payout.clean()
    assert "gross_sales_amount" in exc_info.value.message_dict


def test_marketplace_payout_clean_period_dates_invalid(tenant_a, ecom_vendor_a):
    payout = _marketplace_payout(tenant_a, vendor=ecom_vendor_a)
    today = timezone.now().date()
    payout.period_start = today + timedelta(days=5)
    payout.period_end = today
    with pytest.raises(ValidationError) as exc_info:
        payout.clean()
    assert "period_end" in exc_info.value.message_dict


def test_marketplace_payout_calculate_net(tenant_a, ecom_vendor_a):
    payout = _marketplace_payout(
        tenant_a,
        vendor=ecom_vendor_a,
        gross_sales_amount=Decimal("1000.00"),
        commission_deducted=Decimal("150.00"),
        fees_deducted=Decimal("25.00"),
        refunds_deducted=Decimal("50.00"),
        tax_withholding_amount=Decimal("10.00"),
    )
    payout.calculate_net()
    # 1000 - 150 - 25 - 50 - 10 = 765.00
    assert payout.net_payout_amount == Decimal("765.00")
