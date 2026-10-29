"""Unit and invariant tests for eCommerce 9.8 Personalization & Recommendation Engine models.

Covers:
- AudienceSegment (ESEG)
- RecommendationStrategy (EREC)
- PersonalizedExperience (EPEX)
- ShopperBehaviorEvent (ESBE)

Naming conventions enforced:
- Test functions: test_personalization_*
- Module-level helpers: _personalization_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    AudienceSegment,
    RecommendationStrategy,
    PersonalizedExperience,
    ShopperBehaviorEvent,
    CatalogProduct,
    StoreCategory,
)
from apps.ecommerce.tests.conftest import (
    PERSONALIZATION_MODEL_FIELDS,
    PERSONALIZATION_CHOICES,
    _personalization_segment,
    _personalization_strategy,
    _personalization_experience,
    _personalization_event,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_personalization_*)
# ==============================================================================

def _personalization_make_product(tenant, name="Personalized Item"):
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
        status="published",
    )


def _personalization_make_category(tenant, name="Personalized Category"):
    return StoreCategory.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{tenant.slug}",
    )


# ==============================================================================
# Contract Verification Tests
# ==============================================================================

def test_personalization_model_fields_contract():
    model_classes = {
        "AudienceSegment": AudienceSegment,
        "RecommendationStrategy": RecommendationStrategy,
        "PersonalizedExperience": PersonalizedExperience,
        "ShopperBehaviorEvent": ShopperBehaviorEvent,
    }
    for model_name, expected_fields in PERSONALIZATION_MODEL_FIELDS.items():
        cls = model_classes[model_name]
        actual_fields = {f.name for f in cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing on {model_name}"


def test_personalization_choices_contract():
    assert tuple(AudienceSegment.LIFECYCLE_STAGE_CHOICES) == PERSONALIZATION_CHOICES["AudienceSegment"]["lifecycle_stage"]
    assert tuple(RecommendationStrategy.ALGORITHM_CHOICES) == PERSONALIZATION_CHOICES["RecommendationStrategy"]["algorithm"]
    assert tuple(RecommendationStrategy.PLACEMENT_CHOICES) == PERSONALIZATION_CHOICES["RecommendationStrategy"]["placement"]
    assert tuple(PersonalizedExperience.EXPERIENCE_TYPE_CHOICES) == PERSONALIZATION_CHOICES["PersonalizedExperience"]["experience_type"]
    assert tuple(ShopperBehaviorEvent.EVENT_TYPE_CHOICES) == PERSONALIZATION_CHOICES["ShopperBehaviorEvent"]["event_type"]


# ==============================================================================
# AudienceSegment Model Tests
# ==============================================================================

def test_personalization_segment_creation_and_autonumber(tenant_a):
    seg = _personalization_segment(tenant_a, name="Loyal Shoppers", code="loyal-shoppers")
    assert seg.pk is not None
    assert seg.number.startswith("ESEG-")
    assert seg.name == "Loyal Shoppers"
    assert seg.code == "loyal-shoppers"
    assert seg.is_active is True
    assert "Loyal Shoppers" in str(seg)


def test_personalization_segment_slugifies_code(tenant_a):
    seg = AudienceSegment(
        tenant=tenant_a,
        name="Cart Abandoners Q4",
        code="",
        min_lifetime_spend=Decimal("0.00"),
    )
    seg.clean()
    assert seg.code == "cart-abandoners-q4"


def test_personalization_segment_negative_spend_rejected(tenant_a):
    seg = AudienceSegment(
        tenant=tenant_a,
        name="Invalid Spend Segment",
        code="invalid-spend",
        min_lifetime_spend=Decimal("-10.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        seg.clean()
    assert "min_lifetime_spend" in exc_info.value.error_dict


def test_personalization_segment_cross_tenant_category_rejected(tenant_a, tenant_b):
    cat_b = _personalization_make_category(tenant_b, name="Workspace B Category")
    seg_a = AudienceSegment(
        tenant=tenant_a,
        name="Segment A with Cat B",
        code="seg-a-cat-b",
        target_category=cat_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        seg_a.clean()
    assert "target_category" in exc_info.value.error_dict


def test_personalization_segment_unique_code_per_tenant(tenant_a):
    _personalization_segment(tenant_a, name="Seg 1", code="uniq-code")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _personalization_segment(tenant_a, name="Seg 2", code="uniq-code")


# ==============================================================================
# RecommendationStrategy Model Tests
# ==============================================================================

def test_personalization_strategy_creation_and_autonumber(tenant_a):
    strat = _personalization_strategy(tenant_a, name="Trending Items", code="trending-items")
    assert strat.pk is not None
    assert strat.number.startswith("EREC-")
    assert strat.name == "Trending Items"
    assert strat.max_items == 6
    assert strat.min_rating == Decimal("3.50")
    assert strat.is_active is True
    assert strat.get_algorithm_display() in str(strat)


def test_personalization_strategy_validation_bounds(tenant_a):
    # max_items out of bounds
    strat_bad_items = RecommendationStrategy(
        tenant=tenant_a,
        name="Bad Items",
        code="bad-items",
        max_items=0,
    )
    with pytest.raises(ValidationError) as exc_info:
        strat_bad_items.clean()
    assert "max_items" in exc_info.value.error_dict

    # min_rating out of bounds
    strat_bad_rating = RecommendationStrategy(
        tenant=tenant_a,
        name="Bad Rating",
        code="bad-rating",
        min_rating=Decimal("6.00"),
    )
    with pytest.raises(ValidationError) as exc_info:
        strat_bad_rating.clean()
    assert "min_rating" in exc_info.value.error_dict


def test_personalization_strategy_cross_tenant_fk_rejected(tenant_a, tenant_b):
    seg_b = _personalization_segment(tenant_b, name="Segment B", code="seg-b-strat")
    cat_b = _personalization_make_category(tenant_b, name="Category B")

    strat = RecommendationStrategy(
        tenant=tenant_a,
        name="Cross Tenant Strategy",
        code="cross-tenant-strat",
        target_segment=seg_b,
        target_category=cat_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        strat.clean()
    assert "target_segment" in exc_info.value.error_dict
    assert "target_category" in exc_info.value.error_dict


# ==============================================================================
# PersonalizedExperience Model Tests
# ==============================================================================

def test_personalization_experience_creation_and_autonumber(tenant_a):
    exp = _personalization_experience(tenant_a, name="Flash Promo", code="flash-promo")
    assert exp.pk is not None
    assert exp.number.startswith("EPEX-")
    assert exp.experience_type == "vip_welcome"
    assert exp.priority == 10
    assert exp.is_active is True
    assert "Flash Promo" in str(exp)


def test_personalization_experience_date_validation(tenant_a):
    now = timezone.now()
    exp = PersonalizedExperience(
        tenant=tenant_a,
        name="Date Invariant",
        code="date-invariant",
        start_date=now + timezone.timedelta(days=5),
        end_date=now + timezone.timedelta(days=1),
    )
    with pytest.raises(ValidationError) as exc_info:
        exp.clean()
    assert "end_date" in exc_info.value.error_dict


def test_personalization_experience_url_scheme_security(tenant_a):
    # C2 dangerous schemes
    for dangerous in ["javascript:alert(1)", "DATA:text/html,bad", "vbscript:msgbox"]:
        exp = PersonalizedExperience(
            tenant=tenant_a,
            name="XSS Attempt",
            code=f"xss-{dangerous[:4]}",
            cta_url=dangerous,
        )
        with pytest.raises(ValidationError) as exc_info:
            exp.clean()
        assert "cta_url" in exc_info.value.error_dict

    # Valid scheme
    exp_valid = PersonalizedExperience(
        tenant=tenant_a,
        name="Safe Experience",
        code="safe-exp",
        cta_url="https://example.com/promo",
        hero_image_url="/static/images/banner.png",
    )
    exp_valid.clean()  # Should not raise


def test_personalization_experience_cross_tenant_fk_rejected(tenant_a, tenant_b):
    seg_b = _personalization_segment(tenant_b, name="Segment B", code="seg-b-exp")
    cat_b = _personalization_make_category(tenant_b, name="Category B")
    prod_b = _personalization_make_product(tenant_b, name="Product B")

    exp = PersonalizedExperience(
        tenant=tenant_a,
        name="Cross Tenant Experience",
        code="cross-exp",
        target_segment=seg_b,
        target_category=cat_b,
        target_product=prod_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        exp.clean()
    assert "target_segment" in exc_info.value.error_dict
    assert "target_category" in exc_info.value.error_dict
    assert "target_product" in exc_info.value.error_dict


# ==============================================================================
# ShopperBehaviorEvent Model Tests
# ==============================================================================

def test_personalization_event_creation_and_autonumber(tenant_a):
    event = _personalization_event(
        tenant_a,
        event_type="cart_add",
        session_key="sess-cart-01",
        payload={"cart_value": 89.99},
    )
    assert event.pk is not None
    assert event.number.startswith("ESBE-")
    assert event.event_type == "cart_add"
    assert event.session_key == "sess-cart-01"
    assert event.payload["cart_value"] == 89.99
    assert event.get_event_type_display() in str(event)
