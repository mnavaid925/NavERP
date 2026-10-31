"""Unit, route, filter, and CRUD view tests for eCommerce 9.13 Reviews & User-Generated Content.

Covers:
1. ProductReview Views:
   - list with search, filters (status, rating, sentiment, product), and pagination
   - detail with context contract and IDOR rejection
   - create GET and POST with AuditLog (action="create")
   - edit GET and POST with AuditLog (action="update")
   - delete POST-only gating (405 on GET) with AuditLog (action="delete")
   - moderate GET and POST with pre-selection, timestamping, user attribution, and AuditLog (action="moderate")
2. ProductQuestionAnswer Views:
   - list with search, filters (status, product), and pagination
   - detail with context contract and IDOR rejection
   - create GET and POST with AuditLog (action="create")
   - edit GET and POST with AuditLog (action="update")
   - delete POST-only gating (405 on GET) with AuditLog (action="delete")
   - respond GET (with pre-selection) and POST (staff response attribution, answered_at, AuditLog action="respond")
3. VisualUgcMedia Views:
   - list with search, filters (media_type, rights_status, product), and pagination
   - detail with context contract and IDOR rejection
   - create GET and POST with AuditLog (action="create")
   - edit GET and POST with AuditLog (action="update")
   - delete POST-only gating (405 on GET) with AuditLog (action="delete")
4. ReviewSentimentSummary Views:
   - list with search, product filter, and pagination
   - detail with context contract, approved reviews scoping, and IDOR rejection
   - create GET and POST with summary.recalculate() and AuditLog (action="create")
   - edit GET and POST with AuditLog (action="update")
   - delete POST-only gating (405 on GET) with AuditLog (action="delete")
   - recalculate POST-only action invoking recalculate() and AuditLog (action="recalc")
5. Security & Access Control:
   - Unauthenticated redirect gating
   - Non-admin member 403 Forbidden gating on tenant_admin_required views

Naming conventions enforced:
- Test functions: test_reviewugc_*
- Module-level helpers: _reviewugc_*
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    CatalogProduct,
    ProductQuestionAnswer,
    ProductReview,
    ProductVariant,
    ReviewSentimentSummary,
    VisualUgcMedia,
)
from apps.ecommerce.tests.conftest import (
    REVIEWUGC_CONTEXT_KEYS,
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

def _reviewugc_create_product(tenant, name="Extra View Product", slug_suffix="extra"):
    """Helper to create a catalog product for tenant testing."""
    return CatalogProduct.objects.create(
        tenant=tenant,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{slug_suffix}-{tenant.slug}",
        status="active",
    )


def _reviewugc_create_variant(tenant, product, sku="SKU-UGC-VIEW", name="View Variant"):
    """Helper to create a product variant for view testing."""
    return ProductVariant.objects.create(
        tenant=tenant,
        product=product,
        sku=f"{sku}-{tenant.slug}",
        name=name,
    )


# ==============================================================================
# 1. ProductReview Views
# ==============================================================================

def test_reviewugc_productreview_list_view_and_context_keys(
    client_a, tenant_a, tenant_b, ecom_product_a, ecom_product_b, ecom_reviewugc_review_a, ecom_reviewugc_review_b
):
    """ProductReview list returns 200, enforces tenant isolation, and passes context contract."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"])
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context contract keys
    assert "reviews" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "rating_choices" in resp.context
    assert "sentiment_choices" in resp.context
    assert "products" in resp.context
    assert "selected_status" in resp.context
    assert "selected_rating" in resp.context
    assert "selected_sentiment" in resp.context
    assert "selected_product" in resp.context
    assert "query" in resp.context

    # Tenant scoping: tenant_a sees own review, not tenant_b
    review_ids = [r.pk for r in resp.context["reviews"]]
    assert ecom_reviewugc_review_a.pk in review_ids
    assert ecom_reviewugc_review_b.pk not in review_ids


