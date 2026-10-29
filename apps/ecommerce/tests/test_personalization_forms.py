"""Form validation, exclusion, and tenant isolation tests for eCommerce 9.8 Personalization & Recommendation Engine.

Covers:
- AudienceSegmentForm
- RecommendationStrategyForm
- PersonalizedExperienceForm
- ShopperBehaviorEventFilterForm

Naming conventions enforced:
- Test functions: test_personalization_*
- Module-level helpers: _personalization_*
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.ecommerce.forms.Personalization.AudienceSegments import AudienceSegmentForm
from apps.ecommerce.forms.Personalization.RecommendationStrategies import RecommendationStrategyForm
from apps.ecommerce.forms.Personalization.PersonalizedExperiences import PersonalizedExperienceForm
from apps.ecommerce.forms.Personalization.ShopperBehaviorEvents import ShopperBehaviorEventFilterForm
from apps.ecommerce.models import (
    AudienceSegment,
    RecommendationStrategy,
    PersonalizedExperience,
    CatalogProduct,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    PERSONALIZATION_FORM_FIELDS,
    _personalization_segment,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_personalization_*)
# ==============================================================================

def _personalization_make_product(tenant, name="Form Item"):
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        status="published",
    )


def _personalization_make_category(tenant, name="Form Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
    )


# ==============================================================================
# Form Contract Tests
# ==============================================================================

def test_personalization_form_fields_contract():
    form_classes = {
        "AudienceSegmentForm": AudienceSegmentForm,
        "RecommendationStrategyForm": RecommendationStrategyForm,
        "PersonalizedExperienceForm": PersonalizedExperienceForm,
        "ShopperBehaviorEventFilterForm": ShopperBehaviorEventFilterForm,
    }
    for form_name, expected_fields in PERSONALIZATION_FORM_FIELDS.items():
        cls = form_classes[form_name]
        if hasattr(cls, "Meta") and hasattr(cls.Meta, "fields"):
            actual_fields = tuple(cls.Meta.fields)
        else:
            actual_fields = tuple(cls.base_fields.keys())
        assert actual_fields == expected_fields, f"Field mismatch on {form_name}"


# ==============================================================================
# AudienceSegmentForm Tests
# ==============================================================================

def test_personalization_segment_form_valid(tenant_a):
    cat_a = _personalization_make_category(tenant_a, name="Segment Category")
    form_data = {
        "name": "High Value VIPs",
        "code": "high-value-vips",
        "lifecycle_stage": "high_value_vip",
        "recency_days_max": 45,
        "min_order_count": 5,
        "min_lifetime_spend": "1000.00",
        "target_category": cat_a.pk,
        "is_active": True,
        "description": "High value shoppers form test",
    }
    form = AudienceSegmentForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    segment = form.save(commit=False)
    segment.tenant = tenant_a
    segment.save()
    assert segment.pk is not None
    assert segment.code == "high-value-vips"


def test_personalization_segment_form_rejects_cross_tenant_category(tenant_a, tenant_b):
    cat_b = _personalization_make_category(tenant_b, name="Workspace B Category")
    form_data = {
        "name": "Cross Tenant Segment",
        "code": "cross-tenant-seg",
        "lifecycle_stage": "all",
        "min_lifetime_spend": "0.00",
        "target_category": cat_b.pk,
        "is_active": True,
    }
    form = AudienceSegmentForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_category" in form.errors


# ==============================================================================
# RecommendationStrategyForm Tests
# ==============================================================================

def test_personalization_strategy_form_valid(tenant_a):
    seg_a = _personalization_segment(tenant_a, name="Segment A", code="seg-form-a")
    cat_a = _personalization_make_category(tenant_a, name="Strategy Category")
    form_data = {
        "name": "PDP Related Items",
        "code": "pdp-related-items",
        "algorithm": "related_products",
        "placement": "pdp_related",
        "fallback_strategy": "trending_popular",
        "max_items": 8,
        "min_rating": "4.00",
        "same_brand_only": True,
        "only_in_stock": True,
        "target_category": cat_a.pk,
        "target_segment": seg_a.pk,
        "is_active": True,
        "description": "PDP strategy test",
    }
    form = RecommendationStrategyForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    strategy = form.save(commit=False)
    strategy.tenant = tenant_a
    strategy.save()
    assert strategy.pk is not None
    assert strategy.max_items == 8


def test_personalization_strategy_form_rejects_cross_tenant_relations(tenant_a, tenant_b):
    seg_b = _personalization_segment(tenant_b, name="Segment B", code="seg-form-b")
    cat_b = _personalization_make_category(tenant_b, name="Category B")
    form_data = {
        "name": "Cross Strategy",
        "code": "cross-strat",
        "algorithm": "related_products",
        "placement": "pdp_related",
        "max_items": 5,
        "min_rating": "3.00",
        "target_segment": seg_b.pk,
        "target_category": cat_b.pk,
        "is_active": True,
    }
    form = RecommendationStrategyForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_segment" in form.errors or "target_category" in form.errors


# ==============================================================================
# PersonalizedExperienceForm Tests
# ==============================================================================

def test_personalization_experience_form_valid(tenant_a):
    seg_a = _personalization_segment(tenant_a, name="Target Segment", code="target-seg")
    prod_a = _personalization_make_product(tenant_a, name="Featured Product")
    now = timezone.now()
    form_data = {
        "name": "Homepage Hero Campaign",
        "experience_type": "home_hero",
        "target_segment": seg_a.pk,
        "target_product": prod_a.pk,
        "headline": "Special Welcome Offer",
        "subheadline": "Up to 20% off selected products",
        "cta_label": "Explore Collection",
        "cta_url": "/collections/special/",
        "hero_image_url": "https://example.com/banner.jpg",
        "trigger_delay_hours": 0,
        "priority": 15,
        "start_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": (now + timezone.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
        "is_active": True,
    }
    form = PersonalizedExperienceForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    experience = form.save(commit=False)
    experience.tenant = tenant_a
    experience.save()
    assert experience.pk is not None
    assert experience.priority == 15


def test_personalization_experience_form_rejects_dangerous_urls(tenant_a):
    seg_a = _personalization_segment(tenant_a, name="Target Segment", code="target-seg-xss")
    form_data = {
        "name": "XSS Form Experience",
        "experience_type": "home_hero",
        "target_segment": seg_a.pk,
        "headline": "Malicious Headline",
        "cta_label": "Click Here",
        "cta_url": "javascript:alert(document.cookie)",
        "priority": 1,
        "is_active": True,
    }
    form = PersonalizedExperienceForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cta_url" in form.errors


def test_personalization_experience_form_rejects_cross_tenant_entities(tenant_a, tenant_b):
    seg_b = _personalization_segment(tenant_b, name="Segment B", code="seg-exp-b")
    prod_b = _personalization_make_product(tenant_b, name="Product B")
    form_data = {
        "name": "Cross Tenant Form Exp",
        "experience_type": "home_hero",
        "target_segment": seg_b.pk,
        "target_product": prod_b.pk,
        "headline": "Cross Tenant Offer",
        "cta_label": "View",
        "cta_url": "/shop/",
        "priority": 10,
        "is_active": True,
    }
    form = PersonalizedExperienceForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_segment" in form.errors or "target_product" in form.errors


# ==============================================================================
# ShopperBehaviorEventFilterForm Tests
# ==============================================================================

def test_personalization_event_filter_form_valid():
    form_data = {
        "q": "sess-xyz",
        "event_type": "cart_add",
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
    }
    form = ShopperBehaviorEventFilterForm(data=form_data)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["event_type"] == "cart_add"
    assert form.cleaned_data["q"] == "sess-xyz"
