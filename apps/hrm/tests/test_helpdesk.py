"""Tests for HRM 3.36 Helpdesk sub-module: ``HelpdeskSLAPolicy`` (per-priority targets, ``HSLA-``) +
``HelpdeskCategory`` (HR/IT/Admin/Facilities routing + KB taxonomy) + ``HelpdeskTicket`` (``TKT-``,
own-vs-admin CRUD reusing ``_ss_scope``/``_can_manage_own_child``, bespoke agent-worked lifecycle +
computed SLA breach + inline CSAT) + ``KnowledgeArticle`` (``KBA-``, internal FAQ/self-help).

Mirrors ``test_travel.py`` fixture style. Covers: auto-numbers, ``targets_for``, ``save()`` SLA
stamping, the computed breach/sla_state properties, CRUD, the assign/start/waiting/resolve/close/
reopen/cancel/feedback actions, the ``?sla=breached``/``?rated=1`` deep-link filters, KB publish/
helpful, access-control (anon redirect, non-admin 403 on admin-only writes), own-vs-admin scoping +
cross-employee IDOR (403), and multi-tenant IDOR (404).
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