def test_reviewugc_productreview_list_filters_and_search(
    client_a, tenant_a, ecom_product_a
):
    """ProductReview list filters by search query, status, rating, sentiment, and product."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"])
    p2 = _reviewugc_create_product(tenant_a, name="Secondary Review Item", slug_suffix="p2")

    r1 = _reviewugc_product_review(
        tenant_a,
        ecom_product_a,
        title="Unbelievable Quality",
        body="Fabric feels truly premium",
        reviewer_name="Alice Wonder",
        status="approved",
        rating=5,
        sentiment="positive",
    )
    r2 = _reviewugc_product_review(
        tenant_a,
        p2,
        title="Subpar Craftsmanship",
        body="Stitching tore after two days",
        reviewer_name="Bob Builder",
        status="rejected",
        rating=2,
        sentiment="negative",
    )
    r3 = _reviewugc_product_review(
        tenant_a,
        ecom_product_a,
        title="Average Experience",
        body="Standard everyday item",
        reviewer_name="Charlie Chaplin",
        status="pending",
        rating=3,
        sentiment="neutral",
    )

    # 1. Search query by title
    resp_q1 = client_a.get(url, {"q": "Unbelievable"})
    assert resp_q1.status_code == 200
    pks_q1 = [r.pk for r in resp_q1.context["reviews"]]
    assert r1.pk in pks_q1
    assert r2.pk not in pks_q1

    # 2. Search query by reviewer name
    resp_q2 = client_a.get(url, {"q": "Bob Builder"})
    assert resp_q2.status_code == 200
    pks_q2 = [r.pk for r in resp_q2.context["reviews"]]
    assert r2.pk in pks_q2
    assert r1.pk not in pks_q2

    # 3. Filter by status
    resp_stat = client_a.get(url, {"status": "rejected"})
    assert resp_stat.status_code == 200
    pks_stat = [r.pk for r in resp_stat.context["reviews"]]
    assert r2.pk in pks_stat
    assert r1.pk not in pks_stat

    # 4. Filter by rating
    resp_rate = client_a.get(url, {"rating": "5"})
    assert resp_rate.status_code == 200
    pks_rate = [r.pk for r in resp_rate.context["reviews"]]
    assert r1.pk in pks_rate
    assert r2.pk not in pks_rate

    # 5. Filter by sentiment
    resp_sent = client_a.get(url, {"sentiment": "neutral"})
    assert resp_sent.status_code == 200
    pks_sent = [r.pk for r in resp_sent.context["reviews"]]
    assert r3.pk in pks_sent
    assert r1.pk not in pks_sent

    # 6. Filter by product
    resp_prod = client_a.get(url, {"product": str(p2.pk)})
    assert resp_prod.status_code == 200
    pks_prod = [r.pk for r in resp_prod.context["reviews"]]
    assert r2.pk in pks_prod
    assert r1.pk not in pks_prod


def test_reviewugc_productreview_list_pagination(client_a, tenant_a, ecom_product_a):
    """ProductReview list paginates at 15 items per page."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"])
    for i in range(16):
        _reviewugc_product_review(
            tenant_a,
            ecom_product_a,
            title=f"Review Page Test #{i}",
            reviewer_email=f"reviewer{i}@example.com",
        )

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["reviews"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["reviews"]) >= 1


def test_reviewugc_productreview_detail_view_and_context_keys(
    client_a, tenant_a, ecom_reviewugc_review_a
):
    """ProductReview detail returns 200 and matches REVIEWUGC_CONTEXT_KEYS contract."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200

    for key in REVIEWUGC_CONTEXT_KEYS["ProductReview"]["detail"]:
        assert key in resp.context
    assert resp.context["review"] == ecom_reviewugc_review_a


def test_reviewugc_productreview_detail_idor_and_404(
    client_a, client_b, ecom_reviewugc_review_a
):
    """Foreign tenant B cannot access tenant A review (IDOR protection -> 404)."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk])
    resp_b = client_b.get(url)
    assert resp_b.status_code == 404

    # Non-existent review
    url_404 = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[999999])
    resp_404 = client_a.get(url_404)
    assert resp_404.status_code == 404


def test_reviewugc_productreview_create_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductReview create view supports GET (form) and POST (creation + AuditLog)."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductReview"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["review"] is None

    # POST valid review
    data = {
        "product": ecom_product_a.pk,
        "reviewer_name": "Diana Prince",
        "reviewer_email": "diana@themyscira.gov",
        "rating": 5,
        "title": "Outstanding craftsmanship",
        "body": "Every detail matches the promised specifications.",
        "is_featured": True,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created_review = ProductReview.objects.filter(
        tenant=tenant_a, reviewer_email="diana@themyscira.gov"
    ).first()
    assert created_review is not None
    assert created_review.number.startswith("EPRV-")
    assert created_review.rating == 5
    assert created_review.is_featured is True

    # AuditLog entry verification
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created_review.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == created_review.number


def test_reviewugc_productreview_create_invalid(client_a, tenant_a):
    """ProductReview create with invalid data re-renders form with 200 and errors."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"])
    # Missing required reviewer_name, reviewer_email, title, body, product
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].is_valid() is False
    assert "product" in resp.context["form"].errors


def test_reviewugc_productreview_edit_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a, ecom_reviewugc_review_a
):
    """ProductReview edit view supports GET and POST with AuditLog (action='update')."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[ecom_reviewugc_review_a.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductReview"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["review"] == ecom_reviewugc_review_a

    # POST update
    data = {
        "product": ecom_product_a.pk,
        "reviewer_name": "Updated Reviewer Name",
        "reviewer_email": ecom_reviewugc_review_a.reviewer_email,
        "rating": 4,
        "title": "Updated Headline Review",
        "body": "Updated detailed critique body.",
        "is_featured": False,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk])

    ecom_reviewugc_review_a.refresh_from_db()
    assert ecom_reviewugc_review_a.reviewer_name == "Updated Reviewer Name"
    assert ecom_reviewugc_review_a.rating == 4

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_reviewugc_review_a.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


