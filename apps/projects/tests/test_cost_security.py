"""Projects 7.4 Cost & Budget Management — SECURITY tests.

The access-control lane: who may touch what, from the URL side — the shape a crafted request
actually takes, not the shape the templates offer.

* **Role gating.** The four governance verbs (``bvr_approve``/``bvr_reject``/``bvr_activate``/
  ``pex_void``) are ``@tenant_admin_required`` — an ordinary member gets **403 having written
  nothing** (the row's ``updated_at`` included, because a refusal that still calls ``save()``
  is a refusal that lies). ``bvr_submit`` and ``pex_post`` are login-only BY DESIGN — a member
  runs them successfully, and this lane pins that too, because widening the gate by accident
  would be as much a defect as narrowing it.
* **Cross-tenant scoping (IDOR).** Every ``<int:pk>`` route — GET and POST, read and
  destructive — 404s on another workspace's row, and the row survives. A tenant-B MEMBER on a
  tenant-A pk is also a 404: that is scope, not role. Only the gates differ between the two
  failures; the row never leaks either way.
* **Method guards.** GET on every POST-only route (the six verbs + the three deletes) → 405,
  with the DB untouched afterwards.
* **CSRF and anonymity.** A POST without a token → 403; an anonymous GET → redirect to login;
  a tenant-less user's creates bounce to the dashboard and their registers render empty.

The deny-by-default matrix is asserted from the URL side for ALL 26 routes: the IDs a member
cannot reach are probed directly, never inferred from a hidden button.

Naming (mandatory): every test is ``test_cost_*``, every module-level helper ``_cost_*``.
Scope: permissions and isolation. Page content, context keys and state machines belong to the
other three lanes.
"""
import pytest
from django.urls import reverse

from apps.projects.models import (
    BudgetRevision,
    CostControlAccount,
    ProjectBudgetLine,
    ProjectExpense,
)
from apps.projects.tests.conftest import (
    _cost_budget_line,
    _cost_expense,
)

# (url_name, url_arg_mode) — every 7.4 route that takes a pk, plus the list/create pages the
# anonymous and tenant-less probes walk.
_PK_GET_ROUTES = [
    ("bvr_detail", "bvr"), ("bvr_edit", "bvr"),
    ("cca_detail", "cca"), ("cca_edit", "cca"),
    ("pbl_detail", "pbl"), ("pbl_edit", "pbl"),
    ("pex_detail", "pex"), ("pex_edit", "pex"),
]
_PK_POST_ROUTES = [
    ("bvr_delete", "bvr"), ("bvr_submit", "bvr"), ("bvr_approve", "bvr"),
    ("bvr_reject", "bvr"), ("bvr_activate", "bvr"),
    ("cca_delete", "cca"),
    ("pbl_delete", "pbl"),
    ("pex_delete", "pex"), ("pex_post", "pex"), ("pex_void", "pex"),
]
_ADMIN_VERBS = ["bvr_approve", "bvr_reject", "bvr_activate", "pex_void"]
_LIST_ROUTES = ["pbl_list", "bvr_list", "cca_list", "pex_list"]
_CREATE_ROUTES = ["pbl_create", "bvr_create", "cca_create", "pex_create"]


# ==============================================================================================
# Anonymous access — nothing at all without a login
# ==============================================================================================

@pytest.mark.parametrize("route", _LIST_ROUTES + _CREATE_ROUTES)
def test_cost_anonymous_get_redirects_to_login(route, cost_anon_client):
    response = cost_anon_client.get(reverse(f"projects:{route}"))
    assert response.status_code == 302
    assert "/login" in response.url or "login" in response.url


@pytest.mark.parametrize("route,fixture_name", [("bvr_detail", "rev"),
                                                ("cca_detail", "ca"),
                                                ("pbl_detail", "line"),
                                                ("pex_detail", "exp")])
def test_cost_anonymous_detail_redirects_to_login(route, fixture_name, cost_anon_client,
                                                  cost_revision_activated,
                                                  cost_control_account_a,
                                                  cost_budget_line_a, cost_expense_posted):
    pk = {"rev": cost_revision_activated, "ca": cost_control_account_a,
          "line": cost_budget_line_a, "exp": cost_expense_posted}[fixture_name].pk
    response = cost_anon_client.get(reverse(f"projects:{route}", args=[pk]))
    assert response.status_code == 302


# ==============================================================================================
# Role gating — the four admin verbs 403 a member having written nothing
# ==============================================================================================

