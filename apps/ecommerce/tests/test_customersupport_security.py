"""Multi-tenancy, authorization, IDOR, method safety, and security tests for 9.14 Customer Support.

Covers:
1. Authentication protection (unauthenticated redirects across all endpoints)
2. Multi-tenant data isolation & IDOR prevention (cross-tenant detail, edit, delete -> 404)
3. Privileged action authorization (@tenant_admin_required on delete -> 403 for non-admin)
4. Method safety (@require_POST on delete -> 405 on GET)
5. Cross-tenant reference rejection in forms
6. AuditLog generation on mutating operations
7. XSS sanitization in template rendering
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    CustomerSatisfactionSurvey,
    CustomerSupportTicket,
    KnowledgeBaseArticle,
    OrderIssueClaim,
)
from apps.ecommerce.tests.conftest import CUSTOMERSUPPORT_URLS


# ==============================================================================
# 1. Unauthenticated Requests Redirect to Login
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_unauthenticated_redirects(client, ecom_customersupport_ticket_a, ecom_customersupport_article_a, ecom_customersupport_claim_a, ecom_customersupport_survey_a):
    """Verify all 20 customer support URLs require authentication."""
    pk_map = {
        "customersupportticket": ecom_customersupport_ticket_a.pk,
        "knowledgebasearticle": ecom_customersupport_article_a.pk,
        "orderissueclaim": ecom_customersupport_claim_a.pk,
        "customersatisfactionsurvey": ecom_customersupport_survey_a.pk,
    }

    for url_name in CUSTOMERSUPPORT_URLS.keys():
        entity = url_name.split("_")[0]
        if "<int:pk>" in CUSTOMERSUPPORT_URLS[url_name]:
            url = reverse(f"ecommerce:{url_name}", kwargs={"pk": pk_map[entity]})
        else:
            url = reverse(f"ecommerce:{url_name}")

        response = client.get(url)
        assert response.status_code == 302, f"Expected redirect for unauthenticated {url_name}"
        assert "/accounts/login/" in response.url or "/login/" in response.url


# ==============================================================================
# 2. Multi-Tenant IDOR Protection (Cross-Tenant -> 404)
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_ticket_cross_tenant_idor(
    client_b, ecom_customersupport_ticket_a
):
    """Tenant B user cannot view, edit, or delete Tenant A ticket."""
    pk = ecom_customersupport_ticket_a.pk

    detail_url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:customersupportticket_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:customersupportticket_delete", kwargs={"pk": pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"subject": "Hacked"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_customersupport_article_cross_tenant_idor(
    client_b, ecom_customersupport_article_a
):
    """Tenant B user cannot view, edit, or delete Tenant A knowledge article."""
    pk = ecom_customersupport_article_a.pk

    detail_url = reverse("ecommerce:knowledgebasearticle_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:knowledgebasearticle_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"title": "Hacked"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_customersupport_claim_cross_tenant_idor(
    client_b, ecom_customersupport_claim_a
):
    """Tenant B user cannot view, edit, or delete Tenant A order claim."""
    pk = ecom_customersupport_claim_a.pk

    detail_url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:orderissueclaim_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"customer_notes": "Hacked"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_customersupport_survey_cross_tenant_idor(
    client_b, ecom_customersupport_survey_a
):
    """Tenant B user cannot view, edit, or delete Tenant A survey."""
    pk = ecom_customersupport_survey_a.pk

    detail_url = reverse("ecommerce:customersatisfactionsurvey_detail", kwargs={"pk": pk})
    edit_url = reverse("ecommerce:customersatisfactionsurvey_edit", kwargs={"pk": pk})
    delete_url = reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": pk})

    assert client_b.get(detail_url).status_code == 404
    assert client_b.get(edit_url).status_code == 404
    assert client_b.post(edit_url, {"feedback_comment": "Hacked"}).status_code == 404
    assert client_b.post(delete_url).status_code == 404


# ==============================================================================
# 3. Privileged Actions Authorization (@tenant_admin_required)
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_non_admin_cannot_delete(
    client_a_staff,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """Non-admin authenticated staff receives 403 Forbidden on delete endpoints."""
    urls = [
        reverse("ecommerce:customersupportticket_delete", kwargs={"pk": ecom_customersupport_ticket_a.pk}),
        reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": ecom_customersupport_article_a.pk}),
        reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": ecom_customersupport_claim_a.pk}),
        reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": ecom_customersupport_survey_a.pk}),
    ]

    for url in urls:
        response = client_a_staff.post(url)
        assert response.status_code == 403, f"Non-admin staff should be forbidden on {url}"


# ==============================================================================
# 4. Method Safety (@require_POST on Delete Endpoints)
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_delete_get_method_not_allowed(
    client_a,
    ecom_customersupport_ticket_a,
    ecom_customersupport_article_a,
    ecom_customersupport_claim_a,
    ecom_customersupport_survey_a,
):
    """GET requests to delete endpoints return 405 Method Not Allowed."""
    urls = [
        reverse("ecommerce:customersupportticket_delete", kwargs={"pk": ecom_customersupport_ticket_a.pk}),
        reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": ecom_customersupport_article_a.pk}),
        reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": ecom_customersupport_claim_a.pk}),
        reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": ecom_customersupport_survey_a.pk}),
    ]

    for url in urls:
        response = client_a.get(url)
        assert response.status_code == 405, f"GET on delete endpoint {url} should return 405"


# ==============================================================================
# 5. Cross-Tenant FK Reference Protection in Forms
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_claim_rejects_cross_tenant_order(
    client_a, ecom_order_b
):
    """Creating a claim referencing an order belonging to another tenant is rejected."""
    url = reverse("ecommerce:orderissueclaim_create")
    data = {
        "order": ecom_order_b.pk,
        "claim_type": "damaged_item",
        "status": "submitted",
        "claimed_amount": "50.00",
        "approved_amount": "0.00",
        "resolution_action": "pending",
        "customer_notes": "Damaged goods in delivery",
    }
    response = client_a.post(url, data)
    assert response.status_code == 200
    assert "form" in response.context
    form = response.context["form"]
    assert "order" in form.errors


# ==============================================================================
# 6. AuditLog Verification on Mutation
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_ticket_mutation_logs_audit(
    client_a, tenant_a
):
    """Ticket creation logs an AuditLog row scoped to tenant."""
    url = reverse("ecommerce:customersupportticket_create")
    data = {
        "subject": "Audit Log Test Ticket",
        "customer_name": "Audit Customer",
        "customer_email": "audit@example.com",
        "channel": "email",
        "category": "general",
        "priority": "medium",
        "status": "new",
        "initial_message": "Need help with my account",
    }
    initial_log_count = AuditLog.objects.filter(tenant=tenant_a).count()
    response = client_a.post(url, data)
    assert response.status_code == 302

    new_logs = AuditLog.objects.filter(tenant=tenant_a).count()
    assert new_logs > initial_log_count


# ==============================================================================
# 7. XSS Sanitization in Templates
# ==============================================================================


@pytest.mark.django_db
def test_customersupport_xss_escaping(
    client_a, tenant_a, ecom_profile_a
):
    """Dangerous HTML/script tags in ticket subject and message are escaped in template output."""
    ticket = CustomerSupportTicket.objects.create(
        tenant=tenant_a,
        customer=ecom_profile_a,
        subject="<script>alert('xss-subject')</script>",
        customer_name="<b onmouseover='alert(1)'>Hacker</b>",
        customer_email="xss@example.com",
        initial_message="<img src='x' onerror='alert(2)'>",
        status="new",
        priority="high",
        channel="web_form",
        category="general",
    )

    detail_url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": ticket.pk})
    response = client_a.get(detail_url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "<script>alert('xss-subject')</script>" not in content
    assert "&lt;script&gt;alert(&#x27;xss-subject&#x27;)&lt;/script&gt;" in content or "&lt;script&gt;" in content
    assert "<img src='x' onerror='alert(2)'>" not in content
