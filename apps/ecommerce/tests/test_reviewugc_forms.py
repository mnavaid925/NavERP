"""Form validation, exclusion, tenant isolation, and custom cleaning tests for eCommerce 9.13 Reviews & UGC.

Covers:
1. ProductReviewForm:
   - Mass-assignment exclusions (tenant, number, is_verified_purchase, helpful_votes, etc.)
   - Valid submission and tenant assignment
   - Tenant scoping on foreign key querysets (product, variant, customer, order)
   - Foreign tenant rejection
   - Variant belongs to product cross-validation
   - Order belongs to customer cross-validation
   - Verified purchase computation based on order line existence
2. ProductReviewModerationForm:
   - Moderation fields contract
   - Valid submission of moderation decisions (status, sentiment, merchant response, note)
   - Status choices validation
   - Sentiment choices validation
3. ProductQuestionAnswerForm:
   - Mass-assignment exclusions
   - Valid inquiry submission
   - Optional customer profile and author email
   - Tenant scoping and foreign tenant rejection
4. ProductQuestionAnswerResponseForm:
   - Field layout and choices
   - Required answer_text validation
   - Staff response submission and pinning
5. VisualUgcMediaForm:
   - Mass-assignment exclusions
   - Valid submission with tenant isolation
   - Tenant scoping and foreign tenant rejection
   - Tagged variant belongs to tagged product validation
   - URL scheme validation (HTTP/HTTPS enforcement on media_url & thumbnail_url)
6. ReviewSentimentSummaryForm:
   - Mass-assignment exclusions
   - Unsummarized product filtering on create
   - Duplicate scorecard creation rejection
   - Disabled product field on edit
   - Foreign tenant rejection

Naming conventions enforced:
- Test functions: test_reviewugc_*
- Module-level helpers: _reviewugc_*
"""
import pytest
from django import forms
from django.utils import timezone

from apps.core.models import Party
from apps.ecommerce.forms.ReviewUgc.ProductQuestionAnswers import (
    ProductQuestionAnswerForm,
    ProductQuestionAnswerResponseForm,
)
from apps.ecommerce.forms.ReviewUgc.ProductReviews import (
    ProductReviewForm,
    ProductReviewModerationForm,
)
from apps.ecommerce.forms.ReviewUgc.ReviewSentimentSummaries import (
    ReviewSentimentSummaryForm,
)
from apps.ecommerce.forms.ReviewUgc.VisualUgcMedia import (
    VisualUgcMediaForm,
)
from apps.ecommerce.models import (
    CatalogProduct,
    CustomerAccountProfile,
    EcommerceOrder,
    EcommerceOrderLine,
    ProductQuestionAnswer,
    ProductReview,
    ProductVariant,
    ReviewSentimentSummary,
    VisualUgcMedia,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_reviewugc_*)
# ==============================================================================

def _reviewugc_create_product(tenant, name="Extra Product", slug_suffix="extra"):
    """Helper to create a catalog product for tenant testing."""
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{slug_suffix}-{tenant.slug}",
        status="active",
    )


def _reviewugc_create_variant(tenant, product, sku="SKU-UGC-EXTRA", name="Extra Variant"):
    """Helper to create a product variant for mismatch testing."""
    return ProductVariant.objects.create(
        tenant=tenant,
        product=product,
        sku=f"{sku}-{tenant.slug}",
        name=name,
    )


def _reviewugc_create_customer_profile(tenant, name="Alternative Customer"):
    """Helper to create an extra customer account profile for mismatch testing."""
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    return CustomerAccountProfile.objects.create(tenant=tenant, customer=party)


# ==============================================================================
# 1. Contract & Mass-Assignment Exclusions
# ==============================================================================

