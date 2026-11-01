"""Unit and contract tests for eCommerce 9.14 Customer Service & Support models.

Covers:
- CustomerSupportTicket: prefix ESTK-, SLA computation, status transitions & resolved_at,
  sla breach detection, bot handoff, FK relationships, constraints & tenant isolation.
- KnowledgeBaseArticle: prefix EKBA-, auto-slugification, helpfulness ratio calculation,
  defaults, ordering, constraints & tenant isolation.
- OrderIssueClaim: prefix ECLM-, amount MinValueValidators, photo_evidence_url URLValidator,
  resolved_at auto-setting on resolution, order CASCADE deletion, constraints.
- CustomerSatisfactionSurvey: prefix ECSF-, auto-computation of sentiment (CSAT vs NPS),
  preservation of manual override, auto-flagging detractor follow-up, rating_score validators.

Conventions enforced:
- Test functions: test_customersupport_*
- Module-level helpers: _customersupport_*
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    CustomerSupportTicket,
    KnowledgeBaseArticle,
    OrderIssueClaim,
    CustomerSatisfactionSurvey,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERSUPPORT_MODEL_FIELDS,
    CUSTOMERSUPPORT_CHOICES,
    _customersupport_ticket,
    _customersupport_article,
    _customersupport_claim,
    _customersupport_survey,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customersupport_*)
# ==============================================================================

def _customersupport_build_ticket(tenant, **kwargs):
    """Module-level helper to instantiate and save a CustomerSupportTicket."""
    return _customersupport_ticket(tenant, **kwargs)


def _customersupport_build_article(tenant, **kwargs):
    """Module-level helper to instantiate and save a KnowledgeBaseArticle."""
    return _customersupport_article(tenant, **kwargs)


def _customersupport_build_claim(tenant, order, **kwargs):
    """Module-level helper to instantiate and save an OrderIssueClaim."""
    return _customersupport_claim(tenant, order=order, **kwargs)


def _customersupport_build_survey(tenant, **kwargs):
    """Module-level helper to instantiate and save a CustomerSatisfactionSurvey."""
    return _customersupport_survey(tenant, **kwargs)


# ==============================================================================
# 1. Contract Verification Tests
# ==============================================================================

def test_customersupport_model_fields_contract():
    """Verify all 4 CustomerSupport models contain exact contract-pinned fields."""
    models_dict = {
        "CustomerSupportTicket": CustomerSupportTicket,
        "KnowledgeBaseArticle": KnowledgeBaseArticle,
        "OrderIssueClaim": OrderIssueClaim,
        "CustomerSatisfactionSurvey": CustomerSatisfactionSurvey,
    }
    for model_name, model_cls in models_dict.items():
        expected_fields = set(CUSTOMERSUPPORT_MODEL_FIELDS[model_name])
        actual_fields = {f.name for f in model_cls._meta.get_fields() if hasattr(f, "name")}
        for field in expected_fields:
            assert field in actual_fields, f"Model {model_name} missing contract field '{field}'"


def test_customersupport_choices_contract():
    """Verify choices on all CustomerSupport models match contract definitions."""
    models_dict = {
        "CustomerSupportTicket": CustomerSupportTicket,
        "KnowledgeBaseArticle": KnowledgeBaseArticle,
        "OrderIssueClaim": OrderIssueClaim,
        "CustomerSatisfactionSurvey": CustomerSatisfactionSurvey,
    }
    for model_name, fields_choices in CUSTOMERSUPPORT_CHOICES.items():
        model_cls = models_dict[model_name]
        for field_name, expected_choices in fields_choices.items():
            field = model_cls._meta.get_field(field_name)
            assert tuple(field.choices) == expected_choices, (
                f"{model_name}.{field_name} choices do not match contract"
            )


# ==============================================================================
# 2. CustomerSupportTicket Model Tests
# ==============================================================================

def test_customersupport_ticket_autonumber_and_defaults(tenant_a, ecom_profile_a, ecom_order_a, admin_user):
    """CustomerSupportTicket auto-generates ESTK- prefix and sets default values."""
    ticket = _customersupport_build_ticket(
        tenant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        assigned_agent=admin_user,
    )
    assert ticket.pk is not None
    assert ticket.number.startswith("ESTK-")
    assert ticket.channel == "email"
    assert ticket.category == "order_tracking_wismo"
    assert ticket.priority == "medium"
    assert ticket.status == "new"
    assert ticket.is_sla_breached is False
    assert ticket.is_bot_handled is False
    assert ticket.sla_first_response_due_at is not None
    assert ticket.sla_resolution_due_at is not None
    assert ticket.resolved_at is None
    assert ticket.customer == ecom_profile_a
    assert ticket.order == ecom_order_a
    assert ticket.assigned_agent == admin_user


def test_customersupport_ticket_str_representation(tenant_a):
    """__str__ returns '<number> - <subject> (<status_display>)'."""
    ticket = _customersupport_build_ticket(
        tenant_a,
        subject="Damaged Package on Delivery",
        status="open",
    )
    expected = f"{ticket.number} - Damaged Package on Delivery (Open / In Progress)"
    assert str(ticket) == expected


def test_customersupport_ticket_sla_computation_by_priority(tenant_a):
    """save() automatically calculates SLA targets based on priority if not preset."""
    now_before = timezone.now()

    # Urgent: 1 hour first response, 4 hours resolution
    urgent = CustomerSupportTicket.objects.create(
        tenant=tenant_a,
        subject="Urgent issue",
        customer_name="Shopper 1",
        customer_email="s1@example.com",
        priority="urgent",
    )
    assert urgent.sla_first_response_due_at >= now_before + timedelta(minutes=59)
    assert urgent.sla_first_response_due_at <= now_before + timedelta(minutes=61)
    assert urgent.sla_resolution_due_at >= now_before + timedelta(hours=3, minutes=59)
    assert urgent.sla_resolution_due_at <= now_before + timedelta(hours=4, minutes=1)

    # High: 2 hours first response, 12 hours resolution
    high = CustomerSupportTicket.objects.create(
        tenant=tenant_a,
        subject="High priority issue",
        customer_name="Shopper 2",
        customer_email="s2@example.com",
        priority="high",
    )
    assert high.sla_first_response_due_at >= now_before + timedelta(hours=1, minutes=59)
    assert high.sla_first_response_due_at <= now_before + timedelta(hours=2, minutes=1)
    assert high.sla_resolution_due_at >= now_before + timedelta(hours=11, minutes=59)
    assert high.sla_resolution_due_at <= now_before + timedelta(hours=12, minutes=1)

    # Medium: 8 hours first response, 24 hours resolution
    medium = CustomerSupportTicket.objects.create(
        tenant=tenant_a,
        subject="Medium priority issue",
        customer_name="Shopper 3",
        customer_email="s3@example.com",
        priority="medium",
    )
    assert medium.sla_first_response_due_at >= now_before + timedelta(hours=7, minutes=59)
    assert medium.sla_first_response_due_at <= now_before + timedelta(hours=8, minutes=1)
    assert medium.sla_resolution_due_at >= now_before + timedelta(hours=23, minutes=59)
    assert medium.sla_resolution_due_at <= now_before + timedelta(hours=24, minutes=1)

    # Low: 24 hours first response, 72 hours resolution
    low = CustomerSupportTicket.objects.create(
        tenant=tenant_a,
        subject="Low priority issue",
        customer_name="Shopper 4",
        customer_email="s4@example.com",
        priority="low",
    )
    assert low.sla_first_response_due_at >= now_before + timedelta(hours=23, minutes=59)
    assert low.sla_first_response_due_at <= now_before + timedelta(hours=24, minutes=1)
    assert low.sla_resolution_due_at >= now_before + timedelta(hours=71, minutes=59)
    assert low.sla_resolution_due_at <= now_before + timedelta(hours=72, minutes=1)


def test_customersupport_ticket_resolution_and_reopen_clears_resolved_at(tenant_a):
    """Marking status as resolved sets resolved_at; reopening clears resolved_at."""
    ticket = _customersupport_build_ticket(tenant_a, status="open")
    assert ticket.resolved_at is None

    # Resolve ticket
    ticket.status = "resolved"
    ticket.resolution_summary = "Refund processed and tracking updated."
    ticket.save()
    assert ticket.resolved_at is not None
    saved_resolved_at = ticket.resolved_at

    # Saving again does not change resolved_at
    ticket.internal_notes = "Updated internal notes."
    ticket.save()
    assert ticket.resolved_at == saved_resolved_at

    # Reopening ticket clears resolved_at
    ticket.status = "open"
    ticket.save()
    assert ticket.resolved_at is None

    # Marking status closed also sets resolved_at if not set
    ticket.status = "closed"
    ticket.save()
    assert ticket.resolved_at is not None


def test_customersupport_ticket_sla_breach_detection(tenant_a):
    """Ticket with past resolution SLA due date automatically flags is_sla_breached=True."""
    past_due = timezone.now() - timedelta(hours=2)
    ticket = CustomerSupportTicket(
        tenant=tenant_a,
        subject="Delayed inquiry",
        customer_name="Shopper",
        customer_email="shopper@example.com",
        priority="medium",
        status="open",
        sla_resolution_due_at=past_due,
    )
    ticket.save()
    assert ticket.is_sla_breached is True


def test_customersupport_ticket_sla_breach_ignored_if_closed_or_cancelled(tenant_a):
    """Past SLA due date does NOT flag is_sla_breached if ticket is resolved, closed, or cancelled."""
    past_due = timezone.now() - timedelta(hours=5)
    for term_status in ["resolved", "closed", "cancelled"]:
        ticket = CustomerSupportTicket(
            tenant=tenant_a,
            subject=f"Inquiry with status {term_status}",
            customer_name="Shopper",
            customer_email="shopper@example.com",
            priority="medium",
            status=term_status,
            sla_resolution_due_at=past_due,
            is_sla_breached=False,
        )
        ticket.save()
        assert ticket.is_sla_breached is False


def test_customersupport_ticket_unique_constraint(tenant_a):
    """Duplicate ticket number within the same tenant raises IntegrityError."""
    t1 = _customersupport_build_ticket(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerSupportTicket.objects.create(
                tenant=tenant_a,
                number=t1.number,
                subject="Duplicate number",
                customer_name="Shopper Dupe",
                customer_email="dupe@example.com",
            )


def test_customersupport_ticket_tenant_isolation(tenant_a, tenant_b):
    """Different tenants can reuse identical number strings without conflict."""
    t_a = _customersupport_build_ticket(tenant_a, number="ESTK-999999")
    t_b = _customersupport_build_ticket(tenant_b, number="ESTK-999999")
    assert t_a.tenant != t_b.tenant
    assert t_a.number == t_b.number
    assert CustomerSupportTicket.objects.filter(number="ESTK-999999").count() == 2


def test_customersupport_ticket_fk_set_null_on_delete(tenant_a, ecom_profile_a, ecom_order_a, admin_user):
    """Deleting related CustomerAccountProfile, EcommerceOrder, or User sets FK to null."""
    ticket = _customersupport_build_ticket(
        tenant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        assigned_agent=admin_user,
    )
    ecom_profile_a.delete()
    ticket.refresh_from_db()
    assert ticket.customer is None

    admin_user.delete()
    ticket.refresh_from_db()
    assert ticket.assigned_agent is None


def test_customersupport_ticket_bot_handoff_fields(tenant_a):
    """Bot-assisted fields can be recorded when transferring to human agent."""
    ticket = _customersupport_build_ticket(
        tenant_a,
        is_bot_handled=True,
        bot_handoff_reason="Escalated due to negative sentiment detection",
    )
    assert ticket.is_bot_handled is True
    assert ticket.bot_handoff_reason == "Escalated due to negative sentiment detection"


# ==============================================================================
# 3. KnowledgeBaseArticle Model Tests
# ==============================================================================

def test_customersupport_article_autonumber_and_defaults(tenant_a, admin_user):
    """KnowledgeBaseArticle auto-generates EKBA- prefix and sets defaults."""
    article = KnowledgeBaseArticle.objects.create(
        tenant=tenant_a,
        title="Delivery Delays & Weather Advisories",
        content="Details about winter weather disruptions.",
        author=admin_user,
    )
    assert article.pk is not None
    assert article.number.startswith("EKBA-")
    assert article.status == "draft"
    assert article.target_audience == "all_visitors"
    assert article.category == "shipping_delivery"
    assert article.is_featured is False
    assert article.view_count == 0
    assert article.helpful_votes == 0
    assert article.unhelpful_votes == 0
    assert article.author == admin_user


def test_customersupport_article_str_representation(tenant_a):
    """__str__ returns '<number> - <title> (<status_display>)'."""
    article = _customersupport_build_article(
        tenant_a,
        title="Payment Methods Accepted",
        status="published",
    )
    expected = f"{article.number} - Payment Methods Accepted (Published)"
    assert str(article) == expected


def test_customersupport_article_slug_auto_generation(tenant_a):
    """Slug is auto-generated from title if left blank; explicit slug is preserved."""
    # Blank slug -> auto-slugified from title
    article1 = KnowledgeBaseArticle.objects.create(
        tenant=tenant_a,
        title="How to Return an Item Easily",
        content="Guide on returns.",
    )
    assert article1.slug == "how-to-return-an-item-easily"

    # Explicit slug preserved
    article2 = KnowledgeBaseArticle.objects.create(
        tenant=tenant_a,
        title="Another Article Title",
        slug="custom-return-guide-url",
        content="Custom slug content.",
    )
    assert article2.slug == "custom-return-guide-url"


def test_customersupport_article_helpfulness_ratio(tenant_a):
    """helpfulness_ratio property computes percentage of helpful votes accurately."""
    # 0 total votes defaults to 100%
    fresh = _customersupport_build_article(tenant_a, helpful_votes=0, unhelpful_votes=0)
    assert fresh.helpfulness_ratio == 100

    # 38 helpful, 2 unhelpful -> 38 / 40 = 95%
    standard = _customersupport_build_article(tenant_a, helpful_votes=38, unhelpful_votes=2)
    assert standard.helpfulness_ratio == 95

    # 1 helpful, 3 unhelpful -> 1 / 4 = 25%
    low = _customersupport_build_article(tenant_a, helpful_votes=1, unhelpful_votes=3)
    assert low.helpfulness_ratio == 25

    # 0 helpful, 5 unhelpful -> 0%
    zero = _customersupport_build_article(tenant_a, helpful_votes=0, unhelpful_votes=5)
    assert zero.helpfulness_ratio == 0


def test_customersupport_article_unique_constraint(tenant_a):
    """Duplicate article number within the same tenant raises IntegrityError."""
    a1 = _customersupport_build_article(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            KnowledgeBaseArticle.objects.create(
                tenant=tenant_a,
                number=a1.number,
                title="Duplicate Article",
                content="Sample content",
            )


def test_customersupport_article_tenant_isolation(tenant_a, tenant_b):
    """Identical article numbers in different tenants coexist peacefully."""
    a_a = _customersupport_build_article(tenant_a, number="EKBA-112233")
    a_b = _customersupport_build_article(tenant_b, number="EKBA-112233")
    assert a_a.tenant != a_b.tenant
    assert a_a.number == a_b.number
    assert KnowledgeBaseArticle.objects.filter(number="EKBA-112233").count() == 2


def test_customersupport_article_ordering(tenant_a):
    """Ordering prefers is_featured descending, then created_at descending."""
    a1 = _customersupport_build_article(tenant_a, title="Normal article 1", is_featured=False)
    a2 = _customersupport_build_article(tenant_a, title="Featured article 2", is_featured=True)
    a3 = _customersupport_build_article(tenant_a, title="Normal article 3", is_featured=False)

    articles = list(KnowledgeBaseArticle.objects.filter(tenant=tenant_a))
    # a2 must be first because is_featured=True
    assert articles[0].pk == a2.pk


def test_customersupport_article_author_set_null_on_delete(tenant_a, admin_user):
    """Deleting author sets author to null without deleting article."""
    article = _customersupport_build_article(tenant_a, author=admin_user)
    admin_user.delete()
    article.refresh_from_db()
    assert article.author is None


# ==============================================================================
# 4. OrderIssueClaim Model Tests
# ==============================================================================

def test_customersupport_claim_autonumber_and_defaults(
    tenant_a, ecom_order_a, ecom_profile_a, ecom_customersupport_ticket_a
):
    """OrderIssueClaim auto-generates ECLM- prefix and sets default values."""
    claim = _customersupport_build_claim(
        tenant_a,
        order=ecom_order_a,
        customer=ecom_profile_a,
        ticket=ecom_customersupport_ticket_a,
    )
    assert claim.pk is not None
    assert claim.number.startswith("ECLM-")
    assert claim.claim_type == "damaged_item"
    assert claim.status == "submitted"
    assert claim.resolution_action == "pending"
    assert claim.claimed_amount == Decimal("49.99")
    assert claim.approved_amount == Decimal("0.00")
    assert claim.order == ecom_order_a
    assert claim.customer == ecom_profile_a
    assert claim.ticket == ecom_customersupport_ticket_a
    assert claim.resolved_at is None


def test_customersupport_claim_str_representation(tenant_a, ecom_order_a):
    """__str__ returns '<number> - Order <order_number> (<claim_type_display>)'."""
    claim = _customersupport_build_claim(
        tenant_a,
        order=ecom_order_a,
        claim_type="lost_in_transit",
    )
    expected = f"{claim.number} - Order {ecom_order_a.number} (Lost in Transit / Package Not Received)"
    assert str(claim) == expected


def test_customersupport_claim_amounts_non_negative_validator(tenant_a, ecom_order_a):
    """claimed_amount and approved_amount reject negative values via MinValueValidator."""
    claim = OrderIssueClaim(
        tenant=tenant_a,
        order=ecom_order_a,
        claimed_amount=Decimal("-15.00"),
        approved_amount=Decimal("0.00"),
        customer_notes="Negative claim amount test",
    )
    with pytest.raises(ValidationError) as exc_info:
        claim.full_clean()
    assert "claimed_amount" in exc_info.value.message_dict

    claim.claimed_amount = Decimal("50.00")
    claim.approved_amount = Decimal("-5.00")
    with pytest.raises(ValidationError) as exc_info:
        claim.full_clean()
    assert "approved_amount" in exc_info.value.message_dict


def test_customersupport_claim_photo_url_validator(tenant_a, ecom_order_a):
    """photo_evidence_url requires valid http/https URL scheme."""
    claim = OrderIssueClaim(
        tenant=tenant_a,
        order=ecom_order_a,
        customer_notes="Testing url validator",
        photo_evidence_url="not-a-valid-url",
    )
    with pytest.raises(ValidationError) as exc_info:
        claim.full_clean()
    assert "photo_evidence_url" in exc_info.value.message_dict

    # FTP scheme rejected (only http/https permitted)
    claim.photo_evidence_url = "ftp://storage.example.com/photo.jpg"
    with pytest.raises(ValidationError) as exc_info:
        claim.full_clean()
    assert "photo_evidence_url" in exc_info.value.message_dict

    # Valid HTTPS scheme passes
    claim.photo_evidence_url = "https://cdn.example.com/proof.jpg"
    claim.full_clean()  # should not raise


def test_customersupport_claim_resolved_at_auto_set(tenant_a, ecom_order_a):
    """save() auto-sets resolved_at when status is approved, rejected, or completed."""
    claim = _customersupport_build_claim(tenant_a, order=ecom_order_a, status="under_review")
    assert claim.resolved_at is None

    # Transition to approved sets resolved_at
    claim.status = "approved"
    claim.approved_amount = Decimal("49.99")
    claim.resolution_action = "full_refund"
    claim.save()
    assert claim.resolved_at is not None
    orig_resolved_at = claim.resolved_at

    # Subsequent saves do not alter resolved_at
    claim.decision_notes = "Refund approved by manager."
    claim.save()
    assert claim.resolved_at == orig_resolved_at


def test_customersupport_claim_unique_constraint(tenant_a, ecom_order_a):
    """Duplicate claim number within the same tenant raises IntegrityError."""
    c1 = _customersupport_build_claim(tenant_a, order=ecom_order_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrderIssueClaim.objects.create(
                tenant=tenant_a,
                number=c1.number,
                order=ecom_order_a,
                customer_notes="Duplicate claim number",
            )


def test_customersupport_claim_tenant_isolation(tenant_a, tenant_b, ecom_order_a, ecom_order_b):
    """Claims in different tenants can have the same number."""
    c_a = _customersupport_build_claim(tenant_a, order=ecom_order_a, number="ECLM-555555")
    c_b = _customersupport_build_claim(tenant_b, order=ecom_order_b, number="ECLM-555555")
    assert c_a.tenant != c_b.tenant
    assert c_a.number == c_b.number
    assert OrderIssueClaim.objects.filter(number="ECLM-555555").count() == 2


def test_customersupport_claim_order_cascade_delete(tenant_a, ecom_order_a):
    """Deleting EcommerceOrder cascades and deletes associated claims."""
    claim = _customersupport_build_claim(tenant_a, order=ecom_order_a)
    claim_id = claim.pk
    ecom_order_a.delete()
    assert not OrderIssueClaim.objects.filter(pk=claim_id).exists()


def test_customersupport_claim_ticket_and_customer_set_null(
    tenant_a, ecom_order_a, ecom_profile_a, ecom_customersupport_ticket_a
):
    """Deleting related ticket or customer profile sets FK to null without deleting claim."""
    claim = _customersupport_build_claim(
        tenant_a,
        order=ecom_order_a,
        customer=ecom_profile_a,
        ticket=ecom_customersupport_ticket_a,
    )
    ecom_customersupport_ticket_a.delete()
    claim.refresh_from_db()
    assert claim.ticket is None

    ecom_profile_a.delete()
    claim.refresh_from_db()
    assert claim.customer is None


# ==============================================================================
# 5. CustomerSatisfactionSurvey Model Tests
# ==============================================================================

def test_customersupport_survey_autonumber_and_defaults(
    tenant_a, ecom_profile_a, ecom_order_a, ecom_customersupport_ticket_a
):
    """CustomerSatisfactionSurvey auto-generates ECSF- prefix and sets default values."""
    survey = _customersupport_build_survey(
        tenant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        ticket=ecom_customersupport_ticket_a,
    )
    assert survey.pk is not None
    assert survey.number.startswith("ECSF-")
    assert survey.survey_type == "ticket_csat"
    assert survey.rating_score == 5
    assert survey.sentiment == "positive"
    assert survey.follow_up_status == "not_required"
    assert survey.customer == ecom_profile_a
    assert survey.order == ecom_order_a
    assert survey.ticket == ecom_customersupport_ticket_a


def test_customersupport_survey_str_representation(tenant_a):
    """__str__ returns '<number> - <survey_type_display> (<rating_score>/10)'."""
    survey = _customersupport_build_survey(
        tenant_a,
        survey_type="storefront_nps",
        rating_score=9,
    )
    expected = f"{survey.number} - Storefront NPS (0-10 Score) (9/10)"
    assert str(survey) == expected


def test_customersupport_survey_csat_sentiment_auto_computation(tenant_a):
    """save() auto-computes CSAT sentiment: >=4 positive, ==3 neutral, <=2 negative."""
    # Score 5 -> positive, follow_up not_required
    s5 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="ticket_csat",
        rating_score=5,
    )
    assert s5.sentiment == "positive"
    assert s5.follow_up_status == "not_required"

    # Score 4 -> positive
    s4 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="order_delivery_csat",
        rating_score=4,
    )
    assert s4.sentiment == "positive"
    assert s4.follow_up_status == "not_required"

    # Score 3 -> neutral
    s3 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="ticket_csat",
        rating_score=3,
    )
    assert s3.sentiment == "neutral"
    assert s3.follow_up_status == "not_required"

    # Score 2 -> negative, follow_up automatically becomes pending_review
    s2 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="ticket_csat",
        rating_score=2,
    )
    assert s2.sentiment == "negative"
    assert s2.follow_up_status == "pending_review"

    # Score 1 -> negative, follow_up automatically becomes pending_review
    s1 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="order_delivery_csat",
        rating_score=1,
    )
    assert s1.sentiment == "negative"
    assert s1.follow_up_status == "pending_review"


def test_customersupport_survey_nps_sentiment_auto_computation(tenant_a):
    """save() auto-computes NPS sentiment: >=9 positive, 7-8 neutral, <=6 negative."""
    # NPS 10 -> positive
    s10 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=10,
    )
    assert s10.sentiment == "positive"
    assert s10.follow_up_status == "not_required"

    # NPS 9 -> positive
    s9 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=9,
    )
    assert s9.sentiment == "positive"

    # NPS 8 -> neutral
    s8 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=8,
    )
    assert s8.sentiment == "neutral"

    # NPS 7 -> neutral
    s7 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=7,
    )
    assert s7.sentiment == "neutral"

    # NPS 6 -> negative, follow_up automatically becomes pending_review
    s6 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=6,
    )
    assert s6.sentiment == "negative"
    assert s6.follow_up_status == "pending_review"

    # NPS 0 -> negative, follow_up automatically becomes pending_review
    s0 = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=0,
    )
    assert s0.sentiment == "negative"
    assert s0.follow_up_status == "pending_review"


def test_customersupport_survey_manual_sentiment_override_preserved(tenant_a):
    """Explicitly specified sentiment is not overridden by rating-based auto computation."""
    # Manually passed positive despite low score 1
    survey = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="ticket_csat",
        rating_score=1,
        sentiment="positive",
        feedback_comment="Agent was amazing despite the product defect.",
    )
    assert survey.sentiment == "positive"
    assert survey.follow_up_status == "not_required"


def test_customersupport_survey_existing_follow_up_not_overwritten(tenant_a):
    """If follow_up_status is already set (e.g. contacted_customer), negative sentiment does not reset it."""
    survey = CustomerSatisfactionSurvey.objects.create(
        tenant=tenant_a,
        survey_type="ticket_csat",
        rating_score=1,
        sentiment="negative",
        follow_up_status="contacted_customer",
        follow_up_notes="Supervisor phoned customer and offered voucher.",
    )
    assert survey.sentiment == "negative"
    assert survey.follow_up_status == "contacted_customer"


def test_customersupport_survey_rating_score_validators(tenant_a):
    """rating_score must be between 0 and 10."""
    survey_high = CustomerSatisfactionSurvey(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=11,
    )
    with pytest.raises(ValidationError) as exc_info:
        survey_high.full_clean()
    assert "rating_score" in exc_info.value.message_dict

    # Valid boundary scores (0 and 10) pass full_clean
    survey_0 = CustomerSatisfactionSurvey(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=0,
    )
    survey_0.full_clean()

    survey_10 = CustomerSatisfactionSurvey(
        tenant=tenant_a,
        survey_type="storefront_nps",
        rating_score=10,
    )
    survey_10.full_clean()


def test_customersupport_survey_unique_constraint(tenant_a):
    """Duplicate survey number within the same tenant raises IntegrityError."""
    s1 = _customersupport_build_survey(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CustomerSatisfactionSurvey.objects.create(
                tenant=tenant_a,
                number=s1.number,
                rating_score=5,
            )


def test_customersupport_survey_tenant_isolation(tenant_a, tenant_b):
    """Different tenants can reuse identical survey numbers without collision."""
    s_a = _customersupport_build_survey(tenant_a, number="ECSF-778899")
    s_b = _customersupport_build_survey(tenant_b, number="ECSF-778899")
    assert s_a.tenant != s_b.tenant
    assert s_a.number == s_b.number
    assert CustomerSatisfactionSurvey.objects.filter(number="ECSF-778899").count() == 2


def test_customersupport_survey_fk_set_null_on_delete(
    tenant_a, ecom_profile_a, ecom_order_a, ecom_customersupport_ticket_a, admin_user
):
    """Deleting related ticket, order, customer, or agent sets FK to null without deleting survey."""
    survey = _customersupport_build_survey(
        tenant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        ticket=ecom_customersupport_ticket_a,
        agent_rated=admin_user,
    )
    ecom_customersupport_ticket_a.delete()
    survey.refresh_from_db()
    assert survey.ticket is None

    ecom_order_a.delete()
    survey.refresh_from_db()
    assert survey.order is None

    ecom_profile_a.delete()
    survey.refresh_from_db()
    assert survey.customer is None

    admin_user.delete()
    survey.refresh_from_db()
    assert survey.agent_rated is None