def test_reviewugc_productreview_edit_idor_404(client_b, ecom_reviewugc_review_a):
    """Foreign tenant B cannot edit tenant A review."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[ecom_reviewugc_review_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_reviewugc_productreview_delete_view_post_only(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductReview delete requires POST (GET returns 405) and logs AuditLog."""
    review = _reviewugc_product_review(tenant_a, ecom_product_a)
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[review.pk])

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    review_pk = review.pk
    review_number = review.number
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"])
    assert not ProductReview.objects.filter(pk=review_pk).exists()

    # AuditLog
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).order_by("-id").first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == review_number


def test_reviewugc_productreview_moderate_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductReview moderate view sets status, merchant_response, attribution, and AuditLog."""
    review = _reviewugc_product_review(
        tenant_a, ecom_product_a, status="pending", merchant_response=""
    )
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[review.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductReview"]["moderate"]:
        assert key in resp_get.context
    assert resp_get.context["is_moderation"] is True

    # POST moderation decision
    data = {
        "status": "approved",
        "sentiment": "positive",
        "is_featured": True,
        "merchant_response": "Thank you for the warm feedback! We love hearing this.",
        "moderation_note": "Verified genuine customer feedback.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[review.pk])

    review.refresh_from_db()
    assert review.status == "approved"
    assert review.moderated_by == admin_user
    assert review.merchant_response_at is not None
    assert review.is_featured is True

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="moderate",
        object_id=str(review.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("status") == "approved"


def test_reviewugc_productreview_moderate_clear_merchant_response(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductReview moderate clears merchant_response_at when merchant response is emptied."""
    review = _reviewugc_product_review(
        tenant_a,
        ecom_product_a,
        status="approved",
        merchant_response="Existing response",
        merchant_response_at=timezone.now(),
    )
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[review.pk])
    data = {
        "status": "approved",
        "sentiment": "positive",
        "is_featured": False,
        "merchant_response": "",
        "moderation_note": "Removed outdated response.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302

    review.refresh_from_db()
    assert review.merchant_response == ""
    assert review.merchant_response_at is None


def test_reviewugc_productreview_moderate_idor_404(client_b, ecom_reviewugc_review_a):
    """Foreign tenant B cannot moderate tenant A review."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


# ==============================================================================
# 2. ProductQuestionAnswer Views
# ==============================================================================

def test_reviewugc_productquestionanswer_list_view_and_context_keys(
    client_a, tenant_a, tenant_b, ecom_reviewugc_qa_a, ecom_reviewugc_qa_b
):
    """ProductQuestionAnswer list returns 200, enforces isolation, and passes context keys."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"])
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context contract keys
    assert "questions" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "status_choices" in resp.context
    assert "products" in resp.context
    assert "selected_status" in resp.context
    assert "selected_product" in resp.context
    assert "query" in resp.context

    # Tenant scoping
    q_pks = [q.pk for q in resp.context["questions"]]
    assert ecom_reviewugc_qa_a.pk in q_pks
    assert ecom_reviewugc_qa_b.pk not in q_pks


def test_reviewugc_productquestionanswer_list_filters_and_search(
    client_a, tenant_a, ecom_product_a
):
    """ProductQuestionAnswer list filters by search query, status, and product."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"])
    p2 = _reviewugc_create_product(tenant_a, name="Gadget Device", slug_suffix="p2")

    q1 = _reviewugc_question_answer(
        tenant_a,
        ecom_product_a,
        question_text="Does this include a wireless charger?",
        author_name="Fiona Gallagher",
        status="approved",
    )
    q2 = _reviewugc_question_answer(
        tenant_a,
        p2,
        question_text="Is the firmware open-source?",
        author_name="George Costanza",
        status="pending",
    )

    # 1. Search by question text
    resp_q1 = client_a.get(url, {"q": "wireless charger"})
    assert resp_q1.status_code == 200
    pks_q1 = [q.pk for q in resp_q1.context["questions"]]
    assert q1.pk in pks_q1
    assert q2.pk not in pks_q1

    # 2. Search by author name
    resp_q2 = client_a.get(url, {"q": "Gallagher"})
    assert resp_q2.status_code == 200
    pks_q2 = [q.pk for q in resp_q2.context["questions"]]
    assert q1.pk in pks_q2
    assert q2.pk not in pks_q2

    # 3. Filter by status
    resp_stat = client_a.get(url, {"status": "pending"})
    assert resp_stat.status_code == 200
    pks_stat = [q.pk for q in resp_stat.context["questions"]]
    assert q2.pk in pks_stat
    assert q1.pk not in pks_stat

    # 4. Filter by product
    resp_prod = client_a.get(url, {"product": str(p2.pk)})
    assert resp_prod.status_code == 200
    pks_prod = [q.pk for q in resp_prod.context["questions"]]
    assert q2.pk in pks_prod
    assert q1.pk not in pks_prod


def test_reviewugc_productquestionanswer_list_pagination(client_a, tenant_a, ecom_product_a):
    """ProductQuestionAnswer list paginates at 15 questions per page."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"])
    for i in range(16):
        _reviewugc_question_answer(
            tenant_a,
            ecom_product_a,
            question_text=f"Question pagination item {i}?",
            author_email=f"inquirer{i}@example.com",
        )

    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["questions"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True


def test_reviewugc_productquestionanswer_detail_view_and_context_keys(
    client_a, tenant_a, ecom_reviewugc_qa_a
):
    """ProductQuestionAnswer detail returns 200 and passes REVIEWUGC_CONTEXT_KEYS contract."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200

    for key in REVIEWUGC_CONTEXT_KEYS["ProductQuestionAnswer"]["detail"]:
        assert key in resp.context
    assert resp.context["question"] == ecom_reviewugc_qa_a


def test_reviewugc_productquestionanswer_detail_idor_and_404(
    client_a, client_b, ecom_reviewugc_qa_a
):
    """Foreign tenant B cannot access tenant A question (IDOR -> 404)."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk])
    resp_b = client_b.get(url)
    assert resp_b.status_code == 404

    # Non-existent ID
    resp_404 = client_a.get(reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[999999]))
    assert resp_404.status_code == 404