def test_reviewugc_forms_fields_contract():
    """Verify that all ReviewUgc forms declare the exact expected Meta.fields."""
    assert tuple(ProductReviewForm.Meta.fields) == (
        "product",
        "variant",
        "customer",
        "order",
        "reviewer_name",
        "reviewer_email",
        "rating",
        "title",
        "body",
        "is_featured",
    )
    assert tuple(ProductReviewModerationForm.Meta.fields) == (
        "status",
        "sentiment",
        "is_featured",
        "merchant_response",
        "moderation_note",
    )
    assert tuple(ProductQuestionAnswerForm.Meta.fields) == (
        "product",
        "author_name",
        "author_email",
        "customer",
        "question_text",
    )
    assert tuple(ProductQuestionAnswerResponseForm.Meta.fields) == (
        "status",
        "answer_text",
        "answered_by_name",
        "is_staff_answer",
        "is_pinned",
    )
    assert tuple(VisualUgcMediaForm.Meta.fields) == (
        "media_type",
        "media_url",
        "thumbnail_url",
        "caption",
        "uploader_name",
        "uploader_handle",
        "tagged_product",
        "tagged_variant",
        "rights_status",
        "is_shoppable",
        "is_published",
        "display_order",
    )
    assert tuple(ReviewSentimentSummaryForm.Meta.fields) == (
        "product",
        "improvement_recommendation",
    )


def test_reviewugc_forms_mass_assignment_exclusions():
    """Verify system-generated, ledger, and auditing fields cannot be manipulated via forms."""
    # ProductReviewForm exclusions
    rev_fields = ProductReviewForm.Meta.fields
    for forbidden in (
        "tenant",
        "number",
        "is_verified_purchase",
        "helpful_votes",
        "unhelpful_votes",
        "sentiment_score",
        "moderated_by",
        "merchant_response_at",
        "created_at",
        "updated_at",
    ):
        assert forbidden not in rev_fields, f"Forbidden field '{forbidden}' exposed in ProductReviewForm"

    # ProductQuestionAnswerForm exclusions
    qa_fields = ProductQuestionAnswerForm.Meta.fields
    for forbidden in (
        "tenant",
        "number",
        "status",
        "answer_text",
        "answered_by_name",
        "is_staff_answer",
        "is_pinned",
        "answered_by_user",
        "answered_at",
        "helpful_votes",
        "created_at",
        "updated_at",
    ):
        assert forbidden not in qa_fields, f"Forbidden field '{forbidden}' exposed in ProductQuestionAnswerForm"

    # VisualUgcMediaForm exclusions
    ugc_fields = VisualUgcMediaForm.Meta.fields
    for forbidden in (
        "tenant",
        "number",
        "views_count",
        "clicks_count",
        "created_at",
        "updated_at",
    ):
        assert forbidden not in ugc_fields, f"Forbidden field '{forbidden}' exposed in VisualUgcMediaForm"

    # ReviewSentimentSummaryForm exclusions
    summ_fields = ReviewSentimentSummaryForm.Meta.fields
    for forbidden in (
        "tenant",
        "number",
        "total_reviews",
        "average_rating",
        "rating_5_count",
        "rating_4_count",
        "rating_3_count",
        "rating_2_count",
        "rating_1_count",
        "positive_sentiment_pct",
        "neutral_sentiment_pct",
        "negative_sentiment_pct",
        "top_positive_keywords",
        "top_negative_keywords",
        "last_calculated_at",
        "created_at",
        "updated_at",
    ):
        assert forbidden not in summ_fields, f"Forbidden field '{forbidden}' exposed in ReviewSentimentSummaryForm"


# ==============================================================================
# 2. ProductReviewForm Tests
# ==============================================================================