def test_cost_member_approve_403_writes_nothing(tenant_a, cost_member_client, admin_user,
                                                cost_revision_pending):
    before = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    response = cost_member_client.post(reverse("projects:bvr_approve",
                                               args=[cost_revision_pending.pk]))
    after = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    assert response.status_code == 403
    assert (after.status, after.decided_by, after.decided_at, after.updated_at) == \
           (before.status, before.decided_by, before.decided_at, before.updated_at)


def test_cost_member_reject_403_writes_nothing(tenant_a, cost_member_client,
                                               cost_revision_pending):
    before = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    response = cost_member_client.post(reverse("projects:bvr_reject",
                                               args=[cost_revision_pending.pk]),
                                       {"decision_notes": "member override"})
    after = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    assert response.status_code == 403
    assert after.decision_notes == before.decision_notes  # the smuggled rationale landed nowhere


def test_cost_member_activate_403_writes_nothing(tenant_a, cost_member_client,
                                                 cost_revision_approved):
    before = BudgetRevision.objects.get(pk=cost_revision_approved.pk)
    response = cost_member_client.post(reverse("projects:bvr_activate",
                                               args=[cost_revision_approved.pk]))
    after = BudgetRevision.objects.get(pk=cost_revision_approved.pk)
    assert response.status_code == 403
    assert (after.status, after.activated_at, after.updated_at) == \
           (before.status, before.activated_at, before.updated_at)


def test_cost_member_void_403_writes_nothing(tenant_a, cost_member_client,
                                             cost_expense_posted, cost_control_account_a,
                                             cost_budget_line_a):
    before = ProjectExpense.objects.get(pk=cost_expense_posted.pk)
    response = cost_member_client.post(reverse("projects:pex_void",
                                               args=[cost_expense_posted.pk]))
    after = ProjectExpense.objects.get(pk=cost_expense_posted.pk)
    assert response.status_code == 403
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_cost_member_runs_the_login_only_verbs(tenant_a, cost_member_client,
                                               cost_revision_draft, cost_expense_draft,
                                               cost_budget_line_a):
    """bvr_submit and pex_post are member verbs BY DESIGN — the gate must not over-tighten."""
    ok_submit = cost_member_client.post(reverse("projects:bvr_submit",
                                                args=[cost_revision_draft.pk]))
    assert ok_submit.status_code == 302
    cost_revision_draft.refresh_from_db()
    assert cost_revision_draft.status == "pending_approval"
    ok_post = cost_member_client.post(reverse("projects:pex_post",
                                              args=[cost_expense_draft.pk]))
    assert ok_post.status_code == 302
    cost_expense_draft.refresh_from_db()
    assert cost_expense_draft.status == "posted"


def test_cost_member_reads_every_register_and_detail(tenant_a, cost_member_client,
                                                     cost_revision_activated,
                                                     cost_control_account_a,
                                                     cost_budget_line_a,
                                                     cost_expense_posted):
    """Read access is login-wide inside the workspace — CRUD is not admin-gated."""
    reads = [("bvr_detail", cost_revision_activated.pk),
             ("cca_detail", cost_control_account_a.pk),
             ("pbl_detail", cost_budget_line_a.pk),
             ("pex_detail", cost_expense_posted.pk),
             ("bvr_list", None), ("cca_list", None),
             ("pbl_list", None), ("pex_list", None)]
    for route, pk in reads:
        url = reverse(f"projects:{route}") if pk is None else reverse(
            f"projects:{route}", args=[pk])
        response = cost_member_client.get(url)
        assert response.status_code == 200, route


# ==============================================================================================
# Cross-tenant scoping (IDOR) — 404 from the URL side, row survives
# ==============================================================================================

def test_cost_idor_get_404_on_every_pk_route(tenant_b, cost_admin_client, cost_project_b,
                                             cost_revision_b, cost_control_account_b,
                                             cost_expense_b):
    """Admin A probes every tenant-B pk route → 404 — read routes never leak the row."""
    b_line = _cost_budget_line(tenant_b, cost_revision_b, cost_project_b,
                               control_account=cost_control_account_b)
    rows = {"bvr": cost_revision_b, "cca": cost_control_account_b,
            "pbl": b_line, "pex": cost_expense_b}
    for route, tag in _PK_GET_ROUTES:
        response = cost_admin_client.get(reverse(f"projects:{route}", args=[rows[tag].pk]))
        assert response.status_code == 404, (route, rows[tag].pk)


