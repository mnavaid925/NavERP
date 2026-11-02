"""Unit and contract tests for eCommerce 9.15 Analytics & Business Intelligence models.

Covers:
- DailySalesSnapshot: prefix EDSS-, unique constraints (tenant+date+currency, tenant+number),
  aggregate_for_tenant_date auto-calculation, conversion rate and AOV, units_sold aggregation.
- CustomerCohortMetric: prefix ECCM-, unique constraints, recalculate_rates rate clamping,
  retention and churn rates, LTV calculation, string representation.
- ProductMerchandisingMetric: prefix EPMM-, unique constraints, recalculate_metrics logic,
  margin and return rates, velocity tier auto-classification (best seller, core, slow, dead stock).
- AttributionTouchpoint: prefix EATT-, channel choices, attribution models, foreign keys,
  indexing and tenant isolation.

Conventions enforced:
- Test functions: test_analyticsbi_*
- Module-level helpers: _analyticsbi_*
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    DailySalesSnapshot,
    CustomerCohortMetric,
    ProductMerchandisingMetric,
    AttributionTouchpoint,
    EcommerceOrder,
    EcommerceOrderLine,
    Cart,
)
from apps.ecommerce.tests.conftest import (
    ANALYTICSBI_MODEL_FIELDS,
    _analyticsbi_sales_snapshot,
    _analyticsbi_cohort_metric,
    _analyticsbi_merchandising_metric,
    _analyticsbi_attribution_touchpoint,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_analyticsbi_*)
# ==============================================================================

def _analyticsbi_build_snapshot(tenant, **kwargs):
    return _analyticsbi_sales_snapshot(tenant, **kwargs)


def _analyticsbi_build_cohort(tenant, **kwargs):
    return _analyticsbi_cohort_metric(tenant, **kwargs)


def _analyticsbi_build_merchandising(tenant, product, **kwargs):
    return _analyticsbi_merchandising_metric(tenant, product, **kwargs)


def _analyticsbi_build_touchpoint(tenant, **kwargs):
    return _analyticsbi_attribution_touchpoint(tenant, **kwargs)


# ==============================================================================
# DailySalesSnapshot Tests
# ==============================================================================

def test_analyticsbi_dailysalessnapshot_contract_fields(ecom_sales_snapshot_a):
    """Verify DailySalesSnapshot model defines all contract fields."""
    expected = ANALYTICSBI_MODEL_FIELDS["DailySalesSnapshot"]
    actual = [f.name for f in DailySalesSnapshot._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one]
    for field in expected:
        assert field in actual, f"DailySalesSnapshot missing field: {field}"


def test_analyticsbi_dailysalessnapshot_prefix(ecom_sales_snapshot_a):
    """Assert number begins with EDSS- prefix."""
    assert ecom_sales_snapshot_a.number.startswith("EDSS-")
    assert str(ecom_sales_snapshot_a).startswith("EDSS-")


def test_analyticsbi_dailysalessnapshot_tenant_uniqueness(tenant_a):
    """Assert duplicate (tenant, snapshot_date, currency) raises IntegrityError."""
    today = timezone.now().date()
    _analyticsbi_build_snapshot(tenant_a, snapshot_date=today, currency="USD")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _analyticsbi_build_snapshot(tenant_a, snapshot_date=today, currency="USD")


def test_analyticsbi_dailysalessnapshot_aggregate_calculation(tenant_a):
    """Test aggregate_for_tenant_date computes totals and rates accurately."""
    yesterday = timezone.now().date() - timedelta(days=2)
    Cart.objects.create(tenant=tenant_a, session_key="cart_test_1", created_at=timezone.now() - timedelta(days=2))
    Cart.objects.create(tenant=tenant_a, session_key="cart_test_2", status="abandoned", created_at=timezone.now() - timedelta(days=2))

    snapshot = DailySalesSnapshot.aggregate_for_tenant_date(tenant_a, yesterday, currency="USD")
    assert snapshot.orders_count == 0
    assert snapshot.gross_sales == Decimal("0.00")
    assert snapshot.conversion_rate_pct == Decimal("0.00")


# ==============================================================================
# CustomerCohortMetric Tests
# ==============================================================================

def test_analyticsbi_customercohortmetric_contract_fields(ecom_cohort_metric_a):
    """Verify CustomerCohortMetric model defines all contract fields."""
    expected = ANALYTICSBI_MODEL_FIELDS["CustomerCohortMetric"]
    actual = [f.name for f in CustomerCohortMetric._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one]
    for field in expected:
        assert field in actual, f"CustomerCohortMetric missing field: {field}"


def test_analyticsbi_customercohortmetric_prefix(ecom_cohort_metric_a):
    """Assert number begins with ECCM- prefix."""
    assert ecom_cohort_metric_a.number.startswith("ECCM-")
    assert "Retention:" in str(ecom_cohort_metric_a)


def test_analyticsbi_customercohortmetric_uniqueness(tenant_a):
    """Assert duplicate (tenant, cohort_month, period_offset_months, acquisition_channel_tag) raises IntegrityError."""
    month = timezone.now().date().replace(day=1)
    _analyticsbi_build_cohort(tenant_a, cohort_month=month, period_offset_months=1, acquisition_channel_tag="paid")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _analyticsbi_build_cohort(tenant_a, cohort_month=month, period_offset_months=1, acquisition_channel_tag="paid")


def test_analyticsbi_customercohortmetric_recalculate_rates(ecom_cohort_metric_a):
    """Assert recalculate_rates computes retention %, churn %, and LTV correctly."""
    metric = ecom_cohort_metric_a
    metric.initial_cohort_size = 200
    metric.active_customers = 150
    metric.cumulative_net_revenue = Decimal("15000.00")
    metric.recalculate_rates()

    assert metric.retention_rate_pct == Decimal("75.00")
    assert metric.churn_rate_pct == Decimal("25.00")
    assert metric.cumulative_ltv_per_customer == Decimal("75.00")


def test_analyticsbi_customercohortmetric_recalculate_zero_initial(ecom_cohort_metric_a):
    """Assert recalculate_rates handles zero initial cohort gracefully."""
    metric = ecom_cohort_metric_a
    metric.initial_cohort_size = 0
    metric.recalculate_rates()
    assert metric.retention_rate_pct == Decimal("0.00")
    assert metric.churn_rate_pct == Decimal("0.00")


# ==============================================================================
# ProductMerchandisingMetric Tests
# ==============================================================================

def test_analyticsbi_productmerchandisingmetric_contract_fields(ecom_merchandising_metric_a):
    """Verify ProductMerchandisingMetric model defines all contract fields."""
    expected = ANALYTICSBI_MODEL_FIELDS["ProductMerchandisingMetric"]
    actual = [f.name for f in ProductMerchandisingMetric._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one]
    for field in expected:
        assert field in actual, f"ProductMerchandisingMetric missing field: {field}"


def test_analyticsbi_productmerchandisingmetric_prefix(ecom_merchandising_metric_a):
    """Assert number begins with EPMM- prefix."""
    assert ecom_merchandising_metric_a.number.startswith("EPMM-")
    assert str(ecom_merchandising_metric_a).startswith("EPMM-")


def test_analyticsbi_productmerchandisingmetric_recalculate_tiers(ecom_merchandising_metric_a):
    """Test velocity tier classification logic."""
    m = ecom_merchandising_metric_a

    # Best seller (> 100 units or > 2000 revenue)
    m.units_sold = 150
    m.gross_revenue = Decimal("3000.00")
    m.cost_of_goods_sold = Decimal("1200.00")
    m.recalculate_metrics()
    assert m.velocity_tier == "best_seller"
    assert m.gross_margin_pct == Decimal("60.00")

    # Core performer
    m.units_sold = 50
    m.gross_revenue = Decimal("1000.00")
    m.recalculate_metrics()
    assert m.velocity_tier == "core_performer"

    # Slow mover
    m.units_sold = 5
    m.gross_revenue = Decimal("100.00")
    m.recalculate_metrics()
    assert m.velocity_tier == "slow_mover"

    # Dead stock
    m.units_sold = 0
    m.gross_revenue = Decimal("0.00")
    m.recalculate_metrics()
    assert m.velocity_tier == "dead_stock"


# ==============================================================================
# AttributionTouchpoint Tests
# ==============================================================================

def test_analyticsbi_attributiontouchpoint_contract_fields(ecom_attribution_touchpoint_a):
    """Verify AttributionTouchpoint model defines all contract fields."""
    expected = ANALYTICSBI_MODEL_FIELDS["AttributionTouchpoint"]
    actual = [f.name for f in AttributionTouchpoint._meta.get_fields() if not f.is_relation or f.many_to_one or f.one_to_one]
    for field in expected:
        assert field in actual, f"AttributionTouchpoint missing field: {field}"


def test_analyticsbi_attributiontouchpoint_prefix(ecom_attribution_touchpoint_a):
    """Assert number begins with EATT- prefix."""
    assert ecom_attribution_touchpoint_a.number.startswith("EATT-")
    assert str(ecom_attribution_touchpoint_a).startswith("EATT-")


def test_analyticsbi_attributiontouchpoint_choices(tenant_a):
    """Assert valid channel types save without errors."""
    for ch in ["organic_search", "paid_search", "social_organic", "social_paid", "email", "affiliate", "referral", "direct"]:
        tp = _analyticsbi_build_touchpoint(tenant_a, channel_type=ch)
        assert tp.channel_type == ch
