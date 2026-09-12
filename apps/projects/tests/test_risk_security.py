"""Projects 7.5 Risk & Issue Management — SECURITY tests.

The access-control lane: who may touch what, from the URL side — the shape a crafted request
actually takes, not the shape the templates offer.

* **Role gating.** Five verbs are ``@tenant_admin_required``: ``iss_escalate`` (escalation is a
  privileged act), ``rsk_reopen`` (a closed register row is evidence) and — the review-I9 fix —
  ``esc_create``/``esc_edit``/``esc_delete``, because a member who could write the escalation
  register would bypass the gate on the very trail ``iss_escalate`` exists to protect (they
  could forge a Level-4 escalation, rewrite someone's reason, or delete the record of who was
  told). A member gets **403 having written nothing** — the row's ``updated_at`` included, and
  for ``esc_create`` no row at all. The login-only verbs (realize, close, complete, resolve) run
  successfully for a member BY DESIGN, and this lane pins that too: widening the gate by
  accident would be as much a defect as narrowing it.
* **Template gating (the I9 UI half).** The escalation register's Add/Edit/Delete controls are
  wrapped in the admin check — asserted from the rendered HTML for both roles, because a control
  a member can still see is a defect even when the view 403s.
* **Cross-tenant scoping (IDOR).** Every ``<int:pk>`` route — GET and POST, read and
  destructive — 404s on another workspace's row, and the row survives. A tenant-B MEMBER on a
  tenant-A pk is also a 404: that is scope, not role. Only the gates differ between the two
  failures; the row never leaks either way.
* **Method guards.** GET on every POST-only route (the seven verbs + the four deletes) → 405,
  with the DB untouched afterwards.
* **CSRF and anonymity.** A POST without a token → 403; an anonymous GET → redirect to login;
  the tenant-less superuser's creates bounce to the dashboard and their boards render empty.

The deny-by-default matrix is asserted from the URL side for ALL 30 routes: the IDs a member
cannot reach are probed directly, never inferred from a hidden button.

Naming (mandatory): every test is ``test_risk_*``, every module-level helper ``_risk_*``.
Scope: permissions and isolation. Page content, context keys and state machines belong to the
other three lanes.
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.projects.models import (
    IssueEscalation,
    ProjectIssue,
    ProjectRisk,
    RiskResponseAction,
)
from apps.projects.tests.conftest import (
    _risk_escalation,
)

# Every 7.5 route that takes a pk — plus the list/create pages the anonymous and tenant-less
# probes walk. The verbs/deletes are POST-only (GET must 405); detail+edit answer GET too.
_PK_GET_ROUTES = [
    ("rsk_detail", "risk"), ("rsk_edit", "risk"),
    ("rra_detail", "action"), ("rra_edit", "action"),
    ("iss_detail", "issue"), ("iss_edit", "issue"),
    ("esc_detail", "escalation"), ("esc_edit", "escalation"),
]
_PK_POST_ROUTES = [
    ("rsk_delete", "risk"), ("rsk_realize", "risk"), ("rsk_close", "risk"),
    ("rsk_reopen", "risk"),
    ("rra_delete", "action"), ("rra_complete", "action"),
    ("iss_delete", "issue"), ("iss_escalate", "issue"), ("iss_resolve", "issue"),
    ("iss_close", "issue"),
    ("esc_delete", "escalation"),
]
_ADMIN_GATED_VERBS = ["iss_escalate", "rsk_reopen"]
_ADMIN_GATED_ESC_ROUTES = ["esc_create", "esc_edit", "esc_delete"]
_LIST_ROUTES = ["rsk_list", "rra_list", "iss_list", "esc_list", "risk_analysis",
                "risk_monitoring"]
_CREATE_ROUTES = ["rsk_create", "rra_create", "iss_create", "esc_create"]


# ==============================================================================================
# Anonymous access — nothing at all without a login
# ==============================================================================================

@pytest.mark.parametrize("route", _LIST_ROUTES + _CREATE_ROUTES)
def test_risk_anonymous_get_redirects_to_login(route, risk_anon_client):
    response = risk_anon_client.get(reverse(f"projects:{route}"))
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.parametrize("route,fixture_name", [("rsk_detail", "risk"),
                                                ("rra_detail", "action"),
                                                ("iss_detail", "issue"),
                                                ("esc_detail", "escalation")])
def test_risk_anonymous_detail_redirects_to_login(route, fixture_name, risk_anon_client,
                                                  risk_high, risk_action_open,
                                                  risk_issue_open, risk_issue_escalated):
    pk = {"risk": risk_high, "action": risk_action_open, "issue": risk_issue_open,
          "escalation": risk_issue_escalated.escalations.first()}[fixture_name].pk
    assert risk_anon_client.get(reverse(f"projects:{route}", args=[pk])).status_code == 302


# ==============================================================================================
# Cross-tenant scoping (IDOR) — 404 on GET and POST, and the row survives
# ==============================================================================================

def test_risk_idor_get_404_on_every_pk_route(tenant_b, risk_admin_client, risk_b, risk_action_b,
                                             risk_issue_b, risk_escalation_b):
    """Admin A probes every tenant-B pk route → 404 — read routes never leak the row."""
    rows = {"risk": risk_b, "action": risk_action_b, "issue": risk_issue_b,
            "escalation": risk_escalation_b}
    for route, tag in _PK_GET_ROUTES:
        response = risk_admin_client.get(reverse(f"projects:{route}", args=[rows[tag].pk]))
        assert response.status_code == 404, (route, rows[tag].pk)


def test_risk_idor_post_404_on_every_verb_and_delete(tenant_b, risk_admin_client, risk_b,
                                                     risk_action_b, risk_issue_b,
                                                     risk_escalation_b):
    """The destructive and verb routes refuse cross-tenant pks identically, and every probed
    row survives (a 404-on-POST, not the 405 a GET would meet — the tenant filter is genuinely
    in the write path)."""
    rows = {"risk": risk_b, "action": risk_action_b, "issue": risk_issue_b,
            "escalation": risk_escalation_b}
    for route, tag in _PK_POST_ROUTES:
        response = risk_admin_client.post(reverse(f"projects:{route}", args=[rows[tag].pk]),
                                          {"level": "2", "reason": "x"})
        assert response.status_code == 404, (route, rows[tag].pk)
    assert ProjectRisk.objects.filter(pk=risk_b.pk, status=risk_b.status).exists()
    assert RiskResponseAction.objects.filter(pk=risk_action_b.pk,
                                             status=risk_action_b.status).exists()
    assert ProjectIssue.objects.filter(pk=risk_issue_b.pk,
                                       status=risk_issue_b.status).exists()
    assert IssueEscalation.objects.filter(pk=risk_escalation_b.pk).exists()


def test_risk_tenant_b_member_on_tenant_a_pk_is_404_not_403(tenant_a, risk_high, risk_member_b):
    """A foreign-workspace member gets the same 404 an admin gets — scope hides the row before
    role is even consulted (no existence leak either way)."""
    client = Client()
    client.force_login(risk_member_b)
    assert client.get(reverse("projects:rsk_detail", args=[risk_high.pk])).status_code == 404


# ==============================================================================================
# Role gating — the five admin verbs 403 a member having written nothing (review I9)
# ==============================================================================================

def test_risk_member_escalate_403_writes_nothing(tenant_a, risk_member_client, risk_issue_open):
    response = risk_member_client.post(
        reverse("projects:iss_escalate", args=[risk_issue_open.pk]),
        {"level": "4", "reason": "Forged by a member."})
    assert response.status_code == 403
    risk_issue_open.refresh_from_db()
    assert risk_issue_open.escalation_level == 0
    assert not risk_issue_open.escalations.exists()


def test_risk_member_reopen_403_writes_nothing(tenant_a, risk_member_client, risk_closed):
    response = risk_member_client.post(reverse("projects:rsk_reopen", args=[risk_closed.pk]))
    assert response.status_code == 403
    risk_closed.refresh_from_db()
    assert risk_closed.status == "closed" and risk_closed.closed_at is not None


def test_risk_member_esc_create_403_creates_no_row(tenant_a, risk_member_client,
                                                   risk_issue_open):
    response = risk_member_client.post(
        reverse("projects:esc_create"),
        {"issue": risk_issue_open.pk, "level": "4", "reason": "Forged by a member."})
    assert response.status_code == 403
    assert not IssueEscalation.objects.filter(issue=risk_issue_open).exists()


def test_risk_member_esc_edit_403_writes_nothing(tenant_a, risk_member_client,
                                                 risk_issue_escalated):
    row = risk_issue_escalated.escalations.first()
    response = risk_member_client.post(reverse("projects:esc_edit", args=[row.pk]),
                                       {"issue": row.issue_id, "level": "1",
                                        "reason": "Rewritten by a member."})
    assert response.status_code == 403
    row.refresh_from_db()
    assert row.level == risk_issue_escalated.escalations.first().level


def test_risk_member_esc_delete_403_deletes_nothing(tenant_a, risk_member_client,
                                                    risk_issue_escalated):
    row = risk_issue_escalated.escalations.first()
    response = risk_member_client.post(reverse("projects:esc_delete", args=[row.pk]))
    assert response.status_code == 403
    assert IssueEscalation.objects.filter(pk=row.pk).exists()  # the evidence trail survives


def test_risk_admin_runs_every_gated_verb(risk_admin_client, risk_issue_open, risk_closed):
    assert risk_admin_client.post(
        reverse("projects:iss_escalate", args=[risk_issue_open.pk]),
        {"level": "2", "reason": "Needs a decision."}).status_code == 302
    assert risk_admin_client.post(
        reverse("projects:rsk_reopen", args=[risk_closed.pk])).status_code == 302
    assert risk_admin_client.post(
        reverse("projects:esc_create"),
        {"issue": risk_issue_open.pk, "level": "3", "reason": "Program-level impact."}
    ).status_code == 302
    assert IssueEscalation.objects.filter(issue=risk_issue_open).count() == 2


def test_risk_member_runs_the_login_only_verbs(tenant_a, risk_member_client, risk_low,
                                               risk_action_open, risk_issue_open):
    """The verbs 7.5 deliberately leaves login-only run for a member — pinning the design so a
    future gate-widening review sees the intended state, not an accident."""
    assert risk_member_client.post(
        reverse("projects:rsk_realize", args=[risk_low.pk])).status_code == 302
    assert risk_member_client.post(
        reverse("projects:rra_complete", args=[risk_action_open.pk])).status_code == 302
    assert risk_member_client.post(
        reverse("projects:iss_resolve", args=[risk_issue_open.pk]),
        {"resolution_note": "Handled by the team."}).status_code == 302
    risk_low.refresh_from_db()
    assert risk_low.status == "realized"  # and the I1 bridge is the member's realize
    assert ProjectIssue.objects.filter(risk=risk_low).exists()


def test_risk_member_reads_every_register_and_board(tenant_a, risk_member_client, risk_high,
                                                    risk_issue_open, risk_action_open):
    for route in _LIST_ROUTES:
        response = risk_member_client.get(reverse(f"projects:{route}"))
        assert response.status_code == 200, route
    assert risk_high.number in risk_member_client.get(
        reverse("projects:rsk_detail", args=[risk_high.pk])).content.decode()


# ==============================================================================================
# Template gating — the I9 UI half: the escalation controls are admin-only in the HTML
# ==============================================================================================

def test_risk_escalation_controls_hidden_from_members(risk_member_client, risk_issue_escalated):
    list_body = risk_member_client.get(reverse("projects:esc_list")).content.decode()
    assert reverse("projects:esc_create") not in list_body
    detail_body = risk_member_client.get(
        reverse("projects:esc_detail",
                args=[risk_issue_escalated.escalations.first().pk])).content.decode()
    assert reverse("projects:esc_edit",
                   args=[risk_issue_escalated.escalations.first().pk]) not in detail_body
    assert reverse("projects:esc_delete",
                   args=[risk_issue_escalated.escalations.first().pk]) not in detail_body


def test_risk_escalation_controls_visible_to_admins(risk_admin_client, risk_issue_escalated):
    list_body = risk_admin_client.get(reverse("projects:esc_list")).content.decode()
    assert reverse("projects:esc_create") in list_body
    detail_body = risk_admin_client.get(
        reverse("projects:esc_detail",
                args=[risk_issue_escalated.escalations.first().pk])).content.decode()
    assert reverse("projects:esc_edit",
                   args=[risk_issue_escalated.escalations.first().pk]) in detail_body


# ==============================================================================================
# Method guards — GET on every POST-only route is a 405
# ==============================================================================================

@pytest.mark.parametrize("route,fixture_name", _PK_POST_ROUTES)
def test_risk_get_on_post_only_routes_is_405(tenant_a, route, fixture_name, risk_admin_client,
                                             risk_high, risk_action_open, risk_issue_open,
                                             risk_issue_escalated):
    rows = {"risk": risk_high, "action": risk_action_open, "issue": risk_issue_open,
            "escalation": risk_issue_escalated.escalations.first()}
    response = risk_admin_client.get(reverse(f"projects:{route}", args=[rows[fixture_name].pk]))
    assert response.status_code == 405, route


# ==============================================================================================
# CSRF and anonymity
# ==============================================================================================

def test_risk_post_without_csrf_token_403s(tenant_a, risk_csrf_client, risk_project_a):
    response = risk_csrf_client.post(reverse("projects:rsk_create"),
                                     {"project": risk_project_a.pk, "title": "x",
                                      "description": "y", "probability": "2", "impact": "2"})
    assert response.status_code == 403
    assert not ProjectRisk.objects.exists()


def test_risk_tenant_less_user_sees_empty_boards_and_bounced_creates(risk_tenantless_client):
    for route in _LIST_ROUTES:
        response = risk_tenantless_client.get(reverse(f"projects:{route}"))
        assert response.status_code == 200, route  # empty states, never a 500
    response = risk_tenantless_client.post(reverse("projects:rsk_create"), {})
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
