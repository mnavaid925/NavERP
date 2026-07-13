"""Tests for HRM 3.36 Helpdesk sub-module: ``HelpdeskSLAPolicy`` (per-priority targets, ``HSLA-``) +
``HelpdeskCategory`` (HR/IT/Admin/Facilities routing + KB taxonomy) + ``HelpdeskTicket`` (``TKT-``,
own-vs-admin CRUD reusing ``_ss_scope``/``_can_manage_own_child``, bespoke agent-worked lifecycle +
computed SLA breach + inline CSAT) + ``KnowledgeArticle`` (``KBA-``, internal FAQ/self-help).

Mirrors ``test_travel.py`` fixture style. Covers: auto-numbers, ``targets_for``, ``save()`` SLA
stamping, the computed breach/sla_state properties, CRUD, the assign/start/waiting/resolve/close/
reopen/cancel/feedback actions, the ``?sla=breached``/``?rated=1`` deep-link filters, KB publish/
helpful, access-control (anon redirect, non-admin 403 on admin-only writes), own-vs-admin scoping +
cross-employee IDOR (403), and multi-tenant IDOR (404).

Extended coverage (below the original 22): a full URL sweep of every list/create/detail/edit page
(200), the SLA/category/knowledge-article CRUD cycles the original suite only exercised via list
renders, the waiting/cancel/edit/delete ticket paths, draft-KB-article visibility, a template-comment
leak scan (``{#`` / ``{% comment`` must never reach rendered HTML), and multi-tenant IDOR (404) on
every 3.36 detail endpoint (not just tickets).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
    from apps.accounts.models import User
    user = User.objects.create_user(
        email=email, username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=is_admin,
    )
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def own_client(tenant_a, employee_a):
    """Non-admin user whose EmployeeProfile IS employee_a (the requester/owner)."""
    return _client_for(employee_a.party, tenant_a, email="owner@acme.com", username="owner_acme")


@pytest.fixture
def other_employee_client(tenant_a, employee_a2):
    """Non-admin user for a DIFFERENT employee, same tenant (cross-employee IDOR)."""
    return _client_for(employee_a2.party, tenant_a, email="other@acme.com", username="other_acme")


@pytest.fixture
def sla_a(db, tenant_a):
    from apps.hrm.models import HelpdeskSLAPolicy
    return HelpdeskSLAPolicy.objects.create(
        tenant=tenant_a, name="Standard", is_default=True,
        urgent_response_hours=1, urgent_resolution_hours=4,
        high_response_hours=4, high_resolution_hours=24,
        medium_response_hours=8, medium_resolution_hours=48,
        low_response_hours=24, low_resolution_hours=96,
    )


@pytest.fixture
def category_a(db, tenant_a, admin_user, sla_a):
    from apps.hrm.models import HelpdeskCategory
    return HelpdeskCategory.objects.create(
        tenant=tenant_a, name="IT Support", department="it",
        default_assignee=admin_user, default_sla_policy=sla_a,
    )


@pytest.fixture
def ticket_a(db, tenant_a, employee_a, category_a, sla_a):
    from apps.hrm.models import HelpdeskTicket
    return HelpdeskTicket.objects.create(
        tenant=tenant_a, employee=employee_a, subject="Laptop won't boot",
        description="Black screen after update.", category=category_a, priority="high",
        sla_policy=sla_a, status="new",
    )


@pytest.fixture
def article_a(db, tenant_a, admin_user, category_a):
    from apps.hrm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a, title="Reset your VPN", body="Follow the portal steps.",
        category=category_a, status="published", owner=admin_user,
        published_at=timezone.now(),
    )


@pytest.fixture
def draft_article_a(db, tenant_a, admin_user, category_a):
    """A DRAFT KnowledgeArticle for tenant_a (not yet published) — visibility/access-control tests."""
    from apps.hrm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_a, title="Unpublished onboarding draft", body="Work in progress.",
        category=category_a, status="draft", owner=admin_user,
    )


# ---- tenant_b (IDOR) ----
@pytest.fixture
def sla_b(db, tenant_b):
    from apps.hrm.models import HelpdeskSLAPolicy
    return HelpdeskSLAPolicy.objects.create(tenant=tenant_b, name="Standard B")


@pytest.fixture
def category_b(db, tenant_b, sla_b):
    from apps.hrm.models import HelpdeskCategory
    return HelpdeskCategory.objects.create(tenant=tenant_b, name="IT B", department="it",
                                           default_sla_policy=sla_b)


@pytest.fixture
def ticket_b(db, tenant_b, employee_b, category_b, sla_b):
    from apps.hrm.models import HelpdeskTicket
    return HelpdeskTicket.objects.create(
        tenant=tenant_b, employee=employee_b, subject="B ticket", description="x",
        category=category_b, priority="low", sla_policy=sla_b, status="new",
    )


@pytest.fixture
def article_b(db, tenant_b, category_b):
    """A published KnowledgeArticle belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import KnowledgeArticle
    return KnowledgeArticle.objects.create(
        tenant=tenant_b, title="B article", body="x", category=category_b,
        status="published", published_at=timezone.now(),
    )


