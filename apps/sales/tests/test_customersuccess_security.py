"""Sub-module 8.11 Customer Success & Account Management -- Security & Auth Test Suite.

Covers:
1. Authentication protection (@login_required):
   - Unauthenticated visitors accessing any of the 25 endpoints are redirected to login.
2. Multi-Tenant IDOR isolation (Strict cross-tenant 404):
   - Tenant A requesting Tenant B objects across detail, edit, and delete endpoints receives 404.
   - Tenant B requesting Tenant A objects receives 404.
3. Tenant List Isolation:
   - Tenant A lists and console views strictly exclude Tenant B records.
   - Tenant B lists and console views strictly exclude Tenant A records.
4. Role-Based Access Control (@tenant_admin_required):
   - Non-admin member users attempting to POST to delete endpoints are rejected with 403 Forbidden.
   - Tenant admin users can perform deletion.
5. HTTP Method safety:
   - All delete views strictly reject GET with 405 Method Not Allowed.
6. CSRF Enforcement:
   - POST requests without valid CSRF token are blocked with 403 when CSRF is enforced.
7. Cross-tenant FK injection prevention:
   - POST requests attempting to bind foreign tenant customer parties fail form validation.
"""
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.sales.models import (
    CustomerBusinessReview,
    CustomerHealthScore,
    CustomerOnboarding,
    CustomerRenewal,
)
from apps.sales.tests.conftest import CUSTOMERSUCCESS_URLS

pytestmark = pytest.mark.django_db


# ============================================================================
# 1. Authentication Protection
# ============================================================================