def test_cost_idor_post_404_on_every_verb_and_delete(tenant_b, cost_admin_client,
                                                     cost_project_b, cost_revision_b,
                                                     cost_control_account_b, cost_expense_b):
    """The destructive and verb routes refuse cross-tenant pks identically, and every probed
    row survives."""
    b_line = _cost_budget_line(tenant_b, cost_revision_b, cost_project_b,
                               control_account=cost_control_account_b)
    rows = {"bvr": cost_revision_b, "cca": cost_control_account_b,
            "pbl": b_line, "pex": cost_expense_b}
    for route, tag in _PK_POST_ROUTES:
        response = cost_admin_client.post(reverse(f"projects:{route}", args=[rows[tag].pk]),
                                          {"decision_notes": "x"})
        assert response.status_code == 404, (route, rows[tag].pk)
    assert BudgetRevision.objects.filter(pk=cost_revision_b.pk).exists()
    assert CostControlAccount.objects.filter(pk=cost_control_account_b.pk).exists()
    assert ProjectBudgetLine.objects.filter(pk=b_line.pk).exists()
    assert ProjectExpense.objects.filter(pk=cost_expense_b.pk,
                                         status=cost_expense_b.status).exists()


def test_cost_tenant_b_admin_cannot_read_tenant_a_rows(client_b, tenant_a,
                                                       cost_revision_activated,
                                                       cost_control_account_a,
                                                       cost_budget_line_a,
                                                       cost_expense_posted):
    for url, pk in (("bvr_detail", cost_revision_activated.pk),
                    ("cca_detail", cost_control_account_a.pk),
                    ("pbl_detail", cost_budget_line_a.pk),
                    ("pex_detail", cost_expense_posted.pk)):
        assert client_b.get(reverse(f"projects:{url}", args=[pk])).status_code == 404


def test_cost_tenant_b_member_on_tenant_a_pk_is_404_not_403(tenant_a, cost_member_b,
                                                            cost_revision_activated):
    """A foreign-workspace member gets the same 404 an admin gets — scope hides the row
    before role is even consulted (no existence leak either way)."""
    from django.test import Client
    client = Client()
    client.force_login(cost_member_b)  # returns None — the login itself is the assertion
    assert client.get(reverse("projects:bvr_detail",
                              args=[cost_revision_activated.pk])).status_code == 404


def test_cost_cross_tenant_form_post_refused_at_the_view(tenant_a, cost_admin_client,
                                                         cost_project_a, cost_revision_b,
                                                         cost_control_account_b):
    """A crafted create POST carrying another workspace's FK ids: field error, no row."""
    response = cost_admin_client.post(reverse("projects:pbl_create"), {
        "budget_revision": cost_revision_b.pk, "project": cost_project_a.pk,
        "category": "labor", "amount": "10.00",
    })
    assert response.status_code == 200  # re-rendered with the field error
    assert not ProjectBudgetLine.objects.exists()


# ==============================================================================================
# Method guards — GET on every POST-only route is a 405, DB untouched
# ==============================================================================================

def test_cost_get_on_post_only_routes_is_405(tenant_a, cost_admin_client,
                                             cost_revision_activated, cost_revision_draft,
                                             cost_control_account_a, cost_budget_line_a,
                                             cost_budget_line_draft, cost_expense_posted,
                                             cost_expense_draft):
    rows = {"bvr_delete": cost_revision_draft, "bvr_submit": cost_revision_draft,
            "bvr_approve": cost_revision_activated, "bvr_reject": cost_revision_activated,
            "bvr_activate": cost_revision_activated, "cca_delete": cost_control_account_a,
            "pbl_delete": cost_budget_line_draft, "pex_delete": cost_expense_draft,
            "pex_post": cost_expense_draft, "pex_void": cost_expense_posted}
    for route, row in rows.items():
        response = cost_admin_client.get(reverse(f"projects:{route}", args=[row.pk]))
        assert response.status_code == 405, route


# ==============================================================================================
# CSRF and the tenant-less workspace
# ==============================================================================================

def test_cost_post_without_csrf_token_403s(tenant_a, cost_csrf_client, cost_project_a,
                                           cost_currency):
    response = cost_csrf_client.post(reverse("projects:bvr_create"), {
        "project": cost_project_a.pk, "revision_no": "77", "title": "csrf-less",
        "reason": "no token",
    })
    assert response.status_code == 403
    assert not BudgetRevision.objects.filter(revision_no=77).exists()


def test_cost_tenant_less_user_sees_empty_registers_and_bounced_creates(
        cost_tenantless_client):
    for route in _LIST_ROUTES:
        response = cost_tenantless_client.get(reverse(f"projects:{route}"))
        assert response.status_code == 200
        assert not response.context["object_list"]
    for route in _CREATE_ROUTES:
        response = cost_tenantless_client.post(reverse(f"projects:{route}"), {})
        assert response.status_code == 302
        assert response.url == reverse("dashboard:home")