def test_reviewugc_product_review_form_valid_create(tenant_a, ecom_product_a):
    """Submitting valid product review data creates a pending review with tenant assigned."""
    data = {
        "product": ecom_product_a.pk,
        "rating": 5,
        "title": "Stunning craftsmanship and build quality",
        "body": "Exceeded all expectations, premium materials and fast delivery.",
        "reviewer_name": "Eleanor Vance",
        "reviewer_email": "eleanor@example.com",
        "is_featured": True,
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()
    assert review.pk is not None
    assert review.tenant == tenant_a
    assert review.rating == 5
    assert review.title == "Stunning craftsmanship and build quality"
    assert review.is_featured is True
    assert review.status == "pending"
    assert review.is_verified_purchase is False


def test_reviewugc_product_review_form_tenant_scoping(
    tenant_a,
    tenant_b,
    ecom_product_a,
    ecom_product_b,
    ecom_variant_a,
    ecom_variant_b,
    ecom_profile_a,
    ecom_profile_b,
    ecom_order_a,
    ecom_order_b,
):
    """Foreign key dropdown querysets on ProductReviewForm must be strictly tenant-isolated."""
    form = ProductReviewForm(tenant=tenant_a)
    product_qs = form.fields["product"].queryset
    assert ecom_product_a in product_qs
    assert ecom_product_b not in product_qs

    variant_qs = form.fields["variant"].queryset
    assert ecom_variant_a in variant_qs
    assert ecom_variant_b not in variant_qs

    customer_qs = form.fields["customer"].queryset
    assert ecom_profile_a in customer_qs
    assert ecom_profile_b not in customer_qs

    order_qs = form.fields["order"].queryset
    assert ecom_order_a in order_qs
    assert ecom_order_b not in order_qs


def test_reviewugc_product_review_form_reject_foreign_tenant(tenant_a, ecom_product_b):
    """Submitting a product belonging to tenant_b must be rejected by tenant_a form."""
    data = {
        "product": ecom_product_b.pk,
        "rating": 4,
        "title": "Cross tenant probe",
        "body": "Should fail security check.",
        "reviewer_name": "Bad Actor",
        "reviewer_email": "bad@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors


def test_reviewugc_product_review_form_variant_belongs_to_product_valid(
    tenant_a, ecom_product_a, ecom_variant_a
):
    """Matching product and variant passes clean() validation without variant errors."""
    data = {
        "product": ecom_product_a.pk,
        "variant": ecom_variant_a.pk,
        "rating": 5,
        "title": "Variant matched test",
        "body": "Valid product and variant combination.",
        "reviewer_name": "Valid Buyer",
        "reviewer_email": "valid@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()
    assert review.variant == ecom_variant_a


def test_reviewugc_product_review_form_variant_belongs_to_product_mismatch(
    tenant_a, ecom_product_a
):
    """Providing a variant that belongs to a different product raises a validation error on variant."""
    other_product = _reviewugc_create_product(tenant_a, name="Other Sneaker", slug_suffix="other")
    mismatched_variant = _reviewugc_create_variant(
        tenant_a, other_product, sku="SKU-MISMATCH-1", name="Other Variant"
    )

    data = {
        "product": ecom_product_a.pk,
        "variant": mismatched_variant.pk,
        "rating": 4,
        "title": "Mismatched variant test",
        "body": "This variant belongs to another product.",
        "reviewer_name": "Buyer Two",
        "reviewer_email": "buyer2@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors
    assert "The selected variant does not belong to the selected product." in form.errors["variant"]


def test_reviewugc_product_review_form_order_customer_matching_valid(
    tenant_a, ecom_product_a, ecom_profile_a, ecom_order_a
):
    """Matching order and customer profile passes clean() validation without order error."""
    data = {
        "product": ecom_product_a.pk,
        "customer": ecom_profile_a.pk,
        "order": ecom_order_a.pk,
        "rating": 5,
        "title": "Matched customer order",
        "body": "The order belongs to the specified customer.",
        "reviewer_name": "Matched Buyer",
        "reviewer_email": "matched@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_reviewugc_product_review_form_order_customer_matching_mismatch(
    tenant_a, ecom_product_a, ecom_order_a
):
    """Providing an order that belongs to a different customer profile raises an error on order."""
    other_profile = _reviewugc_create_customer_profile(tenant_a, name="Different Profile")

    data = {
        "product": ecom_product_a.pk,
        "customer": other_profile.pk,
        "order": ecom_order_a.pk,
        "rating": 5,
        "title": "Mismatched customer order test",
        "body": "Order does not belong to this profile.",
        "reviewer_name": "Imposter",
        "reviewer_email": "imposter@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "The selected order does not belong to the selected customer profile." in form.errors["order"]


def test_reviewugc_product_review_form_verified_purchase_true_when_order_contains_product(
    tenant_a, ecom_product_a, ecom_profile_a, ecom_order_a, ecom_order_line_a
):
    """When the submitted order has order lines containing the reviewed product, verified purchase is True."""
    data = {
        "product": ecom_product_a.pk,
        "customer": ecom_profile_a.pk,
        "order": ecom_order_a.pk,
        "rating": 5,
        "title": "Verified purchase review",
        "body": "I genuinely ordered this product in order A.",
        "reviewer_name": "Real Customer",
        "reviewer_email": "real@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()
    assert review.is_verified_purchase is True


def test_reviewugc_product_review_form_verified_purchase_false_when_order_lacks_product(
    tenant_a, ecom_profile_a, ecom_order_a, ecom_order_line_a
):
    """When the submitted order does NOT contain the reviewed product, verified purchase is False."""
    unrelated_product = _reviewugc_create_product(tenant_a, name="Unrelated Mug", slug_suffix="unrelated")

    data = {
        "product": unrelated_product.pk,
        "customer": ecom_profile_a.pk,
        "order": ecom_order_a.pk,
        "rating": 3,
        "title": "Review of product not in order",
        "body": "I ordered shoes, but reviewing mug.",
        "reviewer_name": "Real Customer",
        "reviewer_email": "real@example.com",
    }
    form = ProductReviewForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    review = form.save()
    assert review.is_verified_purchase is False


def test_reviewugc_product_review_form_required_and_choice_validation(tenant_a, ecom_product_a):
    """Omitted required fields and invalid ratings trigger validation errors."""
    # Blank required fields
    form = ProductReviewForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    for req in ("product", "rating", "title", "body", "reviewer_name", "reviewer_email"):
        assert req in form.errors

    # Invalid rating (not in 1..5)
    data = {
        "product": ecom_product_a.pk,
        "rating": 99,
        "title": "Invalid star rating",
        "body": "Should fail validation.",
        "reviewer_name": "Rating Tester",
        "reviewer_email": "tester@example.com",
    }
    form2 = ProductReviewForm(data=data, tenant=tenant_a)
    assert not form2.is_valid()
    assert "rating" in form2.errors


# ==============================================================================
# 3. ProductReviewModerationForm Tests
# ==============================================================================

def test_reviewugc_product_review_moderation_form_valid_submission(ecom_reviewugc_review_a):
    """Moderator submits approval, sentiment categorization, staff response, and internal note."""
    data = {
        "status": "approved",
        "sentiment": "positive",
        "is_featured": True,
        "merchant_response": "Thank you for the glowing praise! Our artisans are thrilled.",
        "moderation_note": "Verified customer receipt manually.",
    }
    form = ProductReviewModerationForm(data=data, instance=ecom_reviewugc_review_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.status == "approved"
    assert updated.sentiment == "positive"
    assert updated.is_featured is True
    assert updated.merchant_response == "Thank you for the glowing praise! Our artisans are thrilled."
    assert updated.moderation_note == "Verified customer receipt manually."


def test_reviewugc_product_review_moderation_form_choices(ecom_reviewugc_review_a):
    """Moderation form accepts all valid choices and rejects invalid status/sentiment."""
    # Test valid choices
    for st in ("pending", "approved", "rejected", "flagged_spam"):
        for sent in ("positive", "neutral", "negative", "mixed"):
            form = ProductReviewModerationForm(
                data={"status": st, "sentiment": sent, "is_featured": False},
                instance=ecom_reviewugc_review_a,
            )
            assert form.is_valid(), f"Failed on status={st}, sentiment={sent}: {form.errors}"

    # Test invalid status
    invalid_form = ProductReviewModerationForm(
        data={"status": "archived", "sentiment": "positive"},
        instance=ecom_reviewugc_review_a,
    )
    assert not invalid_form.is_valid()
    assert "status" in invalid_form.errors

    # Test invalid sentiment
    invalid_sent_form = ProductReviewModerationForm(
        data={"status": "approved", "sentiment": "ecstatic"},
        instance=ecom_reviewugc_review_a,
    )
    assert not invalid_sent_form.is_valid()
    assert "sentiment" in invalid_sent_form.errors


# ==============================================================================
# 4. ProductQuestionAnswerForm Tests
# ==============================================================================

def test_reviewugc_question_answer_form_valid_submission(tenant_a, ecom_product_a):
    """Submitting a valid pre-purchase question creates a pending Q&A entry."""
    data = {
        "product": ecom_product_a.pk,
        "author_name": "Marcus Aurelius",
        "author_email": "marcus@rome.org",
        "question_text": "Is the material water-resistant for heavy rain?",
    }
    form = ProductQuestionAnswerForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    qa = form.save()
    assert qa.pk is not None
    assert qa.tenant == tenant_a
    assert qa.product == ecom_product_a
    assert qa.author_name == "Marcus Aurelius"
    assert qa.author_email == "marcus@rome.org"
    assert qa.status == "pending"
    assert qa.is_staff_answer is False


def test_reviewugc_question_answer_form_optional_customer(tenant_a, ecom_product_a, ecom_profile_a):
    """Customer profile is optional, but correctly linked when provided."""
    # Optional customer omitted
    data_anon = {
        "product": ecom_product_a.pk,
        "author_name": "Anonymous Shopper",
        "question_text": "Does this come with a warranty?",
    }
    form_anon = ProductQuestionAnswerForm(data=data_anon, tenant=tenant_a)
    assert form_anon.is_valid(), form_anon.errors
    qa_anon = form_anon.save()
    assert qa_anon.customer is None

    # Linked customer
    data_cust = {
        "product": ecom_product_a.pk,
        "author_name": "Registered User",
        "customer": ecom_profile_a.pk,
        "question_text": "Can I use my store credits for this?",
    }
    form_cust = ProductQuestionAnswerForm(data=data_cust, tenant=tenant_a)
    assert form_cust.is_valid(), form_cust.errors
    qa_cust = form_cust.save()
    assert qa_cust.customer == ecom_profile_a


def test_reviewugc_question_answer_form_tenant_scoping_and_rejection(
    tenant_a, tenant_b, ecom_product_a, ecom_product_b, ecom_profile_a, ecom_profile_b
):
    """Product and Customer querysets are scoped to tenant, foreign items are rejected."""
    form = ProductQuestionAnswerForm(tenant=tenant_a)
    assert ecom_product_a in form.fields["product"].queryset
    assert ecom_product_b not in form.fields["product"].queryset
    assert ecom_profile_a in form.fields["customer"].queryset
    assert ecom_profile_b not in form.fields["customer"].queryset

    # Cross-tenant product submission rejected
    bad_data = {
        "product": ecom_product_b.pk,
        "author_name": "Foreign Inquirer",
        "question_text": "Cross-tenant inquiry?",
    }
    form_bad = ProductQuestionAnswerForm(data=bad_data, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "product" in form_bad.errors


# ==============================================================================
# 5. ProductQuestionAnswerResponseForm Tests
# ==============================================================================

def test_reviewugc_qa_response_form_valid_submission(ecom_reviewugc_qa_a):
    """Submitting official staff answer sets text, answered_by_name, and status."""
    data = {
        "status": "approved",
        "answer_text": "Yes, our coats feature a DWR water-resistant coating rated to 10,000mm.",
        "answered_by_name": "Dr. Sarah Adams, Head of Quality",
        "is_staff_answer": True,
        "is_pinned": True,
    }
    form = ProductQuestionAnswerResponseForm(data=data, instance=ecom_reviewugc_qa_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.status == "approved"
    assert updated.answer_text == "Yes, our coats feature a DWR water-resistant coating rated to 10,000mm."
    assert updated.answered_by_name == "Dr. Sarah Adams, Head of Quality"
    assert updated.is_staff_answer is True
    assert updated.is_pinned is True


def test_reviewugc_qa_response_form_answer_text_required(ecom_reviewugc_qa_a):
    """The response form requires answer_text to be non-empty upon submission."""
    data = {
        "status": "approved",
        "answer_text": "",
        "answered_by_name": "Support Bot",
        "is_staff_answer": True,
        "is_pinned": False,
    }
    form = ProductQuestionAnswerResponseForm(data=data, instance=ecom_reviewugc_qa_a)
    assert not form.is_valid()
    assert "answer_text" in form.errors


def test_reviewugc_qa_response_form_status_choices(ecom_reviewugc_qa_a):
    """Response form accepts pending/approved/rejected and rejects invalid status."""
    for st in ("pending", "approved", "rejected"):
        form = ProductQuestionAnswerResponseForm(
            data={"status": st, "answer_text": f"Status is {st}."},
            instance=ecom_reviewugc_qa_a,
        )
        assert form.is_valid(), form.errors

    bad_form = ProductQuestionAnswerResponseForm(
        data={"status": "discarded", "answer_text": "Invalid choice."},
        instance=ecom_reviewugc_qa_a,
    )
    assert not bad_form.is_valid()
    assert "status" in bad_form.errors


# ==============================================================================
# 6. VisualUgcMediaForm Tests
# ==============================================================================

def test_reviewugc_visual_ugc_form_valid_submission(tenant_a, ecom_product_a, ecom_variant_a):
    """Submitting valid visual UGC media creates an approved shoppable post."""
    data = {
        "media_type": "photo",
        "media_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
        "thumbnail_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=150",
        "caption": "Best morning run in months! Loving these sneakers.",
        "uploader_name": "Jenny Parker",
        "uploader_handle": "@jenny_runs",
        "tagged_product": ecom_product_a.pk,
        "tagged_variant": ecom_variant_a.pk,
        "rights_status": "approved",
        "is_shoppable": True,
        "is_published": True,
        "display_order": 15,
    }
    form = VisualUgcMediaForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    media = form.save()
    assert media.pk is not None
    assert media.tenant == tenant_a
    assert media.media_type == "photo"
    assert media.tagged_product == ecom_product_a
    assert media.tagged_variant == ecom_variant_a
    assert media.display_order == 15


def test_reviewugc_visual_ugc_form_tenant_scoping_and_foreign_rejection(
    tenant_a, tenant_b, ecom_product_a, ecom_product_b, ecom_variant_a, ecom_variant_b
):
    """Tagged product and variant querysets are tenant scoped, foreign items rejected."""
    form = VisualUgcMediaForm(tenant=tenant_a)
    assert ecom_product_a in form.fields["tagged_product"].queryset
    assert ecom_product_b not in form.fields["tagged_product"].queryset
    assert ecom_variant_a in form.fields["tagged_variant"].queryset
    assert ecom_variant_b not in form.fields["tagged_variant"].queryset

    # Cross-tenant submission rejected
    bad_data = {
        "media_type": "video",
        "media_url": "https://video.example.com/stream.mp4",
        "tagged_product": ecom_product_b.pk,
    }
    form_bad = VisualUgcMediaForm(data=bad_data, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "tagged_product" in form_bad.errors


def test_reviewugc_visual_ugc_form_variant_product_mismatch(tenant_a, ecom_product_a):
    """A tagged_variant that does not belong to the tagged_product triggers a validation error."""
    other_prod = _reviewugc_create_product(tenant_a, name="Other Hoodie", slug_suffix="hoodie")
    other_var = _reviewugc_create_variant(tenant_a, other_prod, sku="SKU-HOODIE-M", name="Medium Hoodie")

    data = {
        "media_type": "photo",
        "media_url": "https://cdn.example.com/ugc.jpg",
        "tagged_product": ecom_product_a.pk,
        "tagged_variant": other_var.pk,
        "rights_status": "approved",
    }
    form = VisualUgcMediaForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "tagged_variant" in form.errors
    assert "The selected variant does not belong to the tagged product." in form.errors["tagged_variant"]


def test_reviewugc_visual_ugc_form_url_scheme_enforcement(tenant_a, ecom_product_a):
    """Enforces that media_url and thumbnail_url only permit HTTP and HTTPS schemes."""
    # Schemes permitted by Django's URLField but rejected by clean_media_url / clean_thumbnail_url
    for non_http_url in (
        "ftp://downloads.example.com/photo.jpg",
        "ftps://downloads.example.com/photo.jpg",
    ):
        data = {
            "media_type": "photo",
            "media_url": non_http_url,
            "tagged_product": ecom_product_a.pk,
        }
        form = VisualUgcMediaForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "media_url" in form.errors
        assert "Only HTTP and HTTPS URL schemes are permitted." in form.errors["media_url"]

    # Invalid scheme on thumbnail_url
    data_bad_thumb = {
        "media_type": "photo",
        "media_url": "https://valid.example.com/photo.jpg",
        "thumbnail_url": "ftp://thumbs.example.com/thumb.jpg",
        "tagged_product": ecom_product_a.pk,
    }
    form_thumb = VisualUgcMediaForm(data=data_bad_thumb, tenant=tenant_a)
    assert not form_thumb.is_valid()
    assert "thumbnail_url" in form_thumb.errors
    assert "Only HTTP and HTTPS URL schemes are permitted." in form_thumb.errors["thumbnail_url"]

    # Disallowed non-standard URLs rejected by standard URL validator
    for bad_url in ("javascript:alert(1)", "file:///etc/passwd"):
        data_bad = {
            "media_type": "photo",
            "media_url": bad_url,
            "tagged_product": ecom_product_a.pk,
        }
        form_bad = VisualUgcMediaForm(data=data_bad, tenant=tenant_a)
        assert not form_bad.is_valid()
        assert "media_url" in form_bad.errors

    # Valid HTTP and HTTPS urls
    data_valid = {
        "media_type": "photo",
        "media_url": "http://photos.example.com/runner.jpg",
        "thumbnail_url": "https://photos.example.com/runner-thumb.jpg",
        "tagged_product": ecom_product_a.pk,
        "rights_status": "approved",
        "display_order": 10,
    }
    form_ok = VisualUgcMediaForm(data=data_valid, tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors


# ==============================================================================
# 7. ReviewSentimentSummaryForm Tests
# ==============================================================================

def test_reviewugc_sentiment_summary_form_create_filters_unsummarized_products(
    tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """On create, product queryset only shows products that do not already have a summary."""
    new_unsummarized_product = _reviewugc_create_product(
        tenant_a, name="New Unsummarized Gadget", slug_suffix="gadget"
    )

    form = ReviewSentimentSummaryForm(tenant=tenant_a)
    qs = form.fields["product"].queryset
    # New product is unsummarized, so it should be available
    assert new_unsummarized_product in qs
    # ecom_product_a already has ecom_reviewugc_summary_a, so it must be excluded
    assert ecom_product_a not in qs
    assert form.fields["product"].disabled is False


def test_reviewugc_sentiment_summary_form_create_duplicate_product_rejected(
    tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """Attempting to select an already-summarized product is rejected by field choices."""
    data = {
        "product": ecom_product_a.pk,
        "improvement_recommendation": "Duplicate scorecard attempt.",
    }
    form = ReviewSentimentSummaryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors
    assert "Select a valid choice" in str(form.errors["product"])


def test_reviewugc_sentiment_summary_form_clean_duplicate_rejection_defense(
    tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """clean() acts as defense-in-depth against duplicate summaries if product is in queryset."""
    form = ReviewSentimentSummaryForm(
        data={
            "product": ecom_product_a.pk,
            "improvement_recommendation": "Duplicate scorecard attempt.",
        },
        tenant=tenant_a,
    )
    # Allow field validation to pass by including all tenant products
    form.fields["product"].queryset = CatalogProduct.objects.filter(tenant=tenant_a)

    # Now clean() detects the existing summary and adds form error
    assert not form.is_valid()
    assert "product" in form.errors
    assert "A review sentiment scorecard already exists for this product." in form.errors["product"]


def test_reviewugc_sentiment_summary_form_create_valid(tenant_a):
    """Creating a sentiment summary for an unsummarized product succeeds."""
    clean_product = _reviewugc_create_product(tenant_a, name="Clean Watch", slug_suffix="watch")
    data = {
        "product": clean_product.pk,
        "improvement_recommendation": "Maintain rigorous leather band quality inspection.",
    }
    form = ReviewSentimentSummaryForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    summary = form.save()
    assert summary.pk is not None
    assert summary.tenant == tenant_a
    assert summary.product == clean_product
    assert summary.improvement_recommendation == "Maintain rigorous leather band quality inspection."


def test_reviewugc_sentiment_summary_form_edit_disables_product(
    tenant_a, ecom_reviewugc_summary_a
):
    """On edit, the product field is disabled and editing recommendations works without duplicate error."""
    form = ReviewSentimentSummaryForm(instance=ecom_reviewugc_summary_a, tenant=tenant_a)
    assert form.fields["product"].disabled is True
    assert ecom_reviewugc_summary_a.product in form.fields["product"].queryset

    data = {
        "product": ecom_reviewugc_summary_a.product.pk,
        "improvement_recommendation": "Updated executive product guidance recommendations.",
    }
    bound_form = ReviewSentimentSummaryForm(
        data=data, instance=ecom_reviewugc_summary_a, tenant=tenant_a
    )
    assert bound_form.is_valid(), bound_form.errors
    updated = bound_form.save()
    assert updated.improvement_recommendation == "Updated executive product guidance recommendations."


def test_reviewugc_sentiment_summary_form_reject_foreign_tenant(tenant_a, ecom_product_b):
    """Submitting tenant_b's product on tenant_a form is rejected."""
    data = {
        "product": ecom_product_b.pk,
        "improvement_recommendation": "Foreign tenant test.",
    }
    form = ReviewSentimentSummaryForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors
