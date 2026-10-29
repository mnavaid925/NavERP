"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.6 Customer Profile.

Covers:
- CustomerAccountProfile views (list, detail, create, edit, delete)
- CustomerAddressPreference views (list, detail, create, edit, delete)
- CustomerWishlist views (list, detail, create, edit, delete, item_add, item_delete)
- CustomerPrivacyRequest views (list, detail, create, edit, delete, generate_export, anonymize)

Naming conventions enforced:
- Test functions: test_customerprofile_*
- Module-level helpers: _customerprofile_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Address, Party
from apps.ecommerce.models import (
    CustomerAccountProfile,
    CustomerAddressPreference,
    CustomerWishlist,
    CustomerWishlistItem,
    CustomerPrivacyRequest,
)
from apps.ecommerce.tests.conftest import (
    _customerprofile_account,
    _customerprofile_address,
    _customerprofile_address_preference,
    _customerprofile_wishlist,
    _customerprofile_wishlist_item,
    _customerprofile_privacy_request,
    _productcatalog_product,
    _productcatalog_variant,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customerprofile_*)
# ==============================================================================

def _customerprofile_create_customer(tenant, name="View Customer"):
    return Party.objects.create(tenant=tenant, name=name, kind="person")


# ==============================================================================
# CustomerAccountProfile View Tests
# ==============================================================================

