"""Form validation and foreign-key isolation tests for eCommerce 9.11 Marketplace forms.

Covers:
- MarketplaceVendorForm
- VendorProductListingForm
- VendorSubOrderForm
- VendorPayoutForm
- Action forms (KYC, suspension, moderation, fulfillment, dispute)

Naming conventions enforced:
- Test functions: test_marketplace_*
- Module-level helpers: _marketplace_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.ecommerce.forms.Marketplace.MarketplaceVendorForms import (
    MarketplaceVendorForm,
    VendorKycVerificationForm,
    VendorSuspensionForm,
)
from apps.ecommerce.forms.Marketplace.VendorProductListingForms import (
    VendorProductListingForm,
    ListingModerationForm,
)
from apps.ecommerce.forms.Marketplace.VendorSubOrderForms import (
    VendorSubOrderForm,
    SubOrderFulfillmentForm,
    SubOrderDisputeForm,
)
from apps.ecommerce.forms.Marketplace.VendorPayoutForms import (
    VendorPayoutForm,
    PayoutApprovalForm,
)
from apps.ecommerce.tests.conftest import (
    _marketplace_party,
    _marketplace_vendor,
    _productcatalog_product,
    _productcatalog_variant,
    _ordermanagement_order,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# MarketplaceVendorForm Tests
# ==============================================================================

def test_marketplace_vendor_form_valid(tenant_a):
    party = _marketplace_party(tenant_a, name="Apex Goods LLC")
    form_data = {
        "party": party.pk,
        "store_name": "Apex Goods Store",
        "slug": "apex-goods-store",
        "status": "approved",
        "kyc_status": "verified",
        "commission_type": "percentage",
        "commission_rate": "12.50",
        "fixed_fee_per_order": "1.00",
        "payout_method": "bank_transfer",
        "min_payout_amount": "50.00",
        "tax_form_status": "not_required",
        "shipping_lead_time_days": 2,
    }
    form = MarketplaceVendorForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_marketplace_vendor_form_excludes(tenant_a):
    form = MarketplaceVendorForm(tenant=tenant_a)
    for field in ["tenant", "number", "rating_average", "rating_count", "kyc_verified_at", "created_at", "updated_at"]:
        assert field not in form.fields


def test_marketplace_vendor_form_reject_foreign_party(tenant_a, tenant_b):
    party_b = _marketplace_party(tenant_b, name="Globex Foreign Party")
    form_data = {
        "party": party_b.pk,
        "store_name": "Infiltrator Store",
        "slug": "infiltrator-store",
        "status": "draft",
        "kyc_status": "unsubmitted",
        "commission_type": "percentage",
        "commission_rate": "15.00",
        "fixed_fee_per_order": "0.00",
        "payout_method": "bank_transfer",
        "min_payout_amount": "50.00",
        "shipping_lead_time_days": 2,
    }
    form = MarketplaceVendorForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors


# ==============================================================================
# VendorProductListingForm Tests
# ==============================================================================

def test_marketplace_listing_form_valid(tenant_a, ecom_vendor_a, ecom_product_a):
    form_data = {
        "vendor": ecom_vendor_a.pk,
        "product": ecom_product_a.pk,
        "seller_sku": "APX-SKU-100",
        "condition": "new",
        "asking_price": "29.99",
        "compare_at_price": "39.99",
        "cost_price": "18.00",
        "available_quantity": 25,
        "low_stock_threshold": 3,
        "lead_time_days": 2,
        "is_active": True,
    }
    form = VendorProductListingForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_marketplace_listing_form_variant_product_mismatch(tenant_a, ecom_vendor_a, ecom_product_a):
    other_product = _productcatalog_product(tenant_a, name="Different Gadget")
    other_variant = _productcatalog_variant(tenant_a, product=other_product, sku="DIFF-SKU-01")

    form_data = {
        "vendor": ecom_vendor_a.pk,
        "product": ecom_product_a.pk,
        "variant": other_variant.pk,
        "seller_sku": "APX-SKU-MISMATCH",
        "condition": "new",
        "asking_price": "19.99",
        "available_quantity": 10,
        "low_stock_threshold": 2,
        "lead_time_days": 1,
        "is_active": True,
    }
    form = VendorProductListingForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors


def test_marketplace_listing_form_excludes_moderation(tenant_a):
    form = VendorProductListingForm(tenant=tenant_a)
    for field in ["moderation_status", "compliance_status", "moderator_notes", "rejection_reason"]:
        assert field not in form.fields


def test_marketplace_listing_form_reject_foreign_vendor(tenant_a, tenant_b, ecom_product_a):
    vendor_b = _marketplace_vendor(tenant_b, store_name="Globex Vendor B")
    form_data = {
        "vendor": vendor_b.pk,
        "product": ecom_product_a.pk,
        "seller_sku": "CROSS-SKU-01",
        "condition": "new",
        "asking_price": "49.99",
        "available_quantity": 5,
        "low_stock_threshold": 1,
        "lead_time_days": 2,
        "is_active": True,
    }
    form = VendorProductListingForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors


# ==============================================================================
# VendorSubOrderForm Tests
# ==============================================================================

def test_marketplace_suborder_form_valid(tenant_a, ecom_vendor_a):
    order = _ordermanagement_order(tenant_a)
    form_data = {
        "vendor": ecom_vendor_a.pk,
        "order": order.pk,
        "fulfillment_status": "unfulfilled",
        "sla_status": "on_time",
        "subtotal_amount": "150.00",
        "shipping_amount": "12.00",
        "commission_rate": "15.00",
        "carrier_name": "FedEx",
        "tracking_number": "FEDEX-12345",
        "dispute_status": "none",
    }
    form = VendorSubOrderForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_marketplace_suborder_form_excludes_payout(tenant_a):
    form = VendorSubOrderForm(tenant=tenant_a)
    for field in ["payout", "payout_status", "commission_amount", "net_vendor_amount"]:
        assert field not in form.fields


def test_marketplace_suborder_form_reject_foreign_order(tenant_a, tenant_b, ecom_vendor_a):
    order_b = _ordermanagement_order(tenant_b)
    form_data = {
        "vendor": ecom_vendor_a.pk,
        "order": order_b.pk,
        "fulfillment_status": "unfulfilled",
        "sla_status": "on_time",
        "subtotal_amount": "100.00",
        "shipping_amount": "10.00",
        "commission_rate": "15.00",
        "dispute_status": "none",
    }
    form = VendorSubOrderForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors


# ==============================================================================
# VendorPayoutForm Tests
# ==============================================================================

def test_marketplace_payout_form_valid(tenant_a, ecom_vendor_a):
    today = timezone.now().date()
    form_data = {
        "vendor": ecom_vendor_a.pk,
        "period_start": today,
        "period_end": today + timedelta(days=7),
        "gross_sales_amount": "500.00",
        "commission_deducted": "75.00",
        "fees_deducted": "10.00",
        "refunds_deducted": "0.00",
        "tax_withholding_amount": "0.00",
        "payout_method": "bank_transfer",
        "reference_code": "REF-PAY-777",
    }
    form = VendorPayoutForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_marketplace_payout_form_excludes_workflow(tenant_a):
    form = VendorPayoutForm(tenant=tenant_a)
    for field in ["payout_status", "net_payout_amount", "processed_at", "approved_by"]:
        assert field not in form.fields


def test_marketplace_payout_form_reject_foreign_vendor(tenant_a, tenant_b):
    vendor_b = _marketplace_vendor(tenant_b, store_name="Globex Vendor B")
    today = timezone.now().date()
    form_data = {
        "vendor": vendor_b.pk,
        "period_start": today,
        "period_end": today + timedelta(days=7),
        "gross_sales_amount": "200.00",
        "commission_deducted": "30.00",
        "fees_deducted": "0.00",
        "refunds_deducted": "0.00",
        "tax_withholding_amount": "0.00",
        "payout_method": "bank_transfer",
    }
    form = VendorPayoutForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors


# ==============================================================================
# Action Forms Tests
# ==============================================================================

def test_marketplace_action_forms_validation():
    # KYC
    kyc_form = VendorKycVerificationForm(data={"kyc_status": "verified", "kyc_notes": "All documents verified"})
    assert kyc_form.is_valid()

    # Suspension
    susp_form = VendorSuspensionForm(data={"suspension_reason": "High chargeback rate"})
    assert susp_form.is_valid()
    assert not VendorSuspensionForm(data={}).is_valid()

    # Moderation
    mod_form = ListingModerationForm(data={"moderation_status": "approved", "compliance_status": "compliant"})
    assert mod_form.is_valid()

    # Fulfillment
    ful_form = SubOrderFulfillmentForm(data={"fulfillment_status": "shipped", "carrier_name": "UPS", "tracking_number": "1Z9999"})
    assert ful_form.is_valid()

    # Dispute
    disp_form = SubOrderDisputeForm(data={"dispute_status": "disputed", "dispute_reason": "Missing accessories"})
    assert disp_form.is_valid()

    # Approval
    appr_form = PayoutApprovalForm(data={"payout_status": "completed", "reference_code": "WIRE-001"})
    assert appr_form.is_valid()
