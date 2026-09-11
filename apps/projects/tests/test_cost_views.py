"""Projects 7.4 Cost & Budget Management — VIEW tests.

The HTTP layer of the sub-module: 26 routes, the pages they render, **every context key the
test contract pins**, the four registers' search/filter/pagination behaviour, and the ten
POST verbs' state machines. Model invariants belong to ``test_cost_models.py`` and form
validation to ``test_cost_forms.py``; role gating (403), cross-tenant IDOR (404), CSRF and
anonymous access belong to ``test_cost_security.py``. Every request here is made by a TENANT
ADMIN (``cost_admin_client``), so the only thing that can refuse a verb in this lane is its
own state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page asserts CONTENT — the row's own ``BVR-``/``CCA-``/``PBL-``/
  ``PEX-`` number in the body — and the pinned keys by name: ``category_totals``/``grand_total``
  on ``pbl_list``, ``obj``/``lines``/``category_totals`` on ``bvr_detail``,
  ``budget_lines``/``expenses`` on ``cca_detail``, ``pending_revisions``/``posted_spend`` on
  the overview.
* **A filter that silently empties a register.** Every documented control on all four
  registers is compared against the ORM's own answer for the same narrowing, and the junk
  values (``?status=nope``, ``?project=0``, ``?project=abc``, an over-range pk, ``?page=abc``,
  ``?page=9999``) must return a 200 page that is never a 500 and never silently emptied (L11).
* **A verb that writes when it should refuse.** All ten verbs are exercised on both sides: the
  happy paths (submit -> approve -> activate; post -> void) and every now-forbidden source
  state, each of which must answer with a message, redirect, and leave the row byte-for-byte
  as it was — ``updated_at`` included, because a refusal that still calls ``save()`` is a
  refusal that lies. The frozen-row guards (review I1) are pinned: a baseline's LINES refuse
  edit/delete exactly like the revision itself.
* **A replayed POST.** Every idempotent verb is posted twice; the second must be refused
  cleanly with ZERO field deltas (a "no-op with a message", never a second audit row of the
  same transition).

Determinism (L16): every date basis is ``_cost_today()`` — never ``datetime.date.today()``.
Message assertions match ASCII SUBSTRINGs only (several messages carry U+2014 — a copy edit
must not turn into a red suite).

Naming (mandatory): every test is ``test_cost_*``, every module-level helper ``_cost_*``.
Scope: views/urls. Models, forms and permissions belong to the other three lanes.
"""
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse

from apps.core.models import AuditLog
from apps.projects.models import (
    BudgetRevision,
    CostControlAccount,
    ProjectBudgetLine,
    ProjectExpense,
)
from apps.projects.tests.conftest import (
    _cost_budget_line,
    _cost_control_account,
    _cost_expense,
    _cost_revision,
    _cost_today,
    _cost_fill_lines,
)

D = Decimal

JUNK_PARAMS = ["?status=nope", "?project=0", "?project=abc", "?page=abc",
               "?budget_revision=99999999999999999999", "?category=%3Cscript%3E",
               "?control_account=0", "?entry_type=%C2%B2"]


# ==============================================================================================
# Registers — content, context keys, filters, pagination
# ==============================================================================================