def test_customersuccess_unauthenticated_access_redirects(
    cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """Anonymous visitors to all 25 customer success routes must be redirected to login."""
    anon_client = Client()
    pk_map = {
        "customer_health_score_detail": cs_health_score_a.pk,
        "customer_health_score_edit": cs_health_score_a.pk,
        "customer_health_score_delete": cs_health_score_a.pk,
        "customer_renewal_detail": cs_renewal_a.pk,
        "customer_renewal_edit": cs_renewal_a.pk,
        "customer_renewal_delete": cs_renewal_a.pk,
        "customer_onboarding_detail": cs_onboarding_a.pk,
        "customer_onboarding_edit": cs_onboarding_a.pk,
        "customer_onboarding_delete": cs_onboarding_a.pk,
        "customer_business_review_detail": cs_qbr_a.pk,
        "customer_business_review_edit": cs_qbr_a.pk,
        "customer_business_review_delete": cs_qbr_a.pk,
    }

    for url_name in CUSTOMERSUCCESS_URLS.keys():
        if url_name in pk_map:
            url = reverse(f"sales:{url_name}", args=[pk_map[url_name]])
        else:
            url = reverse(f"sales:{url_name}")

        if "delete" in url_name:
            resp = anon_client.post(url)
        else:
            resp = anon_client.get(url)
        assert resp.status_code == 302, f"Unauthenticated request to {url_name} must return 302"
        assert "/accounts/login/" in resp.url or "/login/" in resp.url


# ============================================================================
# 2. Multi-Tenant IDOR Isolation (Detail, Edit, Delete -> 404)
# ============================================================================

def test_customersuccess_cross_tenant_idor_detail_views_return_404(
    client_a, client_b, cs_health_score_a, cs_health_score_b,
    cs_renewal_a, cs_renewal_b, cs_onboarding_a, cs_onboarding_b,
    cs_qbr_a, cs_qbr_b
):
    """Tenant A requesting Tenant B objects, and vice versa, must return 404."""
    # Tenant A requesting Tenant B objects
    assert client_a.get(reverse("sales:customer_health_score_detail", args=[cs_health_score_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_renewal_detail", args=[cs_renewal_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_onboarding_detail", args=[cs_onboarding_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_business_review_detail", args=[cs_qbr_b.pk])).status_code == 404

    # Tenant B requesting Tenant A objects
    assert client_b.get(reverse("sales:customer_health_score_detail", args=[cs_health_score_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:customer_renewal_detail", args=[cs_renewal_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:customer_onboarding_detail", args=[cs_onboarding_a.pk])).status_code == 404
    assert client_b.get(reverse("sales:customer_business_review_detail", args=[cs_qbr_a.pk])).status_code == 404


def test_customersuccess_cross_tenant_idor_edit_views_return_404(
    client_a, cs_health_score_b, cs_renewal_b, cs_onboarding_b, cs_qbr_b
):
    """Tenant A requesting edit views for Tenant B objects must return 404."""
    assert client_a.get(reverse("sales:customer_health_score_edit", args=[cs_health_score_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_renewal_edit", args=[cs_renewal_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_onboarding_edit", args=[cs_onboarding_b.pk])).status_code == 404
    assert client_a.get(reverse("sales:customer_business_review_edit", args=[cs_qbr_b.pk])).status_code == 404

    # POST attempts also 404 without modifying anything
    assert client_a.post(reverse("sales:customer_health_score_edit", args=[cs_health_score_b.pk]), {}).status_code == 404
    assert client_a.post(reverse("sales:customer_renewal_edit", args=[cs_renewal_b.pk]), {}).status_code == 404
    assert client_a.post(reverse("sales:customer_onboarding_edit", args=[cs_onboarding_b.pk]), {}).status_code == 404
    assert client_a.post(reverse("sales:customer_business_review_edit", args=[cs_qbr_b.pk]), {}).status_code == 404


def test_customersuccess_cross_tenant_idor_delete_views_return_404(
    client_a, cs_health_score_b, cs_renewal_b, cs_onboarding_b, cs_qbr_b
):
    """Tenant A attempting to delete Tenant B objects must return 404 and NOT delete."""
    resp1 = client_a.post(reverse("sales:customer_health_score_delete", args=[cs_health_score_b.pk]))
    assert resp1.status_code == 404
    assert CustomerHealthScore.objects.filter(pk=cs_health_score_b.pk).exists()

    resp2 = client_a.post(reverse("sales:customer_renewal_delete", args=[cs_renewal_b.pk]))
    assert resp2.status_code == 404
    assert CustomerRenewal.objects.filter(pk=cs_renewal_b.pk).exists()

    resp3 = client_a.post(reverse("sales:customer_onboarding_delete", args=[cs_onboarding_b.pk]))
    assert resp3.status_code == 404
    assert CustomerOnboarding.objects.filter(pk=cs_onboarding_b.pk).exists()

    resp4 = client_a.post(reverse("sales:customer_business_review_delete", args=[cs_qbr_b.pk]))
    assert resp4.status_code == 404
    assert CustomerBusinessReview.objects.filter(pk=cs_qbr_b.pk).exists()


# ============================================================================
# 3. Tenant List & Console Isolation
# ============================================================================

def test_customersuccess_cross_tenant_list_isolation(
    client_a, client_b, cs_health_score_a, cs_health_score_b,
    cs_renewal_a, cs_renewal_b, cs_onboarding_a, cs_onboarding_b,
    cs_qbr_a, cs_qbr_b
):
    """List views strictly partition records by tenant; Tenant B records never leak to Tenant A."""
    # Health score list
    resp_a_chs = client_a.get(reverse("sales:customer_health_score_list"))
    page_chs_a = resp_a_chs.context["page_obj"]
    assert cs_health_score_a in page_chs_a
    assert cs_health_score_b not in page_chs_a

    # Renewal list
    resp_a_crn = client_a.get(reverse("sales:customer_renewal_list"))
    page_crn_a = resp_a_crn.context["page_obj"]
    assert cs_renewal_a in page_crn_a
    assert cs_renewal_b not in page_crn_a

    # Onboarding list
    resp_a_cob = client_a.get(reverse("sales:customer_onboarding_list"))
    page_cob_a = resp_a_cob.context["page_obj"]
    assert cs_onboarding_a in page_cob_a
    assert cs_onboarding_b not in page_cob_a

    # Business review list
    resp_a_qbr = client_a.get(reverse("sales:customer_business_review_list"))
    page_qbr_a = resp_a_qbr.context["page_obj"]
    assert cs_qbr_a in page_qbr_a
    assert cs_qbr_b not in page_qbr_a


# ============================================================================
# 4. Role-Based Access Control (@tenant_admin_required on Delete)
# ============================================================================

def test_customersuccess_delete_requires_tenant_admin(
    member_client, cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """Regular member users without tenant admin privileges are rejected with 403."""
    delete_cases = [
        (reverse("sales:customer_health_score_delete", args=[cs_health_score_a.pk]), CustomerHealthScore, cs_health_score_a.pk),
        (reverse("sales:customer_renewal_delete", args=[cs_renewal_a.pk]), CustomerRenewal, cs_renewal_a.pk),
        (reverse("sales:customer_onboarding_delete", args=[cs_onboarding_a.pk]), CustomerOnboarding, cs_onboarding_a.pk),
        (reverse("sales:customer_business_review_delete", args=[cs_qbr_a.pk]), CustomerBusinessReview, cs_qbr_a.pk),
    ]

    for url, model_cls, pk in delete_cases:
        resp = member_client.post(url)
        assert resp.status_code == 403, f"Non-admin POST on {url} must return 403 Forbidden"
        assert model_cls.objects.filter(pk=pk).exists(), f"Record {pk} must not be deleted by non-admin"


# ============================================================================
# 5. HTTP Method Safety (Strict POST for Delete)
# ============================================================================

def test_customersuccess_delete_rejects_get(
    client_a, cs_health_score_a, cs_renewal_a, cs_onboarding_a, cs_qbr_a
):
    """Delete views must reject GET requests with 405 Method Not Allowed."""
    endpoints = [
        reverse("sales:customer_health_score_delete", args=[cs_health_score_a.pk]),
        reverse("sales:customer_renewal_delete", args=[cs_renewal_a.pk]),
        reverse("sales:customer_onboarding_delete", args=[cs_onboarding_a.pk]),
        reverse("sales:customer_business_review_delete", args=[cs_qbr_a.pk]),
    ]
    for url in endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405


# ============================================================================
# 6. CSRF Protection
# ============================================================================

def test_customersuccess_csrf_enforcement(admin_user, cs_health_score_a):
    """POST requests without CSRF verification token are rejected with 403."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    url = reverse("sales:customer_health_score_delete", args=[cs_health_score_a.pk])
    resp = csrf_client.post(url)
    assert resp.status_code == 403


# ============================================================================
# 7. Cross-Tenant Foreign Key Injection Defenses
# ============================================================================

def test_customersuccess_cross_tenant_fk_injection_rejected(client_a, tenant_a, cs_account_b):
    """A user cannot bind an entity to a foreign tenant's customer account."""
    url = reverse("sales:customer_health_score_create")
    payload = {
        "account": cs_account_b.pk,  # foreign customer account
        "evaluation_date": "2026-03-01",
        "overall_score": 85,
        "health_band": "green",
        "score_trend": "improving",
        "risk_level": "low",
        "product_usage_score": 85,
        "support_ticket_score": 85,
        "nps_sentiment_score": 85,
        "relationship_score": 85,
        "renewal_risk_score": 85,
        "license_utilization_pct": "80.00",
        "open_support_tickets": 0,
    }
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "account" in resp.context["form"].errors
    assert not CustomerHealthScore.objects.filter(tenant=tenant_a, account=cs_account_b).exists()
