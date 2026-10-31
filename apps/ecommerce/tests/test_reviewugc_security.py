"""Comprehensive multi-tenancy, authorization, method safety, IDOR, and XSS security unit tests for eCommerce 9.13 Reviews & User-Generated Content.

Covers:
1. Multi-tenant data isolation & IDOR (cross-tenant detail, edit, delete, moderate, respond, recalculate across all 4 models returns 404).
2. Authentication requirements (unauthenticated requests redirect to login across all 23 endpoints).
3. Authorization & role permissions: standard non-admin staff receive 403 Forbidden on delete, moderate, respond, and recalculate endpoints decorated with @tenant_admin_required.
4. Method safety: GET requests on POST-only endpoints (delete, recalculate) return 405 Method Not Allowed.
5. Cross-record integrity: foreign tenant references and variant-to-product mismatches are rejected with form validation errors.
6. XSS protection: review body, reviewer name, question text, and UGC captions containing HTML/script tags are properly escaped when rendered in templates.
7. AuditLog verification: mutating operations record accurate, tenant-scoped AuditLog rows.

Naming conventions enforced:
- Test functions: test_reviewugc_*
- Module-level helpers: _reviewugc_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
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
from apps.ecommerce.forms.ReviewUgc.VisualUgcMedia import VisualUgcMediaForm
from apps.ecommerce.models import (
    CatalogProduct,
    CustomerAccountProfile,
    ProductQuestionAnswer,
    ProductReview,
    ProductVariant,
    ReviewSentimentSummary,
    VisualUgcMedia,
)
from apps.ecommerce.tests.conftest import (
    REVIEWUGC_URL_NAMES,
    _reviewugc_product_review,
    _reviewugc_question_answer,
    _reviewugc_sentiment_summary,
    _reviewugc_visual_ugc,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_reviewugc_*)
# ==============================================================================

def _reviewugc_create_product(tenant, name="Security Test Product", slug_suffix="sec"):
    """Helper to create an isolated catalog product."""
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{slug_suffix}-{tenant.slug}",
        status="active",
    )


def _reviewugc_create_variant(tenant, product, sku="SKU-SEC-VAR", name="Sec Variant"):
    """Helper to create a product variant."""
    return ProductVariant.objects.create(
        tenant=tenant,
        product=product,
        sku=f"{sku}-{tenant.slug}",
        name=name,
    )


def _reviewugc_create_customer(tenant, name="Sec Customer"):
    """Helper to create a customer profile."""
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    return CustomerAccountProfile.objects.create(tenant=tenant, customer=party)


# ==============================================================================
# 1. Multi-Tenant Data Isolation & IDOR Tests
# ==============================================================================

def test_reviewugc_idor_productreview_cross_tenant_access_blocked(client_b, ecom_reviewugc_review_a):
    """Tenant B user accessing Tenant A ProductReview via detail/edit/delete/moderate returns 404."""
    review = ecom_reviewugc_review_a
    detail_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[review.pk])
    edit_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[review.pk])
    delete_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[review.pk])
    moderate_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[review.pk])

    # Detail
    assert client_b.get(detail_url).status_code == 404

    # Edit GET and POST
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"rating": 1, "title": "Hacked Title"}).status_code == 404

    # Delete POST
    assert client_b.post(delete_url).status_code == 404

    # Moderate GET and POST
    assert client_b.get(moderate_url).status_code == 404
    assert client_b.post(moderate_url, {"status": "rejected"}).status_code == 404

    # Review remains unaffected in database
    review.refresh_from_db()
    assert review.rating == 5
    assert review.status == "approved"


def test_reviewugc_idor_productquestionanswer_cross_tenant_access_blocked(client_b, ecom_reviewugc_qa_a):
    """Tenant B user accessing Tenant A ProductQuestionAnswer via detail/edit/delete/respond returns 404."""
    qa = ecom_reviewugc_qa_a
    detail_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[qa.pk])
    edit_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[qa.pk])
    delete_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[qa.pk])
    respond_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[qa.pk])

    # Detail
    assert client_b.get(detail_url).status_code == 404

    # Edit GET and POST
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"question_text": "Hacked question?"}).status_code == 404

    # Delete POST
    assert client_b.post(delete_url).status_code == 404

    # Respond GET and POST
    assert client_b.get(respond_url).status_code == 404
    assert client_b.post(respond_url, {"answer_text": "Hacked answer"}).status_code == 404

    # QA remains unaffected in database
    qa.refresh_from_db()
    assert qa.question_text == "Is this product dishwasher safe?"
    assert qa.status == "approved"


def test_reviewugc_idor_visualugcmedia_cross_tenant_access_blocked(client_b, ecom_reviewugc_ugc_a):
    """Tenant B user accessing Tenant A VisualUgcMedia via detail/edit/delete returns 404."""
    ugc = ecom_reviewugc_ugc_a
    detail_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ugc.pk])
    edit_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ugc.pk])
    delete_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ugc.pk])

    # Detail
    assert client_b.get(detail_url).status_code == 404

    # Edit GET and POST
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"caption": "Hacked caption"}).status_code == 404

    # Delete POST
    assert client_b.post(delete_url).status_code == 404

    # Media remains intact
    ugc.refresh_from_db()
    assert ugc.caption == "Loving my new product! #shopping"
    assert ugc.is_published is True


def test_reviewugc_idor_reviewsentimentsummary_cross_tenant_access_blocked(client_b, ecom_reviewugc_summary_a):
    """Tenant B user accessing Tenant A ReviewSentimentSummary via detail/edit/delete/recalc returns 404."""
    summary = ecom_reviewugc_summary_a
    detail_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[summary.pk])
    edit_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[summary.pk])
    delete_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[summary.pk])
    recalc_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[summary.pk])

    # Detail
    assert client_b.get(detail_url).status_code == 404

    # Edit GET and POST
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"improvement_recommendation": "Hacked"}).status_code == 404

    # Delete POST
    assert client_b.post(delete_url).status_code == 404

    # Recalculate POST
    assert client_b.post(recalc_url).status_code == 404

    # Summary remains intact
    summary.refresh_from_db()
    assert summary.improvement_recommendation == "Maintain high quality standards."


def test_reviewugc_cross_tenant_list_isolation(
    client_a,
    client_b,
    ecom_product_a,
    ecom_product_b,
    ecom_reviewugc_review_a,
    ecom_reviewugc_review_b,
    ecom_reviewugc_qa_a,
    ecom_reviewugc_qa_b,
    ecom_reviewugc_ugc_a,
    ecom_reviewugc_ugc_b,
    ecom_reviewugc_summary_a,
    ecom_reviewugc_summary_b,
):
    """List views strictly isolate records belonging to each tenant."""
    # 1. ProductReview List
    resp_a = client_a.get(reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"]))
    assert ecom_product_a.name.encode() in resp_a.content
    assert ecom_product_b.name.encode() not in resp_a.content

    resp_b = client_b.get(reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"]))
    assert ecom_product_b.name.encode() in resp_b.content
    assert ecom_product_a.name.encode() not in resp_b.content

    # 2. ProductQuestionAnswer List
    resp_a = client_a.get(reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"]))
    assert ecom_product_a.name.encode() in resp_a.content
    assert ecom_product_b.name.encode() not in resp_a.content

    resp_b = client_b.get(reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"]))
    assert ecom_product_b.name.encode() in resp_b.content
    assert ecom_product_a.name.encode() not in resp_b.content

    # 3. VisualUgcMedia List
    resp_a = client_a.get(reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"]))
    assert ecom_product_a.name.encode() in resp_a.content
    assert ecom_product_b.name.encode() not in resp_a.content

    resp_b = client_b.get(reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"]))
    assert ecom_product_b.name.encode() in resp_b.content
    assert ecom_product_a.name.encode() not in resp_b.content

    # 4. ReviewSentimentSummary List
    resp_a = client_a.get(reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"]))
    assert ecom_product_a.name.encode() in resp_a.content
    assert ecom_product_b.name.encode() not in resp_a.content

    resp_b = client_b.get(reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"]))
    assert ecom_product_b.name.encode() in resp_b.content
    assert ecom_product_a.name.encode() not in resp_b.content


# ==============================================================================
# 2. Authentication Requirements Tests
# ==============================================================================

def test_reviewugc_unauthenticated_requests_redirect_to_login(
    client,
    ecom_reviewugc_review_a,
    ecom_reviewugc_qa_a,
    ecom_reviewugc_ugc_a,
    ecom_reviewugc_summary_a,
):
    """Anonymous unauthenticated requests to all 23 ReviewUgc endpoints redirect to login."""
    endpoints = [
        # ProductReview
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[ecom_reviewugc_review_a.pk]),
        # ProductQuestionAnswer
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[ecom_reviewugc_qa_a.pk]),
        # VisualUgcMedia
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ecom_reviewugc_ugc_a.pk]),
        # ReviewSentimentSummary
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[ecom_reviewugc_summary_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[ecom_reviewugc_summary_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[ecom_reviewugc_summary_a.pk]),
    ]

    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "login" in resp.url, f"Expected login in redirect URL for {url}, got {resp.url}"


# ==============================================================================
# 3. Authorization & Role Permissions (RBAC) Tests
# ==============================================================================

def test_reviewugc_non_admin_member_forbidden_on_privileged_actions(
    member_client,
    ecom_reviewugc_review_a,
    ecom_reviewugc_qa_a,
    ecom_reviewugc_ugc_a,
    ecom_reviewugc_summary_a,
):
    """Standard non-admin members receive 403 Forbidden on views decorated with @tenant_admin_required."""
    privileged_endpoints = [
        # ProductReview: delete (POST) and moderate (GET & POST)
        ("POST", reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[ecom_reviewugc_review_a.pk]), {}),
        ("GET", reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk]), None),
        ("POST", reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk]), {"status": "approved"}),
        # ProductQuestionAnswer: delete (POST) and respond (GET & POST)
        ("POST", reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[ecom_reviewugc_qa_a.pk]), {}),
        ("GET", reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk]), None),
        ("POST", reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk]), {"answer_text": "Answer"}),
        # VisualUgcMedia: delete (POST)
        ("POST", reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ecom_reviewugc_ugc_a.pk]), {}),
        # ReviewSentimentSummary: delete (POST) and recalculate (POST)
        ("POST", reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[ecom_reviewugc_summary_a.pk]), {}),
        ("POST", reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[ecom_reviewugc_summary_a.pk]), {}),
    ]

    for method, url, data in privileged_endpoints:
        if method == "POST":
            resp = member_client.post(url, data or {})
        else:
            resp = member_client.get(url)
        assert resp.status_code == 403, f"Expected 403 Forbidden for non-admin on {url}, got {resp.status_code}"


def test_reviewugc_admin_authorized_on_privileged_actions(
    client_a,
    ecom_reviewugc_review_a,
    ecom_reviewugc_qa_a,
):
    """Tenant admin client can access privileged moderate and respond GET views."""
    mod_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk])
    resp_mod = client_a.get(mod_url)
    assert resp_mod.status_code == 200

    resp_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk])
    resp_qa = client_a.get(resp_url)
    assert resp_qa.status_code == 200


def test_reviewugc_non_admin_member_allowed_standard_crud(
    member_client,
    ecom_reviewugc_review_a,
    ecom_reviewugc_qa_a,
    ecom_reviewugc_ugc_a,
    ecom_reviewugc_summary_a,
):
    """Standard non-admin members can access standard list, detail, create, and edit GET views."""
    standard_get_urls = [
        # Lists
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"]),
        # Details
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk]),
        # Create forms
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"]),
        # Edit forms
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[ecom_reviewugc_summary_a.pk]),
    ]

    for url in standard_get_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Expected 200 for member on {url}, got {resp.status_code}"


# ==============================================================================
# 4. Method Safety Tests
# ==============================================================================

def test_reviewugc_post_only_method_safety(
    client_a,
    ecom_reviewugc_review_a,
    ecom_reviewugc_qa_a,
    ecom_reviewugc_ugc_a,
    ecom_reviewugc_summary_a,
):
    """GET requests on POST-only endpoints (delete, recalculate) return 405 Method Not Allowed."""
    post_only_urls = [
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[ecom_reviewugc_summary_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[ecom_reviewugc_summary_a.pk]),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET on {url}, got {resp.status_code}"


# ==============================================================================
# 5. Cross-Record Integrity & Form Validation Tests
# ==============================================================================

def test_reviewugc_foreign_tenant_references_rejected(
    tenant_a,
    tenant_b,
    ecom_product_b,
    ecom_variant_b,
    ecom_profile_b,
    ecom_order_b,
):
    """Foreign tenant references are rejected across all ReviewUgc forms."""
    # 1. ProductReviewForm rejecting Tenant B references
    rev_form = ProductReviewForm(
        data={
            "product": ecom_product_b.pk,
            "variant": ecom_variant_b.pk,
            "customer": ecom_profile_b.pk,
            "order": ecom_order_b.pk,
            "rating": 5,
            "title": "Cross Tenant Test",
            "body": "Should fail",
            "reviewer_name": "Adversary",
            "reviewer_email": "adv@example.com",
        },
        tenant=tenant_a,
    )
    assert not rev_form.is_valid()
    assert "product" in rev_form.errors

    # 2. ProductQuestionAnswerForm rejecting Tenant B references
    qa_form = ProductQuestionAnswerForm(
        data={
            "product": ecom_product_b.pk,
            "customer": ecom_profile_b.pk,
            "author_name": "Adversary",
            "author_email": "adv@example.com",
            "question_text": "Cross tenant probe question?",
        },
        tenant=tenant_a,
    )
    assert not qa_form.is_valid()
    assert "product" in qa_form.errors

    # 3. VisualUgcMediaForm rejecting Tenant B references
    ugc_form = VisualUgcMediaForm(
        data={
            "media_type": "photo",
            "media_url": "https://example.com/sec.jpg",
            "thumbnail_url": "https://example.com/sec-thumb.jpg",
            "caption": "Cross tenant probe",
            "uploader_name": "Adversary",
            "tagged_product": ecom_product_b.pk,
            "tagged_variant": ecom_variant_b.pk,
            "rights_status": "approved",
            "display_order": 1,
        },
        tenant=tenant_a,
    )
    assert not ugc_form.is_valid()
    assert "tagged_product" in ugc_form.errors

    # 4. ReviewSentimentSummaryForm rejecting Tenant B references
    summ_form = ReviewSentimentSummaryForm(
        data={
            "product": ecom_product_b.pk,
            "improvement_recommendation": "Cross tenant probe",
        },
        tenant=tenant_a,
    )
    assert not summ_form.is_valid()
    assert "product" in summ_form.errors


def test_reviewugc_variant_product_mismatch_rejected(tenant_a, ecom_product_a):
    """Providing a variant that belongs to a different product raises a validation error."""
    other_product = _reviewugc_create_product(tenant_a, name="Other Security Shoe", slug_suffix="other-shoe")
    mismatched_variant = _reviewugc_create_variant(tenant_a, other_product, sku="SKU-MISMATCH-SEC", name="Mismatch Var")

    # ProductReviewForm variant mismatch
    rev_form = ProductReviewForm(
        data={
            "product": ecom_product_a.pk,
            "variant": mismatched_variant.pk,
            "rating": 5,
            "title": "Mismatch Test",
            "body": "Should fail variant check.",
            "reviewer_name": "Tester",
            "reviewer_email": "tester@example.com",
        },
        tenant=tenant_a,
    )
    assert not rev_form.is_valid()
    assert "variant" in rev_form.errors
    assert "The selected variant does not belong to the selected product." in rev_form.errors["variant"]

    # VisualUgcMediaForm tagged_variant mismatch
    ugc_form = VisualUgcMediaForm(
        data={
            "media_type": "photo",
            "media_url": "https://example.com/ugc.jpg",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "caption": "Variant mismatch caption",
            "uploader_name": "Photographer",
            "tagged_product": ecom_product_a.pk,
            "tagged_variant": mismatched_variant.pk,
            "rights_status": "approved",
            "display_order": 1,
        },
        tenant=tenant_a,
    )
    assert not ugc_form.is_valid()
    assert "tagged_variant" in ugc_form.errors
    assert "The selected variant does not belong to the tagged product." in ugc_form.errors["tagged_variant"]


def test_reviewugc_order_customer_mismatch_rejected(tenant_a, ecom_product_a, ecom_order_a):
    """Providing an order that belongs to a different customer profile raises validation error on order."""
    alt_customer = _reviewugc_create_customer(tenant_a, name="Unrelated Profile")

    rev_form = ProductReviewForm(
        data={
            "product": ecom_product_a.pk,
            "rating": 5,
            "title": "Mismatch Order Customer",
            "body": "Should fail cross-record validation.",
            "reviewer_name": "Valid Buyer",
            "reviewer_email": "buyer@example.com",
            "customer": alt_customer.pk,
            "order": ecom_order_a.pk,
        },
        tenant=tenant_a,
    )
    assert not rev_form.is_valid()
    assert "order" in rev_form.errors
    assert "The selected order does not belong to the selected customer profile." in rev_form.errors["order"]


def test_reviewugc_url_scheme_injection_rejected(tenant_a, ecom_product_a):
    """Submitting dangerous non-HTTP/HTTPS URLs (ftp:, javascript:) in UGC media URLs is rejected."""
    # 1. FTP scheme is parsed by URLValidator but rejected by clean_media_url
    form_ftp = VisualUgcMediaForm(
        data={
            "media_type": "photo",
            "media_url": "ftp://example.com/file.jpg",
            "thumbnail_url": "https://example.com/valid.jpg",
            "caption": "FTP scheme test",
            "uploader_name": "Adversary",
            "tagged_product": ecom_product_a.pk,
            "rights_status": "approved",
            "display_order": 1,
        },
        tenant=tenant_a,
    )
    assert not form_ftp.is_valid()
    assert "media_url" in form_ftp.errors
    assert "Only HTTP and HTTPS URL schemes are permitted." in form_ftp.errors["media_url"]

    # 2. Javascript scheme is rejected by URL validation
    form_js = VisualUgcMediaForm(
        data={
            "media_type": "photo",
            "media_url": "javascript:alert(1)",
            "thumbnail_url": "https://example.com/valid.jpg",
            "caption": "JS injection test",
            "uploader_name": "Adversary",
            "tagged_product": ecom_product_a.pk,
            "rights_status": "approved",
            "display_order": 1,
        },
        tenant=tenant_a,
    )
    assert not form_js.is_valid()
    assert "media_url" in form_js.errors


# ==============================================================================
# 6. XSS Protection & HTML Escaping Tests
# ==============================================================================

def test_reviewugc_xss_productreview_escaping(client_a, tenant_a, ecom_product_a):
    """Malicious scripts in ProductReview fields are HTML-escaped and not rendered raw."""
    xss_payload = '<script>alert("xss-productreview")</script>'
    xss_img = '<img src=x onerror=alert("xss-img")>'

    review = _reviewugc_product_review(
        tenant_a,
        ecom_product_a,
        title=xss_payload,
        reviewer_name=xss_payload,
        body=f"Great product! {xss_img}",
        merchant_response=xss_payload,
        moderation_note=xss_payload,
    )

    # 1. Detail View
    detail_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[review.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_payload.encode() not in resp_detail.content
    assert xss_img.encode() not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content

    # 2. List View
    list_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"])
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_payload.encode() not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content


def test_reviewugc_xss_productquestionanswer_escaping(client_a, tenant_a, ecom_product_a):
    """Malicious scripts in ProductQuestionAnswer fields are HTML-escaped and not rendered raw."""
    xss_payload = '<script>alert("xss-question")</script>'
    xss_answer = '<script>alert("xss-answer")</script>'

    qa = _reviewugc_question_answer(
        tenant_a,
        ecom_product_a,
        author_name=xss_payload,
        question_text=xss_payload,
        answer_text=xss_answer,
        answered_by_name=xss_payload,
    )

    # 1. Detail View
    detail_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[qa.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_payload.encode() not in resp_detail.content
    assert xss_answer.encode() not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content

    # 2. List View
    list_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"])
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_payload.encode() not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content


def test_reviewugc_xss_visualugcmedia_escaping(client_a, tenant_a, ecom_product_a):
    """Malicious scripts in VisualUgcMedia captions and user handles are HTML-escaped."""
    xss_caption = '<script>alert("xss-ugc-caption")</script>'
    xss_handle = '<script>alert("xss-ugc-handle")</script>'

    ugc = _reviewugc_visual_ugc(
        tenant_a,
        ecom_product_a,
        caption=xss_caption,
        uploader_name='<script>alert("xss-name")</script>',
        uploader_handle=xss_handle,
    )

    # 1. Detail View
    detail_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ugc.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_caption.encode() not in resp_detail.content
    assert xss_handle.encode() not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content

    # 2. List View
    list_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"])
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_caption.encode() not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content


def test_reviewugc_xss_reviewsentimentsummary_escaping(client_a, tenant_a, ecom_product_a):
    """Malicious scripts in ReviewSentimentSummary recommendations are HTML-escaped on detail."""
    xss_rec = '<script>alert("xss-rec")</script>'

    summary = _reviewugc_sentiment_summary(
        tenant_a,
        ecom_product_a,
        improvement_recommendation=xss_rec,
    )

    # 1. Detail View renders recommendation with autoescaping
    detail_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[summary.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_rec.encode() not in resp_detail.content
    assert b"&lt;script&gt;alert(" in resp_detail.content

    # 2. List View does not expose unescaped script
    list_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"])
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_rec.encode() not in resp_list.content


# ==============================================================================
# 7. AuditLog Verification Tests
# ==============================================================================

def test_reviewugc_productreview_auditlog_recorded(client_a, tenant_a, ecom_product_a, admin_user):
    """ProductReview mutations (create, update, moderate, delete) write tenant-scoped AuditLog rows."""
    # 1. Create
    create_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"])
    resp_create = client_a.post(
        create_url,
        {
            "product": ecom_product_a.pk,
            "rating": 5,
            "title": "Audit Review",
            "body": "Detailed review for audit test.",
            "reviewer_name": "Audit Customer",
            "reviewer_email": "audit@example.com",
        },
    )
    assert resp_create.status_code == 302
    created_review = ProductReview.objects.filter(tenant=tenant_a, title="Audit Review").first()
    assert created_review is not None

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=created_review.pk,
    ).first()
    assert audit_create is not None
    assert audit_create.changes.get("rating") == 5

    # 2. Update / Edit
    edit_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[created_review.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "product": ecom_product_a.pk,
            "rating": 4,
            "title": "Audit Review Updated",
            "body": "Updated body content.",
            "reviewer_name": "Audit Customer",
            "reviewer_email": "audit@example.com",
        },
    )
    assert resp_edit.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_review.pk,
    ).first()
    assert audit_update is not None

    # 3. Moderate
    moderate_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[created_review.pk])
    resp_mod = client_a.post(
        moderate_url,
        {
            "status": "approved",
            "sentiment": "positive",
            "merchant_response": "Thank you for the review!",
            "moderation_note": "Legit verified customer.",
        },
    )
    assert resp_mod.status_code == 302
    audit_mod = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="moderate",
        object_id=created_review.pk,
    ).first()
    assert audit_mod is not None
    assert audit_mod.changes.get("status") == "approved"

    # 4. Delete
    delete_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[created_review.pk])
    review_num = created_review.number
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302
    audit_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=review_num,
    ).first()
    assert audit_del is not None


def test_reviewugc_productquestionanswer_auditlog_recorded(client_a, tenant_a, ecom_product_a, admin_user):
    """ProductQuestionAnswer mutations (create, update, respond, delete) write AuditLog rows."""
    # 1. Create
    create_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"])
    resp_create = client_a.post(
        create_url,
        {
            "product": ecom_product_a.pk,
            "author_name": "Inquiring Buyer",
            "author_email": "buyer@example.com",
            "question_text": "Is this model water resistant?",
        },
    )
    assert resp_create.status_code == 302
    qa = ProductQuestionAnswer.objects.filter(tenant=tenant_a, author_name="Inquiring Buyer").first()
    assert qa is not None

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=qa.pk,
    ).first()
    assert audit_create is not None

    # 2. Update / Edit
    edit_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[qa.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "product": ecom_product_a.pk,
            "author_name": "Inquiring Buyer",
            "author_email": "buyer@example.com",
            "question_text": "Is this model fully waterproof to 50m?",
        },
    )
    assert resp_edit.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=qa.pk,
    ).first()
    assert audit_update is not None

    # 3. Respond
    respond_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[qa.pk])
    resp_resp = client_a.post(
        respond_url,
        {
            "status": "approved",
            "answer_text": "Yes, water resistant up to 50 meters.",
            "answered_by_name": "Staff Support",
            "is_staff_answer": True,
            "is_pinned": True,
        },
    )
    assert resp_resp.status_code == 302
    audit_respond = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="respond",
        object_id=qa.pk,
    ).first()
    assert audit_respond is not None
    assert audit_respond.changes.get("status") == "approved"

    # 4. Delete
    qa_num = qa.number
    del_url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[qa.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    audit_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=qa_num,
    ).first()
    assert audit_del is not None


def test_reviewugc_visualugcmedia_auditlog_recorded(client_a, tenant_a, ecom_product_a, admin_user):
    """VisualUgcMedia mutations (create, update, delete) write AuditLog rows."""
    # 1. Create
    create_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"])
    resp_create = client_a.post(
        create_url,
        {
            "media_type": "photo",
            "media_url": "https://example.com/asset.jpg",
            "thumbnail_url": "https://example.com/asset-thumb.jpg",
            "caption": "Photo for audit test",
            "uploader_name": "Audit Uploader",
            "tagged_product": ecom_product_a.pk,
            "rights_status": "approved",
            "display_order": 5,
        },
    )
    assert resp_create.status_code == 302
    ugc = VisualUgcMedia.objects.filter(tenant=tenant_a, uploader_name="Audit Uploader").first()
    assert ugc is not None

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=ugc.pk,
    ).first()
    assert audit_create is not None

    # 2. Update / Edit
    edit_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ugc.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "media_type": "photo",
            "media_url": "https://example.com/asset.jpg",
            "thumbnail_url": "https://example.com/asset-thumb.jpg",
            "caption": "Photo for audit test - Approved",
            "uploader_name": "Audit Uploader",
            "tagged_product": ecom_product_a.pk,
            "rights_status": "approved",
            "is_published": True,
            "display_order": 5,
        },
    )
    assert resp_edit.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=ugc.pk,
    ).first()
    assert audit_update is not None
    assert audit_update.changes.get("rights_status") == "approved"

    # 3. Delete
    ugc_num = ugc.number
    del_url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ugc.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    audit_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=ugc_num,
    ).first()
    assert audit_del is not None


def test_reviewugc_reviewsentimentsummary_auditlog_recorded(client_a, tenant_a, admin_user):
    """ReviewSentimentSummary mutations (create, update, recalculate, delete) write AuditLog rows."""
    isolated_product = _reviewugc_create_product(tenant_a, name="Scorecard Audit Product", slug_suffix="scorecard")

    # 1. Create
    create_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"])
    resp_create = client_a.post(
        create_url,
        {
            "product": isolated_product.pk,
            "improvement_recommendation": "Initial recommendations.",
        },
    )
    assert resp_create.status_code == 302
    summary = ReviewSentimentSummary.objects.filter(tenant=tenant_a, product=isolated_product).first()
    assert summary is not None

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=summary.pk,
    ).first()
    assert audit_create is not None

    # 2. Update / Edit
    edit_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[summary.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "product": isolated_product.pk,
            "improvement_recommendation": "Enhanced quality guidance and testing.",
        },
    )
    assert resp_edit.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=summary.pk,
    ).first()
    assert audit_update is not None

    # 3. Recalculate
    recalc_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[summary.pk])
    resp_recalc = client_a.post(recalc_url)
    assert resp_recalc.status_code == 302
    audit_recalc = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="recalc",
        object_id=summary.pk,
    ).first()
    assert audit_recalc is not None
    assert audit_recalc.changes.get("action") == "recalculate"

    # 4. Delete
    summary_num = summary.number
    del_url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[summary.pk])
    resp_del = client_a.post(del_url)
    assert resp_del.status_code == 302
    audit_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=summary_num,
    ).first()
    assert audit_del is not None


def test_reviewugc_auditlog_tenant_isolation(client_a, tenant_a, tenant_b, ecom_product_a):
    """Mutating actions performed in Tenant A never contaminate Tenant B audit records."""
    initial_tenant_b_count = AuditLog.objects.filter(tenant=tenant_b).count()

    # Perform create and edit in Tenant A
    create_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"])
    client_a.post(
        create_url,
        {
            "product": ecom_product_a.pk,
            "rating": 5,
            "title": "Tenant Isolation Review",
            "body": "Checking cross tenant audit separation.",
            "reviewer_name": "Audit Isolator",
            "reviewer_email": "isolator@example.com",
        },
    )

    review = ProductReview.objects.filter(tenant=tenant_a, title="Tenant Isolation Review").first()
    assert review is not None

    edit_url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[review.pk])
    client_a.post(
        edit_url,
        {
            "product": ecom_product_a.pk,
            "rating": 5,
            "title": "Tenant Isolation Review Edited",
            "body": "Checking cross tenant audit separation.",
            "reviewer_name": "Audit Isolator",
            "reviewer_email": "isolator@example.com",
        },
    )

    # Verify all new audit logs are scoped strictly to tenant_a
    new_tenant_b_count = AuditLog.objects.filter(tenant=tenant_b).count()
    assert new_tenant_b_count == initial_tenant_b_count, "AuditLog for Tenant B must not increase during Tenant A actions"

    tenant_a_logs = AuditLog.objects.filter(tenant=tenant_a, object_id=review.pk)
    assert tenant_a_logs.count() >= 2
    for log in tenant_a_logs:
        assert log.tenant == tenant_a
