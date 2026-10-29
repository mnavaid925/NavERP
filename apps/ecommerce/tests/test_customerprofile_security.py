"""Multi-tenancy, authentication, and cross-tenant IDOR isolation tests for eCommerce 9.6.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Cross-tenant IDOR defense (404 on all foreign tenant records)
- Queryset isolation across tenant boundaries on list views
- Mutation action cross-tenant tampering guards

Naming conventions enforced:
- Test functions: test_customerprofile_*
- Module-level helpers: _customerprofile_*
"""
import pytest
from django.urls import reverse

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
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("customeraccountprofile_list", []),
        ("customeraccountprofile_create", []),
        ("customeraddresspreference_list", []),
        ("customeraddresspreference_create", []),
        ("customerwishlist_list", []),
        ("customerwishlist_create", []),
        ("customerprivacyrequest_list", []),
        ("customerprivacyrequest_create", []),
    ],
)
def test_customerprofile_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp.url or "login" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Defense Tests (404 on Foreign Tenant Records)
# ==============================================================================

def test_customerprofile_account_idor_defense(client_a, ecom_profile_b):
    # Detail
    url_det = reverse("ecommerce:customeraccountprofile_detail", args=[ecom_profile_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:customeraccountprofile_edit", args=[ecom_profile_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"tier": "platinum"}).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:customeraccountprofile_delete", args=[ecom_profile_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert CustomerAccountProfile.objects.filter(pk=ecom_profile_b.pk).exists()


def test_customerprofile_address_preference_idor_defense(client_a, ecom_pref_b):
    # Detail
    url_det = reverse("ecommerce:customeraddresspreference_detail", args=[ecom_pref_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:customeraddresspreference_edit", args=[ecom_pref_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"label": "Hacked"}).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:customeraddresspreference_delete", args=[ecom_pref_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert CustomerAddressPreference.objects.filter(pk=ecom_pref_b.pk).exists()


def test_customerprofile_wishlist_idor_defense(client_a, ecom_wishlist_b, ecom_wishlist_item_b):
    # Detail
    url_det = reverse("ecommerce:customerwishlist_detail", args=[ecom_wishlist_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:customerwishlist_edit", args=[ecom_wishlist_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Wishlist"}).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:customerwishlist_delete", args=[ecom_wishlist_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert CustomerWishlist.objects.filter(pk=ecom_wishlist_b.pk).exists()

    # Item Add POST to foreign wishlist
    url_item_add = reverse("ecommerce:customerwishlist_item_add", args=[ecom_wishlist_b.pk])
    assert client_a.post(url_item_add, {"desired_quantity": 1}).status_code == 404

    # Item Delete POST to foreign wishlist item
    url_item_del = reverse("ecommerce:customerwishlist_item_delete", args=[ecom_wishlist_item_b.pk])
    assert client_a.post(url_item_del).status_code == 404
    assert CustomerWishlistItem.objects.filter(pk=ecom_wishlist_item_b.pk).exists()


def test_customerprofile_privacy_request_idor_defense(client_a, ecom_privacy_request_b):
    # Detail
    url_det = reverse("ecommerce:customerprivacyrequest_detail", args=[ecom_privacy_request_b.pk])
    assert client_a.get(url_det).status_code == 404

    # Edit GET & POST
    url_edit = reverse("ecommerce:customerprivacyrequest_edit", args=[ecom_privacy_request_b.pk])
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"request_type": "rectification"}).status_code == 404

    # Delete POST
    url_del = reverse("ecommerce:customerprivacyrequest_delete", args=[ecom_privacy_request_b.pk])
    assert client_a.post(url_del).status_code == 404
    assert CustomerPrivacyRequest.objects.filter(pk=ecom_privacy_request_b.pk).exists()

    # Generate Export POST
    url_exp = reverse("ecommerce:customerprivacyrequest_generate_export", args=[ecom_privacy_request_b.pk])
    assert client_a.post(url_exp).status_code == 404

    # Anonymize POST
    url_anon = reverse("ecommerce:customerprivacyrequest_anonymize", args=[ecom_privacy_request_b.pk])
    assert client_a.post(url_anon).status_code == 404


# ==============================================================================
# Cross-Tenant List View Queryset Isolation Tests
# ==============================================================================

def test_customerprofile_list_views_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_profile_a,
    ecom_profile_b,
    ecom_pref_a,
    ecom_pref_b,
    ecom_wishlist_a,
    ecom_wishlist_b,
    ecom_privacy_request_a,
    ecom_privacy_request_b,
):
    # 1. Profile list
    resp_prof = client_a.get(reverse("ecommerce:customeraccountprofile_list"))
    assert resp_prof.status_code == 200
    prof_ids = [p.pk for p in resp_prof.context["profiles"]]
    assert ecom_profile_a.pk in prof_ids
    assert ecom_profile_b.pk not in prof_ids

    # 2. Address Preference list
    resp_pref = client_a.get(reverse("ecommerce:customeraddresspreference_list"))
    assert resp_pref.status_code == 200
    pref_ids = [p.pk for p in resp_pref.context["preferences"]]
    assert ecom_pref_a.pk in pref_ids
    assert ecom_pref_b.pk not in pref_ids

    # 3. Wishlist list
    resp_wl = client_a.get(reverse("ecommerce:customerwishlist_list"))
    assert resp_wl.status_code == 200
    wl_ids = [w.pk for w in resp_wl.context["wishlists"]]
    assert ecom_wishlist_a.pk in wl_ids
    assert ecom_wishlist_b.pk not in wl_ids

    # 4. Privacy Request list
    resp_req = client_a.get(reverse("ecommerce:customerprivacyrequest_list"))
    assert resp_req.status_code == 200
    req_ids = [r.pk for r in resp_req.context["requests"]]
    assert ecom_privacy_request_a.pk in req_ids
    assert ecom_privacy_request_b.pk not in req_ids
