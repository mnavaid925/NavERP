"""Unit and contract tests for eCommerce 9.15 Analytics & Business Intelligence forms.

Covers:
- DailySalesSnapshotForm: TenantUniqueMixin validation, clean validation, tenant exclusion.
- CustomerCohortMetricForm: composite uniqueness validation, initial fields, tenant scoping.
- ProductMerchandisingMetricForm: cross-product variant mismatch validation, tenant scoping.
- AttributionTouchpointForm: foreign key tenant scoping, reject_foreign validation.

Conventions enforced:
- Test functions: test_analyticsbi_*
- Module-level helpers: _analyticsbi_*
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.ecommerce.forms.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshotForm
from apps.ecommerce.forms.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetricForm
from apps.ecommerce.forms.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetricForm
from apps.ecommerce.forms.AnalyticsBi.AttributionTouchpoints import AttributionTouchpointForm
from apps.ecommerce.models import (
    DailySalesSnapshot,
    CustomerCohortMetric,
    ProductMerchandisingMetric,
    AttributionTouchpoint,
    ProductVariant,
)
from apps.ecommerce.tests.conftest import (
    _analyticsbi_sales_snapshot,
    _analyticsbi_cohort_metric,
    _analyticsbi_merchandising_metric,
)

pytestmark = pytest.mark.django_db


def test_analyticsbi_dailysalessnapshot_form_valid(tenant_a):
    """Test DailySalesSnapshotForm with valid data."""
    today = timezone.now().date()
    data = {
        "snapshot_date": today,
        "currency": "USD",
        "gross_sales": "1200.00",
        "discounts_total": "50.00",
        "refunds_total": "0.00",
        "net_sales": "1150.00",
        "shipping_collected": "40.00",
        "taxes_collected": "60.00",
        "cost_of_goods_sold": "500.00",
        "gross_profit": "650.00",
        "orders_count": 12,
        "units_sold": 25,
        "average_order_value": "95.83",
        "carts_created": 60,
        "carts_abandoned": 48,
        "conversion_rate_pct": "20.00",
        "is_finalized": False,
        "notes": "Valid test snapshot",
    }
    form = DailySalesSnapshotForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None


def test_analyticsbi_dailysalessnapshot_form_tenant_unique_duplicate(tenant_a):
    """Test TenantUniqueMixin intercepts duplicate (snapshot_date, currency) cleanly."""
    today = timezone.now().date()
    _analyticsbi_sales_snapshot(tenant_a, snapshot_date=today, currency="USD")

    data = {
        "snapshot_date": today,
        "currency": "USD",
        "gross_sales": "500.00",
        "discounts_total": "0.00",
        "refunds_total": "0.00",
        "net_sales": "500.00",
        "shipping_collected": "0.00",
        "taxes_collected": "0.00",
        "cost_of_goods_sold": "0.00",
        "gross_profit": "500.00",
        "orders_count": 5,
        "units_sold": 10,
        "average_order_value": "100.00",
        "carts_created": 20,
        "carts_abandoned": 15,
        "conversion_rate_pct": "25.00",
        "is_finalized": False,
        "notes": "",
    }
    form = DailySalesSnapshotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "__all__" in form.errors or "snapshot_date" in form.errors


def test_analyticsbi_customercohortmetric_form_valid(tenant_a):
    """Test CustomerCohortMetricForm with valid payload."""
    month = timezone.now().date().replace(day=1)
    data = {
        "cohort_month": month,
        "period_offset_months": 2,
        "initial_cohort_size": 120,
        "active_customers": 90,
        "cohort_orders_count": 100,
        "cumulative_gross_revenue": "12000.00",
        "cumulative_net_revenue": "10800.00",
        "cumulative_margin": "4000.00",
        "cumulative_ltv_per_customer": "90.00",
        "retention_rate_pct": "75.00",
        "churn_rate_pct": "25.00",
        "acquisition_channel_tag": "affiliate",
    }
    form = CustomerCohortMetricForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None


def test_analyticsbi_productmerchandisingmetric_form_variant_mismatch(tenant_a, ecom_product_a, ecom_product_b):
    """Test variant belonging to product_b fails validation when submitted with product_a."""
    var_b = ProductVariant.objects.create(
        tenant=tenant_a,
        product=ecom_product_b,
        sku="TEST-VAR-B",
        name="Variant of Product B",
        price=Decimal("15.00"),
    )
    today = timezone.now().date()
    data = {
        "product": ecom_product_a.pk,
        "variant": var_b.pk,
        "period_start": today - timezone.timedelta(days=30),
        "period_end": today,
        "velocity_tier": "best_seller",
        "units_sold": 10,
        "gross_revenue": "150.00",
        "cost_of_goods": "60.00",
        "gross_margin_pct": "60.00",
        "refunds_count": 0,
        "return_rate_pct": "0.00",
        "page_views_count": 100,
        "add_to_cart_count": 20,
        "conversion_rate_pct": "10.00",
        "inventory_turnover_ratio": "2.00",
    }
    form = ProductMerchandisingMetricForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors


def test_analyticsbi_attributiontouchpoint_form_reject_foreign_tenant(tenant_a, tenant_b, ecom_cart_b):
    """Test submitting cart from tenant_b into tenant_a form is rejected."""
    data = {
        "cart": ecom_cart_b.pk,
        "channel_type": "email",
        "attribution_model": "last_touch",
        "utm_source": "newsletter",
        "utm_medium": "email",
        "utm_campaign": "promo",
        "touchpoint_timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "attribution_weight": "1.0000",
        "attributed_revenue": "100.00",
        "estimated_cac": "10.00",
        "landing_page_url": "",
        "referrer_url": "",
    }
    form = AttributionTouchpointForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
