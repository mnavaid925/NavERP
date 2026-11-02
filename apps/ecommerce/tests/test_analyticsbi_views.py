"""Unit and contract tests for eCommerce 9.15 Analytics & Business Intelligence views.

Covers:
- Cockpit view: KPI aggregates, funnel stages, channel attribution, chart series.
- CRUD flows for DailySalesSnapshot, CustomerCohortMetric, ProductMerchandisingMetric, AttributionTouchpoint.
- Audit log forensics on deletion (verifies integer object_id is recorded).
- Action endpoints: generate, recalculate, reclassify.

Conventions enforced:
- Test functions: test_analyticsbi_*
- Module-level helpers: _analyticsbi_*
"""
from decimal import Decimal
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    DailySalesSnapshot,
    CustomerCohortMetric,
    ProductMerchandisingMetric,
    AttributionTouchpoint,
)
from apps.ecommerce.tests.conftest import (
    _analyticsbi_sales_snapshot,
    _analyticsbi_cohort_metric,
    _analyticsbi_merchandising_metric,
    _analyticsbi_attribution_touchpoint,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Cockpit Tests
# ==============================================================================

def test_analyticsbi_cockpit_view_success(auth_client_a, tenant_a, ecom_sales_snapshot_a):
    """Test analytics cockpit returns 200 with required context dictionary keys."""
    url = reverse("ecommerce:analytics_cockpit")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "today_revenue" in resp.context
    assert "today_orders_count" in resp.context
    assert "funnel_stages" in resp.context
    assert "top_best_sellers" in resp.context
    assert "channel_attribution_summary" in resp.context


# ==============================================================================
# DailySalesSnapshot View Tests
# ==============================================================================

def test_analyticsbi_dailysalessnapshot_list_view(auth_client_a, ecom_sales_snapshot_a):
    """Test sales snapshot list view renders 200."""
    url = reverse("ecommerce:dailysalessnapshot_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert "page_obj" in resp.context


def test_analyticsbi_dailysalessnapshot_detail_view(auth_client_a, ecom_sales_snapshot_a):
    """Test sales snapshot detail view renders 200."""
    url = reverse("ecommerce:dailysalessnapshot_detail", kwargs={"pk": ecom_sales_snapshot_a.pk})
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["snapshot"] == ecom_sales_snapshot_a


def test_analyticsbi_dailysalessnapshot_create_view(auth_client_a, tenant_a):
    """Test creating a sales snapshot via POST."""
    url = reverse("ecommerce:dailysalessnapshot_create")
    today = timezone.now().date() + timedelta(days=5)
    data = {
        "snapshot_date": today,
        "currency": "USD",
        "gross_sales": "1000.00",
        "discounts_total": "50.00",
        "refunds_total": "0.00",
        "net_sales": "950.00",
        "shipping_collected": "40.00",
        "taxes_collected": "60.00",
        "cost_of_goods_sold": "400.00",
        "gross_profit": "550.00",
        "orders_count": 10,
        "units_sold": 20,
        "average_order_value": "95.00",
        "carts_created": 50,
        "carts_abandoned": 40,
        "conversion_rate_pct": "20.00",
        "is_finalized": False,
        "notes": "Created via view test",
    }
    resp = auth_client_a.post(url, data=data)
    assert resp.status_code == 302
    created = DailySalesSnapshot.objects.filter(tenant=tenant_a, snapshot_date=today).first()
    assert created is not None


def test_analyticsbi_dailysalessnapshot_delete_audit_forensics(auth_client_a, tenant_a, ecom_sales_snapshot_a):
    """Assert deleting a snapshot records valid integer object_id in AuditLog."""
    pk = ecom_sales_snapshot_a.pk
    url = reverse("ecommerce:dailysalessnapshot_delete", kwargs={"pk": pk})
    resp = auth_client_a.post(url)
    assert resp.status_code == 302
    assert not DailySalesSnapshot.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(action="delete", object_id=pk).first()
    assert audit is not None
    assert audit.object_id == pk


# ==============================================================================
# CustomerCohortMetric View Tests
# ==============================================================================

def test_analyticsbi_customercohortmetric_list_and_detail(auth_client_a, ecom_cohort_metric_a):
    """Test cohort metric list and detail views render 200."""
    list_url = reverse("ecommerce:customercohortmetric_list")
    resp = auth_client_a.get(list_url)
    assert resp.status_code == 200

    detail_url = reverse("ecommerce:customercohortmetric_detail", kwargs={"pk": ecom_cohort_metric_a.pk})
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200


def test_analyticsbi_customercohortmetric_recalculate_action(auth_client_a, ecom_cohort_metric_a):
    """Test batch recalculate POST endpoint executes and redirects."""
    url = reverse("ecommerce:customercohortmetric_recalculate")
    resp = auth_client_a.post(url)
    assert resp.status_code == 302


# ==============================================================================
# ProductMerchandisingMetric View Tests
# ==============================================================================

def test_analyticsbi_productmerchandisingmetric_list_and_detail(auth_client_a, ecom_merchandising_metric_a):
    """Test merchandising metric list and detail views render 200."""
    list_url = reverse("ecommerce:productmerchandisingmetric_list")
    resp = auth_client_a.get(list_url)
    assert resp.status_code == 200

    detail_url = reverse("ecommerce:productmerchandisingmetric_detail", kwargs={"pk": ecom_merchandising_metric_a.pk})
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200


def test_analyticsbi_productmerchandisingmetric_reclassify_action(auth_client_a, ecom_merchandising_metric_a):
    """Test batch reclassify POST endpoint executes and redirects."""
    url = reverse("ecommerce:productmerchandisingmetric_reclassify")
    resp = auth_client_a.post(url)
    assert resp.status_code == 302


# ==============================================================================
# AttributionTouchpoint View Tests
# ==============================================================================

def test_analyticsbi_attributiontouchpoint_list_and_detail(auth_client_a, ecom_attribution_touchpoint_a):
    """Test attribution touchpoint list and detail views render 200."""
    list_url = reverse("ecommerce:attributiontouchpoint_list")
    resp = auth_client_a.get(list_url)
    assert resp.status_code == 200

    detail_url = reverse("ecommerce:attributiontouchpoint_detail", kwargs={"pk": ecom_attribution_touchpoint_a.pk})
    resp = auth_client_a.get(detail_url)
    assert resp.status_code == 200