def test_reviewugc_productquestionanswer_create_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductQuestionAnswer create view supports GET and POST (creating question with AuditLog)."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductQuestionAnswer"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["question"] is None

    # POST valid question
    data = {
        "product": ecom_product_a.pk,
        "author_name": "Hannah Abbott",
        "author_email": "hannah@hogwarts.ac.uk",
        "question_text": "Is this model compatible with 220V international sockets?",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created_q = ProductQuestionAnswer.objects.filter(
        tenant=tenant_a, author_email="hannah@hogwarts.ac.uk"
    ).first()
    assert created_q is not None
    assert created_q.number.startswith("EPQA-")
    assert created_q.status == "pending"

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created_q.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == created_q.number


def test_reviewugc_productquestionanswer_create_invalid(client_a, tenant_a):
    """ProductQuestionAnswer create with empty fields returns form errors."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"])
    resp = client_a.post(url, {})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].is_valid() is False


def test_reviewugc_productquestionanswer_edit_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a, ecom_reviewugc_qa_a
):
    """ProductQuestionAnswer edit view supports GET and POST with AuditLog (action='update')."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[ecom_reviewugc_qa_a.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductQuestionAnswer"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["question"] == ecom_reviewugc_qa_a

    # POST update
    data = {
        "product": ecom_product_a.pk,
        "author_name": "Updated Question Author",
        "author_email": ecom_reviewugc_qa_a.author_email,
        "question_text": "Updated refined question prompt?",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk])

    ecom_reviewugc_qa_a.refresh_from_db()
    assert ecom_reviewugc_qa_a.author_name == "Updated Question Author"

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_reviewugc_qa_a.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


def test_reviewugc_productquestionanswer_edit_idor_404(client_b, ecom_reviewugc_qa_a):
    """Foreign tenant B cannot edit tenant A question."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["edit"], args=[ecom_reviewugc_qa_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_reviewugc_productquestionanswer_delete_view_post_only(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductQuestionAnswer delete requires POST (GET returns 405) and logs AuditLog."""
    qa = _reviewugc_question_answer(tenant_a, ecom_product_a)
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[qa.pk])

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    qa_pk = qa.pk
    qa_num = qa.number
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"])
    assert not ProductQuestionAnswer.objects.filter(pk=qa_pk).exists()

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).order_by("-id").first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == qa_num