def test_customerprofile_account_list_view(client_a, tenant_a, ecom_profile_a):
    cust2 = _customerprofile_create_customer(tenant_a, name="VIP Shopper")
    _customerprofile_account(tenant_a, cust2, tier="vip", status="active", auth_mode="phone_otp")

    url = reverse("ecommerce:customeraccountprofile_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "profiles" in resp.context
    assert "status_choices" in resp.context
    assert "tier_choices" in resp.context
    assert "auth_mode_choices" in resp.context
    assert len(resp.context["profiles"]) >= 2

    # Filter by tier
    resp_tier = client_a.get(url, {"tier": "vip"})
    assert resp_tier.status_code == 200
    assert len(resp_tier.context["profiles"]) == 1
    assert resp_tier.context["profiles"][0].tier == "vip"

    # Search filter
    resp_search = client_a.get(url, {"q": "VIP Shopper"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["profiles"]) == 1


def test_customerprofile_account_detail_view(client_a, tenant_a, ecom_profile_a):
    url = reverse("ecommerce:customeraccountprofile_detail", args=[ecom_profile_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["profile"] == ecom_profile_a
    assert "address_preferences" in resp.context
    assert "wishlists" in resp.context
    assert "privacy_requests" in resp.context


def test_customerprofile_account_create_view(client_a, tenant_a):
    cust = _customerprofile_create_customer(tenant_a, name="New Created Customer")
    url = reverse("ecommerce:customeraccountprofile_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    # POST
    payload = {
        "customer": cust.pk,
        "tier": "gold",
        "status": "active",
        "auth_mode": "password",
        "phone_number": "+18005550199",
        "phone_verified": False,
        "preferred_language": "en",
        "email_marketing_opt_in": True,
        "notification_frequency": "all",
        "internal_notes": "Created via test view",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CustomerAccountProfile.objects.get(tenant=tenant_a, customer=cust)
    assert created.tier == "gold"
    assert created.marketing_consent_at is not None


def test_customerprofile_account_edit_view(client_a, tenant_a, ecom_profile_a):
    url = reverse("ecommerce:customeraccountprofile_edit", args=[ecom_profile_a.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["profile"] == ecom_profile_a

    # POST
    payload = {
        "customer": ecom_profile_a.customer.pk,
        "tier": "platinum",
        "status": "active",
        "auth_mode": "sso_oauth",
        "phone_number": "+18005559999",
        "phone_verified": True,
        "preferred_language": "fr",
        "notification_frequency": "promotions_only",
        "internal_notes": "Upgraded tier to platinum",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_profile_a.refresh_from_db()
    assert ecom_profile_a.tier == "platinum"
    assert ecom_profile_a.preferred_language == "fr"


def test_customerprofile_account_delete_view(client_a, tenant_a):
    cust = _customerprofile_create_customer(tenant_a, name="To Delete Cust")
    prof = _customerprofile_account(tenant_a, cust)
    url = reverse("ecommerce:customeraccountprofile_delete", args=[prof.pk])

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CustomerAccountProfile.objects.filter(pk=prof.pk).exists()


# ==============================================================================
# CustomerAddressPreference View Tests
# ==============================================================================

def test_customerprofile_address_preference_list_view(client_a, tenant_a, ecom_pref_a):
    url = reverse("ecommerce:customeraddresspreference_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "preferences" in resp.context
    assert "window_choices" in resp.context
    assert len(resp.context["preferences"]) >= 1


def test_customerprofile_address_preference_detail_view(client_a, tenant_a, ecom_pref_a):
    url = reverse("ecommerce:customeraddresspreference_detail", args=[ecom_pref_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["preference"] == ecom_pref_a


def test_customerprofile_address_preference_create_view(client_a, tenant_a, ecom_customer_a):
    addr = _customerprofile_address(tenant_a, ecom_customer_a, line1="88 View St", city="Austin")
    url = reverse("ecommerce:customeraddresspreference_create")

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "customer": ecom_customer_a.pk,
        "address": addr.pk,
        "label": "Secondary Office",
        "is_default_shipping": False,
        "is_default_billing": False,
        "preferred_delivery_window": "morning",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert CustomerAddressPreference.objects.filter(tenant=tenant_a, label="Secondary Office").exists()


def test_customerprofile_address_preference_edit_view(client_a, tenant_a, ecom_pref_a):
    url = reverse("ecommerce:customeraddresspreference_edit", args=[ecom_pref_a.pk])
    payload = {
        "customer": ecom_pref_a.customer.pk,
        "address": ecom_pref_a.address.pk,
        "label": "Updated Home Label",
        "is_default_shipping": True,
        "is_default_billing": True,
        "preferred_delivery_window": "evening",
        "requires_signature": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_pref_a.refresh_from_db()
    assert ecom_pref_a.label == "Updated Home Label"
    assert ecom_pref_a.requires_signature is True


def test_customerprofile_address_preference_delete_view(client_a, tenant_a, ecom_customer_a, ecom_address_a):
    pref = _customerprofile_address_preference(
        tenant_a,
        ecom_customer_a,
        ecom_address_a,
        label="Temp Pref",
        is_default_shipping=False,
        is_default_billing=False,
    )
    url = reverse("ecommerce:customeraddresspreference_delete", args=[pref.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CustomerAddressPreference.objects.filter(pk=pref.pk).exists()


# ==============================================================================
# CustomerWishlist View Tests (including items add/delete)
# ==============================================================================

def test_customerprofile_wishlist_list_view(client_a, tenant_a, ecom_wishlist_a):
    url = reverse("ecommerce:customerwishlist_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "wishlists" in resp.context
    assert "visibility_choices" in resp.context
    assert len(resp.context["wishlists"]) >= 1


def test_customerprofile_wishlist_detail_view(client_a, tenant_a, ecom_wishlist_a, ecom_product_a):
    _customerprofile_wishlist_item(tenant_a, ecom_wishlist_a, ecom_product_a, desired_quantity=2)
    url = reverse("ecommerce:customerwishlist_detail", args=[ecom_wishlist_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["wishlist"] == ecom_wishlist_a
    assert "items" in resp.context
    assert len(resp.context["items"]) == 1


def test_customerprofile_wishlist_create_view(client_a, tenant_a, ecom_customer_a):
    url = reverse("ecommerce:customerwishlist_create")
    payload = {
        "customer": ecom_customer_a.pk,
        "name": "Holiday 2026 Registry",
        "slug": "holiday-2026-registry",
        "visibility": "public",
        "is_default": False,
        "notes": "Public gifts registry",
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert CustomerWishlist.objects.filter(tenant=tenant_a, name="Holiday 2026 Registry").exists()


def test_customerprofile_wishlist_edit_view(client_a, tenant_a, ecom_wishlist_a):
    url = reverse("ecommerce:customerwishlist_edit", args=[ecom_wishlist_a.pk])
    payload = {
        "customer": ecom_wishlist_a.customer.pk,
        "name": "Renamed Wishlist",
        "slug": "renamed-wishlist",
        "visibility": "shared",
        "is_default": True,
        "notes": "Updated notes",
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    ecom_wishlist_a.refresh_from_db()
    assert ecom_wishlist_a.name == "Renamed Wishlist"


def test_customerprofile_wishlist_delete_view(client_a, tenant_a, ecom_customer_a):
    wl = _customerprofile_wishlist(tenant_a, ecom_customer_a, name="Discard Wishlist", is_default=False)
    url = reverse("ecommerce:customerwishlist_delete", args=[wl.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CustomerWishlist.objects.filter(pk=wl.pk).exists()


def test_customerprofile_wishlist_item_add_and_delete_views(client_a, tenant_a, ecom_wishlist_a, ecom_product_a):
    # Add item
    add_url = reverse("ecommerce:customerwishlist_item_add", args=[ecom_wishlist_a.pk])
    payload = {
        "product": ecom_product_a.pk,
        "desired_quantity": "3",
        "priority": "high",
        "comment": "Added via POST",
    }
    resp_add = client_a.post(add_url, payload)
    assert resp_add.status_code == 302

    item = CustomerWishlistItem.objects.get(tenant=tenant_a, wishlist=ecom_wishlist_a, product=ecom_product_a)
    assert item.desired_quantity == 3
    assert item.priority == "high"

    # Delete item
    del_url = reverse("ecommerce:customerwishlist_item_delete", args=[item.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    assert not CustomerWishlistItem.objects.filter(pk=item.pk).exists()


# ==============================================================================
# CustomerPrivacyRequest View Tests (including export & anonymize)
# ==============================================================================

def test_customerprofile_privacy_request_list_view(client_a, tenant_a, ecom_privacy_request_a):
    url = reverse("ecommerce:customerprivacyrequest_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "requests" in resp.context
    assert "type_choices" in resp.context
    assert "status_choices" in resp.context
    assert len(resp.context["requests"]) >= 1


def test_customerprofile_privacy_request_detail_view(client_a, tenant_a, ecom_privacy_request_a):
    url = reverse("ecommerce:customerprivacyrequest_detail", args=[ecom_privacy_request_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["privacy_request"] == ecom_privacy_request_a


def test_customerprofile_privacy_request_create_view(client_a, tenant_a, ecom_customer_a):
    url = reverse("ecommerce:customerprivacyrequest_create")
    deadline = (timezone.now() + timedelta(days=30)).date()
    payload = {
        "customer": ecom_customer_a.pk,
        "request_type": "rectification",
        "requested_by_email": "rectify@example.com",
        "verification_method": "account_login",
        "statutory_deadline": deadline.isoformat(),
        "resolution_notes": "Customer requested address correction",
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    assert CustomerPrivacyRequest.objects.filter(tenant=tenant_a, request_type="rectification").exists()


def test_customerprofile_privacy_request_edit_view(client_a, tenant_a, ecom_privacy_request_a):
    url = reverse("ecommerce:customerprivacyrequest_edit", args=[ecom_privacy_request_a.pk])
    deadline = (timezone.now() + timedelta(days=15)).date()
    payload = {
        "customer": ecom_privacy_request_a.customer.pk,
        "request_type": "access_export",
        "requested_by_email": "updated-privacy@example.com",
        "verification_method": "government_id",
        "statutory_deadline": deadline.isoformat(),
        "resolution_notes": "Identity verified via photo ID",
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 302
    ecom_privacy_request_a.refresh_from_db()
    assert ecom_privacy_request_a.verification_method == "government_id"


def test_customerprofile_privacy_request_delete_view(client_a, tenant_a, ecom_customer_a):
    req = _customerprofile_privacy_request(tenant_a, ecom_customer_a, request_type="opt_out_sale")
    url = reverse("ecommerce:customerprivacyrequest_delete", args=[req.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CustomerPrivacyRequest.objects.filter(pk=req.pk).exists()


def test_customerprofile_privacy_request_generate_export_action(client_a, tenant_a, ecom_privacy_request_a):
    url = reverse("ecommerce:customerprivacyrequest_generate_export", args=[ecom_privacy_request_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    ecom_privacy_request_a.refresh_from_db()
    assert ecom_privacy_request_a.data_export_payload is not None
    assert ecom_privacy_request_a.status == "completed"
    assert ecom_privacy_request_a.completed_at is not None
    assert "customer_name" in ecom_privacy_request_a.data_export_payload
    assert "addresses" in ecom_privacy_request_a.data_export_payload
    assert "wishlists" in ecom_privacy_request_a.data_export_payload


def test_customerprofile_privacy_request_anonymize_action(client_a, tenant_a, ecom_customer_a):
    user = User.objects.create_user(username="gdpr_shopper", email="gdpr@example.com", password="password123")
    profile = _customerprofile_account(tenant_a, ecom_customer_a, user=user)
    wishlist = _customerprofile_wishlist(tenant_a, ecom_customer_a, name="Public Wishlist", visibility="public")

    req = _customerprofile_privacy_request(tenant_a, ecom_customer_a, request_type="erasure_anonymize")
    url = reverse("ecommerce:customerprivacyrequest_anonymize", args=[req.pk])

    resp = client_a.post(url)
    assert resp.status_code == 302

    req.refresh_from_db()
    assert req.status == "completed"

    profile.refresh_from_db()
    assert profile.status == "anonymized"
    assert profile.email_marketing_opt_in is False
    assert profile.sms_marketing_opt_in is False

    user.refresh_from_db()
    assert user.is_active is False

    wishlist.refresh_from_db()
    assert wishlist.visibility == "private"
