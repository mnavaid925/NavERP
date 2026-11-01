"""Comprehensive multi-tenancy, authorization, IDOR, mass assignment, XSS, and audit forensics unit tests for eCommerce 9.14 Customer Service & Support.

Covers:
1. Multi-Tenant Data Isolation & IDOR Protection:
   - Tenant B client accessing Tenant A records (Ticket, Article, Claim, Survey) via detail view -> 404.
   - Tenant B client accessing Tenant A records via edit GET -> 404, edit POST -> 404.
   - Tenant B client accessing Tenant A records via delete POST -> 404.
   - Cross-tenant immutability: records remain untouched in DB after unauthorized access attempts.
   - Cross-tenant list isolation: each tenant sees only its own records in list views.
   - Form FK injection: attempting to associate foreign tenant's customer, order, or ticket in forms -> rejected.
2. Authorization & Role Gating:
   - All 20 routes require authentication: unauthenticated GET/POST requests redirect to login.
   - Deletion requires tenant admin: standard non-admin staff (member_user) attempting delete POST gets 403 Forbidden.
   - Delete routes reject GET requests with 405 Method Not Allowed.
   - Standard non-admin staff are permitted standard CRUD views (list, detail, create GET/POST, edit GET/POST).
3. Mass Assignment Defense:
   - Attempting to pass tenant, number, created_at, updated_at, resolved_at, view_count, helpful_votes in form POST
     does not overwrite protected model fields.
4. XSS & Input Sanitization:
   - Malicious script injection payloads in subjects, titles, notes, and comments are properly HTML-escaped.
   - Photo evidence URL with quote breakout or script payload cannot trigger stored XSS.
5. Audit Logging Forensics:
   - write_audit_log records valid integer object_id on deletion before instance deletion (never None).
   - Create, update, and delete actions generate expected AuditLog records stamped with correct tenant and user.
   - AuditLog records are strictly isolated per tenant (Tenant A mutations never leak to Tenant B).

Naming conventions enforced:
- Test function prefix: test_customersupport_*
- Module-level helpers: _customersupport_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.forms import (
    CustomerSatisfactionSurveyForm,
    CustomerSupportTicketForm,
    KnowledgeBaseArticleForm,
    OrderIssueClaimForm,
)
from apps.ecommerce.models import (
    CustomerSatisfactionSurvey,
    CustomerSupportTicket,
    KnowledgeBaseArticle,
    OrderIssueClaim,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERSUPPORT_URLS,
    _customersupport_article,
    _customersupport_claim,
    _customersupport_survey,
    _customersupport_ticket,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_customersupport_*)
# ==============================================================================

def _customersupport_create_ticket(tenant, **overrides):
    """Helper to create an isolated CustomerSupportTicket."""
    return _customersupport_ticket(tenant, **overrides)


def _customersupport_create_article(tenant, **overrides):
    """Helper to create an isolated KnowledgeBaseArticle."""
    return _customersupport_article(tenant, **overrides)


def _customersupport_create_claim(tenant, order, **overrides):
    """Helper to create an isolated OrderIssueClaim."""
    return _customersupport_claim(tenant, order=order, **overrides)


def _customersupport_create_survey(tenant, **overrides):
    """Helper to create an isolated CustomerSatisfactionSurvey."""
    return _customersupport_survey(tenant, **overrides)


def _customersupport_assert_login_redirect(response, url_name=""):
    """Helper asserting redirect to login page for unauthenticated access."""
    assert response.status_code == 302, f"Expected 302 redirect for {url_name}, got {response.status_code}"
    assert "login" in response.headers.get("Location", ""), (
        f"Expected 'login' in redirect Location for {url_name}, got {response.headers.get('Location')}"
    )


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Protection Tests
# ==============================================================================

def test_customersupport_idor_ticket_cross_tenant_access_blocked(
    client_a, client_b, ecom_customersupport_ticket_a, ecom_customersupport_ticket_b
):
    """Tenant B client cannot view, edit, or delete Tenant A ticket (and vice-versa)."""
    ticket_a = ecom_customersupport_ticket_a
    original_subject = ticket_a.subject
    detail_url = reverse("ecommerce:customersupportticket_detail", args=[ticket_a.pk])
    edit_url = reverse("ecommerce:customersupportticket_edit", args=[ticket_a.pk])
    delete_url = reverse("ecommerce:customersupportticket_delete", args=[ticket_a.pk])

    # Tenant B tries to access Tenant A Ticket
    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"subject": "Hacked Subject", "status": "resolved"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404

    # Verify ticket_a remains intact in database
    ticket_a.refresh_from_db()
    assert ticket_a.subject == original_subject
    assert CustomerSupportTicket.objects.filter(pk=ticket_a.pk).exists()

    # Reverse: Tenant A tries to access Tenant B Ticket
    ticket_b = ecom_customersupport_ticket_b
    detail_b_url = reverse("ecommerce:customersupportticket_detail", args=[ticket_b.pk])
    edit_b_url = reverse("ecommerce:customersupportticket_edit", args=[ticket_b.pk])
    delete_b_url = reverse("ecommerce:customersupportticket_delete", args=[ticket_b.pk])

    assert client_a.get(detail_b_url).status_code == 404
    assert client_a.get(edit_b_url).status_code == 404
    assert client_a.post(edit_b_url, {"subject": "Hacked Subject"}).status_code == 404
    assert client_a.post(delete_b_url).status_code == 404

    ticket_b.refresh_from_db()
    assert CustomerSupportTicket.objects.filter(pk=ticket_b.pk).exists()


def test_customersupport_idor_article_cross_tenant_access_blocked(
    client_a, client_b, ecom_customersupport_article_a, ecom_customersupport_article_b
):
    """Tenant B client cannot view, edit, or delete Tenant A KB article (and vice-versa)."""
    article_a = ecom_customersupport_article_a
    original_title = article_a.title
    detail_url = reverse("ecommerce:knowledgebasearticle_detail", args=[article_a.pk])
    edit_url = reverse("ecommerce:knowledgebasearticle_edit", args=[article_a.pk])
    delete_url = reverse("ecommerce:knowledgebasearticle_delete", args=[article_a.pk])

    # Tenant B tries to access Tenant A Article
    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"title": "Hacked Title", "status": "archived"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404

    article_a.refresh_from_db()
    assert article_a.title == original_title
    assert KnowledgeBaseArticle.objects.filter(pk=article_a.pk).exists()

    # Reverse: Tenant A tries to access Tenant B Article
    article_b = ecom_customersupport_article_b
    detail_b_url = reverse("ecommerce:knowledgebasearticle_detail", args=[article_b.pk])
    edit_b_url = reverse("ecommerce:knowledgebasearticle_edit", args=[article_b.pk])
    delete_b_url = reverse("ecommerce:knowledgebasearticle_delete", args=[article_b.pk])

    assert client_a.get(detail_b_url).status_code == 404
    assert client_a.get(edit_b_url).status_code == 404
    assert client_a.post(edit_b_url, {"title": "Hacked Title"}).status_code == 404
    assert client_a.post(delete_b_url).status_code == 404

    article_b.refresh_from_db()
    assert KnowledgeBaseArticle.objects.filter(pk=article_b.pk).exists()


def test_customersupport_idor_claim_cross_tenant_access_blocked(
    client_a, client_b, ecom_customersupport_claim_a, ecom_customersupport_claim_b
):
    """Tenant B client cannot view, edit, or delete Tenant A claim (and vice-versa)."""
    claim_a = ecom_customersupport_claim_a
    original_notes = claim_a.customer_notes
    detail_url = reverse("ecommerce:orderissueclaim_detail", args=[claim_a.pk])
    edit_url = reverse("ecommerce:orderissueclaim_edit", args=[claim_a.pk])
    delete_url = reverse("ecommerce:orderissueclaim_delete", args=[claim_a.pk])

    # Tenant B tries to access Tenant A Claim
    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"customer_notes": "Hacked Notes", "status": "completed"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404

    claim_a.refresh_from_db()
    assert claim_a.customer_notes == original_notes
    assert OrderIssueClaim.objects.filter(pk=claim_a.pk).exists()

    # Reverse: Tenant A tries to access Tenant B Claim
    claim_b = ecom_customersupport_claim_b
    detail_b_url = reverse("ecommerce:orderissueclaim_detail", args=[claim_b.pk])
    edit_b_url = reverse("ecommerce:orderissueclaim_edit", args=[claim_b.pk])
    delete_b_url = reverse("ecommerce:orderissueclaim_delete", args=[claim_b.pk])

    assert client_a.get(detail_b_url).status_code == 404
    assert client_a.get(edit_b_url).status_code == 404
    assert client_a.post(edit_b_url, {"customer_notes": "Hacked Notes"}).status_code == 404
    assert client_a.post(delete_b_url).status_code == 404

    claim_b.refresh_from_db()
    assert OrderIssueClaim.objects.filter(pk=claim_b.pk).exists()


def test_customersupport_idor_survey_cross_tenant_access_blocked(
    client_a, client_b, ecom_customersupport_survey_a, ecom_customersupport_survey_b
):
    """Tenant B client cannot view, edit, or delete Tenant A survey (and vice-versa)."""
    survey_a = ecom_customersupport_survey_a
    original_comment = survey_a.feedback_comment
    detail_url = reverse("ecommerce:customersatisfactionsurvey_detail", args=[survey_a.pk])
    edit_url = reverse("ecommerce:customersatisfactionsurvey_edit", args=[survey_a.pk])
    delete_url = reverse("ecommerce:customersatisfactionsurvey_delete", args=[survey_a.pk])

    # Tenant B tries to access Tenant A Survey
    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"feedback_comment": "Hacked Feedback", "rating_score": 1}).status_code == 404
    assert client_b.post(delete_url).status_code == 404

    survey_a.refresh_from_db()
    assert survey_a.feedback_comment == original_comment
    assert CustomerSatisfactionSurvey.objects.filter(pk=survey_a.pk).exists()

    # Reverse: Tenant A tries to access Tenant B Survey
    survey_b = ecom_customersupport_survey_b
    detail_b_url = reverse("ecommerce:customersatisfactionsurvey_detail", args=[survey_b.pk])
    edit_b_url = reverse("ecommerce:customersatisfactionsurvey_edit", args=[survey_b.pk])
    delete_b_url = reverse("ecommerce:customersatisfactionsurvey_delete", args=[survey_b.pk])

    assert client_a.get(detail_b_url).status_code == 404
    assert client_a.get(edit_b_url).status_code == 404
    assert client_a.post(edit_b_url, {"feedback_comment": "Hacked Feedback"}).status_code == 404
    assert client_a.post(delete_b_url).status_code == 404

    survey_b.refresh_from_db()
    assert CustomerSatisfactionSurvey.objects.filter(pk=survey_b.pk).exists()


def test_customersupport_cross_tenant_list_isolation(
    client_a,
    client_b,
    ecom_customersupport_ticket_a,
    ecom_customersupport_ticket_b,
    ecom_customersupport_article_a,
    ecom_customersupport_article_b,
    ecom_customersupport_claim_a,
    ecom_customersupport_claim_b,
    ecom_customersupport_survey_a,
    ecom_customersupport_survey_b,
):
    """List views strictly isolate records belonging to each tenant."""
    # Ensure distinct strings for content verification
    ecom_customersupport_ticket_a.subject = "Acme Unique Support Ticket Alpha"
    ecom_customersupport_ticket_a.save()
    ecom_customersupport_ticket_b.subject = "Globex Unique Support Ticket Beta"
    ecom_customersupport_ticket_b.save()

    ecom_customersupport_article_a.title = "Acme Knowledge Base Policy Alpha"
    ecom_customersupport_article_a.save()
    ecom_customersupport_article_b.title = "Globex Knowledge Base Policy Beta"
    ecom_customersupport_article_b.save()

    ecom_customersupport_claim_a.order.number = "ORD-ACME-CLAIM-A"
    ecom_customersupport_claim_a.order.save()
    ecom_customersupport_claim_b.order.number = "ORD-GLOBEX-CLAIM-B"
    ecom_customersupport_claim_b.order.save()

    ecom_customersupport_survey_a.feedback_comment = "Acme Unique Customer Verbatim Alpha"
    ecom_customersupport_survey_a.save()
    ecom_customersupport_survey_b.feedback_comment = "Globex Unique Customer Verbatim Beta"
    ecom_customersupport_survey_b.save()

    # 1. CustomerSupportTicket List
    resp_ticket_a = client_a.get(reverse("ecommerce:customersupportticket_list"))
    assert resp_ticket_a.status_code == 200
    ticket_ids_a = [t.pk for t in resp_ticket_a.context["tickets"]]
    assert ecom_customersupport_ticket_a.pk in ticket_ids_a
    assert ecom_customersupport_ticket_b.pk not in ticket_ids_a
    assert b"Acme Unique Support Ticket Alpha" in resp_ticket_a.content
    assert b"Globex Unique Support Ticket Beta" not in resp_ticket_a.content

    resp_ticket_b = client_b.get(reverse("ecommerce:customersupportticket_list"))
    assert resp_ticket_b.status_code == 200
    ticket_ids_b = [t.pk for t in resp_ticket_b.context["tickets"]]
    assert ecom_customersupport_ticket_b.pk in ticket_ids_b
    assert ecom_customersupport_ticket_a.pk not in ticket_ids_b
    assert b"Globex Unique Support Ticket Beta" in resp_ticket_b.content
    assert b"Acme Unique Support Ticket Alpha" not in resp_ticket_b.content

    # 2. KnowledgeBaseArticle List
    resp_article_a = client_a.get(reverse("ecommerce:knowledgebasearticle_list"))
    assert resp_article_a.status_code == 200
    article_ids_a = [a.pk for a in resp_article_a.context["articles"]]
    assert ecom_customersupport_article_a.pk in article_ids_a
    assert ecom_customersupport_article_b.pk not in article_ids_a
    assert b"Acme Knowledge Base Policy Alpha" in resp_article_a.content
    assert b"Globex Knowledge Base Policy Beta" not in resp_article_a.content

    resp_article_b = client_b.get(reverse("ecommerce:knowledgebasearticle_list"))
    assert resp_article_b.status_code == 200
    article_ids_b = [a.pk for a in resp_article_b.context["articles"]]
    assert ecom_customersupport_article_b.pk in article_ids_b
    assert ecom_customersupport_article_a.pk not in article_ids_b
    assert b"Globex Knowledge Base Policy Beta" in resp_article_b.content
    assert b"Acme Knowledge Base Policy Alpha" not in resp_article_b.content

    # 3. OrderIssueClaim List
    resp_claim_a = client_a.get(reverse("ecommerce:orderissueclaim_list"))
    assert resp_claim_a.status_code == 200
    claim_ids_a = [c.pk for c in resp_claim_a.context["claims"]]
    assert ecom_customersupport_claim_a.pk in claim_ids_a
    assert ecom_customersupport_claim_b.pk not in claim_ids_a
    claim_a_url = reverse("ecommerce:orderissueclaim_detail", args=[ecom_customersupport_claim_a.pk]).encode()
    claim_b_url = reverse("ecommerce:orderissueclaim_detail", args=[ecom_customersupport_claim_b.pk]).encode()
    assert claim_a_url in resp_claim_a.content
    assert claim_b_url not in resp_claim_a.content

    resp_claim_b = client_b.get(reverse("ecommerce:orderissueclaim_list"))
    assert resp_claim_b.status_code == 200
    claim_ids_b = [c.pk for c in resp_claim_b.context["claims"]]
    assert ecom_customersupport_claim_b.pk in claim_ids_b
    assert ecom_customersupport_claim_a.pk not in claim_ids_b
    assert claim_b_url in resp_claim_b.content
    assert claim_a_url not in resp_claim_b.content

    # 4. CustomerSatisfactionSurvey List
    resp_survey_a = client_a.get(reverse("ecommerce:customersatisfactionsurvey_list"))
    assert resp_survey_a.status_code == 200
    survey_ids_a = [s.pk for s in resp_survey_a.context["surveys"]]
    assert ecom_customersupport_survey_a.pk in survey_ids_a
    assert ecom_customersupport_survey_b.pk not in survey_ids_a
    assert b"Acme Unique Customer Verbatim Alpha" in resp_survey_a.content
    assert b"Globex Unique Customer Verbatim Beta" not in resp_survey_a.content

    resp_survey_b = client_b.get(reverse("ecommerce:customersatisfactionsurvey_list"))
    assert resp_survey_b.status_code == 200
    survey_ids_b = [s.pk for s in resp_survey_b.context["surveys"]]
    assert ecom_customersupport_survey_b.pk in survey_ids_b
    assert ecom_customersupport_survey_a.pk not in survey_ids_b
    assert b"Globex Unique Customer Verbatim Beta" in resp_survey_b.content
    assert b"Acme Unique Customer Verbatim Alpha" not in resp_survey_b.content


def test_customersupport_form_foreign_tenant_fk_injection_rejected(
    tenant_a,
    tenant_b,
    ecom_profile_b,
    ecom_order_b,
    ecom_customersupport_ticket_b,
):
    """Foreign tenant references are rejected across all Customer Support forms via reject_foreign."""
    # 1. CustomerSupportTicketForm rejecting Tenant B references
    ticket_form_cust = CustomerSupportTicketForm(
        data={
            "customer": ecom_profile_b.pk,
            "subject": "Foreign Customer Injection",
            "customer_name": "Injected Name",
            "customer_email": "injected@example.com",
            "channel": "email",
            "category": "general",
            "priority": "medium",
            "status": "new",
            "initial_message": "Should fail due to foreign customer.",
        },
        tenant=tenant_a,
    )
    assert not ticket_form_cust.is_valid()
    assert "customer" in ticket_form_cust.errors

    ticket_form_order = CustomerSupportTicketForm(
        data={
            "order": ecom_order_b.pk,
            "subject": "Foreign Order Injection",
            "customer_name": "Injected Name",
            "customer_email": "injected@example.com",
            "channel": "email",
            "category": "general",
            "priority": "medium",
            "status": "new",
            "initial_message": "Should fail due to foreign order.",
        },
        tenant=tenant_a,
    )
    assert not ticket_form_order.is_valid()
    assert "order" in ticket_form_order.errors

    # 2. OrderIssueClaimForm rejecting Tenant B references
    claim_form = OrderIssueClaimForm(
        data={
            "order": ecom_order_b.pk,
            "customer": ecom_profile_b.pk,
            "ticket": ecom_customersupport_ticket_b.pk,
            "claim_type": "damaged_item",
            "status": "submitted",
            "claimed_amount": "50.00",
            "resolution_action": "full_refund",
            "customer_notes": "Attempting foreign references in claim.",
        },
        tenant=tenant_a,
    )
    assert not claim_form.is_valid()
    assert "order" in claim_form.errors

    # 3. CustomerSatisfactionSurveyForm rejecting Tenant B references
    survey_form = CustomerSatisfactionSurveyForm(
        data={
            "ticket": ecom_customersupport_ticket_b.pk,
            "order": ecom_order_b.pk,
            "customer": ecom_profile_b.pk,
            "survey_type": "ticket_csat",
            "rating_score": 5,
            "sentiment": "positive",
            "follow_up_status": "not_required",
            "feedback_comment": "Attempting foreign references in survey.",
        },
        tenant=tenant_a,
    )
    assert not survey_form.is_valid()
    assert "ticket" in survey_form.errors


# ==============================================================================
# 2. Authorization & Role Gating Tests
# ==============================================================================

def test_customersupport_all_routes_require_authentication(
    client,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """All 20 Customer Support routes redirect unauthenticated anonymous requests to login."""
    pk_ticket = ecom_customersupport_ticket_a.pk
    pk_article = ecom_customersupport_article_a.pk
    pk_claim = ecom_customersupport_claim_a.pk
    pk_survey = ecom_customersupport_survey_a.pk

    endpoints = [
        # Tickets (5)
        reverse("ecommerce:customersupportticket_list"),
        reverse("ecommerce:customersupportticket_create"),
        reverse("ecommerce:customersupportticket_detail", args=[pk_ticket]),
        reverse("ecommerce:customersupportticket_edit", args=[pk_ticket]),
        reverse("ecommerce:customersupportticket_delete", args=[pk_ticket]),
        # Articles (5)
        reverse("ecommerce:knowledgebasearticle_list"),
        reverse("ecommerce:knowledgebasearticle_create"),
        reverse("ecommerce:knowledgebasearticle_detail", args=[pk_article]),
        reverse("ecommerce:knowledgebasearticle_edit", args=[pk_article]),
        reverse("ecommerce:knowledgebasearticle_delete", args=[pk_article]),
        # Claims (5)
        reverse("ecommerce:orderissueclaim_list"),
        reverse("ecommerce:orderissueclaim_create"),
        reverse("ecommerce:orderissueclaim_detail", args=[pk_claim]),
        reverse("ecommerce:orderissueclaim_edit", args=[pk_claim]),
        reverse("ecommerce:orderissueclaim_delete", args=[pk_claim]),
        # Surveys (5)
        reverse("ecommerce:customersatisfactionsurvey_list"),
        reverse("ecommerce:customersatisfactionsurvey_create"),
        reverse("ecommerce:customersatisfactionsurvey_detail", args=[pk_survey]),
        reverse("ecommerce:customersatisfactionsurvey_edit", args=[pk_survey]),
        reverse("ecommerce:customersatisfactionsurvey_delete", args=[pk_survey]),
    ]

    assert len(endpoints) == 20

    # Test GET on all 20 endpoints
    for url in endpoints:
        resp = client.get(url)
        _customersupport_assert_login_redirect(resp, url)

    # Test POST on create and edit endpoints for unauthenticated access
    mutating_post_urls = [
        reverse("ecommerce:customersupportticket_create"),
        reverse("ecommerce:customersupportticket_edit", args=[pk_ticket]),
        reverse("ecommerce:customersupportticket_delete", args=[pk_ticket]),
        reverse("ecommerce:knowledgebasearticle_create"),
        reverse("ecommerce:knowledgebasearticle_edit", args=[pk_article]),
        reverse("ecommerce:knowledgebasearticle_delete", args=[pk_article]),
        reverse("ecommerce:orderissueclaim_create"),
        reverse("ecommerce:orderissueclaim_edit", args=[pk_claim]),
        reverse("ecommerce:orderissueclaim_delete", args=[pk_claim]),
        reverse("ecommerce:customersatisfactionsurvey_create"),
        reverse("ecommerce:customersatisfactionsurvey_edit", args=[pk_survey]),
        reverse("ecommerce:customersatisfactionsurvey_delete", args=[pk_survey]),
    ]
    for url in mutating_post_urls:
        resp = client.post(url, {})
        _customersupport_assert_login_redirect(resp, url)


def test_customersupport_delete_routes_reject_get_with_405(
    client_a,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """GET requests on POST-only delete endpoints return 405 Method Not Allowed."""
    delete_urls = [
        reverse("ecommerce:customersupportticket_delete", args=[ecom_customersupport_ticket_a.pk]),
        reverse("ecommerce:knowledgebasearticle_delete", args=[ecom_customersupport_article_a.pk]),
        reverse("ecommerce:orderissueclaim_delete", args=[ecom_customersupport_claim_a.pk]),
        reverse("ecommerce:customersatisfactionsurvey_delete", args=[ecom_customersupport_survey_a.pk]),
    ]

    for url in delete_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET on {url}, got {resp.status_code}"


def test_customersupport_deletion_requires_tenant_admin_member_user_forbidden(
    member_client,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """Standard non-admin members receive 403 Forbidden on all 4 deletion endpoints."""
    # 1. CustomerSupportTicket delete
    tkt_url = reverse("ecommerce:customersupportticket_delete", args=[ecom_customersupport_ticket_a.pk])
    resp_tkt = member_client.post(tkt_url)
    assert resp_tkt.status_code == 403
    assert CustomerSupportTicket.objects.filter(pk=ecom_customersupport_ticket_a.pk).exists()

    # 2. KnowledgeBaseArticle delete
    art_url = reverse("ecommerce:knowledgebasearticle_delete", args=[ecom_customersupport_article_a.pk])
    resp_art = member_client.post(art_url)
    assert resp_art.status_code == 403
    assert KnowledgeBaseArticle.objects.filter(pk=ecom_customersupport_article_a.pk).exists()

    # 3. OrderIssueClaim delete
    clm_url = reverse("ecommerce:orderissueclaim_delete", args=[ecom_customersupport_claim_a.pk])
    resp_clm = member_client.post(clm_url)
    assert resp_clm.status_code == 403
    assert OrderIssueClaim.objects.filter(pk=ecom_customersupport_claim_a.pk).exists()

    # 4. CustomerSatisfactionSurvey delete
    srv_url = reverse("ecommerce:customersatisfactionsurvey_delete", args=[ecom_customersupport_survey_a.pk])
    resp_srv = member_client.post(srv_url)
    assert resp_srv.status_code == 403
    assert CustomerSatisfactionSurvey.objects.filter(pk=ecom_customersupport_survey_a.pk).exists()


def test_customersupport_non_admin_member_allowed_standard_crud(
    member_client,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """Standard non-admin members can access standard list, detail, create, and edit GET views."""
    allowed_urls = [
        # Lists
        reverse("ecommerce:customersupportticket_list"),
        reverse("ecommerce:knowledgebasearticle_list"),
        reverse("ecommerce:orderissueclaim_list"),
        reverse("ecommerce:customersatisfactionsurvey_list"),
        # Details
        reverse("ecommerce:customersupportticket_detail", args=[ecom_customersupport_ticket_a.pk]),
        reverse("ecommerce:knowledgebasearticle_detail", args=[ecom_customersupport_article_a.pk]),
        reverse("ecommerce:orderissueclaim_detail", args=[ecom_customersupport_claim_a.pk]),
        reverse("ecommerce:customersatisfactionsurvey_detail", args=[ecom_customersupport_survey_a.pk]),
        # Create forms
        reverse("ecommerce:customersupportticket_create"),
        reverse("ecommerce:knowledgebasearticle_create"),
        reverse("ecommerce:orderissueclaim_create"),
        reverse("ecommerce:customersatisfactionsurvey_create"),
        # Edit forms
        reverse("ecommerce:customersupportticket_edit", args=[ecom_customersupport_ticket_a.pk]),
        reverse("ecommerce:knowledgebasearticle_edit", args=[ecom_customersupport_article_a.pk]),
        reverse("ecommerce:orderissueclaim_edit", args=[ecom_customersupport_claim_a.pk]),
        reverse("ecommerce:customersatisfactionsurvey_edit", args=[ecom_customersupport_survey_a.pk]),
    ]

    for url in allowed_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Expected 200 for member on {url}, got {resp.status_code}"


def test_customersupport_admin_user_allowed_deletion(client_a, tenant_a, ecom_order_a, ecom_profile_a):
    """Tenant admin client can successfully delete records via POST and is redirected."""
    # 1. Ticket deletion
    ticket = _customersupport_create_ticket(tenant_a, subject="Admin Delete Ticket")
    tkt_url = reverse("ecommerce:customersupportticket_delete", args=[ticket.pk])
    resp_tkt = client_a.post(tkt_url)
    assert resp_tkt.status_code == 302
    assert not CustomerSupportTicket.objects.filter(pk=ticket.pk).exists()

    # 2. Article deletion
    article = _customersupport_create_article(tenant_a, title="Admin Delete Article", slug=f"adm-del-{tenant_a.slug}")
    art_url = reverse("ecommerce:knowledgebasearticle_delete", args=[article.pk])
    resp_art = client_a.post(art_url)
    assert resp_art.status_code == 302
    assert not KnowledgeBaseArticle.objects.filter(pk=article.pk).exists()

    # 3. Claim deletion
    claim = _customersupport_create_claim(tenant_a, order=ecom_order_a, customer=ecom_profile_a)
    clm_url = reverse("ecommerce:orderissueclaim_delete", args=[claim.pk])
    resp_clm = client_a.post(clm_url)
    assert resp_clm.status_code == 302
    assert not OrderIssueClaim.objects.filter(pk=claim.pk).exists()

    # 4. Survey deletion
    survey = _customersupport_create_survey(tenant_a)
    srv_url = reverse("ecommerce:customersatisfactionsurvey_delete", args=[survey.pk])
    resp_srv = client_a.post(srv_url)
    assert resp_srv.status_code == 302
    assert not CustomerSatisfactionSurvey.objects.filter(pk=survey.pk).exists()


# ==============================================================================
# 3. Mass Assignment Defense Tests
# ==============================================================================

def test_customersupport_ticket_mass_assignment_defense(client_a, tenant_a, tenant_b, ecom_customersupport_ticket_a):
    """Passing protected model fields (tenant, number, created_at, updated_at, resolved_at) does not overwrite them."""
    ticket = ecom_customersupport_ticket_a
    original_number = ticket.number
    original_created_at = ticket.created_at

    edit_url = reverse("ecommerce:customersupportticket_edit", args=[ticket.pk])
    malicious_payload = {
        # Valid form fields
        "subject": "Mass Assignment Guard Test",
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "channel": "email",
        "category": "order_tracking_wismo",
        "priority": "urgent",
        "status": "open",
        "initial_message": ticket.initial_message,
        # Attempted mass-assignment fields
        "tenant": tenant_b.pk,
        "number": "TICK-MALICIOUS-9999",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "resolved_at": "2020-01-01T00:00:00Z",
    }
    resp = client_a.post(edit_url, malicious_payload)
    assert resp.status_code == 302

    ticket.refresh_from_db()
    assert ticket.tenant == tenant_a, "Tenant must not be re-assigned via mass assignment"
    assert ticket.number == original_number, "Document number must not be overwritten"
    assert ticket.created_at == original_created_at, "created_at must not be overwritten"
    assert ticket.resolved_at is None, "resolved_at must not be set via unpermitted form field"
    assert ticket.priority == "urgent"


def test_customersupport_article_mass_assignment_defense(client_a, tenant_a, tenant_b, ecom_customersupport_article_a):
    """Passing protected fields (tenant, number, view_count, helpful_votes, unhelpful_votes) does not overwrite them."""
    article = ecom_customersupport_article_a
    original_number = article.number
    original_votes = article.helpful_votes

    edit_url = reverse("ecommerce:knowledgebasearticle_edit", args=[article.pk])
    malicious_payload = {
        # Valid form fields
        "title": "Updated Secure KB Title",
        "slug": article.slug,
        "category": article.category,
        "summary": article.summary,
        "content": article.content,
        "status": "published",
        "target_audience": article.target_audience,
        # Attempted mass-assignment fields
        "tenant": tenant_b.pk,
        "number": "KB-MALICIOUS-8888",
        "view_count": 999999,
        "helpful_votes": 88888,
        "unhelpful_votes": 77777,
        "created_at": "2020-01-01T00:00:00Z",
    }
    resp = client_a.post(edit_url, malicious_payload)
    assert resp.status_code == 302

    article.refresh_from_db()
    assert article.tenant == tenant_a
    assert article.number == original_number
    assert article.helpful_votes == original_votes
    assert article.title == "Updated Secure KB Title"


def test_customersupport_claim_mass_assignment_defense(client_a, tenant_a, tenant_b, ecom_customersupport_claim_a):
    """Passing protected fields (tenant, number, resolved_at) does not overwrite them on claim edit."""
    claim = ecom_customersupport_claim_a
    original_number = claim.number

    edit_url = reverse("ecommerce:orderissueclaim_edit", args=[claim.pk])
    malicious_payload = {
        # Valid form fields
        "order": claim.order.pk,
        "claim_type": claim.claim_type,
        "status": "under_review",
        "claimed_amount": "49.99",
        "approved_amount": "0.00",
        "resolution_action": "pending",
        "customer_notes": claim.customer_notes,
        # Attempted mass-assignment fields
        "tenant": tenant_b.pk,
        "number": "CLM-MALICIOUS-7777",
        "resolved_at": "2020-01-01T00:00:00Z",
        "created_at": "2020-01-01T00:00:00Z",
    }
    resp = client_a.post(edit_url, malicious_payload)
    assert resp.status_code == 302

    claim.refresh_from_db()
    assert claim.tenant == tenant_a
    assert claim.number == original_number
    assert claim.resolved_at is None
    assert claim.status == "under_review"


def test_customersupport_survey_mass_assignment_defense(client_a, tenant_a, tenant_b, ecom_customersupport_survey_a):
    """Passing protected fields (tenant, number, created_at) does not overwrite them on survey edit."""
    survey = ecom_customersupport_survey_a
    original_number = survey.number

    edit_url = reverse("ecommerce:customersatisfactionsurvey_edit", args=[survey.pk])
    malicious_payload = {
        # Valid form fields
        "survey_type": survey.survey_type,
        "rating_score": 4,
        "sentiment": "positive",
        "follow_up_status": "not_required",
        "feedback_comment": "Valid feedback update",
        # Attempted mass-assignment fields
        "tenant": tenant_b.pk,
        "number": "SRV-MALICIOUS-6666",
        "created_at": "2020-01-01T00:00:00Z",
    }
    resp = client_a.post(edit_url, malicious_payload)
    assert resp.status_code == 302

    survey.refresh_from_db()
    assert survey.tenant == tenant_a
    assert survey.number == original_number
    assert survey.rating_score == 4


# ==============================================================================
# 4. XSS & Input Sanitization Tests
# ==============================================================================

def test_customersupport_xss_ticket_escaping(client_a, tenant_a):
    """Malicious script injection payloads in ticket fields are properly HTML-escaped."""
    xss_script = '<script>alert("xss-ticket")</script>'
    xss_img = '"><img src=x onerror=alert("xss-img")>'

    ticket = _customersupport_create_ticket(
        tenant_a,
        subject=xss_script,
        customer_name=xss_img,
        initial_message=f"Need help! {xss_script}",
        resolution_summary=f"Resolved via {xss_img}",
        internal_notes=f"Note: {xss_script}",
    )

    # 1. Detail View
    detail_url = reverse("ecommerce:customersupportticket_detail", args=[ticket.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_script.encode() not in resp_detail.content
    assert b'onerror=alert("xss-img")' not in resp_detail.content
    assert b"&lt;script&gt;alert(&quot;xss-ticket&quot;)&lt;/script&gt;" in resp_detail.content
    assert b"&lt;img src=x" in resp_detail.content

    # 2. List View
    list_url = reverse("ecommerce:customersupportticket_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_script.encode() not in resp_list.content
    assert b"&lt;script&gt;alert(" in resp_list.content


def test_customersupport_xss_article_escaping(client_a, tenant_a):
    """Malicious scripts in Knowledge Base article fields are HTML-escaped."""
    xss_title = '<script>alert("xss-article-title")</script>'
    xss_body = '<script>alert("xss-article-content")</script>'

    article = _customersupport_create_article(
        tenant_a,
        title=xss_title,
        summary='"><img src=x onerror=alert("xss-summary")>',
        content=f"Documentation: {xss_body}",
        keywords='"><script>alert("xss-keywords")</script>',
    )

    # 1. Detail View
    detail_url = reverse("ecommerce:knowledgebasearticle_detail", args=[article.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_title.encode() not in resp_detail.content
    assert xss_body.encode() not in resp_detail.content
    assert b"&lt;script&gt;alert(&quot;xss-article-title&quot;)&lt;/script&gt;" in resp_detail.content
    assert b"&lt;script&gt;alert(&quot;xss-article-content&quot;)&lt;/script&gt;" in resp_detail.content

    # 2. List View
    list_url = reverse("ecommerce:knowledgebasearticle_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_title.encode() not in resp_list.content


def test_customersupport_xss_claim_escaping(client_a, tenant_a, ecom_order_a):
    """Malicious scripts in Order Issue Claim notes and tracking number are HTML-escaped."""
    xss_notes = '<script>alert("xss-claim-notes")</script>'
    xss_dec = '"><img src=x onerror=alert("xss-decision")>'

    claim = _customersupport_create_claim(
        tenant_a,
        order=ecom_order_a,
        customer_notes=f"Damaged item: {xss_notes}",
        decision_notes=f"Review disposition: {xss_dec}",
        carrier_tracking_number='"><script>alert("xss-track")</script>',
    )

    # 1. Detail View
    detail_url = reverse("ecommerce:orderissueclaim_detail", args=[claim.pk])
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert xss_notes.encode() not in resp_detail.content
    assert b'onerror=alert("xss-decision")' not in resp_detail.content
    assert b"&lt;script&gt;alert(&quot;xss-claim-notes&quot;)&lt;/script&gt;" in resp_detail.content

    # 2. List View
    list_url = reverse("ecommerce:orderissueclaim_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert xss_notes.encode() not in resp_list.content


def test_customersupport_xss_claim_photo_evidence_url_breakout_prevented(client_a, tenant_a, ecom_order_a):
    """Photo evidence URL with payload cannot break out of HTML img or a tags (stored XSS defense)."""
    malicious_url = 'https://example.com/damage.jpg"><script>alert("xss-photo")</script><img src="'

    claim = _customersupport_create_claim(
        tenant_a,
        order=ecom_order_a,
        photo_evidence_url=malicious_url,
    )

    detail_url = reverse("ecommerce:orderissueclaim_detail", args=[claim.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200

    # Ensure raw unescaped script tag is not present
    assert b'<script>alert("xss-photo")</script>' not in resp.content
    # Ensure double quote was converted to &quot; preventing tag breakout
    assert b'&quot;&gt;&lt;script&gt;alert(&quot;xss-photo&quot;)&lt;/script&gt;' in resp.content


def test_customersupport_xss_survey_escaping(client_a, tenant_a):
    """Malicious scripts in Customer Satisfaction Survey verbatim feedback are HTML-escaped."""
    xss_feedback = '<script>alert("xss-survey-feedback")</script>'
    xss_follow_up = '"><img src=x onerror=alert("xss-followup")>'

    survey = _customersupport_create_survey(
        tenant_a,
        feedback_comment=xss_feedback,
        follow_up_notes=xss_follow_up,
    )

    detail_url = reverse("ecommerce:customersatisfactionsurvey_detail", args=[survey.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert xss_feedback.encode() not in resp.content
    assert b'onerror=alert("xss-followup")' not in resp.content
    assert b"&lt;script&gt;alert(&quot;xss-survey-feedback&quot;)&lt;/script&gt;" in resp.content


# ==============================================================================
# 5. Audit Logging Forensics Tests
# ==============================================================================

def test_customersupport_ticket_audit_log_forensics(client_a, tenant_a, admin_user):
    """CustomerSupportTicket mutations generate AuditLog rows and deletion captures valid integer object_id."""
    # 1. Create
    create_url = reverse("ecommerce:customersupportticket_create")
    resp_create = client_a.post(
        create_url,
        {
            "subject": "Audit Trail Verification Ticket",
            "customer_name": "Audit Customer",
            "customer_email": "audit.cust@example.com",
            "channel": "email",
            "category": "order_tracking_wismo",
            "priority": "high",
            "status": "new",
            "initial_message": "Testing audit log creation action.",
        },
    )
    assert resp_create.status_code == 302
    ticket = CustomerSupportTicket.objects.filter(tenant=tenant_a, subject="Audit Trail Verification Ticket").first()
    assert ticket is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=ticket.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("number") == ticket.number
    assert log_create.changes.get("priority") == "high"

    # 2. Update
    edit_url = reverse("ecommerce:customersupportticket_edit", args=[ticket.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "subject": "Audit Trail Verification Ticket",
            "customer_name": "Audit Customer",
            "customer_email": "audit.cust@example.com",
            "channel": "email",
            "category": "order_tracking_wismo",
            "priority": "urgent",
            "status": "open",
            "initial_message": "Testing audit log creation action.",
        },
    )
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=ticket.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("status") == "open"
    assert log_update.changes.get("priority") == "urgent"

    # 3. Delete
    tkt_pk = ticket.pk
    tkt_number = ticket.number
    delete_url = reverse("ecommerce:customersupportticket_delete", args=[tkt_pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=tkt_number,
    ).first()
    assert log_delete is not None
    # Crucial forensic check: object_id must NOT be None on deletion
    assert log_delete.object_id is not None
    assert log_delete.object_id == tkt_pk


def test_customersupport_article_audit_log_forensics(client_a, tenant_a, admin_user):
    """KnowledgeBaseArticle mutations generate AuditLog rows and deletion captures valid integer object_id."""
    # 1. Create
    create_url = reverse("ecommerce:knowledgebasearticle_create")
    resp_create = client_a.post(
        create_url,
        {
            "title": "Audit KB Article Title",
            "category": "shipping_delivery",
            "summary": "Summary for audit verification.",
            "content": "Full article body content for audit.",
            "status": "published",
            "target_audience": "all_visitors",
        },
    )
    assert resp_create.status_code == 302
    article = KnowledgeBaseArticle.objects.filter(tenant=tenant_a, title="Audit KB Article Title").first()
    assert article is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=article.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("number") == article.number

    # 2. Update
    edit_url = reverse("ecommerce:knowledgebasearticle_edit", args=[article.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "title": "Audit KB Article Title Updated",
            "category": "shipping_delivery",
            "summary": "Summary for audit verification.",
            "content": "Full article body content for audit.",
            "status": "archived",
            "target_audience": "all_visitors",
        },
    )
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=article.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("status") == "archived"

    # 3. Delete
    art_pk = article.pk
    art_number = article.number
    delete_url = reverse("ecommerce:knowledgebasearticle_delete", args=[art_pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=art_number,
    ).first()
    assert log_delete is not None
    assert log_delete.object_id is not None
    assert log_delete.object_id == art_pk


def test_customersupport_claim_audit_log_forensics(client_a, tenant_a, admin_user, ecom_order_a):
    """OrderIssueClaim mutations generate AuditLog rows and deletion captures valid integer object_id."""
    # 1. Create
    create_url = reverse("ecommerce:orderissueclaim_create")
    resp_create = client_a.post(
        create_url,
        {
            "order": ecom_order_a.pk,
            "claim_type": "damaged_item",
            "status": "submitted",
            "claimed_amount": "60.00",
            "resolution_action": "replacement_reship",
            "customer_notes": "Claim created for audit trail testing.",
        },
    )
    assert resp_create.status_code == 302
    claim = OrderIssueClaim.objects.filter(tenant=tenant_a, customer_notes="Claim created for audit trail testing.").first()
    assert claim is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=claim.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("number") == claim.number

    # 2. Update
    edit_url = reverse("ecommerce:orderissueclaim_edit", args=[claim.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "order": ecom_order_a.pk,
            "claim_type": "damaged_item",
            "status": "approved",
            "claimed_amount": "60.00",
            "approved_amount": "60.00",
            "resolution_action": "full_refund",
            "customer_notes": "Claim created for audit trail testing.",
        },
    )
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=claim.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("status") == "approved"
    assert log_update.changes.get("resolution_action") == "full_refund"

    # 3. Delete
    clm_pk = claim.pk
    clm_number = claim.number
    delete_url = reverse("ecommerce:orderissueclaim_delete", args=[clm_pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=clm_number,
    ).first()
    assert log_delete is not None
    assert log_delete.object_id is not None
    assert log_delete.object_id == clm_pk


def test_customersupport_survey_audit_log_forensics(client_a, tenant_a, admin_user):
    """CustomerSatisfactionSurvey mutations generate AuditLog rows and deletion captures valid integer object_id."""
    # 1. Create
    create_url = reverse("ecommerce:customersatisfactionsurvey_create")
    resp_create = client_a.post(
        create_url,
        {
            "survey_type": "ticket_csat",
            "rating_score": 5,
            "sentiment": "positive",
            "follow_up_status": "not_required",
            "feedback_comment": "Audit survey initial comment.",
        },
    )
    assert resp_create.status_code == 302
    survey = CustomerSatisfactionSurvey.objects.filter(tenant=tenant_a, feedback_comment="Audit survey initial comment.").first()
    assert survey is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=survey.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("number") == survey.number
    assert log_create.changes.get("rating") == 5

    # 2. Update
    edit_url = reverse("ecommerce:customersatisfactionsurvey_edit", args=[survey.pk])
    resp_edit = client_a.post(
        edit_url,
        {
            "survey_type": "ticket_csat",
            "rating_score": 2,
            "sentiment": "negative",
            "follow_up_status": "pending_review",
            "feedback_comment": "Audit survey updated comment.",
        },
    )
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=survey.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("sentiment") == "negative"
    assert log_update.changes.get("follow_up_status") == "pending_review"

    # 3. Delete
    srv_pk = survey.pk
    srv_number = survey.number
    delete_url = reverse("ecommerce:customersatisfactionsurvey_delete", args=[srv_pk])
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        changes__number=srv_number,
    ).first()
    assert log_delete is not None
    assert log_delete.object_id is not None
    assert log_delete.object_id == srv_pk


def test_customersupport_audit_log_cross_tenant_isolation(client_a, tenant_a, tenant_b, admin_user):
    """Mutations performed in Tenant A never generate or contaminate AuditLog records for Tenant B."""
    initial_tenant_b_count = AuditLog.objects.filter(tenant=tenant_b).count()

    # Perform create, edit, and delete in Tenant A
    create_url = reverse("ecommerce:customersupportticket_create")
    client_a.post(
        create_url,
        {
            "subject": "Isolation Audit Ticket",
            "customer_name": "Audit Iso User",
            "customer_email": "iso@example.com",
            "channel": "email",
            "category": "general",
            "priority": "low",
            "status": "new",
            "initial_message": "Cross tenant audit separation check.",
        },
    )
    ticket = CustomerSupportTicket.objects.filter(tenant=tenant_a, subject="Isolation Audit Ticket").first()
    assert ticket is not None

    edit_url = reverse("ecommerce:customersupportticket_edit", args=[ticket.pk])
    client_a.post(
        edit_url,
        {
            "subject": "Isolation Audit Ticket Edited",
            "customer_name": "Audit Iso User",
            "customer_email": "iso@example.com",
            "channel": "email",
            "category": "general",
            "priority": "medium",
            "status": "open",
            "initial_message": "Cross tenant audit separation check.",
        },
    )

    delete_url = reverse("ecommerce:customersupportticket_delete", args=[ticket.pk])
    client_a.post(delete_url)

    # Verify AuditLog count for Tenant B remains unchanged
    new_tenant_b_count = AuditLog.objects.filter(tenant=tenant_b).count()
    assert new_tenant_b_count == initial_tenant_b_count, (
        f"Tenant B AuditLog contaminated: expected {initial_tenant_b_count}, got {new_tenant_b_count}"
    )

    # Verify all generated logs have tenant == tenant_a
    recent_logs = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, changes__number=ticket.number)
    assert recent_logs.exists()
    for log in recent_logs:
        assert log.tenant == tenant_a