def test_reviewugc_productquestionanswer_respond_view_get_preselection(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductQuestionAnswer respond GET provides pre-selection (approved status, agent name, staff flag)."""
    qa = _reviewugc_question_answer(
        tenant_a, ecom_product_a, status="pending", answer_text="", answered_by_name=""
    )
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[qa.pk])

    resp = client_a.get(url)
    assert resp.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ProductQuestionAnswer"]["respond"]:
        assert key in resp.context
    assert resp.context["is_response"] is True

    form = resp.context["form"]
    # Pre-selection rules check
    assert form.initial.get("status") == "approved"
    assert form.initial.get("is_staff_answer") is True
    assert form.initial.get("answered_by_name") in (admin_user.get_full_name(), admin_user.username)


def test_reviewugc_productquestionanswer_respond_view_post_staff_answer(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """ProductQuestionAnswer respond POST saves answer, sets answered_by_user, answered_at, and logs AuditLog."""
    qa = _reviewugc_question_answer(
        tenant_a, ecom_product_a, status="pending", answer_text="", answered_by_name=""
    )
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[qa.pk])

    data = {
        "status": "approved",
        "answer_text": "Yes, it is completely compatible with 110V to 240V international power inputs.",
        "answered_by_name": "Acme Tech Support Team",
        "is_staff_answer": True,
        "is_pinned": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    assert resp.url == reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[qa.pk])

    qa.refresh_from_db()
    assert qa.status == "approved"
    assert qa.answered_by_user == admin_user
    assert qa.answered_at is not None
    assert qa.answered_by_name == "Acme Tech Support Team"
    assert qa.is_staff_answer is True
    assert qa.is_pinned is True

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="respond",
        object_id=str(qa.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("status") == "approved"


def test_reviewugc_productquestionanswer_respond_idor_404(client_b, ecom_reviewugc_qa_a):
    """Foreign tenant B cannot respond to tenant A question."""
    url = reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


# ==============================================================================
# 3. VisualUgcMedia Views
# ==============================================================================

def test_reviewugc_visualugcmedia_list_view_and_context_keys(
    client_a, tenant_a, tenant_b, ecom_reviewugc_ugc_a, ecom_reviewugc_ugc_b
):
    """VisualUgcMedia list returns 200, enforces isolation, and passes context keys."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"])
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context contract keys
    assert "media_items" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "media_type_choices" in resp.context
    assert "rights_status_choices" in resp.context
    assert "products" in resp.context
    assert "selected_media_type" in resp.context
    assert "selected_rights" in resp.context
    assert "selected_product" in resp.context
    assert "query" in resp.context

    # Tenant scoping
    item_pks = [m.pk for m in resp.context["media_items"]]
    assert ecom_reviewugc_ugc_a.pk in item_pks
    assert ecom_reviewugc_ugc_b.pk not in item_pks


def test_reviewugc_visualugcmedia_list_filters_and_search(
    client_a, tenant_a, ecom_product_a
):
    """VisualUgcMedia list filters by search query, media_type, rights_status, and product."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"])
    p2 = _reviewugc_create_product(tenant_a, name="Apparel Jacket", slug_suffix="p2")

    m1 = _reviewugc_visual_ugc(
        tenant_a,
        ecom_product_a,
        caption="Stunning setup on my desk!",
        uploader_name="Ingrid Bergman",
        uploader_handle="@ingrid_designs",
        media_type="photo",
        rights_status="approved",
    )
    m2 = _reviewugc_visual_ugc(
        tenant_a,
        p2,
        caption="Unboxing video walkthrough",
        uploader_name="Jack Sparrow",
        uploader_handle="@jack_s",
        media_type="video",
        rights_status="pending_request",
    )

    # 1. Search by caption
    resp_q1 = client_a.get(url, {"q": "Stunning setup"})
    assert resp_q1.status_code == 200
    pks_q1 = [m.pk for m in resp_q1.context["media_items"]]
    assert m1.pk in pks_q1
    assert m2.pk not in pks_q1

    # 2. Search by uploader handle
    resp_q2 = client_a.get(url, {"q": "@jack_s"})
    assert resp_q2.status_code == 200
    pks_q2 = [m.pk for m in resp_q2.context["media_items"]]
    assert m2.pk in pks_q2
    assert m1.pk not in pks_q2

    # 3. Filter by media_type
    resp_type = client_a.get(url, {"media_type": "video"})
    assert resp_type.status_code == 200
    pks_type = [m.pk for m in resp_type.context["media_items"]]
    assert m2.pk in pks_type
    assert m1.pk not in pks_type

    # 4. Filter by rights_status
    resp_right = client_a.get(url, {"rights_status": "pending_request"})
    assert resp_right.status_code == 200
    pks_right = [m.pk for m in resp_right.context["media_items"]]
    assert m2.pk in pks_right
    assert m1.pk not in pks_right

    # 5. Filter by product
    resp_prod = client_a.get(url, {"product": str(p2.pk)})
    assert resp_prod.status_code == 200
    pks_prod = [m.pk for m in resp_prod.context["media_items"]]
    assert m2.pk in pks_prod
    assert m1.pk not in pks_prod


def test_reviewugc_visualugcmedia_list_pagination(client_a, tenant_a, ecom_product_a):
    """VisualUgcMedia list paginates at 15 items per page."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"])
    for i in range(16):
        _reviewugc_visual_ugc(
            tenant_a,
            ecom_product_a,
            caption=f"Pagination UGC item {i}",
            uploader_handle=f"@user_{i}",
        )

    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["media_items"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True


def test_reviewugc_visualugcmedia_detail_view_and_context_keys(
    client_a, tenant_a, ecom_reviewugc_ugc_a
):
    """VisualUgcMedia detail returns 200 and passes REVIEWUGC_CONTEXT_KEYS contract."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200

    for key in REVIEWUGC_CONTEXT_KEYS["VisualUgcMedia"]["detail"]:
        assert key in resp.context
    assert resp.context["media_item"] == ecom_reviewugc_ugc_a


def test_reviewugc_visualugcmedia_detail_idor_and_404(
    client_a, client_b, ecom_reviewugc_ugc_a
):
    """Foreign tenant B cannot access tenant A media item (IDOR -> 404)."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk])
    resp_b = client_b.get(url)
    assert resp_b.status_code == 404

    # Non-existent pk
    resp_404 = client_a.get(reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[999999]))
    assert resp_404.status_code == 404