# ============================================================ Models
def test_sla_targets_for(sla_a):
    assert sla_a.targets_for("urgent") == (1, 4)
    assert sla_a.targets_for("high") == (4, 24)
    assert sla_a.targets_for("low") == (24, 96)
    # Unknown priority falls back to medium.
    assert sla_a.targets_for("bogus") == (8, 48)


def test_ticket_autonumber_and_sla_stamp(ticket_a):
    assert ticket_a.number.startswith("TKT-")
    # save() stamped the dues from the policy's HIGH targets (4h response / 24h resolution).
    assert ticket_a.first_response_due is not None
    assert ticket_a.resolution_due is not None
    delta = ticket_a.resolution_due - ticket_a.first_response_due
    assert delta == datetime.timedelta(hours=20)


def test_sla_policy_autonumber(sla_a):
    assert sla_a.number.startswith("HSLA-")


def test_article_autonumber(article_a):
    assert article_a.number.startswith("KBA-")


def test_ticket_breach_computed(ticket_a):
    from apps.hrm.models import HelpdeskTicket
    past = timezone.now() - datetime.timedelta(hours=2)
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(
        status="open", first_response_due=past, resolution_due=past, first_responded_at=None)
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.first_response_breached is True
    assert t.resolution_breached is True
    assert t.is_breached is True
    assert t.sla_state == "breached"


def test_ticket_sla_state_ok(ticket_a):
    # Fresh HIGH ticket, dues in the future → on track.
    assert ticket_a.sla_state == "ok"


# ============================================================ CRUD + lifecycle (admin)
def test_lists_render(client_a, ticket_a, category_a, sla_a, article_a):
    for name in ["ticket_list", "helpdeskcategory_list", "helpdesksla_list", "knowledgearticle_list"]:
        resp = client_a.get(reverse(f"hrm:{name}"))
        assert resp.status_code == 200


def test_ticket_detail_renders(client_a, ticket_a):
    resp = client_a.get(reverse("hrm:ticket_detail", args=[ticket_a.pk]))
    assert resp.status_code == 200
    assert ticket_a.number.encode() in resp.content


def test_category_create_inherits_defaults_on_ticket(client_a, employee_a, category_a):
    from apps.hrm.models import HelpdeskTicket
    resp = client_a.post(reverse("hrm:ticket_create"), {
        "subject": "Email down", "description": "cannot send", "category": category_a.pk,
        "priority": "urgent", "employee_pk": employee_a.pk,
    })
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(tenant=category_a.tenant, subject="Email down")
    # Inherited the category's default SLA policy + assignee, and dues were stamped.
    assert t.sla_policy_id == category_a.default_sla_policy_id
    assert t.assignee_id == category_a.default_assignee_id
    assert t.resolution_due is not None


