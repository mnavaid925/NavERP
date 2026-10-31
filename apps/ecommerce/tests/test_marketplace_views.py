"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.11 Marketplace & Multi-Vendor.

Covers:
- Marketplace Console Dashboard
- MarketplaceVendor CRUD + KYC + Suspend views
- VendorProductListing CRUD + Moderate views
- VendorSubOrder CRUD + Fulfill + Dispute views
- VendorPayout CRUD + Execute views

Naming conventions enforced:
- Test functions: test_marketplace_*
- Module-level helpers: _marketplace_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
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
# Marketplace Console Dashboard
# ==============================================================================

def test_marketplace_console_dashboard_view(client_a, tenant_a, ecom_vendor_a, ecom_suborder_a):
    url = reverse("ecommerce:marketplace_console")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "metrics" in resp.context
    assert resp.context["metrics"]["total_vendors"] >= 1
    assert "pending_kyc_vendors" in resp.context
    assert "pending_listings" in resp.context
    assert "sla_risk_suborders" in resp.context
    assert "active_disputes" in resp.context


# ==============================================================================
# MarketplaceVendor Views
# ==============================================================================

def test_marketplace_vendor_list_view(client_a, tenant_a, ecom_vendor_a):
    _marketplace_vendor(tenant_a, store_name="Boutique Crafts", status="draft", kyc_status="pending")
    url = reverse("ecommerce:marketplacevendor_list")

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "vendors" in resp.context
    assert "status_choices" in resp.context
    assert "kyc_status_choices" in resp.context
    assert len(resp.context["vendors"]) >= 2

    # Filter search
    resp_search = client_a.get(url, {"q": "Boutique"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["vendors"]) == 1

    # Filter status
    resp_status = client_a.get(url, {"status": "draft"})
    assert resp_status.status_code == 200
    assert len(resp_status.context["vendors"]) == 1


def test_marketplace_vendor_create_view(client_a, tenant_a):
    party = _marketplace_party(tenant_a, name="New Vendor Corp")
    url = reverse("ecommerce:marketplacevendor_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    # POST
    data = {
        "party": party.pk,
        "store_name": "Sunrise Electronics",
        "slug": "sunrise-electronics",
        "status": "approved",
        "kyc_status": "verified",
        "commission_type": "percentage",
        "commission_rate": "15.00",
        "fixed_fee_per_order": "1.50",
        "payout_method": "bank_transfer",
        "min_payout_amount": "50.00",
        "tax_form_status": "not_required",
        "shipping_lead_time_days": 2,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = MarketplaceVendor.objects.get(tenant=tenant_a, store_name="Sunrise Electronics")
    assert created.number.startswith("EMKV-")


def test_marketplace_vendor_detail_and_edit_view(client_a, tenant_a, ecom_vendor_a):
    detail_url = reverse("ecommerce:marketplacevendor_detail", kwargs={"pk": ecom_vendor_a.pk})
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["vendor"] == ecom_vendor_a
    assert "listings" in resp_detail.context
    assert "sub_orders" in resp_detail.context
    assert "payouts" in resp_detail.context
    assert "disputes" in resp_detail.context

    edit_url = reverse("ecommerce:marketplacevendor_edit", kwargs={"pk": ecom_vendor_a.pk})
    resp_edit = client_a.post(edit_url, {
        "party": ecom_vendor_a.party_id,
        "store_name": "Apex Updated Store",
        "slug": ecom_vendor_a.slug,
        "status": ecom_vendor_a.status,
        "kyc_status": ecom_vendor_a.kyc_status,
        "commission_type": ecom_vendor_a.commission_type,
        "commission_rate": "18.00",
        "fixed_fee_per_order": ecom_vendor_a.fixed_fee_per_order,
        "payout_method": ecom_vendor_a.payout_method,
        "min_payout_amount": ecom_vendor_a.min_payout_amount,
        "tax_form_status": "not_required",
        "shipping_lead_time_days": 3,
    })
    assert resp_edit.status_code == 302
    ecom_vendor_a.refresh_from_db()
    assert ecom_vendor_a.store_name == "Apex Updated Store"
    assert ecom_vendor_a.commission_rate == Decimal("18.00")


def test_marketplace_vendor_verify_kyc_action(client_a, tenant_a):
    vendor = _marketplace_vendor(tenant_a, store_name="KYC Pending Store", kyc_status="pending")
    url = reverse("ecommerce:marketplacevendor_verify_kyc", kwargs={"pk": vendor.pk})

    resp = client_a.post(url, {
        "kyc_status": "verified",
        "kyc_document_type": "Certificate of Incorporation",
        "kyc_notes": "All identity checks passed.",
    })
    assert resp.status_code == 302
    vendor.refresh_from_db()
    assert vendor.kyc_status == "verified"
    assert vendor.status == "approved"
    assert vendor.kyc_verified_at is not None


def test_marketplace_vendor_suspend_action(client_a, tenant_a, ecom_vendor_a):
    url = reverse("ecommerce:marketplacevendor_suspend", kwargs={"pk": ecom_vendor_a.pk})
    resp = client_a.post(url, {
        "suspension_reason": "Excessive late dispatch SLA breaches",
    })
    assert resp.status_code == 302
    ecom_vendor_a.refresh_from_db()
    assert ecom_vendor_a.status == "suspended"
    assert "late dispatch" in ecom_vendor_a.suspension_reason


def test_marketplace_vendor_delete_view(client_a, tenant_a):
    vendor = _marketplace_vendor(tenant_a, store_name="Doomed Vendor")
    url = reverse("ecommerce:marketplacevendor_delete", kwargs={"pk": vendor.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not MarketplaceVendor.objects.filter(pk=vendor.pk).exists()


# ==============================================================================
# VendorProductListing Views
# ==============================================================================

def test_marketplace_listing_list_and_detail(client_a, tenant_a, ecom_listing_a):
    list_url = reverse("ecommerce:vendorproductlisting_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "listings" in resp_list.context
    assert len(resp_list.context["listings"]) >= 1

    detail_url = reverse("ecommerce:vendorproductlisting_detail", kwargs={"pk": ecom_listing_a.pk})
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["listing"] == ecom_listing_a


def test_marketplace_listing_create_and_edit(client_a, tenant_a, ecom_vendor_a, ecom_product_a):
    create_url = reverse("ecommerce:vendorproductlisting_create")
    resp_create = client_a.post(create_url, {
        "vendor": ecom_vendor_a.pk,
        "product": ecom_product_a.pk,
        "seller_sku": "SKU-PRO-CREATE",
        "condition": "new",
        "asking_price": "89.00",
        "compare_at_price": "99.00",
        "cost_price": "50.00",
        "available_quantity": 40,
        "low_stock_threshold": 5,
        "lead_time_days": 2,
        "is_active": True,
    })
    assert resp_create.status_code == 302
    created = VendorProductListing.objects.get(tenant=tenant_a, seller_sku="SKU-PRO-CREATE")
    assert created.number.startswith("EVPL-")

    edit_url = reverse("ecommerce:vendorproductlisting_edit", kwargs={"pk": created.pk})
    resp_edit = client_a.post(edit_url, {
        "vendor": ecom_vendor_a.pk,
        "product": ecom_product_a.pk,
        "seller_sku": "SKU-PRO-CREATE",
        "condition": "new",
        "asking_price": "79.00",
        "compare_at_price": "99.00",
        "cost_price": "50.00",
        "available_quantity": 35,
        "low_stock_threshold": 5,
        "lead_time_days": 2,
        "is_active": True,
    })
    assert resp_edit.status_code == 302
    created.refresh_from_db()
    assert created.asking_price == Decimal("79.00")


def test_marketplace_listing_moderate_action(client_a, tenant_a, ecom_listing_a):
    url = reverse("ecommerce:vendorproductlisting_moderate", kwargs={"pk": ecom_listing_a.pk})
    resp = client_a.post(url, {
        "moderation_status": "rejected",
        "compliance_status": "flagged_prohibited",
        "moderator_notes": "Contains restricted battery formulation.",
        "rejection_reason": "PROHIBITED_BATTERY",
    })
    assert resp.status_code == 302
    ecom_listing_a.refresh_from_db()
    assert ecom_listing_a.moderation_status == "rejected"
    assert ecom_listing_a.compliance_status == "flagged_prohibited"
    assert ecom_listing_a.rejection_reason == "PROHIBITED_BATTERY"
    assert "battery" in ecom_listing_a.moderator_notes


def test_marketplace_listing_delete_view(client_a, tenant_a, ecom_vendor_a, ecom_product_a):
    listing = _marketplace_listing(tenant_a, vendor=ecom_vendor_a, product=ecom_product_a, seller_sku="SKU-DELETE-ME")
    url = reverse("ecommerce:vendorproductlisting_delete", kwargs={"pk": listing.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not VendorProductListing.objects.filter(pk=listing.pk).exists()


# ==============================================================================
# VendorSubOrder Views
# ==============================================================================

def test_marketplace_suborder_list_and_detail(client_a, tenant_a, ecom_suborder_a):
    list_url = reverse("ecommerce:vendorsuborder_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "sub_orders" in resp_list.context
    assert "payout_status_choices" in resp_list.context
    assert len(resp_list.context["sub_orders"]) >= 1

    detail_url = reverse("ecommerce:vendorsuborder_detail", kwargs={"pk": ecom_suborder_a.pk})
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["sub_order"] == ecom_suborder_a
    assert "order_lines" in resp_detail.context


def test_marketplace_suborder_fulfill_action(client_a, tenant_a, ecom_suborder_a):
    url = reverse("ecommerce:vendorsuborder_fulfill", kwargs={"pk": ecom_suborder_a.pk})
    resp = client_a.post(url, {
        "fulfillment_status": "shipped",
        "carrier_name": "FedEx Priority",
        "tracking_number": "123456789012",
        "tracking_url": "https://fedex.com/track/123456789012",
    })
    assert resp.status_code == 302
    ecom_suborder_a.refresh_from_db()
    assert ecom_suborder_a.fulfillment_status == "shipped"
    assert ecom_suborder_a.tracking_number == "123456789012"
    assert ecom_suborder_a.dispatched_at is not None


def test_marketplace_suborder_dispute_action(client_a, tenant_a, ecom_suborder_a):
    url = reverse("ecommerce:vendorsuborder_dispute", kwargs={"pk": ecom_suborder_a.pk})
    resp = client_a.post(url, {
        "dispute_status": "disputed",
        "dispute_reason": "Damaged goods in transit",
        "dispute_notes": "Customer provided photos of dented package.",
    })
    assert resp.status_code == 302
    ecom_suborder_a.refresh_from_db()
    assert ecom_suborder_a.dispute_status == "disputed"
    assert ecom_suborder_a.payout_status == "withheld_dispute"


def test_marketplace_suborder_delete_view(client_a, tenant_a, ecom_vendor_a):
    sub = _marketplace_suborder(tenant_a, vendor=ecom_vendor_a)
    url = reverse("ecommerce:vendorsuborder_delete", kwargs={"pk": sub.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not VendorSubOrder.objects.filter(pk=sub.pk).exists()


# ==============================================================================
# VendorPayout Views
# ==============================================================================

def test_marketplace_payout_list_and_detail(client_a, tenant_a, ecom_payout_a):
    list_url = reverse("ecommerce:vendorpayout_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert "payouts" in resp_list.context
    assert len(resp_list.context["payouts"]) >= 1

    detail_url = reverse("ecommerce:vendorpayout_detail", kwargs={"pk": ecom_payout_a.pk})
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["payout"] == ecom_payout_a
    assert "settled_suborders" in resp_detail.context


def test_marketplace_payout_create_and_execute(client_a, tenant_a, ecom_vendor_a):
    today = timezone.now().date()
    create_url = reverse("ecommerce:vendorpayout_create")
    resp_create = client_a.post(create_url, {
        "vendor": ecom_vendor_a.pk,
        "period_start": today - timedelta(days=14),
        "period_end": today,
        "gross_sales_amount": "800.00",
        "commission_deducted": "120.00",
        "fees_deducted": "10.00",
        "refunds_deducted": "0.00",
        "tax_withholding_amount": "0.00",
        "payout_method": "bank_transfer",
        "reference_code": "DISB-2026-001",
    })
    assert resp_create.status_code == 302
    created = VendorPayout.objects.get(tenant=tenant_a, reference_code="DISB-2026-001")
    assert created.number.startswith("EVPO-")
    assert created.net_payout_amount == Decimal("670.00")

    # Link an accrued suborder to test execution
    sub = _marketplace_suborder(
        tenant_a,
        vendor=ecom_vendor_a,
        payout=created,
        payout_status="in_payout_batch",
    )

    exec_url = reverse("ecommerce:vendorpayout_execute", kwargs={"pk": created.pk})
    resp_exec = client_a.post(exec_url)
    assert resp_exec.status_code == 302
    created.refresh_from_db()
    sub.refresh_from_db()
    assert created.payout_status == "completed"
    assert created.processed_at is not None
    assert sub.payout_status == "paid"


def test_marketplace_payout_delete_view(client_a, tenant_a, ecom_vendor_a):
    payout = _marketplace_payout(tenant_a, vendor=ecom_vendor_a)
    sub = _marketplace_suborder(tenant_a, vendor=ecom_vendor_a, payout=payout, payout_status="in_payout_batch")

    url = reverse("ecommerce:vendorpayout_delete", kwargs={"pk": payout.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not VendorPayout.objects.filter(pk=payout.pk).exists()
    sub.refresh_from_db()
    assert sub.payout is None
    assert sub.payout_status == "accrued"