def test_reviewugc_visualugcmedia_create_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """VisualUgcMedia create view supports GET and POST with AuditLog (action='create')."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["VisualUgcMedia"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["media_item"] is None

    # POST valid item
    data = {
        "media_type": "instagram",
        "media_url": "https://images.unsplash.com/photo-1512436991641-6745cdb1723f",
        "thumbnail_url": "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?w=150",
        "caption": "Style inspiration with our new leather boots.",
        "uploader_name": "Karen Page",
        "uploader_handle": "@karen_styles",
        "tagged_product": ecom_product_a.pk,
        "rights_status": "approved",
        "is_shoppable": True,
        "is_published": True,
        "display_order": 5,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created_media = VisualUgcMedia.objects.filter(
        tenant=tenant_a, uploader_handle="@karen_styles"
    ).first()
    assert created_media is not None
    assert created_media.number.startswith("EUGC-")
    assert created_media.media_type == "instagram"

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created_media.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == created_media.number


def test_reviewugc_visualugcmedia_create_invalid(client_a, tenant_a):
    """VisualUgcMedia create with invalid/missing URL returns form errors."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"])
    resp = client_a.post(url, {"media_url": "ftp://bad-scheme.com/pic.jpg"})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].is_valid() is False


def test_reviewugc_visualugcmedia_edit_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_product_a, ecom_reviewugc_ugc_a
):
    """VisualUgcMedia edit view supports GET and POST with AuditLog (action='update')."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ecom_reviewugc_ugc_a.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["VisualUgcMedia"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["media_item"] == ecom_reviewugc_ugc_a

    # POST update
    data = {
        "media_type": ecom_reviewugc_ugc_a.media_type,
        "media_url": ecom_reviewugc_ugc_a.media_url,
        "thumbnail_url": ecom_reviewugc_ugc_a.thumbnail_url,
        "caption": "Updated caption description.",
        "uploader_name": "Updated Uploader",
        "uploader_handle": "@updated_handle",
        "tagged_product": ecom_product_a.pk,
        "rights_status": "approved",
        "is_shoppable": True,
        "is_published": False,
        "display_order": 20,
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk])

    ecom_reviewugc_ugc_a.refresh_from_db()
    assert ecom_reviewugc_ugc_a.caption == "Updated caption description."
    assert ecom_reviewugc_ugc_a.is_published is False

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_reviewugc_ugc_a.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


def test_reviewugc_visualugcmedia_edit_idor_404(client_b, ecom_reviewugc_ugc_a):
    """Foreign tenant B cannot edit tenant A media item."""
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["edit"], args=[ecom_reviewugc_ugc_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_reviewugc_visualugcmedia_delete_view_post_only(
    client_a, tenant_a, admin_user, ecom_product_a
):
    """VisualUgcMedia delete requires POST (GET returns 405) and logs AuditLog."""
    media = _reviewugc_visual_ugc(tenant_a, ecom_product_a)
    url = reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[media.pk])

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    media_pk = media.pk
    media_num = media.number
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"])
    assert not VisualUgcMedia.objects.filter(pk=media_pk).exists()

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).order_by("-id").first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == media_num


# ==============================================================================
# 4. ReviewSentimentSummary Views
# ==============================================================================

def test_reviewugc_reviewsentimentsummary_list_view_and_context_keys(
    client_a, tenant_a, tenant_b, ecom_reviewugc_summary_a, ecom_reviewugc_summary_b
):
    """ReviewSentimentSummary list returns 200, enforces isolation, and passes context keys."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"])
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context contract keys
    assert "summaries" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "products" in resp.context
    assert "selected_product" in resp.context
    assert "query" in resp.context

    # Tenant scoping
    summary_pks = [s.pk for s in resp.context["summaries"]]
    assert ecom_reviewugc_summary_a.pk in summary_pks
    assert ecom_reviewugc_summary_b.pk not in summary_pks