def test_ticket_lifecycle(client_a, admin_user, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    # assign
    resp = client_a.post(reverse("hrm:ticket_assign", args=[ticket_a.pk]), {"assignee": admin_user.pk})
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.assignee_id == admin_user.pk and t.status == "open"
    # start
    client_a.post(reverse("hrm:ticket_start", args=[ticket_a.pk]))
    t.refresh_from_db()
    assert t.status == "in_progress" and t.first_responded_at is not None
    # resolve (note required)
    assert client_a.post(reverse("hrm:ticket_resolve", args=[ticket_a.pk]), {}).status_code == 302
    t.refresh_from_db()
    assert t.status != "resolved"  # rejected: no note
    client_a.post(reverse("hrm:ticket_resolve", args=[ticket_a.pk]), {"resolution_notes": "Fixed it."})
    t.refresh_from_db()
    assert t.status == "resolved" and t.resolved_at is not None
    # close then reopen
    client_a.post(reverse("hrm:ticket_close", args=[ticket_a.pk]))
    t.refresh_from_db()
    assert t.status == "closed" and t.closed_at is not None
    client_a.post(reverse("hrm:ticket_reopen", args=[ticket_a.pk]))
    t.refresh_from_db()
    assert t.status == "open" and t.resolved_at is None


def test_ticket_feedback_by_requester(own_client, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(status="resolved", resolved_at=timezone.now())
    resp = own_client.post(reverse("hrm:ticket_feedback", args=[ticket_a.pk]),
                           {"satisfaction_rating": "5", "satisfaction_comment": "Great"})
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.satisfaction_rating == 5 and t.satisfaction_at is not None


def test_sla_breached_filter(client_a, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    past = timezone.now() - datetime.timedelta(hours=2)
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(
        status="open", first_response_due=past, resolution_due=past, first_responded_at=None)
    resp = client_a.get(reverse("hrm:ticket_list") + "?sla=breached")
    assert resp.status_code == 200
    assert ticket_a.number.encode() in resp.content


def test_rated_filter(client_a, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(satisfaction_rating=4)
    resp = client_a.get(reverse("hrm:ticket_list") + "?rated=1")
    assert resp.status_code == 200
    assert ticket_a.number.encode() in resp.content


def test_kb_helpful_increments(own_client, article_a):
    from apps.hrm.models import KnowledgeArticle
    own_client.post(reverse("hrm:knowledgearticle_helpful", args=[article_a.pk]))
    assert KnowledgeArticle.objects.get(pk=article_a.pk).helpful_count == 1


def test_kb_detail_bumps_views(own_client, article_a):
    from apps.hrm.models import KnowledgeArticle
    own_client.get(reverse("hrm:knowledgearticle_detail", args=[article_a.pk]))
    assert KnowledgeArticle.objects.get(pk=article_a.pk).view_count == 1


# ============================================================ Access control + isolation
def test_anonymous_redirected(client, ticket_a):
    resp = client.get(reverse("hrm:ticket_list"))
    assert resp.status_code == 302 and "/login" in resp.url


def test_non_admin_cannot_create_category(own_client):
    resp = own_client.get(reverse("hrm:helpdeskcategory_create"))
    assert resp.status_code == 403


def test_non_admin_cannot_assign(own_client, admin_user, ticket_a):
    resp = own_client.post(reverse("hrm:ticket_assign", args=[ticket_a.pk]), {"assignee": admin_user.pk})
    # own_client is the requester (not an agent/admin) → assign is blocked (redirect, no change).
    from apps.hrm.models import HelpdeskTicket
    assert HelpdeskTicket.objects.get(pk=ticket_a.pk).assignee_id != admin_user.pk


def test_own_scoping_hides_others(other_employee_client, ticket_a):
    # employee_a2's user should not see employee_a's ticket in the list.
    resp = other_employee_client.get(reverse("hrm:ticket_list"))
    assert resp.status_code == 200
    assert ticket_a.number.encode() not in resp.content


def test_cross_employee_idor_403(other_employee_client, ticket_a):
    resp = other_employee_client.get(reverse("hrm:ticket_detail", args=[ticket_a.pk]))
    assert resp.status_code == 403


def test_multitenant_idor_404(client_a, ticket_b):
    resp = client_a.get(reverse("hrm:ticket_detail", args=[ticket_b.pk]))
    assert resp.status_code == 404


def test_category_delete_guarded_while_in_use(client_a, category_a, ticket_a):
    from apps.hrm.models import HelpdeskCategory
    resp = client_a.post(reverse("hrm:helpdeskcategory_delete", args=[category_a.pk]))
    assert resp.status_code == 302
    assert HelpdeskCategory.objects.filter(pk=category_a.pk).exists()  # blocked (in use)


# ============================================================ Extended: full URL sweep
def test_full_url_sweep_admin_gets(client_a, employee_a, ticket_a, category_a, sla_a, article_a):
    """Every 3.36 list/create/detail/edit GET renders (200) for a tenant admin — catches broken
    ``{% url %}`` reverses and context-variable mismatches that ``manage.py check`` can't see.
    ``ticket_create`` needs ``?employee=<pk>`` for an admin (who has no EmployeeProfile of their own)
    — without it the view correctly redirects to ticket_list rather than 500ing, which is the real
    UI contract, not a bug."""
    urls = [
        ("hrm:helpdesksla_list", [], ""),
        ("hrm:helpdesksla_create", [], ""),
        ("hrm:helpdesksla_detail", [sla_a.pk], ""),
        ("hrm:helpdesksla_edit", [sla_a.pk], ""),
        ("hrm:helpdeskcategory_list", [], ""),
        ("hrm:helpdeskcategory_create", [], ""),
        ("hrm:helpdeskcategory_detail", [category_a.pk], ""),
        ("hrm:helpdeskcategory_edit", [category_a.pk], ""),
        ("hrm:ticket_list", [], ""),
        ("hrm:ticket_create", [], f"?employee={employee_a.pk}"),
        ("hrm:ticket_detail", [ticket_a.pk], ""),
        ("hrm:ticket_edit", [ticket_a.pk], ""),
        ("hrm:knowledgearticle_list", [], ""),
        ("hrm:knowledgearticle_create", [], ""),
        ("hrm:knowledgearticle_detail", [article_a.pk], ""),
        ("hrm:knowledgearticle_edit", [article_a.pk], ""),
    ]
    for name, args, qs in urls:
        resp = client_a.get(reverse(name, args=args) + qs)
        assert resp.status_code == 200, f"{name}{args}{qs} -> {resp.status_code}"


def test_ticket_create_admin_without_target_employee_redirects(client_a):
    """An admin GETting ticket_create with no ``?employee=`` and no EmployeeProfile of their own is
    redirected to the list rather than erroring — asserting this so the behavior stays intentional."""
    resp = client_a.get(reverse("hrm:ticket_create"))
    assert resp.status_code == 302
    assert resp.url == reverse("hrm:ticket_list")


def test_ticket_list_deep_links_sweep(client_a, ticket_a):
    """?sla=breached and ?rated=1 both render 200 even with no matching rows (empty-state path)."""
    for qs in ("?sla=breached", "?rated=1"):
        resp = client_a.get(reverse("hrm:ticket_list") + qs)
        assert resp.status_code == 200


# ============================================================ Extended: SLA policy CRUD
def _sla_payload(**over):
    payload = {
        "name": "Gold Support", "description": "",
        "urgent_response_hours": 1, "urgent_resolution_hours": 4,
        "high_response_hours": 2, "high_resolution_hours": 8,
        "medium_response_hours": 4, "medium_resolution_hours": 24,
        "low_response_hours": 8, "low_resolution_hours": 48,
        "is_active": "on",
    }
    payload.update(over)
    return payload


def test_sla_crud_full_cycle(client_a, tenant_a):
    from apps.hrm.models import HelpdeskSLAPolicy
    resp = client_a.post(reverse("hrm:helpdesksla_create"), _sla_payload())
    assert resp.status_code == 302
    pol = HelpdeskSLAPolicy.objects.get(tenant=tenant_a, name="Gold Support")
    assert pol.number.startswith("HSLA-")

    resp = client_a.post(reverse("hrm:helpdesksla_edit", args=[pol.pk]),
                         _sla_payload(name="Gold Support Plus"))
    assert resp.status_code == 302
    pol.refresh_from_db()
    assert pol.name == "Gold Support Plus"

    # Not referenced by any ticket -> delete succeeds.
    resp = client_a.post(reverse("hrm:helpdesksla_delete", args=[pol.pk]))
    assert resp.status_code == 302
    assert not HelpdeskSLAPolicy.objects.filter(pk=pol.pk).exists()


def test_sla_delete_guarded_while_in_use(client_a, sla_a, ticket_a):
    from apps.hrm.models import HelpdeskSLAPolicy
    resp = client_a.post(reverse("hrm:helpdesksla_delete", args=[sla_a.pk]))
    assert resp.status_code == 302
    assert HelpdeskSLAPolicy.objects.filter(pk=sla_a.pk).exists()  # blocked (in use)


# ============================================================ Extended: category CRUD
def test_category_crud_full_cycle(client_a, tenant_a, sla_a):
    from apps.hrm.models import HelpdeskCategory
    resp = client_a.post(reverse("hrm:helpdeskcategory_create"), {
        "name": "Payroll Queries", "department": "hr", "description": "",
        "default_assignee": "", "default_sla_policy": sla_a.pk, "is_active": "on",
    })
    assert resp.status_code == 302
    cat = HelpdeskCategory.objects.get(tenant=tenant_a, name="Payroll Queries")

    resp = client_a.get(reverse("hrm:helpdeskcategory_detail", args=[cat.pk]))
    assert resp.status_code == 200

    resp = client_a.post(reverse("hrm:helpdeskcategory_edit", args=[cat.pk]), {
        "name": "Payroll Queries Updated", "department": "hr", "description": "",
        "default_assignee": "", "default_sla_policy": sla_a.pk, "is_active": "on",
    })
    assert resp.status_code == 302
    cat.refresh_from_db()
    assert cat.name == "Payroll Queries Updated"

    # Not referenced by any ticket -> delete succeeds.
    resp = client_a.post(reverse("hrm:helpdeskcategory_delete", args=[cat.pk]))
    assert resp.status_code == 302
    assert not HelpdeskCategory.objects.filter(pk=cat.pk).exists()


# ============================================================ Extended: knowledge article CRUD
def test_knowledgearticle_crud_full_cycle(client_a, tenant_a, category_a):
    from apps.hrm.models import KnowledgeArticle
    resp = client_a.post(reverse("hrm:knowledgearticle_create"), {
        "title": "How to submit a timesheet", "category": category_a.pk,
        "summary": "", "body": "Go to Time > Timesheets and submit.", "tags": "timesheet",
        "status": "draft",
    })
    assert resp.status_code == 302
    art = KnowledgeArticle.objects.get(tenant=tenant_a, title="How to submit a timesheet")
    assert art.number.startswith("KBA-")
    assert art.published_at is None

    resp = client_a.get(reverse("hrm:knowledgearticle_edit", args=[art.pk]))
    assert resp.status_code == 200
    # Publishing on edit stamps published_at.
    resp = client_a.post(reverse("hrm:knowledgearticle_edit", args=[art.pk]), {
        "title": art.title, "category": category_a.pk, "summary": "", "body": art.body,
        "tags": "timesheet", "status": "published",
    })
    assert resp.status_code == 302
    art.refresh_from_db()
    assert art.status == "published" and art.published_at is not None

    resp = client_a.post(reverse("hrm:knowledgearticle_delete", args=[art.pk]))
    assert resp.status_code == 302
    assert not KnowledgeArticle.objects.filter(pk=art.pk).exists()


def test_draft_article_hidden_from_non_admin_list_and_403_on_direct_detail(own_client, draft_article_a):
    resp = own_client.get(reverse("hrm:knowledgearticle_list"))
    assert resp.status_code == 200
    assert draft_article_a.title.encode() not in resp.content
    resp = own_client.get(reverse("hrm:knowledgearticle_detail", args=[draft_article_a.pk]))
    assert resp.status_code == 403


# ============================================================ Extended: remaining ticket lifecycle
def test_ticket_waiting_action(client_a, admin_user, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    client_a.post(reverse("hrm:ticket_assign", args=[ticket_a.pk]), {"assignee": admin_user.pk})
    resp = client_a.post(reverse("hrm:ticket_waiting", args=[ticket_a.pk]))
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.status == "waiting" and t.first_responded_at is not None


def test_ticket_cancel_by_requester(own_client, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    resp = own_client.post(reverse("hrm:ticket_cancel", args=[ticket_a.pk]))
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.status == "cancelled" and t.closed_at is not None


def test_ticket_edit_view(client_a, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    resp = client_a.get(reverse("hrm:ticket_edit", args=[ticket_a.pk]))
    assert resp.status_code == 200
    resp = client_a.post(reverse("hrm:ticket_edit", args=[ticket_a.pk]), {
        "subject": "Laptop still won't boot", "description": ticket_a.description,
        "category": ticket_a.category_id, "priority": "urgent",
    })
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.subject == "Laptop still won't boot" and t.priority == "urgent"


def test_ticket_delete_view(own_client, ticket_a):
    from apps.hrm.models import HelpdeskTicket
    resp = own_client.post(reverse("hrm:ticket_delete", args=[ticket_a.pk]))
    assert resp.status_code == 302
    assert not HelpdeskTicket.objects.filter(pk=ticket_a.pk).exists()


# ============================================================ Extended: comment-leak scan
def test_no_template_comment_leak_on_lists_and_details(client_a, ticket_a, category_a, sla_a, article_a):
    """Django strips ``{# ... #}`` server-side, but a broken/unclosed comment tag or a stray literal
    would leak into the response. Assert none of the raw comment markers ever reach the rendered
    bytes, on every list AND detail page, and that the seeded record is actually present."""
    pairs = [
        (reverse("hrm:helpdesksla_list"), sla_a.number, reverse("hrm:helpdesksla_detail", args=[sla_a.pk])),
        (reverse("hrm:helpdeskcategory_list"), category_a.name,
         reverse("hrm:helpdeskcategory_detail", args=[category_a.pk])),
        (reverse("hrm:ticket_list"), ticket_a.number, reverse("hrm:ticket_detail", args=[ticket_a.pk])),
        (reverse("hrm:knowledgearticle_list"), article_a.number,
         reverse("hrm:knowledgearticle_detail", args=[article_a.pk])),
    ]
    for list_url, needle, detail_url in pairs:
        list_resp = client_a.get(list_url)
        assert list_resp.status_code == 200
        assert b"{#" not in list_resp.content and b"{% comment" not in list_resp.content
        assert needle.encode() in list_resp.content

        detail_resp = client_a.get(detail_url)
        assert detail_resp.status_code == 200
        assert b"{#" not in detail_resp.content and b"{% comment" not in detail_resp.content
        assert needle.encode() in detail_resp.content


# ============================================================ Extended: multi-tenant IDOR (every detail)
def test_multitenant_idor_404_sla(client_a, sla_b):
    resp = client_a.get(reverse("hrm:helpdesksla_detail", args=[sla_b.pk]))
    assert resp.status_code == 404


def test_multitenant_idor_404_category(client_a, category_b):
    resp = client_a.get(reverse("hrm:helpdeskcategory_detail", args=[category_b.pk]))
    assert resp.status_code == 404


def test_multitenant_idor_404_article(client_a, article_b):
    resp = client_a.get(reverse("hrm:knowledgearticle_detail", args=[article_b.pk]))
    assert resp.status_code == 404


def test_multitenant_idor_404_ticket_actions(client_a, ticket_b):
    """A cross-tenant lifecycle POST must 404, not silently act on another tenant's ticket."""
    resp = client_a.post(reverse("hrm:ticket_start", args=[ticket_b.pk]))
    assert resp.status_code == 404


# ============================================================ Review-driven regression guards
def test_admin_cannot_reassign_closed_ticket(client_a, admin_user, ticket_a):
    """ticket_assign status-guard (code-review): a crafted admin POST must NOT reassign a closed or
    cancelled ticket — matching the template that hides the Assign form once the ticket is finished."""
    from apps.hrm.models import HelpdeskTicket
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(status="closed", assignee=None)
    resp = client_a.post(reverse("hrm:ticket_assign", args=[ticket_a.pk]), {"assignee": admin_user.pk})
    assert resp.status_code == 302
    t = HelpdeskTicket.objects.get(pk=ticket_a.pk)
    assert t.assignee_id is None and t.status == "closed"  # unchanged


@pytest.fixture
def many_tickets_a(db, tenant_a, employee_a, category_a, sla_a):
    """15 open tickets for employee_a — enough that a per-row FK query (N+1) blows the query ceiling."""
    from apps.hrm.models import HelpdeskTicket
    for i in range(15):
        HelpdeskTicket.objects.create(
            tenant=tenant_a, employee=employee_a, subject=f"Ticket {i}", description="x",
            category=category_a, priority="medium", sla_policy=sla_a, status="open")


def test_ticket_list_no_nplus1(client_a, many_tickets_a, django_assert_max_num_queries):
    """ticket_list stays a fixed query count regardless of row count (select_related covers every FK
    the list template renders); 15 tickets with a per-row query would be ~60 — the ceiling catches it."""
    with django_assert_max_num_queries(25):
        resp = client_a.get(reverse("hrm:ticket_list"))
    assert resp.status_code == 200


def test_ticket_detail_no_nplus1(client_a, admin_user, ticket_a, django_assert_max_num_queries):
    """ticket_detail's select_related covers employee__party/category/sla_policy/assignee."""
    from apps.hrm.models import HelpdeskTicket
    HelpdeskTicket.objects.filter(pk=ticket_a.pk).update(assignee=admin_user)
    with django_assert_max_num_queries(15):
        resp = client_a.get(reverse("hrm:ticket_detail", args=[ticket_a.pk]))
    assert resp.status_code == 200


def test_knowledgearticle_list_no_nplus1(client_a, tenant_a, category_a, admin_user,
                                         django_assert_max_num_queries):
    from apps.hrm.models import KnowledgeArticle
    for i in range(15):
        KnowledgeArticle.objects.create(
            tenant=tenant_a, title=f"Article {i}", body="x", category=category_a,
            status="published", owner=admin_user, published_at=timezone.now())
    with django_assert_max_num_queries(20):
        resp = client_a.get(reverse("hrm:knowledgearticle_list"))
    assert resp.status_code == 200
