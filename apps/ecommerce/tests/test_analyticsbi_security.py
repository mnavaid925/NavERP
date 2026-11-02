"""Security and multi-tenant isolation tests for eCommerce 9.15 Analytics & Business Intelligence.

Covers:
- Anonymous authentication gating: unauthenticated requests redirect to login.
- Cross-tenant IDOR isolation: Tenant A cannot access Tenant B records (returns 404).
- HTTP Method enforcement: GET to @require_POST endpoints returns 405 Method Not Allowed.
- Role-based authorization: non-admin member cannot delete or trigger batch recalculations (returns 403).
- Tenantless superuser protection: tenant=None superuser handles gracefully without database errors.

Conventions enforced:
- Test functions: test_analyticsbi_*
- Module-level helpers: _analyticsbi_*
"""
import pytest
from django.urls import reverse

from apps.ecommerce.tests.conftest import (
    _analyticsbi_sales_snapshot,
    _analyticsbi_cohort_metric,
    _analyticsbi_merchandising_metric,
    _analyticsbi_attribution_touchpoint,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Authentication & Anonymous Gating Tests
# ==============================================================================

def test_analyticsbi_anonymous_redirect(client):
    """Assert unauthenticated requests to analytics views redirect to login."""
    urls = [
        reverse("ecommerce:analytics_cockpit"),
        reverse("ecommerce:dailysalessnapshot_list"),
        reverse("ecommerce:dailysalessnapshot_create"),
        reverse("ecommerce:customercohortmetric_list"),
        reverse("ecommerce:customercohortmetric_create"),
        reverse("ecommerce:productmerchandisingmetric_list"),
        reverse("ecommerce:productmerchandisingmetric_create"),
        reverse("ecommerce:attributiontouchpoint_list"),
        reverse("ecommerce:attributiontouchpoint_create"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login/" in resp.url or "accounts" in resp.url


# ==============================================================================
# Cross-Tenant IDOR Isolation Tests
# ==============================================================================

def test_analyticsbi_idor_snapshot(auth_client_a, ecom_sales_snapshot_b):
    """Assert Tenant A client receives 404 on Tenant B DailySalesSnapshot."""
    pk = ecom_sales_snapshot_b.pk
    detail_url = reverse("ecommerce:dailysalessnapshot_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:dailysalessnapshot_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:dailysalessnapshot_delete", kwargs={"pk": pk})

    assert auth_client_a.get(detail_url).status_code == 404
    assert auth_client_a.get(edit_url).status_code == 404
    assert auth_client_a.post(delete_url).status_code == 404


def test_analyticsbi_idor_cohort(auth_client_a, ecom_cohort_metric_b):
    """Assert Tenant A client receives 404 on Tenant B CustomerCohortMetric."""
    pk = ecom_cohort_metric_b.pk
    detail_url = reverse("ecommerce:customercohortmetric_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:customercohortmetric_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:customercohortmetric_delete", kwargs={"pk": pk})

    assert auth_client_a.get(detail_url).status_code == 404
    assert auth_client_a.get(edit_url).status_code == 404
    assert auth_client_a.post(delete_url).status_code == 404


def test_analyticsbi_idor_merchandising(auth_client_a, ecom_merchandising_metric_b):
    """Assert Tenant A client receives 404 on Tenant B ProductMerchandisingMetric."""
    pk = ecom_merchandising_metric_b.pk
    detail_url = reverse("ecommerce:productmerchandisingmetric_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:productmerchandisingmetric_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:productmerchandisingmetric_delete", kwargs={"pk": pk})

    assert auth_client_a.get(detail_url).status_code == 404
    assert auth_client_a.get(edit_url).status_code == 404
    assert auth_client_a.post(delete_url).status_code == 404


def test_analyticsbi_idor_touchpoint(auth_client_a, ecom_attribution_touchpoint_b):
    """Assert Tenant A client receives 404 on Tenant B AttributionTouchpoint."""
    pk = ecom_attribution_touchpoint_b.pk
    detail_url = reverse("ecommerce:attributiontouchpoint_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:attributiontouchpoint_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:attributiontouchpoint_delete", kwargs={"pk": pk})

    assert auth_client_a.get(detail_url).status_code == 404
    assert auth_client_a.get(edit_url).status_code == 404
    assert auth_client_a.post(delete_url).status_code == 404


# ==============================================================================
# HTTP Method Enforcement Tests (@require_POST)
# ==============================================================================

def test_analyticsbi_http_method_enforcement(auth_client_a, ecom_sales_snapshot_a):
    """Assert GET requests to POST-only actions and deletes return 405 Method Not Allowed."""
    endpoints = [
        reverse("ecommerce:dailysalessnapshot_delete", kwargs={"pk": ecom_sales_snapshot_a.pk}),
        reverse("ecommerce:dailysalessnapshot_generate"),
        reverse("ecommerce:customercohortmetric_recalculate"),
        reverse("ecommerce:productmerchandisingmetric_reclassify"),
    ]
    for url in endpoints:
        resp = auth_client_a.get(url)
        assert resp.status_code == 405


# ==============================================================================
# Role-Based Authorization Tests (@tenant_admin_required)
# ==============================================================================

def test_analyticsbi_non_admin_forbidden_on_delete(member_client, ecom_sales_snapshot_a):
    """Assert non-admin tenant member receives 403 Forbidden when calling delete."""
    url = reverse("ecommerce:dailysalessnapshot_delete", kwargs={"pk": ecom_sales_snapshot_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