def test_reviewugc_reviewsentimentsummary_list_filters_and_search(
    client_a, tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """ReviewSentimentSummary list filters by query (name, number, recommendation) and product."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"])
    p2 = _reviewugc_create_product(tenant_a, name="Ergonomic Keyboard", slug_suffix="p2")
    s2 = _reviewugc_sentiment_summary(
        tenant_a,
        p2,
        improvement_recommendation="Reinforce wrist-rest magnetic attachment latch.",
    )

    # 1. Search by product name
    resp_q1 = client_a.get(url, {"q": "Ergonomic"})
    assert resp_q1.status_code == 200
    pks_q1 = [s.pk for s in resp_q1.context["summaries"]]
    assert s2.pk in pks_q1
    assert ecom_reviewugc_summary_a.pk not in pks_q1

    # 2. Search by recommendation keyword
    resp_q2 = client_a.get(url, {"q": "magnetic attachment"})
    assert resp_q2.status_code == 200
    pks_q2 = [s.pk for s in resp_q2.context["summaries"]]
    assert s2.pk in pks_q2
    assert ecom_reviewugc_summary_a.pk not in pks_q2

    # 3. Filter by product
    resp_prod = client_a.get(url, {"product": str(p2.pk)})
    assert resp_prod.status_code == 200
    pks_prod = [s.pk for s in resp_prod.context["summaries"]]
    assert s2.pk in pks_prod
    assert ecom_reviewugc_summary_a.pk not in pks_prod


def test_reviewugc_reviewsentimentsummary_list_pagination(client_a, tenant_a):
    """ReviewSentimentSummary list paginates at 15 items per page."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"])
    for i in range(16):
        prod = _reviewugc_create_product(tenant_a, name=f"Scorecard Prod {i}", slug_suffix=f"pg{i}")
        _reviewugc_sentiment_summary(tenant_a, prod)

    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["summaries"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True


def test_reviewugc_reviewsentimentsummary_detail_view_and_context_keys(
    client_a, tenant_a, ecom_reviewugc_summary_a
):
    """ReviewSentimentSummary detail returns 200 and passes REVIEWUGC_CONTEXT_KEYS contract."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200

    for key in REVIEWUGC_CONTEXT_KEYS["ReviewSentimentSummary"]["detail"]:
        assert key in resp.context
    assert resp.context["summary"] == ecom_reviewugc_summary_a
    assert "recent_reviews" in resp.context


def test_reviewugc_reviewsentimentsummary_detail_recent_reviews_filtering(
    client_a, tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """ReviewSentimentSummary detail only displays approved reviews for its product."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk])
    p_other = _reviewugc_create_product(tenant_a, name="Other Brand Item", slug_suffix="other")

    r_approved = _reviewugc_product_review(
        tenant_a, ecom_product_a, status="approved", title="Approved Target Review"
    )
    r_pending = _reviewugc_product_review(
        tenant_a, ecom_product_a, status="pending", title="Pending Hidden Review"
    )
    r_other = _reviewugc_product_review(
        tenant_a, p_other, status="approved", title="Approved Other Product Review"
    )

    resp = client_a.get(url)
    assert resp.status_code == 200
    recent_pks = [r.pk for r in resp.context["recent_reviews"]]
    assert r_approved.pk in recent_pks
    assert r_pending.pk not in recent_pks
    assert r_other.pk not in recent_pks


def test_reviewugc_reviewsentimentsummary_detail_idor_and_404(
    client_a, client_b, ecom_reviewugc_summary_a
):
    """Foreign tenant B cannot access tenant A sentiment summary (IDOR -> 404)."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk])
    resp_b = client_b.get(url)
    assert resp_b.status_code == 404

    # Non-existent pk
    resp_404 = client_a.get(reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[999999]))
    assert resp_404.status_code == 404


def test_reviewugc_reviewsentimentsummary_create_view_get_and_post(
    client_a, tenant_a, admin_user
):
    """ReviewSentimentSummary create supports GET and POST (creating scorecard, calculating, and logging AuditLog)."""
    unsum_product = _reviewugc_create_product(tenant_a, name="New Unsummarized Headset", slug_suffix="headset")
    # Add an approved review to trigger calculate logic
    _reviewugc_product_review(
        tenant_a, unsum_product, rating=5, sentiment="positive", status="approved"
    )

    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ReviewSentimentSummary"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["summary"] is None

    # POST valid scorecard initialization
    data = {
        "product": unsum_product.pk,
        "improvement_recommendation": "Monitor battery performance in hot ambient temperatures.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created_summary = ReviewSentimentSummary.objects.filter(
        tenant=tenant_a, product=unsum_product
    ).first()
    assert created_summary is not None
    assert created_summary.number.startswith("ERVM-")
    assert created_summary.total_reviews == 1
    assert created_summary.average_rating == Decimal("5.00")

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created_summary.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == created_summary.number


def test_reviewugc_reviewsentimentsummary_create_duplicate_product_invalid(
    client_a, tenant_a, ecom_product_a, ecom_reviewugc_summary_a
):
    """ReviewSentimentSummary rejects creating duplicate scorecard for already summarized product."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"])
    data = {
        "product": ecom_product_a.pk,
        "improvement_recommendation": "Duplicate scorecard attempt.",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].is_valid() is False


