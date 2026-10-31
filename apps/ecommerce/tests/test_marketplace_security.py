"""Multi-tenancy, authentication, and cross-tenant IDOR isolation tests for eCommerce 9.11 Marketplace.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Cross-tenant IDOR defense (404 on all foreign tenant records for detail, edit, delete, action endpoints)
- Queryset isolation across tenant boundaries on list views

Naming conventions enforced:
- Test functions: test_marketplace_*
- Module-level helpers: _marketplace_*
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name",
    [
        "marketplace_console",
        "marketplacevendor_list",
        "marketplacevendor_create",
        "vendorproductlisting_list",
        "vendorproductlisting_create",
        "vendorsuborder_list",
        "vendorsuborder_create",
        "vendorpayout_list",
        "vendorpayout_create",
    ],
)
def test_marketplace_anonymous_redirects_to_login(client, url_name):
    url = reverse(f"ecommerce:{url_name}")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Defense Tests
# ==============================================================================

def test_marketplace_vendor_cross_tenant_idor(client_b, ecom_vendor_a):
    detail_url = reverse("ecommerce:marketplacevendor_detail", kwargs={"pk": ecom_vendor_a.pk})
    edit_url = reverse("ecommerce:marketplacevendor_edit", kwargs={"pk": ecom_vendor_a.pk})
    delete_url = reverse("ecommerce:marketplacevendor_delete", kwargs={"pk": ecom_vendor_a.pk})
    kyc_url = reverse("ecommerce:marketplacevendor_verify_kyc", kwargs={"pk": ecom_vendor_a.pk})
    suspend_url = reverse("ecommerce:marketplacevendor_suspend", kwargs={"pk": ecom_vendor_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"store_name": "Hacked"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(kyc_url, {"kyc_status": "verified"}).status_code == 404
    assert client_b.post(suspend_url, {"suspension_reason": "Malicious"}).status_code == 404


def test_marketplace_listing_cross_tenant_idor(client_b, ecom_listing_a):
    detail_url = reverse("ecommerce:vendorproductlisting_detail", kwargs={"pk": ecom_listing_a.pk})
    edit_url = reverse("ecommerce:vendorproductlisting_edit", kwargs={"pk": ecom_listing_a.pk})
    delete_url = reverse("ecommerce:vendorproductlisting_delete", kwargs={"pk": ecom_listing_a.pk})
    mod_url = reverse("ecommerce:vendorproductlisting_moderate", kwargs={"pk": ecom_listing_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"asking_price": "1.00"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(mod_url, {"moderation_status": "rejected"}).status_code == 404


def test_marketplace_suborder_cross_tenant_idor(client_b, ecom_suborder_a):
    detail_url = reverse("ecommerce:vendorsuborder_detail", kwargs={"pk": ecom_suborder_a.pk})
    edit_url = reverse("ecommerce:vendorsuborder_edit", kwargs={"pk": ecom_suborder_a.pk})
    delete_url = reverse("ecommerce:vendorsuborder_delete", kwargs={"pk": ecom_suborder_a.pk})
    fulfill_url = reverse("ecommerce:vendorsuborder_fulfill", kwargs={"pk": ecom_suborder_a.pk})
    dispute_url = reverse("ecommerce:vendorsuborder_dispute", kwargs={"pk": ecom_suborder_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"carrier_name": "Fake"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(fulfill_url, {"fulfillment_status": "shipped"}).status_code == 404
    assert client_b.post(dispute_url, {"dispute_status": "disputed"}).status_code == 404


def test_marketplace_payout_cross_tenant_idor(client_b, ecom_payout_a):
    detail_url = reverse("ecommerce:vendorpayout_detail", kwargs={"pk": ecom_payout_a.pk})
    edit_url = reverse("ecommerce:vendorpayout_edit", kwargs={"pk": ecom_payout_a.pk})
    delete_url = reverse("ecommerce:vendorpayout_delete", kwargs={"pk": ecom_payout_a.pk})
    exec_url = reverse("ecommerce:vendorpayout_execute", kwargs={"pk": ecom_payout_a.pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"reference_code": "STOLEN"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404
    assert client_b.post(exec_url).status_code == 404


# ==============================================================================
# Queryset Isolation Tests
# ==============================================================================

def test_marketplace_queryset_isolation_in_lists(
    client_a, client_b,
    ecom_vendor_a, ecom_vendor_b,
    ecom_listing_a, ecom_listing_b,
    ecom_suborder_a, ecom_suborder_b,
    ecom_payout_a, ecom_payout_b,
):
    # Vendors list
    resp_va = client_a.get(reverse("ecommerce:marketplacevendor_list"))
    resp_vb = client_b.get(reverse("ecommerce:marketplacevendor_list"))
    assert ecom_vendor_a in resp_va.context["vendors"]
    assert ecom_vendor_b not in resp_va.context["vendors"]
    assert ecom_vendor_b in resp_vb.context["vendors"]
    assert ecom_vendor_a not in resp_vb.context["vendors"]

    # Listings list
    resp_la = client_a.get(reverse("ecommerce:vendorproductlisting_list"))
    resp_lb = client_b.get(reverse("ecommerce:vendorproductlisting_list"))
    assert ecom_listing_a in resp_la.context["listings"]
    assert ecom_listing_b not in resp_la.context["listings"]
    assert ecom_listing_b in resp_lb.context["listings"]
    assert ecom_listing_a not in resp_lb.context["listings"]

    # Sub-Orders list
    resp_soa = client_a.get(reverse("ecommerce:vendorsuborder_list"))
    resp_sob = client_b.get(reverse("ecommerce:vendorsuborder_list"))
    assert ecom_suborder_a in resp_soa.context["sub_orders"]
    assert ecom_suborder_b not in resp_soa.context["sub_orders"]
    assert ecom_suborder_b in resp_sob.context["sub_orders"]
    assert ecom_suborder_a not in resp_sob.context["sub_orders"]

    # Payouts list
    resp_pa = client_a.get(reverse("ecommerce:vendorpayout_list"))
    resp_pb = client_b.get(reverse("ecommerce:vendorpayout_list"))
    assert ecom_payout_a in resp_pa.context["payouts"]
    assert ecom_payout_b not in resp_pa.context["payouts"]
    assert ecom_payout_b in resp_pb.context["payouts"]
    assert ecom_payout_a not in resp_pb.context["payouts"]
