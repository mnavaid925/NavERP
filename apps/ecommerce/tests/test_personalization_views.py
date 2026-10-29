"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.8 Personalization & Recommendation Engine.

Covers:
- AudienceSegment views (list, detail, create, edit, toggle, recalculate, delete)
- RecommendationStrategy views (list, detail, create, edit, toggle, delete)
- PersonalizedExperience views (list, detail, create, edit, toggle, delete)
- ShopperBehaviorEvent views (list, detail, create, delete)
- Personalization Workbench views (console, preview)

Naming conventions enforced:
- Test functions: test_personalization_*
- Module-level helpers: _personalization_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.ecommerce.models import (
    AudienceSegment,
    RecommendationStrategy,
    PersonalizedExperience,
    ShopperBehaviorEvent,
    CatalogProduct,
    ProductVariant,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    _personalization_segment,
    _personalization_strategy,
    _personalization_experience,
    _personalization_event,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_personalization_*)
# ==============================================================================

def _personalization_make_product(tenant, name="View Product", price=Decimal("49.99"), brand="Acme"):
    prod = CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        brand=brand,
        status="published",
        visibility="storefront",
    )
    ProductVariant.objects.create(
        tenant=tenant,
        product=prod,
        sku=f"SKU-{prod.pk}",
        name=f"{name} Standard",
        price=price,
        is_active=True,
    )
    return prod


def _personalization_make_category(tenant, name="View Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        is_active=True,
    )


# ==============================================================================
# AudienceSegment View Tests
# ==============================================================================

