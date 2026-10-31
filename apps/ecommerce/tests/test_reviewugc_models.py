"""Unit and contract tests for eCommerce 9.13 Reviews & User-Generated Content models.

Covers:
- ProductReview: number prefix EPRV-, choices, star_range / empty_star_range, constraints
- ProductQuestionAnswer: number prefix EPQA-, choices, is_staff_answer, pinned status, constraints
- VisualUgcMedia: number prefix EUGC-, media types, rights status, shoppable/published flags, ordering
- ReviewSentimentSummary: number prefix ERVM-, OneToOne with CatalogProduct, rating_X_pct properties,
  recalculate() aggregate logic, mixed sentiment handling, tenant isolation

Naming conventions enforced:
- Test functions: test_reviewugc_*
- Module-level helpers: _reviewugc_*
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    CatalogProduct,
    ProductReview,
    ProductQuestionAnswer,
    VisualUgcMedia,
    ReviewSentimentSummary,
)
from apps.ecommerce.tests.conftest import (
    REVIEWUGC_MODEL_FIELDS,
    REVIEWUGC_CHOICES,
    _reviewugc_product_review,
    _reviewugc_question_answer,
    _reviewugc_visual_ugc,
    _reviewugc_sentiment_summary,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_reviewugc_*)
# ==============================================================================

def _reviewugc_create_product(tenant, name="Test Product", slug_suffix="1"):
    """Helper to generate an extra catalog product without fixture collision."""
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{slug_suffix}-{tenant.slug}",
        status="active",
    )


# ==============================================================================
# 1. Contract Verification Tests
# ==============================================================================

def test_reviewugc_model_fields_contract():
    """Verify all 4 ReviewUgc models contain the expected contract fields."""
    model_classes = {
        "ProductReview": ProductReview,
        "ProductQuestionAnswer": ProductQuestionAnswer,
        "VisualUgcMedia": VisualUgcMedia,
        "ReviewSentimentSummary": ReviewSentimentSummary,
    }
    for model_name, expected_fields in REVIEWUGC_MODEL_FIELDS.items():
        cls = model_classes[model_name]
        actual_fields = {f.name for f in cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing on {model_name}"


def test_reviewugc_choices_contract():
    """Verify choices on ProductReview, ProductQuestionAnswer, and VisualUgcMedia match contract."""
    assert tuple(ProductReview.RATING_CHOICES) == REVIEWUGC_CHOICES["ProductReview"]["rating"]
    assert tuple(ProductReview.STATUS_CHOICES) == REVIEWUGC_CHOICES["ProductReview"]["status"]
    assert tuple(ProductReview.SENTIMENT_CHOICES) == REVIEWUGC_CHOICES["ProductReview"]["sentiment"]
    assert tuple(ProductQuestionAnswer.STATUS_CHOICES) == REVIEWUGC_CHOICES["ProductQuestionAnswer"]["status"]
    assert tuple(VisualUgcMedia.MEDIA_TYPE_CHOICES) == REVIEWUGC_CHOICES["VisualUgcMedia"]["media_type"]
    assert tuple(VisualUgcMedia.RIGHTS_STATUS_CHOICES) == REVIEWUGC_CHOICES["VisualUgcMedia"]["rights_status"]


# ==============================================================================
# 2. ProductReview Model Tests
# ==============================================================================

def test_reviewugc_review_creation_and_autonumber(tenant_a, ecom_product_a):
    """ProductReview auto-generates EPRV- prefix, sets defaults, and implements __str__."""
    review = _reviewugc_product_review(tenant_a, ecom_product_a)
    assert review.pk is not None
    assert review.number.startswith("EPRV-")
    assert review.rating == 5
    assert review.status == "approved"
    assert review.sentiment == "positive"
    assert review.sentiment_score == Decimal("0.85")
    assert review.is_verified_purchase is True
    assert review.is_featured is False
    assert review.helpful_votes == 3
    assert review.unhelpful_votes == 0
    assert str(review) == f"{review.number} - {ecom_product_a.name} (5★)"


def test_reviewugc_review_star_range_properties(tenant_a, ecom_product_a):
    """star_range and empty_star_range return correct ranges for stars display."""
    review_5 = _reviewugc_product_review(tenant_a, ecom_product_a, rating=5)
    assert list(review_5.star_range) == [0, 1, 2, 3, 4]
    assert list(review_5.empty_star_range) == []

    review_3 = _reviewugc_product_review(tenant_a, ecom_product_a, rating=3)
    assert list(review_3.star_range) == [0, 1, 2]
    assert list(review_3.empty_star_range) == [0, 1]

    review_1 = _reviewugc_product_review(tenant_a, ecom_product_a, rating=1)
    assert list(review_1.star_range) == [0]
    assert list(review_1.empty_star_range) == [0, 1, 2, 3]


def test_reviewugc_review_with_optional_relations(
    tenant_a, ecom_product_a, ecom_variant_a, ecom_profile_a, ecom_order_a, admin_user
):
    """ProductReview supports optional variant, customer, order, and moderator relations."""
    now = timezone.now()
    review = ProductReview.objects.create(
        tenant=tenant_a,
        product=ecom_product_a,
        variant=ecom_variant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        reviewer_name="Verified VIP",
        reviewer_email="vip@example.com",
        rating=4,
        title="Great Shoes!",
        body="Comfortable and stylish.",
        status="approved",
        sentiment="positive",
        sentiment_score=Decimal("0.75"),
        is_verified_purchase=True,
        media_urls=["https://example.com/photo1.jpg"],
        merchant_response="Thank you for being a loyal customer!",
        merchant_response_at=now,
        moderated_by=admin_user,
        moderation_note="Verified authentic customer purchase.",
    )
    assert review.pk is not None
    assert review.variant == ecom_variant_a
    assert review.customer == ecom_profile_a
    assert review.order == ecom_order_a
    assert review.moderated_by == admin_user
    assert review.media_urls == ["https://example.com/photo1.jpg"]
    assert review.merchant_response_at == now


def test_reviewugc_review_unique_constraint(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """ProductReview enforces unique constraint on (tenant, number)."""
    r1 = _reviewugc_product_review(tenant_a, ecom_product_a, number="EPRV-TEST-999")
    assert r1.number == "EPRV-TEST-999"

    # Same number on same tenant must fail
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ProductReview.objects.create(
                tenant=tenant_a,
                product=ecom_product_a,
                reviewer_name="Duplicate Tester",
                reviewer_email="dup@example.com",
                number="EPRV-TEST-999",
                rating=5,
                title="Duplicate",
                body="Duplicate text",
            )

    # Same number on different tenant must succeed
    r2 = _reviewugc_product_review(tenant_b, ecom_product_b, number="EPRV-TEST-999")
    assert r2.number == "EPRV-TEST-999"
    assert r2.tenant == tenant_b


def test_reviewugc_review_ordering_and_featured(tenant_a, ecom_product_a):
    """ProductReview orders featured reviews first, followed by newest created_at."""
    r_normal = _reviewugc_product_review(
        tenant_a, ecom_product_a, is_featured=False, title="Normal Review"
    )
    r_featured = _reviewugc_product_review(
        tenant_a, ecom_product_a, is_featured=True, title="Featured Review"
    )

    reviews = list(ProductReview.objects.filter(tenant=tenant_a, product=ecom_product_a))
    assert reviews[0] == r_featured
    assert reviews[1] == r_normal


# ==============================================================================
# 3. ProductQuestionAnswer Model Tests
# ==============================================================================

def test_reviewugc_question_creation_and_autonumber(tenant_a, ecom_product_a):
    """ProductQuestionAnswer auto-generates EPQA- prefix, sets defaults, and implements __str__."""
    qa = _reviewugc_question_answer(tenant_a, ecom_product_a)
    assert qa.pk is not None
    assert qa.number.startswith("EPQA-")
    assert qa.author_name == "Prospective Buyer"
    assert qa.status == "approved"
    assert qa.is_staff_answer is True
    assert qa.is_pinned is False
    assert qa.helpful_votes == 2
    assert str(qa) == f"{qa.number} - {ecom_product_a.name} (approved)"


def test_reviewugc_question_staff_answer(tenant_a, ecom_product_a, admin_user):
    """ProductQuestionAnswer tracks staff answers, answering user, and answer timestamp."""
    now = timezone.now()
    qa = ProductQuestionAnswer.objects.create(
        tenant=tenant_a,
        product=ecom_product_a,
        author_name="Customer Jane",
        author_email="jane@example.com",
        question_text="Does this come with a warranty?",
        status="approved",
        answer_text="Yes, 2 years manufacturer warranty included.",
        answered_by_name="Store Support Lead",
        is_staff_answer=True,
        answered_by_user=admin_user,
        answered_at=now,
    )
    assert qa.is_staff_answer is True
    assert qa.answered_by_user == admin_user
    assert qa.answered_by_name == "Store Support Lead"
    assert qa.answered_at == now


def test_reviewugc_question_pinned_ordering(tenant_a, ecom_product_a):
    """ProductQuestionAnswer orders pinned inquiries first."""
    qa_unpinned = _reviewugc_question_answer(tenant_a, ecom_product_a, is_pinned=False)
    qa_pinned = _reviewugc_question_answer(tenant_a, ecom_product_a, is_pinned=True)

    items = list(ProductQuestionAnswer.objects.filter(tenant=tenant_a, product=ecom_product_a))
    assert items[0] == qa_pinned
    assert items[1] == qa_unpinned


def test_reviewugc_question_unique_constraint(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """ProductQuestionAnswer enforces unique constraint on (tenant, number)."""
    qa1 = _reviewugc_question_answer(tenant_a, ecom_product_a, number="EPQA-TEST-100")
    assert qa1.number == "EPQA-TEST-100"

    # Same number on same tenant must fail
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ProductQuestionAnswer.objects.create(
                tenant=tenant_a,
                product=ecom_product_a,
                author_name="Dup",
                question_text="Dup question?",
                number="EPQA-TEST-100",
            )

    # Same number on different tenant succeeds
    qa2 = _reviewugc_question_answer(tenant_b, ecom_product_b, number="EPQA-TEST-100")
    assert qa2.number == "EPQA-TEST-100"
    assert qa2.tenant == tenant_b


# ==============================================================================
# 4. VisualUgcMedia Model Tests
# ==============================================================================

def test_reviewugc_visual_ugc_creation_and_autonumber(tenant_a, ecom_product_a):
    """VisualUgcMedia auto-generates EUGC- prefix, sets defaults, and implements __str__."""
    ugc = _reviewugc_visual_ugc(tenant_a, ecom_product_a)
    assert ugc.pk is not None
    assert ugc.number.startswith("EUGC-")
    assert ugc.media_type == "photo"
    assert ugc.rights_status == "approved"
    assert ugc.is_shoppable is True
    assert ugc.is_published is True
    assert ugc.display_order == 10
    assert ugc.views_count == 0
    assert ugc.clicks_count == 0
    assert str(ugc) == f"{ugc.number} - {ecom_product_a.name} (Customer Photo)"


def test_reviewugc_visual_ugc_media_types_and_rights(tenant_a, ecom_product_a):
    """VisualUgcMedia supports photo, video, instagram, tiktok and rights status progression."""
    for m_type in ["photo", "video", "instagram", "tiktok"]:
        ugc = _reviewugc_visual_ugc(tenant_a, ecom_product_a, media_type=m_type)
        assert ugc.media_type == m_type

    for r_stat in ["approved", "pending_request", "rejected"]:
        ugc = _reviewugc_visual_ugc(tenant_a, ecom_product_a, rights_status=r_stat)
        assert ugc.rights_status == r_stat


def test_reviewugc_visual_ugc_shoppable_and_published_flags(tenant_a, ecom_product_a):
    """VisualUgcMedia flags can be toggled and filtered correctly."""
    ugc_pub = _reviewugc_visual_ugc(
        tenant_a, ecom_product_a, is_shoppable=True, is_published=True
    )
    ugc_unpub = _reviewugc_visual_ugc(
        tenant_a, ecom_product_a, is_shoppable=False, is_published=False
    )

    published = VisualUgcMedia.objects.filter(tenant=tenant_a, is_published=True)
    assert ugc_pub in published
    assert ugc_unpub not in published

    shoppable = VisualUgcMedia.objects.filter(tenant=tenant_a, is_shoppable=True)
    assert ugc_pub in shoppable
    assert ugc_unpub not in shoppable


def test_reviewugc_visual_ugc_ordering(tenant_a, ecom_product_a):
    """VisualUgcMedia orders by display_order ascending, then newest created_at."""
    ugc_high = _reviewugc_visual_ugc(tenant_a, ecom_product_a, display_order=50)
    ugc_low = _reviewugc_visual_ugc(tenant_a, ecom_product_a, display_order=5)

    items = list(VisualUgcMedia.objects.filter(tenant=tenant_a, tagged_product=ecom_product_a))
    assert items[0] == ugc_low
    assert items[1] == ugc_high


def test_reviewugc_visual_ugc_unique_constraint(tenant_a, tenant_b, ecom_product_a, ecom_product_b):
    """VisualUgcMedia enforces unique constraint on (tenant, number)."""
    ugc1 = _reviewugc_visual_ugc(tenant_a, ecom_product_a, number="EUGC-TEST-100")
    assert ugc1.number == "EUGC-TEST-100"

    # Same number on same tenant must fail
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            VisualUgcMedia.objects.create(
                tenant=tenant_a,
                tagged_product=ecom_product_a,
                media_url="https://example.com/another.jpg",
                number="EUGC-TEST-100",
            )

    # Same number on different tenant succeeds
    ugc2 = _reviewugc_visual_ugc(tenant_b, ecom_product_b, number="EUGC-TEST-100")
    assert ugc2.number == "EUGC-TEST-100"
    assert ugc2.tenant == tenant_b


# ==============================================================================
# 5. ReviewSentimentSummary Model Tests
# ==============================================================================

def test_reviewugc_sentiment_summary_creation_and_autonumber(tenant_a, ecom_product_a):
    """ReviewSentimentSummary auto-generates ERVM- prefix and implements __str__."""
    prod = _reviewugc_create_product(tenant_a, name="Summary Prod 1", slug_suffix="s1")
    summary = _reviewugc_sentiment_summary(tenant_a, prod)
    assert summary.pk is not None
    assert summary.number.startswith("ERVM-")
    assert summary.total_reviews == 10
    assert summary.average_rating == Decimal("4.60")
    assert str(summary) == f"{summary.number} - {prod.name} (4.60★ / 10 reviews)"


def test_reviewugc_sentiment_summary_onetoone_constraint(tenant_a):
    """ReviewSentimentSummary has a OneToOneField with CatalogProduct."""
    prod = _reviewugc_create_product(tenant_a, name="OneToOne Prod", slug_suffix="o2o")
    summary = _reviewugc_sentiment_summary(tenant_a, prod)
    assert prod.review_summary == summary

    # Attempting a second summary for the same product must fail OneToOne uniqueness
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            ReviewSentimentSummary.objects.create(
                tenant=tenant_a,
                product=prod,
                total_reviews=5,
            )


def test_reviewugc_sentiment_summary_rating_pct_properties(tenant_a):
    """rating_X_pct properties compute correct percentages or 0.0 when no reviews."""
    prod = _reviewugc_create_product(tenant_a, name="Rating Pct Prod", slug_suffix="pct")
    summary = _reviewugc_sentiment_summary(
        tenant_a,
        prod,
        total_reviews=10,
        rating_5_count=5,
        rating_4_count=3,
        rating_3_count=1,
        rating_2_count=1,
        rating_1_count=0,
    )
    assert summary.rating_5_pct == 50.0
    assert summary.rating_4_pct == 30.0
    assert summary.rating_3_pct == 10.0
    assert summary.rating_2_pct == 10.0
    assert summary.rating_1_pct == 0.0

    # Zero total reviews returns 0.0 for all percentages
    summary_empty = _reviewugc_sentiment_summary(
        tenant_a,
        _reviewugc_create_product(tenant_a, name="Empty Prod", slug_suffix="empty"),
        total_reviews=0,
        rating_5_count=0,
        rating_4_count=0,
        rating_3_count=0,
        rating_2_count=0,
        rating_1_count=0,
    )
    assert summary_empty.rating_5_pct == 0.0
    assert summary_empty.rating_4_pct == 0.0
    assert summary_empty.rating_3_pct == 0.0
    assert summary_empty.rating_2_pct == 0.0
    assert summary_empty.rating_1_pct == 0.0


def test_reviewugc_sentiment_summary_recalculate_empty(tenant_a):
    """recalculate() with no approved reviews resets counts and averages to zero."""
    prod = _reviewugc_create_product(tenant_a, name="Recalc Empty Prod", slug_suffix="re-empty")
    summary = ReviewSentimentSummary.objects.create(
        tenant=tenant_a,
        product=prod,
        total_reviews=99,
        average_rating=Decimal("4.50"),
    )
    summary.recalculate()
    summary.refresh_from_db()

    assert summary.total_reviews == 0
    assert summary.average_rating == Decimal("0.00")
    assert summary.rating_5_count == 0
    assert summary.rating_4_count == 0
    assert summary.rating_3_count == 0
    assert summary.rating_2_count == 0
    assert summary.rating_1_count == 0
    assert summary.positive_sentiment_pct == Decimal("0.00")
    assert summary.neutral_sentiment_pct == Decimal("0.00")
    assert summary.negative_sentiment_pct == Decimal("0.00")


def test_reviewugc_sentiment_summary_recalculate_with_reviews(tenant_a):
    """recalculate() correctly aggregates approved reviews only and computes stars & sentiment."""
    prod = _reviewugc_create_product(tenant_a, name="Recalc Prod", slug_suffix="recalc")

    # Approved reviews (total 4: two 5-star positive, one 4-star neutral, one 2-star negative)
    _reviewugc_product_review(tenant_a, prod, rating=5, sentiment="positive", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=5, sentiment="positive", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=4, sentiment="neutral", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=2, sentiment="negative", status="approved")

    # Non-approved reviews (must NOT be counted)
    _reviewugc_product_review(tenant_a, prod, rating=1, sentiment="negative", status="rejected")
    _reviewugc_product_review(tenant_a, prod, rating=5, sentiment="positive", status="pending")

    summary = ReviewSentimentSummary.objects.create(tenant=tenant_a, product=prod)
    summary.recalculate()
    summary.refresh_from_db()

    assert summary.total_reviews == 4
    assert summary.rating_5_count == 2
    assert summary.rating_4_count == 1
    assert summary.rating_3_count == 0
    assert summary.rating_2_count == 1
    assert summary.rating_1_count == 0

    # (5*2 + 4*1 + 2*1) / 4 = 16 / 4 = 4.00
    assert summary.average_rating == Decimal("4.00")

    # 2 positive / 4 = 50.00%
    assert summary.positive_sentiment_pct == Decimal("50.00")
    # 1 neutral / 4 = 25.00%
    assert summary.neutral_sentiment_pct == Decimal("25.00")
    # 1 negative / 4 = 25.00%
    assert summary.negative_sentiment_pct == Decimal("25.00")


def test_reviewugc_sentiment_summary_mixed_sentiment_handling(tenant_a):
    """recalculate() counts 'mixed' sentiment into neutral_sentiment_pct as designed."""
    prod = _reviewugc_create_product(tenant_a, name="Mixed Sent Prod", slug_suffix="mixed")

    # 1 positive, 1 mixed, 1 neutral, 1 negative (total 4)
    _reviewugc_product_review(tenant_a, prod, rating=5, sentiment="positive", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=3, sentiment="mixed", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=3, sentiment="neutral", status="approved")
    _reviewugc_product_review(tenant_a, prod, rating=1, sentiment="negative", status="approved")

    summary = ReviewSentimentSummary.objects.create(tenant=tenant_a, product=prod)
    summary.recalculate()
    summary.refresh_from_db()

    assert summary.total_reviews == 4
    assert summary.positive_sentiment_pct == Decimal("25.00")
    # Mixed (1) + Neutral (1) = 2 -> 50.00%
    assert summary.neutral_sentiment_pct == Decimal("50.00")
    assert summary.negative_sentiment_pct == Decimal("25.00")


def test_reviewugc_sentiment_summary_tenant_isolation(tenant_a, tenant_b):
    """recalculate() aggregates reviews only from the matching tenant and product."""
    prod_a = _reviewugc_create_product(tenant_a, name="Iso Prod A", slug_suffix="iso-a")
    prod_b = _reviewugc_create_product(tenant_b, name="Iso Prod B", slug_suffix="iso-b")

    # Tenant A: 1 review (5 star, positive)
    _reviewugc_product_review(tenant_a, prod_a, rating=5, sentiment="positive", status="approved")

    # Tenant B: 2 reviews (1 star, negative)
    _reviewugc_product_review(tenant_b, prod_b, rating=1, sentiment="negative", status="approved")
    _reviewugc_product_review(tenant_b, prod_b, rating=1, sentiment="negative", status="approved")

    summary_a = ReviewSentimentSummary.objects.create(tenant=tenant_a, product=prod_a)
    summary_a.recalculate()
    summary_a.refresh_from_db()

    assert summary_a.total_reviews == 1
    assert summary_a.average_rating == Decimal("5.00")
    assert summary_a.positive_sentiment_pct == Decimal("100.00")
    assert summary_a.negative_sentiment_pct == Decimal("0.00")

    # Verify unique constraint on tenant, number across tenants
    summary_b = ReviewSentimentSummary.objects.create(
        tenant=tenant_b, product=prod_b, number=summary_a.number
    )
    assert summary_b.number == summary_a.number
    assert summary_b.tenant != summary_a.tenant
