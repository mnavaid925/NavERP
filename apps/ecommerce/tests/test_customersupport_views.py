"""Unit, route, filter, and CRUD view tests for eCommerce 9.14 Customer Service & Support.

Covers:
1. URL resolution and route name verification for all 20 views (CUSTOMERSUPPORT_URLS).
2. CustomerSupportTicket Views:
   - list with search (?q=), dropdown filters (?status=, ?priority=, ?channel=, ?category=, ?agent=),
     junk parameter resilience (?page=999, ?channel=unknown, ?agent=invalid), pagination, empty list handling,
     and context keys contract.
   - detail view context, rendered order total (total_amount), back button, customer info, and IDOR 404 rejection.
   - create GET (form rendered) and POST (creates ticket, audit log action="create", redirects to detail), invalid POST.
   - edit GET and POST (updates ticket, audit log action="update", redirects to detail), IDOR 404 rejection.
   - delete GET 405 (Method Not Allowed), POST non-admin 403 (tenant admin required),
     POST admin 302 (deletes ticket, writes audit log before delete with valid object_id), IDOR 404 rejection.
3. KnowledgeBaseArticle Views:
   - list with search, category/status/audience filters, pagination, deferred content column, and context keys contract.
   - detail view context, content rendered, view count increment by 1, and IDOR 404 rejection.
   - create GET and POST (sets tenant, auto-sets author, audit log action="create", redirects to detail), invalid POST.
   - edit GET and POST (updates article, audit log action="update", redirects to detail), IDOR 404 rejection.
   - delete GET 405, POST non-admin 403, POST admin 302 (audit log before delete), IDOR 404 rejection.
4. OrderIssueClaim Views:
   - list with search, claim_type/status/resolution filters, select_related("customer__customer"), context contract.
   - detail view context, order total rendered, no inline onerror XSS, back button, and IDOR 404 rejection.
   - create GET and POST (audit log action="create", redirects to detail), invalid POST.
   - edit GET and POST (updates status/action, audit log action="update", redirects to detail), IDOR 404 rejection.
   - delete GET 405, POST non-admin 403, POST admin 302 (audit log before delete), IDOR 404 rejection.
5. CustomerSatisfactionSurvey Views:
   - list with search, survey_type/sentiment/follow_up filters, sentiment badge and text styling, context contract.
   - detail view context, score display, written comment, and IDOR 404 rejection.
   - create GET and POST (audit log action="create", redirects to detail), invalid POST.
   - edit GET and POST (updates sentiment/status, audit log action="update", redirects to detail), IDOR 404 rejection.
   - delete GET 405, POST non-admin 403, POST admin 302 (audit log before delete), IDOR 404 rejection.
6. Authentication & Authorization Gating (Cross-Cutting):
   - Unauthenticated redirect to login for all 20 views.

Conventions enforced:
- Test function prefix: test_customersupport_*
- Module-level helpers: _customersupport_*
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import resolve, reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    CustomerSatisfactionSurvey,
    CustomerSupportTicket,
    KnowledgeBaseArticle,
    OrderIssueClaim,
)
from apps.ecommerce.tests.conftest import (
    CUSTOMERSUPPORT_CHOICES,
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
    """Helper to create a CustomerSupportTicket with defaults."""
    return _customersupport_ticket(tenant, **overrides)


def _customersupport_create_article(tenant, **overrides):
    """Helper to create a KnowledgeBaseArticle with defaults."""
    return _customersupport_article(tenant, **overrides)


def _customersupport_create_claim(tenant, order, **overrides):
    """Helper to create an OrderIssueClaim with defaults."""
    return _customersupport_claim(tenant, order=order, **overrides)


def _customersupport_create_survey(tenant, **overrides):
    """Helper to create a CustomerSatisfactionSurvey with defaults."""
    return _customersupport_survey(tenant, **overrides)


# ==============================================================================
# 1. URL Routing Contract Tests
# ==============================================================================

def test_customersupport_urls_contract():
    """Verify all 20 contract-pinned 9.14 Customer Support routes resolve successfully via reverse()."""
    dummy_pk = 1
    assert len(CUSTOMERSUPPORT_URLS) == 20

    for url_name in CUSTOMERSUPPORT_URLS:
        kwargs = {"pk": dummy_pk} if "<int:pk>" in CUSTOMERSUPPORT_URLS[url_name] else {}
        resolved_url = reverse(f"ecommerce:{url_name}", kwargs=kwargs)
        assert resolved_url is not None
        assert resolved_url.startswith("/ecommerce/customer-support/")

        # Verify Django URL resolver maps to the view name
        match = resolve(resolved_url)
        assert match.view_name == f"ecommerce:{url_name}"
        assert callable(match.func)


# ==============================================================================
# 2. CustomerSupportTicket Views
# ==============================================================================

def test_customersupport_ticket_list_context_and_tenant_isolation(
    client_a, tenant_a, tenant_b, ecom_customersupport_ticket_a, ecom_customersupport_ticket_b
):
    """Ticket list returns 200, provides all expected context keys, and isolates tenant data."""
    url = reverse("ecommerce:customersupportticket_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Verify context keys contract
    expected_keys = [
        "tickets",
        "page_obj",
        "paginator",
        "status_choices",
        "priority_choices",
        "channel_choices",
        "category_choices",
        "agents",
        "selected_status",
        "selected_priority",
        "selected_channel",
        "selected_category",
        "selected_agent",
        "query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Missing context key: {key}"

    # Verify choices match model definition
    assert resp.context["status_choices"] == CustomerSupportTicket.STATUS_CHOICES
    assert resp.context["priority_choices"] == CustomerSupportTicket.PRIORITY_CHOICES
    assert resp.context["channel_choices"] == CustomerSupportTicket.CHANNEL_CHOICES
    assert resp.context["category_choices"] == CustomerSupportTicket.CATEGORY_CHOICES

    # Tenant scoping: tenant_a sees ticket_a but not ticket_b
    ticket_ids = [t.pk for t in resp.context["tickets"]]
    assert ecom_customersupport_ticket_a.pk in ticket_ids
    assert ecom_customersupport_ticket_b.pk not in ticket_ids


def test_customersupport_ticket_list_search_filters(client_a, tenant_a):
    """Ticket list filters by text search (?q=) across subject, number, customer_name, and initial_message."""
    url = reverse("ecommerce:customersupportticket_list")

    t1 = _customersupport_create_ticket(
        tenant_a,
        subject="Payment Failed Checkout",
        customer_name="Alice Smith",
        initial_message="Card got declined at final checkout step.",
    )
    t2 = _customersupport_create_ticket(
        tenant_a,
        subject="Warranty Replacement",
        customer_name="Bob Jones",
        initial_message="Speaker chassis arrived completely cracked.",
    )

    # Search by subject keyword
    resp1 = client_a.get(url, {"q": "Checkout"})
    assert resp1.status_code == 200
    ids1 = [t.pk for t in resp1.context["tickets"]]
    assert t1.pk in ids1
    assert t2.pk not in ids1

    # Search by customer name
    resp2 = client_a.get(url, {"q": "Bob Jones"})
    assert resp2.status_code == 200
    ids2 = [t.pk for t in resp2.context["tickets"]]
    assert t2.pk in ids2
    assert t1.pk not in ids2

    # Search by ticket number
    resp3 = client_a.get(url, {"q": t1.number})
    assert resp3.status_code == 200
    ids3 = [t.pk for t in resp3.context["tickets"]]
    assert t1.pk in ids3
    assert t2.pk not in ids3


def test_customersupport_ticket_list_dropdown_filters(client_a, tenant_a, admin_user):
    """Ticket list filters by dropdown selections (?status=, ?priority=, ?channel=, ?category=, ?agent=)."""
    url = reverse("ecommerce:customersupportticket_list")

    t_urgent = _customersupport_create_ticket(
        tenant_a,
        status="open",
        priority="urgent",
        channel="chat",
        category="order_tracking_wismo",
        assigned_agent=admin_user,
    )
    t_low = _customersupport_create_ticket(
        tenant_a,
        status="resolved",
        priority="low",
        channel="email",
        category="product_inquiry",
        assigned_agent=None,
    )

    # Filter status
    resp_status = client_a.get(url, {"status": "open"})
    ids = [t.pk for t in resp_status.context["tickets"]]
    assert t_urgent.pk in ids
    assert t_low.pk not in ids

    # Filter priority
    resp_prio = client_a.get(url, {"priority": "urgent"})
    ids = [t.pk for t in resp_prio.context["tickets"]]
    assert t_urgent.pk in ids
    assert t_low.pk not in ids

    # Filter channel
    resp_chan = client_a.get(url, {"channel": "chat"})
    ids = [t.pk for t in resp_chan.context["tickets"]]
    assert t_urgent.pk in ids
    assert t_low.pk not in ids

    # Filter category
    resp_cat = client_a.get(url, {"category": "product_inquiry"})
    ids = [t.pk for t in resp_cat.context["tickets"]]
    assert t_low.pk in ids
    assert t_urgent.pk not in ids

    # Filter assigned agent
    resp_agent = client_a.get(url, {"agent": str(admin_user.pk)})
    ids = [t.pk for t in resp_agent.context["tickets"]]
    assert t_urgent.pk in ids
    assert t_low.pk not in ids


def test_customersupport_ticket_list_junk_parameters(client_a, tenant_a, ecom_customersupport_ticket_a):
    """Ticket list handles junk query parameters gracefully without throwing 500s."""
    url = reverse("ecommerce:customersupportticket_list")

    # Non-existent page number defaults to last page
    resp_junk_page = client_a.get(url, {"page": "999"})
    assert resp_junk_page.status_code == 200
    assert resp_junk_page.context["page_obj"].number == resp_junk_page.context["paginator"].num_pages

    # Invalid channel choice results in empty list, no crash
    resp_junk_channel = client_a.get(url, {"channel": "carrier_pigeon_unknown"})
    assert resp_junk_channel.status_code == 200
    assert len(resp_junk_channel.context["tickets"]) == 0

    # Non-digit agent filter is safely ignored
    resp_junk_agent = client_a.get(url, {"agent": "abc_not_a_number"})
    assert resp_junk_agent.status_code == 200
    ids = [t.pk for t in resp_junk_agent.context["tickets"]]
    assert ecom_customersupport_ticket_a.pk in ids


def test_customersupport_ticket_list_pagination(client_a, tenant_a):
    """Ticket list paginates cleanly at 15 items per page."""
    url = reverse("ecommerce:customersupportticket_list")
    # Clean out any previous tickets to test exact 15 boundary
    CustomerSupportTicket.objects.filter(tenant=tenant_a).delete()

    tickets = [_customersupport_create_ticket(tenant_a, subject=f"Ticket {i}") for i in range(18)]

    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["tickets"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["tickets"]) == 3
    assert not resp_p2.context["page_obj"].has_next()


def test_customersupport_ticket_list_empty(client_a, tenant_a):
    """Ticket list handles 0 records gracefully."""
    CustomerSupportTicket.objects.filter(tenant=tenant_a).delete()
    url = reverse("ecommerce:customersupportticket_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert len(resp.context["tickets"]) == 0
    assert resp.context["paginator"].count == 0


def test_customersupport_ticket_detail_view_content(
    client_a, tenant_a, ecom_profile_a, ecom_order_a, admin_user
):
    """Ticket detail displays subject, ticket number, customer name, order total, and back button."""
    ticket = _customersupport_create_ticket(
        tenant_a,
        customer=ecom_profile_a,
        order=ecom_order_a,
        assigned_agent=admin_user,
        subject="Missing Package Investigation",
        customer_name="Eleanor Rigby",
        customer_email="eleanor@example.com",
    )
    url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": ticket.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["ticket"] == ticket

    content = resp.content.decode()
    assert ticket.number in content
    assert "Missing Package Investigation" in content
    assert "Eleanor Rigby" in content
    # Order total rendered as total_amount
    assert str(ecom_order_a.total_amount) in content
    # Back button navigation link present
    back_url = reverse("ecommerce:customersupportticket_list")
    assert f'href="{back_url}"' in content


def test_customersupport_ticket_detail_idor_404(client_a, tenant_b, ecom_customersupport_ticket_b):
    """Tenant A cannot view Tenant B's support ticket (returns 404)."""
    url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": ecom_customersupport_ticket_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_ticket_create_get(client_a, tenant_a):
    """Ticket create GET returns 200 with blank form and ticket=None."""
    url = reverse("ecommerce:customersupportticket_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["ticket"] is None


def test_customersupport_ticket_create_post_success_and_audit(client_a, tenant_a, admin_user):
    """Ticket create POST creates record, sets tenant, writes AuditLog, and redirects."""
    url = reverse("ecommerce:customersupportticket_create")
    payload = {
        "subject": "Delivery Delayed Beyond ETA",
        "customer_name": "Samantha Swift",
        "customer_email": "samantha@example.com",
        "customer_phone": "+1 555-0123",
        "channel": "email",
        "category": "order_tracking_wismo",
        "priority": "high",
        "status": "new",
        "initial_message": "My package was expected yesterday but has not arrived.",
        "resolution_summary": "",
        "internal_notes": "Carrier tracking shows sorting facility delay.",
        "assigned_agent": str(admin_user.pk),
    }

    resp = client_a.post(url, data=payload)
    created = CustomerSupportTicket.objects.filter(
        tenant=tenant_a,
        customer_email="samantha@example.com",
    ).first()
    assert created is not None
    assert created.subject == "Delivery Delayed Beyond ETA"
    assert created.priority == "high"

    # Redirect to detail view
    detail_url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": created.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    # AuditLog written
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes["number"] == created.number


def test_customersupport_ticket_create_post_invalid(client_a, tenant_a):
    """Ticket create POST with invalid data re-renders form with 200 and errors."""
    url = reverse("ecommerce:customersupportticket_create")
    # Missing required subject and customer_name
    payload = {
        "customer_email": "invalid-email-address",
        "initial_message": "",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False
    assert "subject" in resp.context["form"].errors
    assert "customer_email" in resp.context["form"].errors


def test_customersupport_ticket_edit_get(client_a, tenant_a, ecom_customersupport_ticket_a):
    """Ticket edit GET returns 200 with pre-populated form."""
    url = reverse("ecommerce:customersupportticket_edit", kwargs={"pk": ecom_customersupport_ticket_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["ticket"] == ecom_customersupport_ticket_a
    assert resp.context["form"].instance == ecom_customersupport_ticket_a


def test_customersupport_ticket_edit_post_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_ticket_a
):
    """Ticket edit POST updates ticket fields, writes AuditLog, and redirects."""
    url = reverse("ecommerce:customersupportticket_edit", kwargs={"pk": ecom_customersupport_ticket_a.pk})
    payload = {
        "subject": "Updated Ticket Subject",
        "customer_name": ecom_customersupport_ticket_a.customer_name,
        "customer_email": ecom_customersupport_ticket_a.customer_email,
        "customer_phone": ecom_customersupport_ticket_a.customer_phone,
        "channel": ecom_customersupport_ticket_a.channel,
        "category": ecom_customersupport_ticket_a.category,
        "priority": "urgent",
        "status": "resolved",
        "initial_message": ecom_customersupport_ticket_a.initial_message,
        "resolution_summary": "Issue resolved with replacement shipment.",
        "internal_notes": "Supervisor approved overnight reship.",
    }

    resp = client_a.post(url, data=payload)
    detail_url = reverse("ecommerce:customersupportticket_detail", kwargs={"pk": ecom_customersupport_ticket_a.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    ecom_customersupport_ticket_a.refresh_from_db()
    assert ecom_customersupport_ticket_a.priority == "urgent"
    assert ecom_customersupport_ticket_a.status == "resolved"
    assert "Issue resolved" in ecom_customersupport_ticket_a.resolution_summary

    # AuditLog written
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_customersupport_ticket_a.pk),
    ).first()
    assert audit is not None
    assert audit.changes["status"] == "resolved"


def test_customersupport_ticket_edit_idor_404(client_a, tenant_b, ecom_customersupport_ticket_b):
    """Tenant A cannot edit Tenant B's ticket (returns 404)."""
    url = reverse("ecommerce:customersupportticket_edit", kwargs={"pk": ecom_customersupport_ticket_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404

    resp_post = client_a.post(url, {"subject": "Hacked"})
    assert resp_post.status_code == 404


def test_customersupport_ticket_delete_method_not_allowed_get(client_a, ecom_customersupport_ticket_a):
    """GET request to ticket delete URL returns 405 Method Not Allowed."""
    url = reverse("ecommerce:customersupportticket_delete", kwargs={"pk": ecom_customersupport_ticket_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_customersupport_ticket_delete_non_admin_forbidden(member_client, ecom_customersupport_ticket_a):
    """Non-tenant-admin member cannot delete ticket (returns 403 Forbidden)."""
    url = reverse("ecommerce:customersupportticket_delete", kwargs={"pk": ecom_customersupport_ticket_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CustomerSupportTicket.objects.filter(pk=ecom_customersupport_ticket_a.pk).exists()


def test_customersupport_ticket_delete_admin_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_ticket_a
):
    """Tenant admin POST deletes ticket, redirects to list, and writes AuditLog with valid object_id before delete."""
    pk = ecom_customersupport_ticket_a.pk
    number = ecom_customersupport_ticket_a.number
    url = reverse("ecommerce:customersupportticket_delete", kwargs={"pk": pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:customersupportticket_list")
    assert not CustomerSupportTicket.objects.filter(pk=pk).exists()

    # Verify AuditLog logged valid object_id before deletion
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes["number"] == number


def test_customersupport_ticket_delete_idor_404(client_a, tenant_b, ecom_customersupport_ticket_b):
    """Tenant A cannot delete Tenant B's ticket (returns 404)."""
    url = reverse("ecommerce:customersupportticket_delete", kwargs={"pk": ecom_customersupport_ticket_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert CustomerSupportTicket.objects.filter(pk=ecom_customersupport_ticket_b.pk).exists()


# ==============================================================================
# 3. KnowledgeBaseArticle Views
# ==============================================================================

def test_customersupport_article_list_context_and_tenant_isolation(
    client_a, tenant_a, tenant_b, ecom_customersupport_article_a, ecom_customersupport_article_b
):
    """Article list returns 200, passes context contract, and enforces tenant scoping."""
    url = reverse("ecommerce:knowledgebasearticle_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    expected_keys = [
        "articles",
        "page_obj",
        "paginator",
        "category_choices",
        "status_choices",
        "audience_choices",
        "selected_category",
        "selected_status",
        "selected_audience",
        "query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Missing context key: {key}"

    article_ids = [a.pk for a in resp.context["articles"]]
    assert ecom_customersupport_article_a.pk in article_ids
    assert ecom_customersupport_article_b.pk not in article_ids


def test_customersupport_article_list_deferred_content_column(
    client_a, tenant_a, ecom_customersupport_article_a
):
    """Article list queryset defers heavy 'content' column for performance."""
    url = reverse("ecommerce:knowledgebasearticle_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    articles = resp.context["articles"]
    assert len(articles) > 0
    # Content field should be deferred
    assert "content" in articles[0].get_deferred_fields()


def test_customersupport_article_list_search_and_filters(client_a, tenant_a, admin_user):
    """Article list filters by search (?q=) and dropdowns (?category=, ?status=, ?audience=)."""
    url = reverse("ecommerce:knowledgebasearticle_list")

    a1 = _customersupport_create_article(
        tenant_a,
        title="International Shipping Rates",
        slug=f"intl-shipping-{tenant_a.slug}",
        category="shipping_delivery",
        status="published",
        target_audience="all_visitors",
        keywords="customs, duties, international",
        author=admin_user,
    )
    a2 = _customersupport_create_article(
        tenant_a,
        title="B2B Wholesale Tax Exemption",
        slug=f"b2b-tax-{tenant_a.slug}",
        category="account_security",
        status="draft",
        target_audience="b2b_wholesale",
        keywords="reseller, certificate, tax",
        author=admin_user,
    )

    # Search keyword
    resp_q = client_a.get(url, {"q": "Wholesale"})
    ids = [a.pk for a in resp_q.context["articles"]]
    assert a2.pk in ids
    assert a1.pk not in ids

    # Filter category
    resp_cat = client_a.get(url, {"category": "shipping_delivery"})
    ids = [a.pk for a in resp_cat.context["articles"]]
    assert a1.pk in ids
    assert a2.pk not in ids

    # Filter status
    resp_stat = client_a.get(url, {"status": "draft"})
    ids = [a.pk for a in resp_stat.context["articles"]]
    assert a2.pk in ids
    assert a1.pk not in ids

    # Filter audience
    resp_aud = client_a.get(url, {"audience": "b2b_wholesale"})
    ids = [a.pk for a in resp_aud.context["articles"]]
    assert a2.pk in ids
    assert a1.pk not in ids


def test_customersupport_article_list_pagination_and_empty(client_a, tenant_a, admin_user):
    """Article list handles empty list, junk pagination, and multi-page splits."""
    KnowledgeBaseArticle.objects.filter(tenant=tenant_a).delete()
    url = reverse("ecommerce:knowledgebasearticle_list")

    # Empty list
    resp_empty = client_a.get(url)
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["articles"]) == 0

    # Create 17 articles to test 15-per-page pagination
    for i in range(17):
        _customersupport_create_article(
            tenant_a,
            title=f"Article {i}",
            slug=f"art-{i}-{tenant_a.slug}",
            author=admin_user,
        )

    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["articles"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["articles"]) == 2

    # Junk page returns last page
    resp_junk = client_a.get(url, {"page": "invalid_page"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_customersupport_article_detail_view_and_view_count_increment(
    client_a, tenant_a, ecom_customersupport_article_a
):
    """Article detail renders content and increments view_count on each GET request."""
    initial_views = ecom_customersupport_article_a.view_count
    url = reverse("ecommerce:knowledgebasearticle_detail", kwargs={"pk": ecom_customersupport_article_a.pk})

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["article"].pk == ecom_customersupport_article_a.pk

    content = resp.content.decode()
    assert ecom_customersupport_article_a.title in content
    assert ecom_customersupport_article_a.summary in content
    assert ecom_customersupport_article_a.content in content

    # View count incremented by 1
    ecom_customersupport_article_a.refresh_from_db()
    assert ecom_customersupport_article_a.view_count == initial_views + 1
    assert resp.context["article"].view_count == initial_views + 1

    # Second view increments again
    client_a.get(url)
    ecom_customersupport_article_a.refresh_from_db()
    assert ecom_customersupport_article_a.view_count == initial_views + 2


def test_customersupport_article_detail_idor_404(client_a, tenant_b, ecom_customersupport_article_b):
    """Tenant A cannot view Tenant B's article (returns 404)."""
    url = reverse("ecommerce:knowledgebasearticle_detail", kwargs={"pk": ecom_customersupport_article_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_article_create_get(client_a, tenant_a):
    """Article create GET returns 200 with blank form."""
    url = reverse("ecommerce:knowledgebasearticle_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["article"] is None


def test_customersupport_article_create_post_success_and_audit(client_a, tenant_a, admin_user):
    """Article create POST saves article, sets author, writes AuditLog, and redirects to detail."""
    url = reverse("ecommerce:knowledgebasearticle_create")
    payload = {
        "title": "Comprehensive Sizing Guide",
        "slug": f"sizing-guide-{tenant_a.slug}",
        "category": "product_sizing",
        "summary": "Size conversion charts for footwear and apparel.",
        "content": "## Sizing Chart\nMeasure chest and waist for accurate fit.",
        "status": "published",
        "target_audience": "all_visitors",
        "keywords": "size, fit, measurements, footwear, chart",
    }

    resp = client_a.post(url, data=payload)
    created = KnowledgeBaseArticle.objects.filter(
        tenant=tenant_a,
        slug=f"sizing-guide-{tenant_a.slug}",
    ).first()
    assert created is not None
    assert created.author == admin_user
    assert created.status == "published"

    detail_url = reverse("ecommerce:knowledgebasearticle_detail", kwargs={"pk": created.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    # AuditLog written
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None
    assert audit.changes["title"] == "Comprehensive Sizing Guide"


def test_customersupport_article_create_post_invalid(client_a, tenant_a):
    """Article create POST with invalid data returns 200 and re-renders form errors."""
    url = reverse("ecommerce:knowledgebasearticle_create")
    payload = {
        "title": "",  # Required
        "summary": "",  # Required
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False
    assert "title" in resp.context["form"].errors


def test_customersupport_article_edit_get(client_a, tenant_a, ecom_customersupport_article_a):
    """Article edit GET returns 200 with populated form."""
    url = reverse("ecommerce:knowledgebasearticle_edit", kwargs={"pk": ecom_customersupport_article_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["article"] == ecom_customersupport_article_a


def test_customersupport_article_edit_post_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_article_a
):
    """Article edit POST updates record, writes AuditLog, and redirects to detail."""
    url = reverse("ecommerce:knowledgebasearticle_edit", kwargs={"pk": ecom_customersupport_article_a.pk})
    payload = {
        "title": "Updated Return Policies 2026",
        "slug": ecom_customersupport_article_a.slug,
        "category": ecom_customersupport_article_a.category,
        "summary": ecom_customersupport_article_a.summary,
        "content": "Updated return window policy text.",
        "status": "archived",
        "target_audience": ecom_customersupport_article_a.target_audience,
    }

    resp = client_a.post(url, data=payload)
    detail_url = reverse("ecommerce:knowledgebasearticle_detail", kwargs={"pk": ecom_customersupport_article_a.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    ecom_customersupport_article_a.refresh_from_db()
    assert ecom_customersupport_article_a.title == "Updated Return Policies 2026"
    assert ecom_customersupport_article_a.status == "archived"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_customersupport_article_a.pk),
    ).first()
    assert audit is not None
    assert audit.changes["title"] == "Updated Return Policies 2026"


def test_customersupport_article_edit_idor_404(client_a, tenant_b, ecom_customersupport_article_b):
    """Tenant A cannot edit Tenant B's article (returns 404)."""
    url = reverse("ecommerce:knowledgebasearticle_edit", kwargs={"pk": ecom_customersupport_article_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_article_delete_method_not_allowed_get(client_a, ecom_customersupport_article_a):
    """GET request to article delete URL returns 405 Method Not Allowed."""
    url = reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": ecom_customersupport_article_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_customersupport_article_delete_non_admin_forbidden(member_client, ecom_customersupport_article_a):
    """Non-tenant-admin member cannot delete article (returns 403 Forbidden)."""
    url = reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": ecom_customersupport_article_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert KnowledgeBaseArticle.objects.filter(pk=ecom_customersupport_article_a.pk).exists()


def test_customersupport_article_delete_admin_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_article_a
):
    """Tenant admin POST deletes article, redirects to list, and writes AuditLog with valid object_id before delete."""
    pk = ecom_customersupport_article_a.pk
    number = ecom_customersupport_article_a.number
    url = reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:knowledgebasearticle_list")
    assert not KnowledgeBaseArticle.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes["number"] == number


def test_customersupport_article_delete_idor_404(client_a, tenant_b, ecom_customersupport_article_b):
    """Tenant A cannot delete Tenant B's article (returns 404)."""
    url = reverse("ecommerce:knowledgebasearticle_delete", kwargs={"pk": ecom_customersupport_article_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert KnowledgeBaseArticle.objects.filter(pk=ecom_customersupport_article_b.pk).exists()


# ==============================================================================
# 4. OrderIssueClaim Views
# ==============================================================================

def test_customersupport_claim_list_context_and_tenant_isolation(
    client_a, tenant_a, tenant_b, ecom_customersupport_claim_a, ecom_customersupport_claim_b
):
    """Claim list returns 200, passes context contract, select_related, and isolates tenants."""
    url = reverse("ecommerce:orderissueclaim_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    expected_keys = [
        "claims",
        "page_obj",
        "paginator",
        "claim_type_choices",
        "status_choices",
        "resolution_choices",
        "selected_claim_type",
        "selected_status",
        "selected_resolution",
        "query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Missing context key: {key}"

    assert resp.context["claim_type_choices"] == OrderIssueClaim.CLAIM_TYPE_CHOICES
    assert resp.context["status_choices"] == OrderIssueClaim.STATUS_CHOICES
    assert resp.context["resolution_choices"] == OrderIssueClaim.RESOLUTION_CHOICES

    claim_ids = [c.pk for c in resp.context["claims"]]
    assert ecom_customersupport_claim_a.pk in claim_ids
    assert ecom_customersupport_claim_b.pk not in claim_ids


def test_customersupport_claim_list_search_and_filters(
    client_a, tenant_a, ecom_order_a, ecom_profile_a
):
    """Claim list filters by text search (?q=) and dropdowns (?claim_type=, ?status=, ?resolution=)."""
    url = reverse("ecommerce:orderissueclaim_list")

    c1 = _customersupport_create_claim(
        tenant_a,
        order=ecom_order_a,
        customer=ecom_profile_a,
        claim_type="damaged_item",
        status="submitted",
        resolution_action="replacement_reship",
        carrier_tracking_number="TRACK-1111",
        customer_notes="Crushed box received",
    )
    c2 = _customersupport_create_claim(
        tenant_a,
        order=ecom_order_a,
        customer=ecom_profile_a,
        claim_type="wrong_item",
        status="approved",
        resolution_action="full_refund",
        carrier_tracking_number="TRACK-2222",
        customer_notes="Wrong color sneakers delivered",
    )

    # Search tracking number
    resp_q = client_a.get(url, {"q": "TRACK-1111"})
    ids = [c.pk for c in resp_q.context["claims"]]
    assert c1.pk in ids
    assert c2.pk not in ids

    # Filter claim_type
    resp_type = client_a.get(url, {"claim_type": "wrong_item"})
    ids = [c.pk for c in resp_type.context["claims"]]
    assert c2.pk in ids
    assert c1.pk not in ids

    # Filter status
    resp_stat = client_a.get(url, {"status": "approved"})
    ids = [c.pk for c in resp_stat.context["claims"]]
    assert c2.pk in ids
    assert c1.pk not in ids

    # Filter resolution
    resp_res = client_a.get(url, {"resolution": "replacement_reship"})
    ids = [c.pk for c in resp_res.context["claims"]]
    assert c1.pk in ids
    assert c2.pk not in ids


def test_customersupport_claim_list_pagination_and_empty(client_a, tenant_a, ecom_order_a):
    """Claim list handles pagination and empty list cleanly."""
    OrderIssueClaim.objects.filter(tenant=tenant_a).delete()
    url = reverse("ecommerce:orderissueclaim_list")

    resp_empty = client_a.get(url)
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["claims"]) == 0

    for i in range(16):
        _customersupport_create_claim(tenant_a, order=ecom_order_a)

    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["claims"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["claims"]) == 1


def test_customersupport_claim_detail_view_content(
    client_a, tenant_a, ecom_customersupport_claim_a
):
    """Claim detail renders claim info, order total, and back button."""
    url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": ecom_customersupport_claim_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["claim"] == ecom_customersupport_claim_a

    content = resp.content.decode()
    assert ecom_customersupport_claim_a.number in content
    assert str(ecom_customersupport_claim_a.order.total_amount) in content
    assert str(ecom_customersupport_claim_a.claimed_amount) in content
    back_url = reverse("ecommerce:orderissueclaim_list")
    assert f'href="{back_url}"' in content


def test_customersupport_claim_detail_xss_resilience(
    client_a, tenant_a, ecom_order_a
):
    """Claim detail does not render unescaped onerror attribute or inline XSS from photo_evidence_url."""
    malicious_url = 'https://example.com/photo.jpg" onerror="alert(1)'
    claim = _customersupport_create_claim(
        tenant_a,
        order=ecom_order_a,
        photo_evidence_url=malicious_url,
    )
    url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": claim.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    content = resp.content.decode()
    # Django auto-escaping transforms double quotes into &quot;
    assert 'onerror="alert(1)"' not in content
    assert '&quot;' in content or '&#x27;' in content or 'onerror=&quot;alert(1)&quot;' in content


def test_customersupport_claim_detail_idor_404(client_a, tenant_b, ecom_customersupport_claim_b):
    """Tenant A cannot view Tenant B's claim (returns 404)."""
    url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": ecom_customersupport_claim_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_claim_create_get(client_a, tenant_a):
    """Claim create GET returns 200 with blank form."""
    url = reverse("ecommerce:orderissueclaim_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["claim"] is None


def test_customersupport_claim_create_post_success_and_audit(
    client_a, tenant_a, admin_user, ecom_order_a, ecom_profile_a
):
    """Claim create POST saves claim, writes AuditLog, and redirects to detail."""
    url = reverse("ecommerce:orderissueclaim_create")
    payload = {
        "order": str(ecom_order_a.pk),
        "customer": str(ecom_profile_a.pk),
        "claim_type": "lost_in_transit",
        "status": "submitted",
        "claimed_amount": "89.50",
        "approved_amount": "0.00",
        "resolution_action": "pending",
        "carrier_tracking_number": "TRK987654321",
        "customer_notes": "Carrier states delivered on porch but no package found.",
    }

    resp = client_a.post(url, data=payload)
    created = OrderIssueClaim.objects.filter(
        tenant=tenant_a,
        carrier_tracking_number="TRK987654321",
    ).first()
    assert created is not None
    assert created.claim_type == "lost_in_transit"
    assert created.claimed_amount == Decimal("89.50")

    detail_url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": created.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None
    assert audit.changes["claim_type"] == "lost_in_transit"


def test_customersupport_claim_create_post_invalid(client_a, tenant_a):
    """Claim create POST with invalid data returns 200 and re-renders form errors."""
    url = reverse("ecommerce:orderissueclaim_create")
    payload = {
        "order": "",  # Missing required order
        "claim_type": "invalid_type",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False
    assert "order" in resp.context["form"].errors


def test_customersupport_claim_edit_get(client_a, tenant_a, ecom_customersupport_claim_a):
    """Claim edit GET returns 200 with pre-populated form."""
    url = reverse("ecommerce:orderissueclaim_edit", kwargs={"pk": ecom_customersupport_claim_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["claim"] == ecom_customersupport_claim_a


def test_customersupport_claim_edit_post_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_claim_a
):
    """Claim edit POST updates resolution and amount, writes AuditLog, and redirects."""
    url = reverse("ecommerce:orderissueclaim_edit", kwargs={"pk": ecom_customersupport_claim_a.pk})
    payload = {
        "order": str(ecom_customersupport_claim_a.order.pk),
        "customer": str(ecom_customersupport_claim_a.customer.pk) if ecom_customersupport_claim_a.customer else "",
        "claim_type": ecom_customersupport_claim_a.claim_type,
        "status": "approved",
        "claimed_amount": str(ecom_customersupport_claim_a.claimed_amount),
        "approved_amount": "49.99",
        "resolution_action": "full_refund",
        "decision_notes": "Carrier investigation confirmed package lost in transfer hub.",
        "customer_notes": ecom_customersupport_claim_a.customer_notes,
    }

    resp = client_a.post(url, data=payload)
    detail_url = reverse("ecommerce:orderissueclaim_detail", kwargs={"pk": ecom_customersupport_claim_a.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    ecom_customersupport_claim_a.refresh_from_db()
    assert ecom_customersupport_claim_a.status == "approved"
    assert ecom_customersupport_claim_a.approved_amount == Decimal("49.99")
    assert ecom_customersupport_claim_a.resolution_action == "full_refund"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_customersupport_claim_a.pk),
    ).first()
    assert audit is not None
    assert audit.changes["status"] == "approved"
    assert audit.changes["resolution_action"] == "full_refund"


def test_customersupport_claim_edit_idor_404(client_a, tenant_b, ecom_customersupport_claim_b):
    """Tenant A cannot edit Tenant B's claim (returns 404)."""
    url = reverse("ecommerce:orderissueclaim_edit", kwargs={"pk": ecom_customersupport_claim_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_claim_delete_method_not_allowed_get(client_a, ecom_customersupport_claim_a):
    """GET request to claim delete URL returns 405 Method Not Allowed."""
    url = reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": ecom_customersupport_claim_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_customersupport_claim_delete_non_admin_forbidden(member_client, ecom_customersupport_claim_a):
    """Non-tenant-admin member cannot delete claim (returns 403 Forbidden)."""
    url = reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": ecom_customersupport_claim_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert OrderIssueClaim.objects.filter(pk=ecom_customersupport_claim_a.pk).exists()


def test_customersupport_claim_delete_admin_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_claim_a
):
    """Tenant admin POST deletes claim, redirects to list, and writes AuditLog with valid object_id before delete."""
    pk = ecom_customersupport_claim_a.pk
    number = ecom_customersupport_claim_a.number
    url = reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:orderissueclaim_list")
    assert not OrderIssueClaim.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes["number"] == number


def test_customersupport_claim_delete_idor_404(client_a, tenant_b, ecom_customersupport_claim_b):
    """Tenant A cannot delete Tenant B's claim (returns 404)."""
    url = reverse("ecommerce:orderissueclaim_delete", kwargs={"pk": ecom_customersupport_claim_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert OrderIssueClaim.objects.filter(pk=ecom_customersupport_claim_b.pk).exists()


# ==============================================================================
# 5. CustomerSatisfactionSurvey Views
# ==============================================================================

def test_customersupport_survey_list_context_and_tenant_isolation(
    client_a, tenant_a, tenant_b, ecom_customersupport_survey_a, ecom_customersupport_survey_b
):
    """Survey list returns 200, passes context contract, and enforces tenant scoping."""
    url = reverse("ecommerce:customersatisfactionsurvey_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    expected_keys = [
        "surveys",
        "page_obj",
        "paginator",
        "survey_type_choices",
        "sentiment_choices",
        "follow_up_choices",
        "selected_survey_type",
        "selected_sentiment",
        "selected_follow_up",
        "query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Missing context key: {key}"

    assert resp.context["survey_type_choices"] == CustomerSatisfactionSurvey.SURVEY_TYPE_CHOICES
    assert resp.context["sentiment_choices"] == CustomerSatisfactionSurvey.SENTIMENT_CHOICES
    assert resp.context["follow_up_choices"] == CustomerSatisfactionSurvey.FOLLOW_UP_CHOICES

    survey_ids = [s.pk for s in resp.context["surveys"]]
    assert ecom_customersupport_survey_a.pk in survey_ids
    assert ecom_customersupport_survey_b.pk not in survey_ids


def test_customersupport_survey_list_sentiment_styling(client_a, tenant_a):
    """Survey list renders appropriate color badge and text classes per sentiment."""
    CustomerSatisfactionSurvey.objects.filter(tenant=tenant_a).delete()

    s_pos = _customersupport_create_survey(
        tenant_a,
        rating_score=5,
        sentiment="positive",
        feedback_comment="Phenomenal quick resolution!",
    )
    s_neu = _customersupport_create_survey(
        tenant_a,
        rating_score=3,
        sentiment="neutral",
        feedback_comment="Average experience, took a while.",
    )
    s_neg = _customersupport_create_survey(
        tenant_a,
        rating_score=1,
        sentiment="negative",
        feedback_comment="Terrible support and rude agent.",
    )

    url = reverse("ecommerce:customersatisfactionsurvey_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    content = resp.content.decode()
    # Positive: badge-green and text-green-700
    assert "badge-green" in content
    assert "text-green-700" in content
    # Neutral: badge-amber and text-amber-600
    assert "badge-amber" in content
    assert "text-amber-600" in content
    # Negative: badge-red and text-red-700
    assert "badge-red" in content
    assert "text-red-700" in content


def test_customersupport_survey_list_search_and_filters(client_a, tenant_a):
    """Survey list filters by text search (?q=) and dropdowns (?survey_type=, ?sentiment=, ?follow_up=)."""
    url = reverse("ecommerce:customersatisfactionsurvey_list")

    s1 = _customersupport_create_survey(
        tenant_a,
        survey_type="ticket_csat",
        sentiment="positive",
        follow_up_status="not_required",
        feedback_comment="Lightning fast reply!",
    )
    s2 = _customersupport_create_survey(
        tenant_a,
        survey_type="storefront_nps",
        sentiment="negative",
        rating_score=2,
        follow_up_status="pending_review",
        feedback_comment="Website checkout bug prevented purchase.",
    )

    # Search keyword
    resp_q = client_a.get(url, {"q": "Lightning"})
    ids = [s.pk for s in resp_q.context["surveys"]]
    assert s1.pk in ids
    assert s2.pk not in ids

    # Filter survey_type
    resp_type = client_a.get(url, {"survey_type": "storefront_nps"})
    ids = [s.pk for s in resp_type.context["surveys"]]
    assert s2.pk in ids
    assert s1.pk not in ids

    # Filter sentiment
    resp_sent = client_a.get(url, {"sentiment": "positive"})
    ids = [s.pk for s in resp_sent.context["surveys"]]
    assert s1.pk in ids
    assert s2.pk not in ids

    # Filter follow_up
    resp_fu = client_a.get(url, {"follow_up": "pending_review"})
    ids = [s.pk for s in resp_fu.context["surveys"]]
    assert s2.pk in ids
    assert s1.pk not in ids


def test_customersupport_survey_list_pagination_and_empty(client_a, tenant_a):
    """Survey list handles empty list, junk parameters, and pagination."""
    CustomerSatisfactionSurvey.objects.filter(tenant=tenant_a).delete()
    url = reverse("ecommerce:customersatisfactionsurvey_list")

    resp_empty = client_a.get(url)
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["surveys"]) == 0

    for i in range(16):
        _customersupport_create_survey(tenant_a, feedback_comment=f"Survey {i}")

    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["surveys"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["surveys"]) == 1

    resp_junk = client_a.get(url, {"page": "invalid_page"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_customersupport_survey_detail_view_and_score(
    client_a, tenant_a, ecom_customersupport_survey_a
):
    """Survey detail renders score scorecard, customer feedback comment, and context."""
    url = reverse("ecommerce:customersatisfactionsurvey_detail", kwargs={"pk": ecom_customersupport_survey_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["survey"] == ecom_customersupport_survey_a

    content = resp.content.decode()
    assert ecom_customersupport_survey_a.number in content
    assert str(ecom_customersupport_survey_a.rating_score) in content
    assert ecom_customersupport_survey_a.feedback_comment in content
    back_url = reverse("ecommerce:customersatisfactionsurvey_list")
    assert f'href="{back_url}"' in content


def test_customersupport_survey_detail_idor_404(client_a, tenant_b, ecom_customersupport_survey_b):
    """Tenant A cannot view Tenant B's survey (returns 404)."""
    url = reverse("ecommerce:customersatisfactionsurvey_detail", kwargs={"pk": ecom_customersupport_survey_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_survey_create_get(client_a, tenant_a):
    """Survey create GET returns 200 with blank form."""
    url = reverse("ecommerce:customersatisfactionsurvey_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["survey"] is None


def test_customersupport_survey_create_post_success_and_audit(client_a, tenant_a, admin_user):
    """Survey create POST saves survey, writes AuditLog, and redirects to detail."""
    url = reverse("ecommerce:customersatisfactionsurvey_create")
    payload = {
        "survey_type": "ticket_csat",
        "rating_score": 5,
        "sentiment": "positive",
        "feedback_comment": "Agent went above and beyond to replace my shipment.",
        "follow_up_status": "not_required",
    }

    resp = client_a.post(url, data=payload)
    created = CustomerSatisfactionSurvey.objects.filter(
        tenant=tenant_a,
        feedback_comment="Agent went above and beyond to replace my shipment.",
    ).first()
    assert created is not None
    assert created.rating_score == 5
    assert created.sentiment == "positive"

    detail_url = reverse("ecommerce:customersatisfactionsurvey_detail", kwargs={"pk": created.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None
    assert audit.changes["survey_type"] == "ticket_csat"
    assert audit.changes["rating"] == 5


def test_customersupport_survey_create_post_invalid(client_a, tenant_a):
    """Survey create POST with invalid score returns 200 and re-renders form errors."""
    url = reverse("ecommerce:customersatisfactionsurvey_create")
    # CSAT requires 1 <= score <= 5 (score 9 is invalid)
    payload = {
        "survey_type": "ticket_csat",
        "rating_score": 9,
        "sentiment": "positive",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].is_valid() is False
    assert "rating_score" in resp.context["form"].errors


def test_customersupport_survey_edit_get(client_a, tenant_a, ecom_customersupport_survey_a):
    """Survey edit GET returns 200 with populated form."""
    url = reverse("ecommerce:customersatisfactionsurvey_edit", kwargs={"pk": ecom_customersupport_survey_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["survey"] == ecom_customersupport_survey_a


def test_customersupport_survey_edit_post_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_survey_a
):
    """Survey edit POST updates sentiment and follow-up, writes AuditLog, and redirects."""
    url = reverse("ecommerce:customersatisfactionsurvey_edit", kwargs={"pk": ecom_customersupport_survey_a.pk})
    payload = {
        "survey_type": ecom_customersupport_survey_a.survey_type,
        "rating_score": ecom_customersupport_survey_a.rating_score,
        "sentiment": "positive",
        "feedback_comment": ecom_customersupport_survey_a.feedback_comment,
        "follow_up_status": "resolved_closed_loop",
        "follow_up_notes": "Supervisor followed up via phone; customer confirmed satisfaction.",
    }

    resp = client_a.post(url, data=payload)
    detail_url = reverse("ecommerce:customersatisfactionsurvey_detail", kwargs={"pk": ecom_customersupport_survey_a.pk})
    assert resp.status_code == 302
    assert resp.url == detail_url

    ecom_customersupport_survey_a.refresh_from_db()
    assert ecom_customersupport_survey_a.follow_up_status == "resolved_closed_loop"
    assert "Supervisor followed up" in ecom_customersupport_survey_a.follow_up_notes

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(ecom_customersupport_survey_a.pk),
    ).first()
    assert audit is not None
    assert audit.changes["follow_up_status"] == "resolved_closed_loop"


def test_customersupport_survey_edit_idor_404(client_a, tenant_b, ecom_customersupport_survey_b):
    """Tenant A cannot edit Tenant B's survey (returns 404)."""
    url = reverse("ecommerce:customersatisfactionsurvey_edit", kwargs={"pk": ecom_customersupport_survey_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_customersupport_survey_delete_method_not_allowed_get(client_a, ecom_customersupport_survey_a):
    """GET request to survey delete URL returns 405 Method Not Allowed."""
    url = reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": ecom_customersupport_survey_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_customersupport_survey_delete_non_admin_forbidden(member_client, ecom_customersupport_survey_a):
    """Non-tenant-admin member cannot delete survey (returns 403 Forbidden)."""
    url = reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": ecom_customersupport_survey_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CustomerSatisfactionSurvey.objects.filter(pk=ecom_customersupport_survey_a.pk).exists()


def test_customersupport_survey_delete_admin_success_and_audit(
    client_a, tenant_a, admin_user, ecom_customersupport_survey_a
):
    """Tenant admin POST deletes survey, redirects to list, and writes AuditLog with valid object_id before delete."""
    pk = ecom_customersupport_survey_a.pk
    number = ecom_customersupport_survey_a.number
    url = reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("ecommerce:customersatisfactionsurvey_list")
    assert not CustomerSatisfactionSurvey.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user
    assert audit.changes["number"] == number


def test_customersupport_survey_delete_idor_404(client_a, tenant_b, ecom_customersupport_survey_b):
    """Tenant A cannot delete Tenant B's survey (returns 404)."""
    url = reverse("ecommerce:customersatisfactionsurvey_delete", kwargs={"pk": ecom_customersupport_survey_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert CustomerSatisfactionSurvey.objects.filter(pk=ecom_customersupport_survey_b.pk).exists()


# ==============================================================================
# 6. Authentication & Authorization Gating (Cross-Cutting)
# ==============================================================================

def test_customersupport_unauthenticated_access_redirects_login():
    """All 20 customer support routes require authentication and redirect unauthenticated clients to login."""
    anon_client = Client()
    dummy_pk = 1

    for url_name in CUSTOMERSUPPORT_URLS:
        kwargs = {"pk": dummy_pk} if "<int:pk>" in CUSTOMERSUPPORT_URLS[url_name] else {}
        url = reverse(f"ecommerce:{url_name}", kwargs=kwargs)

        # GET request
        resp_get = anon_client.get(url)
        assert resp_get.status_code == 302
        assert "/login/" in resp_get.url

        # POST request
        resp_post = anon_client.post(url, {})
        assert resp_post.status_code == 302
        assert "/login/" in resp_post.url