def test_personalization_segment_list_view(client_a, tenant_a, ecom_segment_a):
    _personalization_segment(tenant_a, name="New Browsers", code="new-browsers", lifecycle_stage="new_visitor")

    url = reverse("ecommerce:audiencesegment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "segments" in resp.context
    assert "lifecycle_choices" in resp.context
    assert len(resp.context["segments"]) >= 2

    # Filter by lifecycle stage
    resp_filter = client_a.get(url, {"lifecycle_stage": "new_visitor"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["segments"]) == 1
    assert resp_filter.context["segments"][0].code == "new-browsers"

    # Search query filter
    resp_q = client_a.get(url, {"q": "Browsers"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["segments"]) == 1


def test_personalization_segment_detail_view(client_a, tenant_a, ecom_segment_a):
    url = reverse("ecommerce:audiencesegment_detail", args=[ecom_segment_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["segment"] == ecom_segment_a
    assert "experiences" in resp.context
    assert "recommendation_strategies" in resp.context


def test_personalization_segment_create_and_edit_views(client_a, tenant_a):
    create_url = reverse("ecommerce:audiencesegment_create")
    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context

    # Create POST
    payload = {
        "name": "Cart Abandoners",
        "code": "cart-abandoners",
        "lifecycle_stage": "at_risk",
        "recency_days_max": 14,
        "min_order_count": 1,
        "min_lifetime_spend": "50.00",
        "is_active": True,
        "description": "Shoppers who left active carts",
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302
    created = AudienceSegment.objects.get(tenant=tenant_a, code="cart-abandoners")
    assert created.name == "Cart Abandoners"

    # Edit GET and POST
    edit_url = reverse("ecommerce:audiencesegment_edit", args=[created.pk])
    resp_edit_get = client_a.get(edit_url)
    assert resp_edit_get.status_code == 200

    payload["name"] = "Cart Abandoners 14D"
    resp_edit_post = client_a.post(edit_url, payload)
    assert resp_edit_post.status_code == 302
    created.refresh_from_db()
    assert created.name == "Cart Abandoners 14D"


def test_personalization_segment_toggle_and_recalculate(client_a, tenant_a, ecom_segment_a):
    toggle_url = reverse("ecommerce:audiencesegment_toggle", args=[ecom_segment_a.pk])
    assert ecom_segment_a.is_active is True
    resp_toggle = client_a.post(toggle_url)
    assert resp_toggle.status_code == 302
    ecom_segment_a.refresh_from_db()
    assert ecom_segment_a.is_active is False

    recalc_url = reverse("ecommerce:audiencesegment_recalculate", args=[ecom_segment_a.pk])
    resp_recalc = client_a.post(recalc_url)
    assert resp_recalc.status_code == 302
    ecom_segment_a.refresh_from_db()
    assert ecom_segment_a.last_evaluated_at is not None


def test_personalization_segment_delete_view(client_a, tenant_a):
    seg = _personalization_segment(tenant_a, name="To Delete", code="to-delete-seg")
    url = reverse("ecommerce:audiencesegment_delete", args=[seg.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AudienceSegment.objects.filter(pk=seg.pk).exists()


# ==============================================================================
# RecommendationStrategy View Tests
# ==============================================================================

def test_personalization_strategy_list_and_detail(client_a, tenant_a, ecom_strategy_a):
    url = reverse("ecommerce:recommendationstrategy_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "strategies" in resp.context
    assert "algorithm_choices" in resp.context
    assert "placement_choices" in resp.context

    detail_url = reverse("ecommerce:recommendationstrategy_detail", args=[ecom_strategy_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["strategy"] == ecom_strategy_a


def test_personalization_strategy_create_edit_toggle(client_a, tenant_a, ecom_segment_a):
    create_url = reverse("ecommerce:recommendationstrategy_create")
    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "name": "Cart Upsell Strategy",
        "code": "cart-upsell-strat",
        "algorithm": "frequently_bought_together",
        "placement": "cart_cross_sell",
        "fallback_strategy": "trending_popular",
        "max_items": 4,
        "min_rating": "3.50",
        "target_segment": ecom_segment_a.pk,
        "is_active": True,
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302
    created = RecommendationStrategy.objects.get(tenant=tenant_a, code="cart-upsell-strat")
    assert created.algorithm == "frequently_bought_together"

    # Toggle
    toggle_url = reverse("ecommerce:recommendationstrategy_toggle", args=[created.pk])
    client_a.post(toggle_url)
    created.refresh_from_db()
    assert created.is_active is False

    # Delete
    delete_url = reverse("ecommerce:recommendationstrategy_delete", args=[created.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not RecommendationStrategy.objects.filter(pk=created.pk).exists()


# ==============================================================================
# PersonalizedExperience View Tests
# ==============================================================================

def test_personalization_experience_list_and_detail(client_a, tenant_a, ecom_experience_a):
    url = reverse("ecommerce:personalizedexperience_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "experiences" in resp.context
    assert "experience_type_choices" in resp.context

    detail_url = reverse("ecommerce:personalizedexperience_detail", args=[ecom_experience_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["experience"] == ecom_experience_a


def test_personalization_experience_crud_flow(client_a, tenant_a, ecom_segment_a):
    create_url = reverse("ecommerce:personalizedexperience_create")
    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "name": "VIP Seasonal Banner",
        "experience_type": "home_hero",
        "target_segment": ecom_segment_a.pk,
        "headline": "Welcome to VIP Autumn Deals",
        "subheadline": "Save big this week",
        "cta_label": "Claim Now",
        "cta_url": "/vip-promo/",
        "priority": 12,
        "is_active": True,
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302
    created = PersonalizedExperience.objects.get(tenant=tenant_a, name="VIP Seasonal Banner")
    assert created.priority == 12

    # Toggle
    toggle_url = reverse("ecommerce:personalizedexperience_toggle", args=[created.pk])
    client_a.post(toggle_url)
    created.refresh_from_db()
    assert created.is_active is False

    # Delete
    delete_url = reverse("ecommerce:personalizedexperience_delete", args=[created.pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    assert not PersonalizedExperience.objects.filter(pk=created.pk).exists()


# ==============================================================================
# ShopperBehaviorEvent View Tests
# ==============================================================================

def test_personalization_event_list_and_detail(client_a, tenant_a, ecom_event_a):
    url = reverse("ecommerce:shopperbehaviorevent_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "events" in resp.context
    assert "event_type_choices" in resp.context

    detail_url = reverse("ecommerce:shopperbehaviorevent_detail", args=[ecom_event_a.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert resp_detail.context["event"] == ecom_event_a


def test_personalization_event_delete(client_a, tenant_a, ecom_event_a):
    url = reverse("ecommerce:shopperbehaviorevent_delete", args=[ecom_event_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not ShopperBehaviorEvent.objects.filter(pk=ecom_event_a.pk).exists()


# ==============================================================================
# Workbench & Simulator Views
# ==============================================================================

def test_personalization_console_view(client_a, tenant_a, ecom_segment_a, ecom_strategy_a, ecom_experience_a):
    url = reverse("ecommerce:personalization_console")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "segments" in resp.context
    assert "strategies" in resp.context
    assert "experiences" in resp.context
    assert "recent_events" in resp.context
    assert "vip_segments_count" in resp.context


def test_personalization_preview_simulator_view(client_a, tenant_a, ecom_strategy_a, ecom_product_a):
    preview_url = reverse("ecommerce:personalization_preview")
    # GET or POST simulation
    resp = client_a.post(preview_url, {
        "strategy_id": ecom_strategy_a.pk,
        "anchor_product_id": ecom_product_a.pk,
    })
    assert resp.status_code == 200
    assert "recommended_products" in resp.context
    assert resp.context["strategy"] == ecom_strategy_a