def test_cost_pbl_list_renders_rows_and_totals(tenant_a, cost_admin_client,
                                               cost_budget_line_a, cost_budget_line_draft):
    response = cost_admin_client.get(reverse("projects:pbl_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert cost_budget_line_a.number in body
    grand = ProjectBudgetLine.objects.filter(tenant=tenant_a).aggregate(t=Sum("amount"))["t"]
    assert str(grand) in body  # the totals strip agrees with the DB


def test_cost_pbl_list_context_keys(tenant_a, cost_admin_client, cost_budget_line_a):
    response = cost_admin_client.get(reverse("projects:pbl_list"))
    assert response.context["grand_total"] is not None
    assert set(response.context["category_totals"].keys()) == {
        "labor", "material", "equipment", "subcontract", "overhead", "contingency", "other"}
    assert response.context["q"] == ""


def test_cost_bvr_list_renders_rows(tenant_a, cost_admin_client, cost_revision_activated,
                                    cost_revision_pending):
    response = cost_admin_client.get(reverse("projects:bvr_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert cost_revision_activated.number in body
    assert cost_revision_pending.number in body


def test_cost_cca_list_renders_rows_and_badges(tenant_a, cost_admin_client,
                                               cost_control_account_a,
                                               cost_control_account_b):
    response = cost_admin_client.get(reverse("projects:cca_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert cost_control_account_a.number in body
    assert "badge-green" in body  # both fixture CAs are "under" without expenses
    assert cost_control_account_a.cpi is None  # CPI renders as — on the register


def test_cost_pex_list_renders_rows_and_soft_reference(tenant_a, cost_admin_client,
                                                       cost_expense_posted,
                                                       cost_expense_draft,
                                                       cost_expense_void):
    response = cost_admin_client.get(reverse("projects:pex_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert cost_expense_posted.number in body
    assert "PO-00042" in body  # the soft source reference renders on the register
    assert cost_expense_void.number in body  # void rows stay visible


def test_cost_pbl_filter_narrows_like_the_orm(tenant_a, cost_admin_client,
                                              cost_budget_line_a, cost_budget_line_draft,
                                              cost_project_a):
    response = cost_admin_client.get(reverse("projects:pbl_list") +
                                     f"?project={cost_project_a.pk}&category=labor")
    expected = ProjectBudgetLine.objects.filter(
        tenant=tenant_a, project_id=cost_project_a.pk, category="labor").count()
    assert response.status_code == 200
    assert len(response.context["object_list"]) == expected


def test_cost_bvr_filter_status_narrows_like_the_orm(tenant_a, cost_admin_client,
                                                     cost_revision_activated,
                                                     cost_revision_pending):
    response = cost_admin_client.get(reverse("projects:bvr_list") + "?status=pending_approval")
    rows = list(response.context["object_list"])
    assert all(r.status == "pending_approval" for r in rows)
    assert {r.pk for r in rows} == {cost_revision_pending.pk}


def test_cost_registers_junk_params_return_the_default_page(tenant_a, cost_admin_client,
                                                            cost_budget_line_a,
                                                            cost_revision_activated,
                                                            cost_control_account_a,
                                                            cost_expense_posted):
    """L11: junk that cannot match is IGNORED — 200, and the register is not silently emptied.
    Page junk (?page=abc / ?page=9999) clamps to a valid page; only the row-page params assert
    the marker, because a clamped page may lawfully show different rows."""
    for url_name, marker in (("pbl_list", cost_budget_line_a.number),
                             ("bvr_list", cost_revision_activated.number),
                             ("cca_list", cost_control_account_a.number),
                             ("pex_list", cost_expense_posted.number)):
        for junk in JUNK_PARAMS:
            response = cost_admin_client.get(reverse(f"projects:{url_name}") + junk)
            assert response.status_code == 200, (url_name, junk)
            if "page=" not in junk:
                assert marker in response.content.decode(), (url_name, junk)


def test_cost_pbl_page_two_holds_the_overflow(tenant_a, cost_admin_client,
                                              cost_budget_line_a, cost_budget_line_draft,
                                              cost_revision_activated, cost_project_a):
    _cost_fill_lines(tenant_a, cost_revision_activated, cost_project_a, 16)
    first_page = cost_admin_client.get(reverse("projects:pbl_list"))
    assert first_page.status_code == 200
    assert len(first_page.context["object_list"]) == 15
    second_page = cost_admin_client.get(reverse("projects:pbl_list") + "?page=2")
    assert second_page.status_code == 200
    assert 1 <= len(second_page.context["object_list"]) <= 15
    page1_numbers = {o.number for o in first_page.context["object_list"]}
    page2_numbers = {o.number for o in second_page.context["object_list"]}
    assert not page1_numbers & page2_numbers


def test_cost_bvr_detail_renders_delta_headline_and_lines(tenant_a, cost_admin_client,
                                                          cost_revision_activated,
                                                          cost_budget_line_a,
                                                          cost_revision_pending):
    response = cost_admin_client.get(reverse("projects:bvr_detail",
                                             args=[cost_revision_pending.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert "-300.00" in body  # the pending revision's delta vs the 300 baseline
    assert response.context["category_totals"] is not None
    # A revision's page shows ITS OWN lines — the pending one has none, so the empty state:
    assert "No budget lines yet" in body
    # The baseline's own page renders its line rows and the category totals:
    base_page = cost_admin_client.get(reverse("projects:bvr_detail",
                                              args=[cost_revision_activated.pk]))
    assert cost_budget_line_a.number in base_page.content.decode()


def test_cost_cca_detail_renders_the_evm_panel(tenant_a, cost_admin_client,
                                               cost_control_account_a, cost_budget_line_a,
                                               cost_expense_posted):
    response = cost_admin_client.get(reverse("projects:cca_detail",
                                             args=[cost_control_account_a.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    for figure in ("300.00", "150.00", "100.00", "1.50", "200.00"):
        assert figure in body, figure
    assert "Planning-grade" in body      # the PV honesty caption
    assert response.context["budget_lines"] is not None
    assert response.context["expenses"] is not None


def test_cost_cca_detail_panel_pins_to_the_active_revision(tenant_a, cost_admin_client,
                                                           cost_control_account_a,
                                                           cost_budget_line_a,
                                                           cost_expense_posted,
                                                           cost_revision_activated):
    """A superseded-but-stamped revision's lines must not leak into the panel (the fixer's
    cca_detail pinning): the panel's budget_lines belong to the CURRENT baseline."""
    response = cost_admin_client.get(reverse("projects:cca_detail",
                                             args=[cost_control_account_a.pk]))
    lines = list(response.context["budget_lines"])
    assert {line.budget_revision_id for line in lines} == {cost_revision_activated.pk}


def test_cost_pbl_detail_renders(tenant_a, cost_admin_client, cost_budget_line_a):
    response = cost_admin_client.get(reverse("projects:pbl_detail",
                                             args=[cost_budget_line_a.pk]))
    assert response.status_code == 200
    assert cost_budget_line_a.number in response.content.decode()


def test_cost_pex_detail_renders_evidence(tenant_a, cost_admin_client, cost_expense_posted):
    response = cost_admin_client.get(reverse("projects:pex_detail",
                                             args=[cost_expense_posted.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert cost_expense_posted.number in body
    assert "PO-00042" in body


def test_cost_overview_carries_the_cost_cards(tenant_a, cost_admin_client,
                                              cost_revision_pending, cost_expense_posted):
    response = cost_admin_client.get(reverse("projects:overview"))
    assert response.status_code == 200
    assert response.context["pending_revisions"] == 1
    assert response.context["posted_spend"] == D("100.00")


# ==============================================================================================
# Create views — number minting, authorship stamp, tenant guard
# ==============================================================================================

def test_cost_bvr_create_posts_a_draft_and_stamps_author(tenant_a, cost_admin_client,
                                                         admin_user, cost_project_a,
                                                         cost_currency):
    data = {
        "project": cost_project_a.pk, "revision_no": "50", "title": "Created by test",
        "currency": cost_currency.pk, "reason": "test", "impact_note": "",
        "schedule_impact_note": "", "requested_by": "",
    }
    response = cost_admin_client.post(reverse("projects:bvr_create"), data, follow=True)
    assert response.status_code == 200
    obj = BudgetRevision.objects.get(project=cost_project_a, revision_no=50)
    assert obj.status == "draft" and obj.created_by == admin_user
    assert obj.number in response.content.decode()  # the success message carries the number


def test_cost_bvr_create_tenant_less_redirects_home(cost_tenantless_client, tenant_a,
                                                    cost_project_a):
    response = cost_tenantless_client.post(reverse("projects:bvr_create"), {})
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")


def test_cost_pbl_create_posts_a_line(tenant_a, cost_admin_client, cost_project_a,
                                      cost_revision_draft):
    response = cost_admin_client.post(reverse("projects:pbl_create"), {
        "budget_revision": cost_revision_draft.pk, "project": cost_project_a.pk,
        "category": "other", "amount": "77.00", "note": "",
    })
    assert response.status_code == 302
    assert ProjectBudgetLine.objects.filter(
        budget_revision=cost_revision_draft, category="other").exists()


def test_cost_pex_create_posts_a_draft(tenant_a, cost_admin_client, cost_project_a,
                                       cost_control_account_a):
    response = cost_admin_client.post(reverse("projects:pex_create"), {
        "project": cost_project_a.pk, "control_account": cost_control_account_a.pk,
        "entry_type": "actual", "source_kind": "manual", "source_number": "",
        "amount": "33.00", "entry_date": _cost_today().isoformat(), "description": "",
    })
    assert response.status_code == 302
    assert ProjectExpense.objects.filter(
        control_account=cost_control_account_a, amount=Decimal("33.00"),
        status="draft").exists()


def test_cost_cca_create_posts_an_account(tenant_a, cost_admin_client, cost_project_a):
    response = cost_admin_client.post(reverse("projects:cca_create"), {
        "project": cost_project_a.pk, "name": "Created CA", "code": "CA-V.1",
        "contingency": "0.00", "percent_complete": "0.00", "status": "planning",
        "note": "",
    })
    assert response.status_code == 302
    assert CostControlAccount.objects.filter(project=cost_project_a, code="CA-V.1").exists()


# ==============================================================================================
# Revision verbs — happy paths, refusals, replay, audit
# ==============================================================================================

def test_cost_bvr_submit_walk(tenant_a, cost_admin_client, admin_user, cost_revision_draft):
    response = cost_admin_client.post(reverse("projects:bvr_submit",
                                              args=[cost_revision_draft.pk]), follow=True)
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == reverse("projects:bvr_detail",
                                                    args=[cost_revision_draft.pk])
    cost_revision_draft.refresh_from_db()
    assert cost_revision_draft.status == "pending_approval"
    assert cost_revision_draft.requested_at is not None
    assert AuditLog.objects.filter(object_id=str(cost_revision_draft.pk),
                                   action="submit").exists()


def test_cost_bvr_submit_replay_refused_with_zero_deltas(tenant_a, cost_admin_client,
                                                         cost_revision_draft):
    cost_admin_client.post(reverse("projects:bvr_submit", args=[cost_revision_draft.pk]))
    before = BudgetRevision.objects.get(pk=cost_revision_draft.pk)
    response = cost_admin_client.post(reverse("projects:bvr_submit",
                                              args=[cost_revision_draft.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_draft.pk)
    assert "already" in response.content.decode()
    assert (before.status, before.requested_at, before.updated_at) == \
           (after.status, after.requested_at, after.updated_at)


def test_cost_bvr_approve_walk(tenant_a, cost_admin_client, admin_user,
                               cost_revision_pending):
    response = cost_admin_client.post(reverse("projects:bvr_approve",
                                              args=[cost_revision_pending.pk]), follow=True)
    assert response.status_code == 200
    cost_revision_pending.refresh_from_db()
    assert cost_revision_pending.status == "approved"
    assert cost_revision_pending.decided_by == admin_user
    assert cost_revision_pending.decided_at is not None
    assert cost_revision_pending.activated_at is None  # approve does NOT activate


def test_cost_bvr_approve_on_draft_refused(tenant_a, cost_admin_client, cost_revision_draft):
    before = BudgetRevision.objects.get(pk=cost_revision_draft.pk)
    response = cost_admin_client.post(reverse("projects:bvr_approve",
                                              args=[cost_revision_draft.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_draft.pk)
    assert "Only a revision pending approval" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_cost_bvr_reject_requires_notes(tenant_a, cost_admin_client, cost_revision_pending):
    before = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    response = cost_admin_client.post(reverse("projects:bvr_reject",
                                              args=[cost_revision_pending.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    assert "stated reason" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_cost_bvr_reject_walk_persists_the_evidence(tenant_a, cost_admin_client, admin_user,
                                                    cost_revision_pending):
    cost_admin_client.post(reverse("projects:bvr_reject", args=[cost_revision_pending.pk]),
                           {"decision_notes": "No budget for this."})
    cost_revision_pending.refresh_from_db()
    assert cost_revision_pending.status == "rejected"
    assert cost_revision_pending.decision_notes == "No budget for this."
    assert cost_revision_pending.decided_by == admin_user


def test_cost_bvr_activate_walk_supersedes_the_other_approved(tenant_a, cost_admin_client,
                                                              cost_revision_approved,
                                                              cost_revision_pending):
    second = _cost_revision(tenant_a, cost_revision_approved.project, no=9,
                            status="pending_approval")
    cost_admin_client.post(reverse("projects:bvr_approve", args=[second.pk]))
    cost_admin_client.post(reverse("projects:bvr_activate",
                                   args=[cost_revision_approved.pk]))
    cost_revision_approved.refresh_from_db()
    second.refresh_from_db()
    assert cost_revision_approved.activated_at is not None
    assert second.status == "superseded"  # approve-does-not-activate: supersedes ALL approved
    assert AuditLog.objects.filter(object_id=str(second.pk), action="supersede").exists()


def test_cost_bvr_activate_replay_says_so(tenant_a, cost_admin_client,
                                          cost_revision_approved):
    cost_admin_client.post(reverse("projects:bvr_activate", args=[cost_revision_approved.pk]))
    before = BudgetRevision.objects.get(pk=cost_revision_approved.pk)
    response = cost_admin_client.post(reverse("projects:bvr_activate",
                                              args=[cost_revision_approved.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_approved.pk)
    assert "already the active baseline" in response.content.decode()
    assert (after.activated_at, after.updated_at) == (before.activated_at, before.updated_at)


def test_cost_bvr_activate_on_pending_refused(tenant_a, cost_admin_client,
                                              cost_revision_pending):
    before = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    response = cost_admin_client.post(reverse("projects:bvr_activate",
                                              args=[cost_revision_pending.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_pending.pk)
    assert "Only an approved revision" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


# ==============================================================================================
# Expense verbs
# ==============================================================================================

def test_cost_pex_post_walk(tenant_a, cost_admin_client, cost_expense_draft,
                            cost_expense_posted, cost_control_account_a,
                            cost_budget_line_a):
    response = cost_admin_client.post(reverse("projects:pex_post",
                                              args=[cost_expense_draft.pk]), follow=True)
    assert response.status_code == 200
    cost_expense_draft.refresh_from_db()
    assert cost_expense_draft.status == "posted"
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("150.00")  # the seeded posted 100 + the newly posted 50


def test_cost_pex_post_replay_says_already(tenant_a, cost_admin_client, cost_expense_draft):
    cost_admin_client.post(reverse("projects:pex_post", args=[cost_expense_draft.pk]))
    before = ProjectExpense.objects.get(pk=cost_expense_draft.pk)
    response = cost_admin_client.post(reverse("projects:pex_post",
                                              args=[cost_expense_draft.pk]), follow=True)
    after = ProjectExpense.objects.get(pk=cost_expense_draft.pk)
    assert "already posted" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_cost_pex_void_walk(tenant_a, cost_admin_client, cost_expense_posted,
                            cost_control_account_a, cost_budget_line_a):
    response = cost_admin_client.post(reverse("projects:pex_void",
                                              args=[cost_expense_posted.pk]), follow=True)
    assert response.status_code == 200
    cost_expense_posted.refresh_from_db()
    assert cost_expense_posted.status == "void"
    ca = CostControlAccount.objects.get(pk=cost_control_account_a.pk)
    assert ca.ac == D("0.00")  # void stops counting
    assert ProjectExpense.objects.filter(pk=cost_expense_posted.pk).exists()  # stays visible


def test_cost_pex_void_on_draft_refused(tenant_a, cost_admin_client, cost_expense_draft):
    before = ProjectExpense.objects.get(pk=cost_expense_draft.pk)
    response = cost_admin_client.post(reverse("projects:pex_void",
                                              args=[cost_expense_draft.pk]), follow=True)
    after = ProjectExpense.objects.get(pk=cost_expense_draft.pk)
    assert "Only a posted expense can be voided" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_cost_pex_post_on_void_refused(tenant_a, cost_admin_client, cost_expense_posted):
    cost_expense_posted.status = "void"
    cost_expense_posted.save(update_fields=["status", "updated_at"])
    before = ProjectExpense.objects.get(pk=cost_expense_posted.pk)
    response = cost_admin_client.post(reverse("projects:pex_post",
                                              args=[cost_expense_posted.pk]), follow=True)
    after = ProjectExpense.objects.get(pk=cost_expense_posted.pk)
    assert "cannot be posted" in response.content.decode()
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


# ==============================================================================================
# Frozen rows — revisions, expenses, and the baseline's LINES (review I1)
# ==============================================================================================

def test_cost_bvr_edit_refused_on_activated_baseline(tenant_a, cost_admin_client,
                                                     cost_revision_activated):
    before = BudgetRevision.objects.get(pk=cost_revision_activated.pk)
    response = cost_admin_client.get(reverse("projects:bvr_edit",
                                             args=[cost_revision_activated.pk]), follow=True)
    after = BudgetRevision.objects.get(pk=cost_revision_activated.pk)
    assert "frozen cost history" in response.content.decode()
    assert (after.title, after.updated_at) == (before.title, before.updated_at)


def test_cost_bvr_delete_refused_on_activated_baseline(tenant_a, cost_admin_client,
                                                       cost_revision_activated):
    response = cost_admin_client.post(reverse("projects:bvr_delete",
                                              args=[cost_revision_activated.pk]), follow=True)
    assert BudgetRevision.objects.filter(pk=cost_revision_activated.pk).exists()
    assert "frozen cost history" in response.content.decode()


def test_cost_bvr_edit_and_delete_open_on_draft(tenant_a, cost_admin_client,
                                                cost_revision_draft):
    got = cost_admin_client.get(reverse("projects:bvr_edit", args=[cost_revision_draft.pk]))
    assert got.status_code == 200  # the form renders for an unlocked row
    response = cost_admin_client.post(reverse("projects:bvr_delete",
                                              args=[cost_revision_draft.pk]))
    assert response.status_code == 302
    assert not BudgetRevision.objects.filter(pk=cost_revision_draft.pk).exists()


def test_cost_pex_edit_delete_refused_on_posted(tenant_a, cost_admin_client,
                                                cost_expense_posted):
    got = cost_admin_client.get(reverse("projects:pex_edit",
                                        args=[cost_expense_posted.pk]), follow=True)
    assert "frozen cost evidence" in got.content.decode()
    cost_admin_client.post(reverse("projects:pex_delete", args=[cost_expense_posted.pk]))
    assert ProjectExpense.objects.filter(pk=cost_expense_posted.pk).exists()


def test_cost_pbl_edit_delete_refused_on_a_baseline_line(tenant_a, cost_admin_client,
                                                         cost_budget_line_a):
    """Review I1's ruling: the ACTIVE baseline cannot be rewritten through its lines."""
    got = cost_admin_client.get(reverse("projects:pbl_edit",
                                        args=[cost_budget_line_a.pk]), follow=True)
    assert "frozen cost history" in got.content.decode()
    cost_admin_client.post(reverse("projects:pbl_delete", args=[cost_budget_line_a.pk]))
    assert ProjectBudgetLine.objects.filter(pk=cost_budget_line_a.pk).exists()


def test_cost_pbl_edit_delete_open_on_a_draft_line(tenant_a, cost_admin_client,
                                                   cost_budget_line_draft):
    got = cost_admin_client.get(reverse("projects:pbl_edit",
                                        args=[cost_budget_line_draft.pk]))
    assert got.status_code == 200
    response = cost_admin_client.post(reverse("projects:pbl_delete",
                                              args=[cost_budget_line_draft.pk]))
    assert response.status_code == 302
    assert not ProjectBudgetLine.objects.filter(pk=cost_budget_line_draft.pk).exists()


# ==============================================================================================
# Deletes land on the list; audit rows record the removal
# ==============================================================================================

def test_cost_expense_delete_on_draft_lands_on_list_with_audit(tenant_a, cost_admin_client,
                                                               admin_user,
                                                               cost_expense_draft):
    response = cost_admin_client.post(reverse("projects:pex_delete",
                                              args=[cost_expense_draft.pk]), follow=True)
    assert response.request["PATH_INFO"] == reverse("projects:pex_list")
    assert not ProjectExpense.objects.filter(pk=cost_expense_draft.pk).exists()
    assert AuditLog.objects.filter(object_id=str(cost_expense_draft.pk),
                                   action="delete").exists()