def test_reviewugc_reviewsentimentsummary_edit_view_get_and_post(
    client_a, tenant_a, admin_user, ecom_reviewugc_summary_a
):
    """ReviewSentimentSummary edit view supports GET and POST with AuditLog (action='update')."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[ecom_reviewugc_summary_a.pk])

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    for key in REVIEWUGC_CONTEXT_KEYS["ReviewSentimentSummary"]["form"]:
        assert key in resp_get.context
    assert resp_get.context["summary"] == ecom_reviewugc_summary_a

    # POST update
    data = {
        "product": ecom_reviewugc_summary_a.product_id,
        "improvement_recommendation": "Updated guidance: Increase packaging bubble wrap protection.",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk])

    ecom_reviewugc_summary_a.refresh_from_db()
    assert "bubble wrap protection" in ecom_reviewugc_summary_a.improvement_recommendation

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_reviewugc_summary_a.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


def test_reviewugc_reviewsentimentsummary_edit_idor_404(client_b, ecom_reviewugc_summary_a):
    """Foreign tenant B cannot edit tenant A sentiment summary."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["edit"], args=[ecom_reviewugc_summary_a.pk])
    resp = client_b.get(url)
    assert resp.status_code == 404


def test_reviewugc_reviewsentimentsummary_delete_view_post_only(
    client_a, tenant_a, admin_user
):
    """ReviewSentimentSummary delete requires POST (GET returns 405) and logs AuditLog."""
    prod = _reviewugc_create_product(tenant_a, name="Delete Scorecard Item", slug_suffix="del")
    summary = _reviewugc_sentiment_summary(tenant_a, prod)
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[summary.pk])

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    summary_pk = summary.pk
    summary_num = summary.number
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"])
    assert not ReviewSentimentSummary.objects.filter(pk=summary_pk).exists()

    # AuditLog entry
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).order_by("-id").first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("number") == summary_num


def test_reviewugc_reviewsentimentsummary_recalculate_view_action(
    client_a, tenant_a, admin_user
):
    """ReviewSentimentSummary recalculate requires POST (GET returns 405), re-computes metrics, and writes AuditLog action='recalc'."""
    prod = _reviewugc_create_product(tenant_a, name="Recalc Target Item", slug_suffix="recalc")
    summary = _reviewugc_sentiment_summary(
        tenant_a, prod, total_reviews=0, average_rating=Decimal("0.00")
    )
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[summary.pk])

    # 1. GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Seed 2 approved reviews
    _reviewugc_product_review(
        tenant_a, prod, rating=5, sentiment="positive", status="approved"
    )
    _reviewugc_product_review(
        tenant_a, prod, rating=3, sentiment="neutral", status="approved"
    )

    # 2. POST triggers recalculation
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[summary.pk])

    summary.refresh_from_db()
    assert summary.total_reviews == 2
    assert summary.average_rating == Decimal("4.00")
    assert summary.rating_5_count == 1
    assert summary.rating_3_count == 1

    # AuditLog entry with action="recalc"
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="recalc",
        object_id=str(summary.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes.get("action") == "recalculate"
    assert audit.changes.get("total_reviews") == 2


def test_reviewugc_reviewsentimentsummary_recalculate_idor_404(
    client_b, ecom_reviewugc_summary_a
):
    """Foreign tenant B cannot recalculate tenant A sentiment scorecard."""
    url = reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[ecom_reviewugc_summary_a.pk])
    resp = client_b.post(url)
    assert resp.status_code == 404


# ==============================================================================
# 5. Security & Access Control
# ==============================================================================

def test_reviewugc_unauthenticated_requests_redirect(
    ecom_reviewugc_review_a, ecom_reviewugc_qa_a, ecom_reviewugc_ugc_a, ecom_reviewugc_summary_a
):
    """Unauthenticated requests to all ReviewUgc views redirect to login."""
    anon = Client()
    routes = [
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["detail"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["edit"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["detail"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["detail"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["list"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["create"]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["detail"], args=[ecom_reviewugc_summary_a.pk]),
    ]
    for url in routes:
        resp = anon.get(url)
        assert resp.status_code == 302
        assert "/login/" in resp.url


def test_reviewugc_non_admin_member_forbidden_on_privileged_actions(
    member_client, ecom_reviewugc_review_a, ecom_reviewugc_qa_a, ecom_reviewugc_ugc_a, ecom_reviewugc_summary_a
):
    """Non-tenant-admin member is forbidden (403) from privileged delete, moderate, respond, and recalculate views."""
    privileged_posts = [
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["delete"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductReview"]["moderate"], args=[ecom_reviewugc_review_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["delete"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ProductQuestionAnswer"]["respond"], args=[ecom_reviewugc_qa_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["VisualUgcMedia"]["delete"], args=[ecom_reviewugc_ugc_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["delete"], args=[ecom_reviewugc_summary_a.pk]),
        reverse(REVIEWUGC_URL_NAMES["ReviewSentimentSummary"]["recalculate"], args=[ecom_reviewugc_summary_a.pk]),
    ]
    for url in privileged_posts:
        resp = member_client.post(url, {})
        assert resp.status_code == 403
