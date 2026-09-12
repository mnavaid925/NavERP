"""Projects 7.7 Scope & Requirements Management — VIEW tests.

The HTTP layer of the sub-module: 37 routes (10 requirement + 8 scope-item + 10 change-request
+ 9 verification + 1 computed matrix), the pages they render, **every context key the test
contract pins** (§4 of ``.claude/tasks/test-contract-projects-7.7.md``), the four registers'
search / filter / derived-lens / pagination behaviour, the sixteen POST verbs' state machines
and the pinned figures of the computed ``scope_matrix`` board.

Model invariants belong to ``test_scope_models.py`` and form validation to
``test_scope_forms.py``. Role gating (403), the GET-405 method guard, crafted cross-tenant
FKs, CSRF and anonymous access belong to ``test_scope_security.py`` — this lane makes every
request as a TENANT ADMIN (``scope_admin_client``), so the only thing that can refuse a verb
here is its own state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every list / detail / form asserts CONTENT — the row's own ``REQ-`` /
  ``SCI-`` / ``SCR-`` / ``SVR-`` number, its ``title`` / ``statement`` / ``deliverable``, the
  project name — and the detail pages additionally assert the verb control appropriate to the
  row's state.
* **A filter or lens that silently empties a register.** Every documented control on all four
  registers is compared against the ORM's own answer for the same narrowing; the derived lenses
  (``?untraced=1`` / ``?pending=1`` / ``?verified=1`` on requirements, ``?boundaries=1`` /
  ``?open=1`` on items, ``?pending=1`` / ``?high_impact=1`` on changes, ``?pending=1`` on
  verifications) are pinned to their real membership; and every junk value (``?status=nope``,
  ``?project=0``, ``?project=abc``, ``?page=abc``, ``?untraced=x``, ``?pending=``) returns a
  200 default page — never a 500, never a silently emptied register (L11).
* **A verb that writes when it should refuse.** All sixteen verbs are exercised on both sides:
  the happy paths (draft → submitted → approved → implemented → verified; open → validated →
  realized / retired; draft → submitted → under-review → approved / rejected → implemented;
  pending → accepted / rejected / waived) and every now-forbidden source state, each of which
  must answer with a message and leave the row's state untouched. ``sci_retire`` refusing a
  REALIZED row (I3) is pinned by name; ``scr_approve`` / ``scr_reject`` from BOTH ``submitted``
  and ``under_review`` are pinned allowed. Every verb is replayed once to confirm the second
  POST is refused with no re-stamp.
* **A locked row that still mutates.** A verified requirement, a realized / retired / violated
  scope item, an implemented change request and a decided verification refuse edit AND delete
  with the frozen-evidence message while the row survives byte-for-byte.
* **The pinned matrix figures.** ``scope_matrix`` context is asserted value-by-value: coverage
  (2/4 traced → 50.0), the row/cell dicts, the gap-list lengths, the three creep month buckets
  (40000/60000/10000 → bars 66.7/100.0/16.7, ``creep_max`` 60000.00), ``type_rows`` /
  ``priority_rows`` and ``scope_summary``; plus the 0-safe branch on an empty project.

Determinism (L16): every date basis is ``_scope_today()`` — never ``datetime.date.today()``.
Message assertions match ASCII SUBSTRINGs only (several messages carry U+2014 — a copy edit
must not turn into a red suite).

Naming (mandatory): every test is ``test_scope_*``, every module-level helper ``_scope_*`` /
``_SCOPE_*``. Scope: views / urls. Models, forms and permissions belong to the other lanes.

Step 4 of 6 for sub-module 7.7 (models → forms → **views** → security → …).
"""
import re
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.core.models import AuditLog
from apps.projects.models import (
    Requirement,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
)
from apps.projects.tests.conftest import (
    SCOPE_PAGE_SIZE,
    _scope_change,
    _scope_item,
    _scope_requirement,
    _scope_today,
    _scope_verification,
)

D = Decimal


# ==============================================================================================
# Route table, junk params, payload builders
# ==============================================================================================

#: The 37 route names with the contract's first path segment. Per-row routes are those that
#: are neither a register nor an ``add/`` form — reverse() needs a pk for them.
_SCOPE_NO_PK_ROUTES = {
    "req_list", "req_create", "sci_list", "sci_create", "scr_list", "scr_create",
    "svr_list", "svr_create", "scope_matrix",
}

_SCOPE_ROUTES = [
    ("req_list", "requirements/"), ("req_create", "requirements/"),
    ("req_detail", "requirements/"), ("req_edit", "requirements/"),
    ("req_delete", "requirements/"), ("req_submit", "requirements/"),
    ("req_approve", "requirements/"), ("req_reject", "requirements/"),
    ("req_implement", "requirements/"), ("req_verify", "requirements/"),
    ("sci_list", "scope-items/"), ("sci_create", "scope-items/"),
    ("sci_detail", "scope-items/"), ("sci_edit", "scope-items/"),
    ("sci_delete", "scope-items/"), ("sci_validate", "scope-items/"),
    ("sci_realize", "scope-items/"), ("sci_retire", "scope-items/"),
    ("scr_list", "scope-changes/"), ("scr_create", "scope-changes/"),
    ("scr_detail", "scope-changes/"), ("scr_edit", "scope-changes/"),
    ("scr_delete", "scope-changes/"), ("scr_submit", "scope-changes/"),
    ("scr_review", "scope-changes/"), ("scr_approve", "scope-changes/"),
    ("scr_reject", "scope-changes/"), ("scr_implement", "scope-changes/"),
    ("svr_list", "scope-verifications/"), ("svr_create", "scope-verifications/"),
    ("svr_detail", "scope-verifications/"), ("svr_edit", "scope-verifications/"),
    ("svr_delete", "scope-verifications/"), ("svr_accept", "scope-verifications/"),
    ("svr_reject", "scope-verifications/"), ("svr_waive", "scope-verifications/"),
    ("scope_matrix", "scope-matrix/"),
]


def _scope_reverse(name):
    """Reverse a 7.7 route, passing a pk only for the per-row patterns."""
    if name in _SCOPE_NO_PK_ROUTES:
        return reverse(f"projects:{name}")
    return reverse(f"projects:{name}", args=[1])

#: L11 junk that must never 500 and never silently empty a register. Only a ``?page=`` value
#: may lawfully change which rows render, so the marker assert skips it.
_SCOPE_JUNK_PARAMS = [
    "?status=nope", "?project=0", "?project=abc", "?page=abc", "?page=9999",
    "?item_type=%3Cscript%3E", "?acceptance_status=%C2%B2", "?owner=0",
]

#: Rows whose rendered page must never carry a raw template comment or a Python repr.
_SCOPE_LEAK_MARKERS = ("{#", "{% comment", "<QuerySet", "object at 0x")


def _scope_requirement_payload(project, **over):
    """A valid ``RequirementForm`` POST body (mirrors the form lane's builder)."""
    data = {
        "project": project.pk if project is not None else "",
        "parent": "", "wbs_node": "",
        "title": "View-built requirement",
        "description": "The capability the solution must provide.",
        "requirement_type": "functional", "elicitation_method": "interview",
        "elicitation_note": "", "source_party": "", "priority": "must",
        "acceptance_criteria": "", "version": "1.0", "verification_method": "test",
        "owner": "", "requested_by": "",
    }
    data.update(over)
    return data


def _scope_item_payload(project, **over):
    """A valid ``ScopeItemForm`` POST body."""
    data = {
        "project": project.pk if project is not None else "",
        "requirement": "", "item_type": "assumption",
        "statement": "View-built scope item", "description": "",
        "impact_area": "scope", "owner": "",
        "identified_date": _scope_today().isoformat(), "review_date": "",
    }
    data.update(over)
    return data


def _scope_change_payload(project, **over):
    """A valid ``ScopeChangeForm`` POST body."""
    data = {
        "project": project.pk if project is not None else "",
        "requirement": "", "risk": "",
        "title": "View-built change",
        "description": "The scope change the board is asked to weigh.",
        "justification": "", "source": "internal", "priority": "medium",
        "schedule_impact_days": "", "cost_impact": "0.00",
        "quality_impact": "none", "quality_note": "", "requested_by": "",
    }
    data.update(over)
    return data


def _scope_verification_payload(project, **over):
    """A valid ``ScopeVerificationForm`` POST body."""
    data = {
        "project": project.pk if project is not None else "",
        "wbs_node": "", "requirement": "",
        "deliverable": "View-built deliverable",
        "method": "inspection", "result": "pass",
        "inspected_by": "", "inspection_date": _scope_today().isoformat(),
        "findings": "",
    }
    data.update(over)
    return data


def _scope_error_queued(response):
    """True when the (possibly followed) response carried at least one error message."""
    return any(m.level_tag == "error" for m in get_messages(response.wsgi_request))


def _scope_row_index(rows):
    """``matrix_rows`` keyed by requirement pk — order-independent per-row assertions."""
    return {row["requirement"].pk: row for row in rows}


def _scope_creep_index(creep_rows):
    """``creep_rows`` keyed by the ``YYYY-MM`` period."""
    return {row["period"]: row for row in creep_rows}


def _scope_assert_no_leak(response):
    body = response.content.decode()
    for marker in _SCOPE_LEAK_MARKERS:
        assert marker not in body, marker


# ==============================================================================================
# A. Every route resolves to the contract's path
# ==============================================================================================

@pytest.mark.parametrize("name,prefix", _SCOPE_ROUTES)
def test_scope_route_reverses_to_the_contract_path(name, prefix):
    url = _scope_reverse(name)
    assert url.startswith(f"/projects/{prefix}"), url


def test_scope_route_names_are_37_and_disjoint():
    """The contract's 37 names, each with a distinct resolved path — a shadowed name shows up
    here as a collision rather than as a mysteriously wrong page."""
    urls = {name: _scope_reverse(name) for name, _prefix in _SCOPE_ROUTES}
    assert len(urls) == 37
    assert len(set(urls.values())) == 37  # every name points somewhere distinct


# ==============================================================================================
# B. GET pages render with REAL content
# ==============================================================================================

def test_scope_req_list_renders_the_seeded_number_and_title(scope_admin_client,
                                                            scope_requirement_draft):
    response = scope_admin_client.get(reverse("projects:req_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_requirement_draft.number in body
    assert scope_requirement_draft.title in body
    assert scope_requirement_draft.project.name in body
    for key in ("object_list", "page_obj", "q", "projects", "type_choices", "priority_choices",
                "status_choices", "method_choices", "owners", "requirements"):
        assert key in response.context, key


def test_scope_sci_list_renders_the_seeded_number_and_statement(scope_admin_client,
                                                                scope_item_open):
    response = scope_admin_client.get(reverse("projects:sci_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_item_open.number in body
    assert scope_item_open.statement in body
    for key in ("object_list", "page_obj", "q", "projects", "type_choices", "status_choices",
                "impact_choices", "owners"):
        assert key in response.context, key


def test_scope_scr_list_renders_the_seeded_number_and_title(scope_admin_client,
                                                            scope_change_draft):
    response = scope_admin_client.get(reverse("projects:scr_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_change_draft.number in body
    assert scope_change_draft.title in body
    for key in ("object_list", "page_obj", "q", "projects", "status_choices", "priority_choices",
                "source_choices", "requirements", "owners"):
        assert key in response.context, key


def test_scope_svr_list_renders_the_seeded_number_and_deliverable(scope_admin_client,
                                                                  scope_verification_pending):
    response = scope_admin_client.get(reverse("projects:svr_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_verification_pending.number in body
    assert scope_verification_pending.deliverable in body
    for key in ("object_list", "page_obj", "q", "projects", "method_choices", "result_choices",
                "status_choices", "requirements", "owners"):
        assert key in response.context, key


def test_scope_req_detail_renders_and_offers_the_submit_control(scope_admin_client,
                                                               scope_requirement_draft):
    """A ``submitted``-eligible row's page carries ITS OWN submit form action; every detail
    also pins the ``obj`` context key the template builds on."""
    response = scope_admin_client.get(
        reverse("projects:req_detail", args=[scope_requirement_draft.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_requirement_draft.number in body
    assert scope_requirement_draft.title in body
    assert reverse("projects:req_submit", args=[scope_requirement_draft.pk]) in body
    assert response.context["obj"].pk == scope_requirement_draft.pk


def test_scope_req_detail_verified_offers_no_approve_form(scope_admin_client,
                                                          scope_requirement_verified):
    """A verified row is frozen: the lifecycle block renders the frozen copy, not the verb
    controls."""
    response = scope_admin_client.get(
        reverse("projects:req_detail", args=[scope_requirement_verified.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_requirement_verified.number in body
    assert reverse("projects:req_approve", args=[scope_requirement_verified.pk]) not in body
    assert reverse("projects:req_verify", args=[scope_requirement_verified.pk]) not in body


def test_scope_req_detail_submitted_offers_the_approve_form(scope_admin_client,
                                                           scope_requirement_submitted):
    response = scope_admin_client.get(
        reverse("projects:req_detail", args=[scope_requirement_submitted.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert reverse("projects:req_approve", args=[scope_requirement_submitted.pk]) in body
    assert reverse("projects:req_reject", args=[scope_requirement_submitted.pk]) in body


def test_scope_sci_detail_renders_and_offers_the_realize_control(scope_admin_client,
                                                                 scope_item_open):
    response = scope_admin_client.get(
        reverse("projects:sci_detail", args=[scope_item_open.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_item_open.number in body
    assert scope_item_open.statement in body
    assert reverse("projects:sci_realize", args=[scope_item_open.pk]) in body
    assert response.context["obj"].pk == scope_item_open.pk


def test_scope_sci_detail_locked_row_hides_the_verb_forms(scope_admin_client,
                                                          scope_item_realized):
    response = scope_admin_client.get(
        reverse("projects:sci_detail", args=[scope_item_realized.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_item_realized.number in body
    assert reverse("projects:sci_realize", args=[scope_item_realized.pk]) not in body
    assert reverse("projects:sci_retire", args=[scope_item_realized.pk]) not in body


def test_scope_scr_detail_renders_and_offers_the_implement_control(scope_admin_client,
                                                                  scope_change_approved):
    response = scope_admin_client.get(
        reverse("projects:scr_detail", args=[scope_change_approved.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_change_approved.number in body
    assert scope_change_approved.title in body
    assert reverse("projects:scr_implement", args=[scope_change_approved.pk]) in body
    assert response.context["obj"].pk == scope_change_approved.pk


def test_scope_scr_detail_submitted_offers_the_board_controls(scope_admin_client,
                                                              scope_change_submitted):
    response = scope_admin_client.get(
        reverse("projects:scr_detail", args=[scope_change_submitted.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert reverse("projects:scr_approve", args=[scope_change_submitted.pk]) in body
    assert reverse("projects:scr_reject", args=[scope_change_submitted.pk]) in body


def test_scope_svr_detail_renders_and_offers_the_accept_control(scope_admin_client,
                                                                scope_verification_pending):
    response = scope_admin_client.get(
        reverse("projects:svr_detail", args=[scope_verification_pending.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_verification_pending.number in body
    assert scope_verification_pending.deliverable in body
    assert reverse("projects:svr_accept", args=[scope_verification_pending.pk]) in body
    assert response.context["obj"].pk == scope_verification_pending.pk


def test_scope_svr_detail_decided_row_hides_the_decision_forms(scope_admin_client,
                                                              scope_verification_accepted):
    response = scope_admin_client.get(
        reverse("projects:svr_detail", args=[scope_verification_accepted.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert scope_verification_accepted.number in body
    assert reverse("projects:svr_accept", args=[scope_verification_accepted.pk]) not in body


def test_scope_create_and_edit_forms_render_their_own_labels(scope_admin_client,
                                                             scope_project_a,
                                                             scope_requirement_draft):
    """The four create forms render 200 with the model form bound, and the requirement edit
    form renders the row's NUMBER in its breadcrumb (the ``is_edit`` branch)."""
    for name, marker in (("req_create", "Requirement"), ("sci_create", "Scope Item"),
                         ("scr_create", "Change"), ("svr_create", "Inspection")):
        response = scope_admin_client.get(reverse(f"projects:{name}"))
        assert response.status_code == 200, name
        assert marker in response.content.decode(), name
        assert response.context["is_edit"] is False, name
    edit = scope_admin_client.get(
        reverse("projects:req_edit", args=[scope_requirement_draft.pk]))
    assert edit.status_code == 200
    assert edit.context["is_edit"] is True
    assert scope_requirement_draft.number in edit.content.decode()


def test_scope_edit_forms_render_for_each_unlocked_entity(scope_admin_client, scope_item_open,
                                                          scope_change_draft,
                                                          scope_verification_pending):
    for name, obj in (("sci_edit", scope_item_open), ("scr_edit", scope_change_draft),
                      ("svr_edit", scope_verification_pending)):
        response = scope_admin_client.get(reverse(f"projects:{name}", args=[obj.pk]))
        assert response.status_code == 200, name
        assert obj.number in response.content.decode(), name
        assert response.context["obj"].pk == obj.pk, name


def test_scope_create_form_seeds_the_project_from_the_query_string(scope_admin_client,
                                                                   scope_project_a):
    """``?project=`` pre-selects the FK on every create form (``as_db_int``-guarded initial)."""
    for name in ("req_create", "sci_create", "scr_create", "svr_create"):
        response = scope_admin_client.get(
            reverse(f"projects:{name}") + f"?project={scope_project_a.pk}")
        assert response.status_code == 200, name
        assert response.context["form"].initial.get("project") == scope_project_a.pk, name


# ==============================================================================================
# C. The pinned scope_matrix figures (Python value first, one HTML spot-check)
# ==============================================================================================

def _scope_matrix_response(scope_admin_client, scope_matrix_project_a):
    return scope_admin_client.get(
        reverse("projects:scope_matrix") + f"?project={scope_matrix_project_a.pk}")


def test_scope_matrix_coverage_figures(
        scope_admin_client, scope_matrix_project_a, scope_wbs_m1, scope_wbs_m2,
        scope_matrix_req_traced_approved, scope_matrix_req_untraced_draft,
        scope_matrix_req_traced_implemented_verified, scope_matrix_req_untraced_approved,
        scope_matrix_ver_accepted, scope_matrix_ver_pending, scope_matrix_ver_orphan,
        scope_matrix_change_m1, scope_matrix_change_m2, scope_matrix_change_m3,
        scope_matrix_change_low, scope_matrix_item_in_scope,
        scope_matrix_item_out_of_scope, scope_matrix_item_constraint_validated_overdue,
        scope_matrix_item_assumption, scope_matrix_item_dependency_realized):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    assert response.status_code == 200
    coverage = response.context["coverage"]
    assert coverage["total"] == 4
    assert coverage["traced"] == 2
    assert coverage["untraced"] == 2
    assert coverage["verified"] == 1
    assert coverage["coverage_pct"] == 50.0


def test_scope_matrix_work_packages_and_wp_total(scope_admin_client, scope_matrix_project_a,
                                                 scope_wbs_m1, scope_wbs_m2):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    assert [wp.pk for wp in response.context["work_packages"]] == \
        [scope_wbs_m1.pk, scope_wbs_m2.pk]
    assert response.context["wp_total"] == 2


def test_scope_matrix_rows_cells_and_verification_counts(
        scope_admin_client, scope_matrix_project_a, scope_wbs_m1, scope_wbs_m2,
        scope_matrix_req_traced_approved, scope_matrix_req_untraced_draft,
        scope_matrix_req_traced_implemented_verified, scope_matrix_req_untraced_approved,
        scope_matrix_ver_accepted, scope_matrix_ver_pending, scope_matrix_ver_orphan):
    """Each requirement's row is asserted by IDENTITY (keyed on its pk), so the pinned cell /
    count triple cannot be satisfied by a different row of the same shape."""
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    rows = _scope_row_index(response.context["matrix_rows"])
    assert len(rows) == 4
    expected = {
        scope_matrix_req_traced_approved.pk: ([True, False], True, 0, 0),
        scope_matrix_req_untraced_draft.pk: ([False, False], False, 0, 0),
        scope_matrix_req_traced_implemented_verified.pk: ([False, True], True, 2, 1),
        scope_matrix_req_untraced_approved.pk: ([False, False], False, 0, 0),
    }
    for pk, (cells, traced, ver_count, ver_ok) in expected.items():
        row = rows[pk]
        assert row["cells"] == cells, pk
        assert row["traced"] is traced, pk
        assert row["verification_count"] == ver_count, pk
        assert row["verified_count"] == ver_ok, pk


def test_scope_matrix_gap_lists(scope_admin_client, scope_matrix_project_a,
                                scope_matrix_req_traced_approved,
                                scope_matrix_req_untraced_draft,
                                scope_matrix_req_traced_implemented_verified,
                                scope_matrix_req_untraced_approved):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    untraced = {r.pk for r in response.context["untraced"]}
    unverified = {r.pk for r in response.context["unverified"]}
    assert untraced == {scope_matrix_req_untraced_draft.pk,
                        scope_matrix_req_untraced_approved.pk}
    assert unverified == {scope_matrix_req_traced_approved.pk,
                          scope_matrix_req_untraced_approved.pk}
    assert len(response.context["untraced"]) == 2
    assert len(response.context["unverified"]) == 2


def test_scope_matrix_creep_rows_and_max(scope_admin_client, scope_matrix_project_a,
                                         scope_matrix_change_m1, scope_matrix_change_m2,
                                         scope_matrix_change_m3):
    """The three month buckets are pinned by period, with the Decimal ``bar_pct`` compared by
    ``str()`` (the contract's own instruction — the 0-safe branch returns a float instead)."""
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    rows = _scope_creep_index(response.context["creep_rows"])
    assert [r["period"] for r in response.context["creep_rows"]] == sorted(rows)
    assert len(rows) == 3
    months = sorted(rows)
    first, second, third = (rows[m] for m in months)
    # Ordered oldest → newest: 40000 (2 months back), 60000 (last month), 10000 (this month).
    assert first["count"] == 1 and first["schedule_days"] == 0
    assert second["count"] == 1 and second["schedule_days"] == 0
    assert third["count"] == 1 and third["schedule_days"] == 12
    assert str(first["cost_total"]) == "40000.00"
    assert str(second["cost_total"]) == "60000.00"
    assert str(third["cost_total"]) == "10000.00"
    assert str(first["bar_pct"]) == "66.7"
    assert str(second["bar_pct"]) == "100.0"
    assert str(third["bar_pct"]) == "16.7"
    assert str(response.context["creep_max"]) == "60000.00"
    assert first["label"] and second["label"] and third["label"]


def test_scope_matrix_creep_totals_and_high_impact(scope_admin_client, scope_matrix_project_a,
                                                   scope_matrix_change_m1,
                                                   scope_matrix_change_m2,
                                                   scope_matrix_change_m3):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    creep = response.context["creep"]
    assert creep["count"] == 3
    assert str(creep["cost_total"]) == "110000.00"
    assert creep["schedule_days"] == 12
    assert creep["high_impact_count"] == 2


def test_scope_matrix_draft_control_row_is_not_in_creep(scope_admin_client,
                                                        scope_matrix_project_a,
                                                        scope_matrix_change_low,
                                                        scope_matrix_change_m1,
                                                        scope_matrix_change_m2,
                                                        scope_matrix_change_m3):
    """``scope_matrix_change_low`` is a DRAFT with a huge cost impact: the creep panel reads
    STATUS, so it moves no figure — while the register and the high-impact lens still see it."""
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    assert response.context["creep"]["count"] == 3
    assert str(response.context["creep_max"]) == "60000.00"
    assert str(response.context["creep"]["cost_total"]) == "110000.00"
    assert str(scope_matrix_change_low.cost_impact) == "999999.00"  # materially huge, ignored


def test_scope_matrix_type_and_priority_rows_in_choice_order(
        scope_admin_client, scope_matrix_project_a, scope_matrix_req_traced_approved,
        scope_matrix_req_untraced_draft, scope_matrix_req_traced_implemented_verified,
        scope_matrix_req_untraced_approved):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    assert response.context["type_rows"] == [
        {"label": "Functional", "count": 2},
        {"label": "Non-Functional", "count": 0},
        {"label": "Business", "count": 1},
        {"label": "Technical", "count": 1},
        {"label": "Regulatory", "count": 0},
        {"label": "Interface", "count": 0},
    ]
    assert response.context["priority_rows"] == [
        {"label": "Must Have", "count": 2},
        {"label": "Should Have", "count": 1},
        {"label": "Could Have", "count": 1},
        {"label": "Won't Have", "count": 0},
    ]


def test_scope_matrix_scope_summary(scope_admin_client, scope_matrix_project_a,
                                    scope_matrix_item_in_scope,
                                    scope_matrix_item_out_of_scope,
                                    scope_matrix_item_constraint_validated_overdue,
                                    scope_matrix_item_assumption,
                                    scope_matrix_item_dependency_realized):
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    assert response.context["scope_summary"] == {
        "items": 5, "boundaries": 2, "constraints": 1, "assumptions": 1,
        "open_items": 4, "overdue_items": 1,
    }


def test_scope_matrix_renders_a_few_figures_into_html(
        scope_admin_client, scope_matrix_project_a, scope_matrix_req_traced_approved,
        scope_matrix_req_untraced_draft, scope_matrix_req_traced_implemented_verified,
        scope_matrix_req_untraced_approved, scope_matrix_change_m1, scope_matrix_change_m2,
        scope_matrix_change_m3):
    """ONE test ties the context contract to the wire: the same figures the context tests pin
    must actually appear, or the template reads a different key than the view writes (L8)."""
    response = _scope_matrix_response(scope_admin_client, scope_matrix_project_a)
    body = response.content.decode()
    assert "50.0%" in body             # coverage_pct on the stat card
    assert "60000.00" in body          # creep_max in the bar caption
    assert "Sep" in body or "Aug" in body or "Jul" in body  # a creep month label
    assert scope_matrix_project_a.name in body


def test_scope_matrix_empty_project_is_zero_safe(scope_admin_client, tenant_a, admin_user):
    """A project with no rows of any kind: 0-safe coverage, empty lists, ``creep_max`` 0 and
    therefore no bar percentage — and the page still renders 200."""
    from apps.projects.tests.conftest import _projectinitiation_project
    empty = _projectinitiation_project(
        tenant_a, name="Scope empty host", code="SME-01", status="active",
        created_by=admin_user)
    response = scope_admin_client.get(
        reverse("projects:scope_matrix") + f"?project={empty.pk}")
    assert response.status_code == 200
    assert response.context["coverage"]["total"] == 0
    assert response.context["coverage"]["traced"] == 0
    assert response.context["coverage"]["untraced"] == 0
    assert response.context["coverage"]["verified"] == 0
    assert response.context["coverage"]["coverage_pct"] == 0.0
    assert response.context["matrix_rows"] == []
    assert response.context["untraced"] == []
    assert response.context["unverified"] == []
    assert response.context["creep_rows"] == []
    assert response.context["creep_max"] == 0
    creep = response.context["creep"]
    assert creep["count"] == 0
    assert str(creep["cost_total"]) == "0.00"
    assert creep["schedule_days"] == 0
    assert creep["high_impact_count"] == 0
    assert response.context["work_packages"] == []
    assert response.context["wp_total"] == 0
    assert all(row["count"] == 0 for row in response.context["type_rows"])
    assert all(row["count"] == 0 for row in response.context["priority_rows"])
    assert response.context["scope_summary"] == {
        "items": 0, "boundaries": 0, "constraints": 0, "assumptions": 0,
        "open_items": 0, "overdue_items": 0,
    }


def test_scope_matrix_zero_cost_creep_row_gets_float_zero_bar(scope_admin_client, tenant_a,
                                                              admin_user):
    """The 0-safe branch is ``if creep_max else 0.0``: a row whose ``cost_total`` is 0 still
    renders a ``bar_pct`` of the plain float ``0.0``, never a ZeroDivisionError."""
    from apps.projects.tests.conftest import _projectinitiation_project
    project = _projectinitiation_project(tenant_a, name="Scope zero creep", code="SMZ-01",
                                         status="active", created_by=admin_user)
    _scope_change(tenant_a, project, status="approved")
    response = scope_admin_client.get(
        reverse("projects:scope_matrix") + f"?project={project.pk}")
    assert response.status_code == 200
    rows = response.context["creep_rows"]
    assert len(rows) == 1
    assert str(rows[0]["cost_total"]) == "0.00"
    assert rows[0]["bar_pct"] == 0.0
    assert response.context["creep_max"] == 0


def test_scope_matrix_without_project_is_tenant_wide_without_columns(
        scope_admin_client, scope_matrix_project_a, scope_matrix_req_traced_approved):
    """No ``?project=`` → tenant-wide figures, no columns (``work_packages == []``)."""
    response = scope_admin_client.get(reverse("projects:scope_matrix"))
    assert response.status_code == 200
    assert response.context["project"] is None
    assert response.context["work_packages"] == []
    assert response.context["wp_total"] == 0


def test_scope_matrix_foreign_project_pk_is_a_tenant_wide_no_op(scope_admin_client,
                                                                scope_project_b):
    """A valid tenant-B pk skips the scope (``.filter(tenant=...).first()`` → None) rather than
    404ing or leaking tenant-B rows."""
    response = scope_admin_client.get(
        reverse("projects:scope_matrix") + f"?project={scope_project_b.pk}")
    assert response.status_code == 200
    assert response.context["project"] is None


def test_scope_matrix_junk_project_param_is_ignored(scope_admin_client):
    """L11: ``?project=abc`` is ``as_db_int``-guarded → 200 tenant-wide, never a 500."""
    for junk in ("?project=abc", "?project=99999999999999999999", "?project=%C2%B2"):
        response = scope_admin_client.get(reverse("projects:scope_matrix") + junk)
        assert response.status_code == 200, junk
        assert response.context["project"] is None, junk


# ==============================================================================================
# D. Search + filters + derived lenses + pagination
# ==============================================================================================

def test_scope_req_search_hits_and_misses(scope_admin_client, scope_requirement_draft,
                                          scope_requirement_submitted):
    hit = scope_admin_client.get(reverse("projects:req_list") + "?q=delivery evidence")
    assert scope_requirement_draft.pk in {o.pk for o in hit.context["object_list"]}
    miss = scope_admin_client.get(reverse("projects:req_list") + "?q=zzz-nothing-matches")
    assert len(list(miss.context["object_list"])) == 0
    # the number is one of the search fields too
    by_number = scope_admin_client.get(
        reverse("projects:req_list") + f"?q={scope_requirement_submitted.number}")
    assert scope_requirement_submitted.pk in {o.pk for o in by_number.context["object_list"]}


def test_scope_sci_search_hits_and_misses(scope_admin_client, scope_item_open):
    hit = scope_admin_client.get(reverse("projects:sci_list") + "?q=depot Wi-Fi")
    assert scope_item_open.pk in {o.pk for o in hit.context["object_list"]}
    miss = scope_admin_client.get(reverse("projects:sci_list") + "?q=zzz-nothing-matches")
    assert len(list(miss.context["object_list"])) == 0


def test_scope_scr_search_hits_and_misses(scope_admin_client, scope_change_submitted):
    hit = scope_admin_client.get(reverse("projects:scr_list") + "?q=northern depot")
    assert scope_change_submitted.pk in {o.pk for o in hit.context["object_list"]}
    miss = scope_admin_client.get(reverse("projects:scr_list") + "?q=zzz-nothing-matches")
    assert len(list(miss.context["object_list"])) == 0


def test_scope_svr_search_hits_and_misses(scope_admin_client, scope_verification_pending):
    hit = scope_admin_client.get(reverse("projects:svr_list") + "?q=onboarding runbook")
    assert scope_verification_pending.pk in {o.pk for o in hit.context["object_list"]}
    miss = scope_admin_client.get(reverse("projects:svr_list") + "?q=zzz-nothing-matches")
    assert len(list(miss.context["object_list"])) == 0


def test_scope_req_filters_match_orm_exactly(scope_admin_client, scope_project_a,
                                             scope_requirement_draft,
                                             scope_requirement_approved):
    cases = [("project", scope_project_a.pk), ("requirement_type", "functional"),
             ("elicitation_method", "interview"), ("priority", "must"), ("status", "draft")]
    for param, value in cases:
        response = scope_admin_client.get(
            reverse("projects:req_list") + f"?{param}={value}")
        assert response.status_code == 200, param
        expected = Requirement.objects.filter(tenant=scope_project_a.tenant_id,
                                              **{param: value})
        assert {o.pk for o in response.context["object_list"]} == \
            {o.pk for o in expected}, param


def test_scope_req_filter_junk_value_is_a_200_no_op(scope_admin_client, scope_requirement_draft):
    """A junk enum must not silently empty the register (L11)."""
    for junk in ("?status=nope", "?requirement_type=%3Cscript%3E", "?project=0", "?owner=0",
                 "?project=abc"):
        response = scope_admin_client.get(reverse("projects:req_list") + junk)
        assert response.status_code == 200, junk
        assert scope_requirement_draft.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_sci_filters_and_junk(scope_admin_client, tenant_a, scope_project_a, scope_item_open,
                                    scope_item_realized):
    for param, value in (("item_type", "assumption"), ("status", "open"),
                         ("impact_area", "scope")):
        response = scope_admin_client.get(reverse("projects:sci_list") + f"?{param}={value}")
        assert response.status_code == 200, param
        expected = ScopeItem.objects.filter(tenant=tenant_a, **{param: value})
        assert {o.pk for o in response.context["object_list"]} == \
            {o.pk for o in expected}, param
    for junk in ("?status=nope", "?item_type=zzz", "?project=0", "?project=abc"):
        response = scope_admin_client.get(reverse("projects:sci_list") + junk)
        assert response.status_code == 200, junk
        assert scope_item_open.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_scr_filters_and_junk(scope_admin_client, tenant_a, scope_change_submitted,
                                    scope_change_draft):
    for param, value in (("status", "submitted"), ("priority", "medium"), ("source", "internal")):
        response = scope_admin_client.get(reverse("projects:scr_list") + f"?{param}={value}")
        assert response.status_code == 200, param
        expected = ScopeChangeRequest.objects.filter(tenant=tenant_a, **{param: value})
        assert {o.pk for o in response.context["object_list"]} == \
            {o.pk for o in expected}, param
    for junk in ("?status=nope", "?source=zzz", "?project=0", "?project=abc"):
        response = scope_admin_client.get(reverse("projects:scr_list") + junk)
        assert response.status_code == 200, junk
        assert scope_change_submitted.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_svr_filters_and_junk(scope_admin_client, tenant_a, scope_verification_pending,
                                    scope_verification_accepted):
    for param, value in (("acceptance_status", "pending"), ("result", "conditional"),
                         ("method", "review")):
        response = scope_admin_client.get(reverse("projects:svr_list") + f"?{param}={value}")
        assert response.status_code == 200, param
        expected = ScopeVerification.objects.filter(tenant=tenant_a, **{param: value})
        assert {o.pk for o in response.context["object_list"]} == \
            {o.pk for o in expected}, param
    for junk in ("?acceptance_status=nope", "?result=zzz", "?project=0", "?project=abc"):
        response = scope_admin_client.get(reverse("projects:svr_list") + junk)
        assert response.status_code == 200, junk
        assert scope_verification_pending.pk in \
            {o.pk for o in response.context["object_list"]}, junk


def test_scope_registers_junk_params_return_the_default_page(scope_admin_client,
                                                             scope_requirement_draft,
                                                             scope_item_open,
                                                             scope_change_submitted,
                                                             scope_verification_pending):
    """L11 sweep: the same junk set against all four registers is 200 and never empties the
    page (``?page=`` may lawfully change which rows render, so its marker is skipped)."""
    markers = {"req_list": scope_requirement_draft.pk, "sci_list": scope_item_open.pk,
               "scr_list": scope_change_submitted.pk, "svr_list": scope_verification_pending.pk}
    for url_name, marker in markers.items():
        for junk in _SCOPE_JUNK_PARAMS:
            response = scope_admin_client.get(reverse(f"projects:{url_name}") + junk)
            assert response.status_code == 200, (url_name, junk)
            if "page=" not in junk:
                assert marker in {o.pk for o in response.context["object_list"]}, \
                    (url_name, junk)


def test_scope_req_lenses_narrow_correctly(scope_admin_client, tenant_a, scope_requirement_draft,
                                           scope_requirement_submitted,
                                           scope_requirement_approved,
                                           scope_requirement_verified):
    untraced = scope_admin_client.get(reverse("projects:req_list") + "?untraced=1")
    assert {o.pk for o in untraced.context["object_list"]} == \
        {o.pk for o in Requirement.objects.filter(tenant=tenant_a, wbs_node__isnull=True)}

    pending = scope_admin_client.get(reverse("projects:req_list") + "?pending=1")
    assert {o.pk for o in pending.context["object_list"]} == \
        {o.pk for o in Requirement.objects.filter(tenant=tenant_a,
                                                  status__in=("draft", "submitted"))}
    assert scope_requirement_approved.pk not in {o.pk for o in pending.context["object_list"]}

    verified = scope_admin_client.get(reverse("projects:req_list") + "?verified=1")
    assert {o.pk for o in verified.context["object_list"]} == {scope_requirement_verified.pk}


def test_scope_req_lens_junk_value_is_a_no_op(scope_admin_client, scope_requirement_draft):
    for junk in ("?untraced=x", "?pending=", "?untraced=0", "?pending=true"):
        response = scope_admin_client.get(reverse("projects:req_list") + junk)
        assert response.status_code == 200, junk
        assert scope_requirement_draft.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_sci_lenses_narrow_correctly(scope_admin_client, tenant_a, scope_item_open,
                                           scope_item_validated, scope_item_realized,
                                           scope_matrix_item_in_scope):
    """The boundary lens reads the model's ``BOUNDARY_TYPES``; the open lens reads
    ``is_open``. Both are pre-scoped on real columns, so the ORM can prove them."""
    boundaries = scope_admin_client.get(reverse("projects:sci_list") + "?boundaries=1")
    assert {o.pk for o in boundaries.context["object_list"]} == \
        {o.pk for o in ScopeItem.objects.filter(tenant=tenant_a, item_type__in=("in_scope",
                                                                                "out_of_scope"))}
    assert scope_item_open.pk not in {o.pk for o in boundaries.context["object_list"]}

    open_rows = scope_admin_client.get(reverse("projects:sci_list") + "?open=1")
    assert {o.pk for o in open_rows.context["object_list"]} == \
        {o.pk for o in ScopeItem.objects.filter(tenant=tenant_a,
                                                status__in=("open", "validated"))}
    assert scope_item_realized.pk not in {o.pk for o in open_rows.context["object_list"]}


def test_scope_sci_lens_junk_value_is_a_no_op(scope_admin_client, scope_item_open):
    for junk in ("?boundaries=x", "?open=", "?boundaries=0"):
        response = scope_admin_client.get(reverse("projects:sci_list") + junk)
        assert response.status_code == 200, junk
        assert scope_item_open.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_scr_lenses_narrow_correctly(scope_admin_client, tenant_a, scope_change_draft,
                                           scope_change_submitted, scope_change_under_review,
                                           scope_change_approved, scope_change_high_impact,
                                           scope_change_sub_threshold):
    pending = scope_admin_client.get(reverse("projects:scr_list") + "?pending=1")
    assert {o.pk for o in pending.context["object_list"]} == \
        {o.pk for o in ScopeChangeRequest.objects.filter(
            tenant=tenant_a, status__in=("draft", "submitted", "under_review"))}
    assert scope_change_approved.pk not in {o.pk for o in pending.context["object_list"]}

    high = scope_admin_client.get(reverse("projects:scr_list") + "?high_impact=1")
    high_pks = {o.pk for o in high.context["object_list"]}
    assert scope_change_high_impact.pk in high_pks
    assert scope_change_sub_threshold.pk not in high_pks  # one unit below every threshold
    for row in high.context["object_list"]:
        assert row.is_high_impact


def test_scope_scr_lens_junk_value_is_a_no_op(scope_admin_client, scope_change_submitted):
    for junk in ("?pending=x", "?high_impact=", "?pending=0"):
        response = scope_admin_client.get(reverse("projects:scr_list") + junk)
        assert response.status_code == 200, junk
        assert scope_change_submitted.pk in {o.pk for o in response.context["object_list"]}, junk


def test_scope_svr_lens_narrows_correctly(scope_admin_client, tenant_a,
                                          scope_verification_pending,
                                          scope_verification_accepted):
    pending = scope_admin_client.get(reverse("projects:svr_list") + "?pending=1")
    assert {o.pk for o in pending.context["object_list"]} == \
        {o.pk for o in ScopeVerification.objects.filter(tenant=tenant_a,
                                                        acceptance_status="pending")}
    assert scope_verification_accepted.pk not in {o.pk for o in pending.context["object_list"]}


def test_scope_svr_lens_junk_value_is_a_no_op(scope_admin_client, scope_verification_pending):
    for junk in ("?pending=x", "?pending=", "?pending=0"):
        response = scope_admin_client.get(reverse("projects:svr_list") + junk)
        assert response.status_code == 200, junk
        assert scope_verification_pending.pk in \
            {o.pk for o in response.context["object_list"]}, junk


def test_scope_req_pagination_splits_at_page_size(scope_admin_client, tenant_a, scope_project_a,
                                                  scope_requirement_draft):
    from apps.projects.tests.conftest import _scope_fill_requirements
    _scope_fill_requirements(tenant_a, scope_project_a, SCOPE_PAGE_SIZE + 1)
    first = scope_admin_client.get(reverse("projects:req_list"))
    assert first.status_code == 200
    assert len(first.context["object_list"]) == SCOPE_PAGE_SIZE
    second = scope_admin_client.get(reverse("projects:req_list") + "?page=2")
    assert second.status_code == 200
    assert len(second.context["object_list"]) == \
        (SCOPE_PAGE_SIZE + 2) - SCOPE_PAGE_SIZE  # the draft fixture + 16 fills = 17 rows
    page1 = {o.pk for o in first.context["object_list"]}
    page2 = {o.pk for o in second.context["object_list"]}
    assert not page1 & page2


def test_scope_sci_pagination_splits_at_page_size(scope_admin_client, tenant_a, scope_project_a):
    from apps.projects.tests.conftest import _scope_fill_items
    _scope_fill_items(tenant_a, scope_project_a, SCOPE_PAGE_SIZE + 1)
    first = scope_admin_client.get(reverse("projects:sci_list"))
    second = scope_admin_client.get(reverse("projects:sci_list") + "?page=2")
    assert first.status_code == 200 and second.status_code == 200
    assert len(first.context["object_list"]) == SCOPE_PAGE_SIZE
    assert len(second.context["object_list"]) == 1
    page1 = {o.pk for o in first.context["object_list"]}
    page2 = {o.pk for o in second.context["object_list"]}
    assert not page1 & page2


def test_scope_scr_pagination_splits_at_page_size(scope_admin_client, tenant_a, scope_project_a):
    from apps.projects.tests.conftest import _scope_fill_changes
    _scope_fill_changes(tenant_a, scope_project_a, SCOPE_PAGE_SIZE + 1)
    first = scope_admin_client.get(reverse("projects:scr_list"))
    second = scope_admin_client.get(reverse("projects:scr_list") + "?page=2")
    assert first.status_code == 200 and second.status_code == 200
    assert len(first.context["object_list"]) == SCOPE_PAGE_SIZE
    assert len(second.context["object_list"]) == 1
    assert not ({o.pk for o in first.context["object_list"]}
                & {o.pk for o in second.context["object_list"]})


def test_scope_svr_pagination_splits_at_page_size(scope_admin_client, tenant_a, scope_project_a):
    for i in range(SCOPE_PAGE_SIZE + 1):
        _scope_verification(tenant_a, scope_project_a, deliverable=f"Backlog inspection {i:02d}")
    first = scope_admin_client.get(reverse("projects:svr_list"))
    second = scope_admin_client.get(reverse("projects:svr_list") + "?page=2")
    assert first.status_code == 200 and second.status_code == 200
    assert len(first.context["object_list"]) == SCOPE_PAGE_SIZE
    assert len(second.context["object_list"]) == 1
    assert not ({o.pk for o in first.context["object_list"]}
                & {o.pk for o in second.context["object_list"]})


def test_scope_page_two_abc_clamps_to_page_one(scope_admin_client, scope_requirement_draft):
    """L9/L11: ``?page=abc`` is page 1, not a 500 and not an empty page."""
    response = scope_admin_client.get(reverse("projects:req_list") + "?page=abc")
    assert response.status_code == 200
    assert response.context["page_obj"].number == 1
    assert scope_requirement_draft.pk in {o.pk for o in response.context["object_list"]}


# ==============================================================================================
# E. CRUD round trips — create, edit, delete
# ==============================================================================================

def test_scope_req_create_round_trip(scope_admin_client, admin_user, tenant_a, scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:req_create"),
        _scope_requirement_payload(scope_project_a, title="Created by the view lane"))
    assert response.status_code == 302
    obj = Requirement.objects.get(tenant=tenant_a, title="Created by the view lane")
    assert response.url == reverse("projects:req_detail", args=[obj.pk])
    assert obj.created_by == admin_user
    assert obj.requested_by == admin_user  # stamped when the form left it blank
    assert re.fullmatch(r"REQ-\d{5}", obj.number)
    assert obj.status == "draft"
    assert AuditLog.objects.filter(object_id=str(obj.pk), action="create").exists()


def test_scope_sci_create_round_trip(scope_admin_client, admin_user, tenant_a, scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:sci_create"),
        _scope_item_payload(scope_project_a, statement="Created by the view lane"))
    assert response.status_code == 302
    obj = ScopeItem.objects.get(tenant=tenant_a, statement="Created by the view lane")
    assert response.url == reverse("projects:sci_detail", args=[obj.pk])
    assert obj.created_by == admin_user
    assert re.fullmatch(r"SCI-\d{5}", obj.number)
    assert obj.status == "open"


def test_scope_scr_create_round_trip(scope_admin_client, admin_user, tenant_a, scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:scr_create"),
        _scope_change_payload(scope_project_a, title="Created by the view lane"))
    assert response.status_code == 302
    obj = ScopeChangeRequest.objects.get(tenant=tenant_a, title="Created by the view lane")
    assert response.url == reverse("projects:scr_detail", args=[obj.pk])
    assert obj.created_by == admin_user
    assert obj.requested_by == admin_user
    assert re.fullmatch(r"SCR-\d{5}", obj.number)
    assert obj.status == "draft"


def test_scope_svr_create_round_trip(scope_admin_client, admin_user, tenant_a, scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:svr_create"),
        _scope_verification_payload(scope_project_a, deliverable="Created by the view lane"))
    assert response.status_code == 302
    obj = ScopeVerification.objects.get(tenant=tenant_a, deliverable="Created by the view lane")
    assert response.url == reverse("projects:svr_detail", args=[obj.pk])
    assert obj.created_by == admin_user
    assert obj.inspected_by == admin_user
    assert re.fullmatch(r"SVR-\d{5}", obj.number)
    assert obj.acceptance_status == "pending"


def test_scope_req_edit_round_trip(scope_admin_client, scope_project_a, scope_requirement_draft):
    got = scope_admin_client.get(
        reverse("projects:req_edit", args=[scope_requirement_draft.pk]))
    assert got.status_code == 200
    response = scope_admin_client.post(
        reverse("projects:req_edit", args=[scope_requirement_draft.pk]),
        _scope_requirement_payload(scope_project_a, title="Edited requirement title"))
    assert response.status_code == 302
    scope_requirement_draft.refresh_from_db()
    assert scope_requirement_draft.title == "Edited requirement title"
    assert AuditLog.objects.filter(object_id=str(scope_requirement_draft.pk),
                                   action="update").exists()


def test_scope_sci_edit_round_trip(scope_admin_client, scope_project_a, scope_item_open):
    response = scope_admin_client.post(
        reverse("projects:sci_edit", args=[scope_item_open.pk]),
        _scope_item_payload(scope_project_a, statement="Edited scope statement"))
    assert response.status_code == 302
    scope_item_open.refresh_from_db()
    assert scope_item_open.statement == "Edited scope statement"


def test_scope_scr_edit_round_trip(scope_admin_client, scope_project_a, scope_change_draft):
    response = scope_admin_client.post(
        reverse("projects:scr_edit", args=[scope_change_draft.pk]),
        _scope_change_payload(scope_project_a, title="Edited change title"))
    assert response.status_code == 302
    scope_change_draft.refresh_from_db()
    assert scope_change_draft.title == "Edited change title"


def test_scope_svr_edit_round_trip(scope_admin_client, scope_project_a,
                                   scope_verification_pending):
    response = scope_admin_client.post(
        reverse("projects:svr_edit", args=[scope_verification_pending.pk]),
        _scope_verification_payload(scope_project_a, deliverable="Edited deliverable"))
    assert response.status_code == 302
    scope_verification_pending.refresh_from_db()
    assert scope_verification_pending.deliverable == "Edited deliverable"


@pytest.mark.parametrize("url_name,fixture,model", [
    ("req_delete", "scope_requirement_draft", Requirement),
    ("sci_delete", "scope_item_open", ScopeItem),
    ("scr_delete", "scope_change_draft", ScopeChangeRequest),
    ("svr_delete", "scope_verification_pending", ScopeVerification),
])
def test_scope_delete_is_post_only_and_removes_the_row(request, scope_admin_client, url_name,
                                                      fixture, model):
    obj = request.getfixturevalue(fixture)
    response = scope_admin_client.post(reverse(f"projects:{url_name}", args=[obj.pk]))
    assert response.status_code == 302
    assert not model.objects.filter(pk=obj.pk).exists()
    assert AuditLog.objects.filter(object_id=str(obj.pk), action="delete").exists()


def test_scope_create_tenantless_redirects_home(scope_tenantless_client, scope_project_a):
    """A tenant=None user must not mint an orphan row — every create view redirects home."""
    for name, payload in (
            ("req_create", _scope_requirement_payload(scope_project_a)),
            ("sci_create", _scope_item_payload(scope_project_a)),
            ("scr_create", _scope_change_payload(scope_project_a)),
            ("svr_create", _scope_verification_payload(scope_project_a))):
        response = scope_tenantless_client.post(reverse(f"projects:{name}"), payload)
        assert response.status_code == 302, name
        assert response.url == reverse("dashboard:home"), name


# ==============================================================================================
# F. The sixteen verbs — happy path, wrong-state refusal, idempotence
# ==============================================================================================

# -- Requirement verbs ------------------------------------------------------------------------

def test_scope_req_submit_happy_path(scope_admin_client, admin_user, scope_requirement_draft):
    response = scope_admin_client.post(
        reverse("projects:req_submit", args=[scope_requirement_draft.pk]))
    assert response.status_code == 302
    scope_requirement_draft.refresh_from_db()
    assert scope_requirement_draft.status == "submitted"
    log = AuditLog.objects.get(object_id=str(scope_requirement_draft.pk), action="submit")
    assert log.changes == {"verb": "submit", "from": "draft", "to": "submitted"}


def test_scope_req_submit_refused_on_submitted(scope_admin_client, scope_requirement_submitted):
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:req_submit", args=[scope_requirement_submitted.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_scope_req_submit_replay_is_refused(scope_admin_client, scope_requirement_draft):
    scope_admin_client.post(reverse("projects:req_submit", args=[scope_requirement_draft.pk]))
    before = Requirement.objects.get(pk=scope_requirement_draft.pk)
    response = scope_admin_client.post(
        reverse("projects:req_submit", args=[scope_requirement_draft.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_draft.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_scope_req_approve_happy_path(scope_admin_client, admin_user, scope_requirement_submitted):
    response = scope_admin_client.post(
        reverse("projects:req_approve", args=[scope_requirement_submitted.pk]))
    assert response.status_code == 302
    scope_requirement_submitted.refresh_from_db()
    assert scope_requirement_submitted.status == "approved"
    assert scope_requirement_submitted.approved_by == admin_user
    assert scope_requirement_submitted.approved_at is not None
    log = AuditLog.objects.get(object_id=str(scope_requirement_submitted.pk), action="approve")
    assert log.changes == {"verb": "approve", "from": "submitted", "to": "approved"}


def test_scope_req_approve_refused_on_approved(scope_admin_client, scope_requirement_approved):
    before = Requirement.objects.get(pk=scope_requirement_approved.pk)
    response = scope_admin_client.post(
        reverse("projects:req_approve", args=[scope_requirement_approved.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_approved.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.approved_at) == (before.status, before.approved_at)


def test_scope_req_approve_replay_is_refused(scope_admin_client, scope_requirement_submitted):
    scope_admin_client.post(reverse("projects:req_approve", args=[scope_requirement_submitted.pk]))
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:req_approve", args=[scope_requirement_submitted.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.approved_at) == (before.status, before.approved_at)


def test_scope_req_reject_happy_path_persists_the_reason(scope_admin_client, admin_user,
                                                         scope_requirement_submitted):
    response = scope_admin_client.post(
        reverse("projects:req_reject", args=[scope_requirement_submitted.pk]),
        {"reason": "Not fundable this quarter."})
    assert response.status_code == 302
    scope_requirement_submitted.refresh_from_db()
    assert scope_requirement_submitted.status == "rejected"
    assert scope_requirement_submitted.rejection_reason == "Not fundable this quarter."
    assert scope_requirement_submitted.approved_by is None
    assert scope_requirement_submitted.approved_at is None
    log = AuditLog.objects.get(object_id=str(scope_requirement_submitted.pk), action="reject")
    assert log.changes["verb"] == "reject" and log.changes["to"] == "rejected"


def test_scope_req_reject_without_a_reason_is_refused(scope_admin_client,
                                                      scope_requirement_submitted):
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:req_reject", args=[scope_requirement_submitted.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.rejection_reason) == (before.status, before.rejection_reason)


def test_scope_req_reject_refused_on_approved(scope_admin_client, scope_requirement_approved):
    before = Requirement.objects.get(pk=scope_requirement_approved.pk)
    response = scope_admin_client.post(
        reverse("projects:req_reject", args=[scope_requirement_approved.pk]),
        {"reason": "x"}, follow=True)
    after = Requirement.objects.get(pk=scope_requirement_approved.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_req_implement_happy_path(scope_admin_client, scope_requirement_approved):
    response = scope_admin_client.post(
        reverse("projects:req_implement", args=[scope_requirement_approved.pk]))
    assert response.status_code == 302
    scope_requirement_approved.refresh_from_db()
    assert scope_requirement_approved.status == "implemented"
    log = AuditLog.objects.get(object_id=str(scope_requirement_approved.pk), action="implement")
    assert log.changes == {"verb": "implement", "from": "approved", "to": "implemented"}


def test_scope_req_implement_refused_on_implemented(scope_admin_client,
                                                    scope_requirement_implemented):
    before = Requirement.objects.get(pk=scope_requirement_implemented.pk)
    response = scope_admin_client.post(
        reverse("projects:req_implement", args=[scope_requirement_implemented.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_implemented.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_req_verify_happy_path_stamps_the_evidence(scope_admin_client, admin_user,
                                                         scope_requirement_implemented):
    response = scope_admin_client.post(
        reverse("projects:req_verify", args=[scope_requirement_implemented.pk]),
        {"note": "Confirmed against the acceptance test pack."})
    assert response.status_code == 302
    scope_requirement_implemented.refresh_from_db()
    assert scope_requirement_implemented.status == "verified"
    assert scope_requirement_implemented.verified_by == admin_user
    assert scope_requirement_implemented.verified_at is not None
    assert scope_requirement_implemented.verification_note == \
        "Confirmed against the acceptance test pack."
    log = AuditLog.objects.get(object_id=str(scope_requirement_implemented.pk), action="verify")
    assert log.changes == {"verb": "verify", "from": "implemented", "to": "verified"}


def test_scope_req_verify_refused_on_submitted(scope_admin_client, scope_requirement_submitted):
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:req_verify", args=[scope_requirement_submitted.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.verified_at) == (before.status, before.verified_at)


def test_scope_req_verify_replay_is_refused(scope_admin_client, scope_requirement_implemented):
    scope_admin_client.post(reverse("projects:req_verify", args=[scope_requirement_implemented.pk]))
    before = Requirement.objects.get(pk=scope_requirement_implemented.pk)
    response = scope_admin_client.post(
        reverse("projects:req_verify", args=[scope_requirement_implemented.pk]), follow=True)
    after = Requirement.objects.get(pk=scope_requirement_implemented.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.verified_at) == (before.status, before.verified_at)


# -- ScopeItem verbs --------------------------------------------------------------------------

def test_scope_sci_validate_happy_path(scope_admin_client, scope_item_open):
    response = scope_admin_client.post(
        reverse("projects:sci_validate", args=[scope_item_open.pk]))
    assert response.status_code == 302
    scope_item_open.refresh_from_db()
    assert scope_item_open.status == "validated"
    # The action string is "submit" (the row advanced a gate); the verb rides in changes.
    log = AuditLog.objects.get(object_id=str(scope_item_open.pk), action="submit")
    assert log.changes == {"verb": "validate", "from": "open", "to": "validated"}


def test_scope_sci_validate_refused_on_validated(scope_admin_client, scope_item_validated):
    before = ScopeItem.objects.get(pk=scope_item_validated.pk)
    response = scope_admin_client.post(
        reverse("projects:sci_validate", args=[scope_item_validated.pk]), follow=True)
    after = ScopeItem.objects.get(pk=scope_item_validated.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_sci_realize_happy_path_binds_the_outcome(scope_admin_client, scope_item_open):
    response = scope_admin_client.post(
        reverse("projects:sci_realize", args=[scope_item_open.pk]),
        {"outcome": "The assumption held through go-live."})
    assert response.status_code == 302
    scope_item_open.refresh_from_db()
    assert scope_item_open.status == "realized"
    assert scope_item_open.outcome == "The assumption held through go-live."
    assert scope_item_open.closed_at is not None
    log = AuditLog.objects.get(object_id=str(scope_item_open.pk), action="realize")
    assert log.changes == {"verb": "realize", "from": "open", "to": "realized"}


def test_scope_sci_realize_refused_on_realized(scope_admin_client, scope_item_realized):
    before = ScopeItem.objects.get(pk=scope_item_realized.pk)
    response = scope_admin_client.post(
        reverse("projects:sci_realize", args=[scope_item_realized.pk]),
        {"outcome": "x"}, follow=True)
    after = ScopeItem.objects.get(pk=scope_item_realized.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.outcome) == (before.status, before.outcome)


def test_scope_sci_realize_refused_without_an_outcome(scope_admin_client, scope_item_open):
    before = ScopeItem.objects.get(pk=scope_item_open.pk)
    response = scope_admin_client.post(
        reverse("projects:sci_realize", args=[scope_item_open.pk]), follow=True)
    after = ScopeItem.objects.get(pk=scope_item_open.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_sci_retire_happy_path(scope_admin_client, scope_item_validated):
    response = scope_admin_client.post(
        reverse("projects:sci_retire", args=[scope_item_validated.pk]),
        {"outcome": "The boundary moved after the replan."})
    assert response.status_code == 302
    scope_item_validated.refresh_from_db()
    assert scope_item_validated.status == "retired"
    assert scope_item_validated.outcome == "The boundary moved after the replan."
    assert scope_item_validated.closed_at is not None
    log = AuditLog.objects.get(object_id=str(scope_item_validated.pk), action="retire")
    assert log.changes == {"verb": "retire", "from": "validated", "to": "retired"}


def test_scope_sci_retire_refused_on_realized(scope_admin_client, scope_item_realized):
    """The I3 fix, pinned by name: a REALIZED row is not ``is_open``, so retire refuses it."""
    before = ScopeItem.objects.get(pk=scope_item_realized.pk)
    response = scope_admin_client.post(
        reverse("projects:sci_retire", args=[scope_item_realized.pk]),
        {"outcome": "should not land"}, follow=True)
    after = ScopeItem.objects.get(pk=scope_item_realized.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.outcome) == (before.status, before.outcome)


def test_scope_sci_retire_already_retired_is_an_informational_no_op(scope_admin_client,
                                                                    scope_item_validated):
    """Post-fix: an already-retired row answers ``messages.info`` (no error level asserted —
    the contract pins the STATE unchanged, not the message level)."""
    scope_admin_client.post(reverse("projects:sci_retire", args=[scope_item_validated.pk]),
                            {"outcome": "first retire"})
    before = ScopeItem.objects.get(pk=scope_item_validated.pk)
    response = scope_admin_client.post(
        reverse("projects:sci_retire", args=[scope_item_validated.pk]),
        {"outcome": "second retire"}, follow=True)
    after = ScopeItem.objects.get(pk=scope_item_validated.pk)
    assert after.status == "retired"
    assert (after.outcome, after.updated_at) == (before.outcome, before.updated_at)


# -- ScopeChangeRequest verbs -----------------------------------------------------------------

def test_scope_scr_submit_happy_path(scope_admin_client, scope_change_draft):
    response = scope_admin_client.post(
        reverse("projects:scr_submit", args=[scope_change_draft.pk]))
    assert response.status_code == 302
    scope_change_draft.refresh_from_db()
    assert scope_change_draft.status == "submitted"
    log = AuditLog.objects.get(object_id=str(scope_change_draft.pk), action="submit")
    assert log.changes == {"verb": "submit", "from": "draft", "to": "submitted"}


def test_scope_scr_submit_refused_on_submitted(scope_admin_client, scope_change_submitted):
    before = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_submit", args=[scope_change_submitted.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_scr_submit_replay_is_refused(scope_admin_client, scope_change_draft):
    scope_admin_client.post(reverse("projects:scr_submit", args=[scope_change_draft.pk]))
    before = ScopeChangeRequest.objects.get(pk=scope_change_draft.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_submit", args=[scope_change_draft.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_draft.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


def test_scope_scr_review_happy_path(scope_admin_client, scope_change_submitted):
    response = scope_admin_client.post(
        reverse("projects:scr_review", args=[scope_change_submitted.pk]))
    assert response.status_code == 302
    scope_change_submitted.refresh_from_db()
    assert scope_change_submitted.status == "under_review"
    log = AuditLog.objects.get(object_id=str(scope_change_submitted.pk), action="review")
    assert log.changes == {"verb": "review", "from": "submitted", "to": "under_review"}


def test_scope_scr_review_refused_on_under_review(scope_admin_client, scope_change_under_review):
    before = ScopeChangeRequest.objects.get(pk=scope_change_under_review.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_review", args=[scope_change_under_review.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_under_review.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_scr_approve_happy_path_from_submitted(scope_admin_client, admin_user,
                                                     scope_change_submitted):
    response = scope_admin_client.post(
        reverse("projects:scr_approve", args=[scope_change_submitted.pk]))
    assert response.status_code == 302
    scope_change_submitted.refresh_from_db()
    assert scope_change_submitted.status == "approved"
    assert scope_change_submitted.decided_by == admin_user
    assert scope_change_submitted.decided_at is not None
    log = AuditLog.objects.get(object_id=str(scope_change_submitted.pk), action="approve")
    assert log.changes == {"verb": "approve", "from": "submitted", "to": "approved"}


def test_scope_scr_approve_allowed_from_under_review(scope_admin_client,
                                                     scope_change_under_review):
    """Both ``submitted`` AND ``under_review`` are decidable — the second half of the contract's
    approve/reject gate."""
    response = scope_admin_client.post(
        reverse("projects:scr_approve", args=[scope_change_under_review.pk]))
    assert response.status_code == 302
    scope_change_under_review.refresh_from_db()
    assert scope_change_under_review.status == "approved"


def test_scope_scr_approve_refused_on_draft(scope_admin_client, scope_change_draft):
    before = ScopeChangeRequest.objects.get(pk=scope_change_draft.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_approve", args=[scope_change_draft.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_draft.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.decided_at) == (before.status, before.decided_at)


def test_scope_scr_approve_refused_on_implemented(scope_admin_client, scope_change_implemented):
    before = ScopeChangeRequest.objects.get(pk=scope_change_implemented.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_approve", args=[scope_change_implemented.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_implemented.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_scr_reject_happy_path_persists_the_note(scope_admin_client, admin_user,
                                                       scope_change_submitted):
    response = scope_admin_client.post(
        reverse("projects:scr_reject", args=[scope_change_submitted.pk]),
        {"decision_note": "Too late in the cycle to absorb."})
    assert response.status_code == 302
    scope_change_submitted.refresh_from_db()
    assert scope_change_submitted.status == "rejected"
    assert scope_change_submitted.decision_note == "Too late in the cycle to absorb."
    assert scope_change_submitted.decided_by == admin_user
    assert scope_change_submitted.decided_at is not None
    log = AuditLog.objects.get(object_id=str(scope_change_submitted.pk), action="reject")
    assert log.changes["verb"] == "reject" and log.changes["to"] == "rejected"


def test_scope_scr_reject_allowed_from_under_review(scope_admin_client,
                                                    scope_change_under_review):
    response = scope_admin_client.post(
        reverse("projects:scr_reject", args=[scope_change_under_review.pk]),
        {"decision_note": "Board turned it down."})
    assert response.status_code == 302
    scope_change_under_review.refresh_from_db()
    assert scope_change_under_review.status == "rejected"


def test_scope_scr_reject_without_a_note_is_refused(scope_admin_client, scope_change_submitted):
    before = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_reject", args=[scope_change_submitted.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.decision_note) == (before.status, before.decision_note)


def test_scope_scr_reject_refused_on_rejected(scope_admin_client, scope_change_rejected):
    before = ScopeChangeRequest.objects.get(pk=scope_change_rejected.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_reject", args=[scope_change_rejected.pk]),
        {"decision_note": "again"}, follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_rejected.pk)
    assert _scope_error_queued(response)
    assert after.status == before.status


def test_scope_scr_implement_happy_path(scope_admin_client, scope_change_approved):
    response = scope_admin_client.post(
        reverse("projects:scr_implement", args=[scope_change_approved.pk]))
    assert response.status_code == 302
    scope_change_approved.refresh_from_db()
    assert scope_change_approved.status == "implemented"
    assert scope_change_approved.implemented_at is not None
    log = AuditLog.objects.get(object_id=str(scope_change_approved.pk), action="implement")
    assert log.changes == {"verb": "implement", "from": "approved", "to": "implemented"}


def test_scope_scr_implement_refused_on_implemented(scope_admin_client, scope_change_implemented):
    before = ScopeChangeRequest.objects.get(pk=scope_change_implemented.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_implement", args=[scope_change_implemented.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_implemented.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.implemented_at) == (before.status, before.implemented_at)


def test_scope_scr_implement_replay_is_refused(scope_admin_client, scope_change_approved):
    scope_admin_client.post(reverse("projects:scr_implement", args=[scope_change_approved.pk]))
    before = ScopeChangeRequest.objects.get(pk=scope_change_approved.pk)
    response = scope_admin_client.post(
        reverse("projects:scr_implement", args=[scope_change_approved.pk]), follow=True)
    after = ScopeChangeRequest.objects.get(pk=scope_change_approved.pk)
    assert _scope_error_queued(response)
    assert (after.status, after.updated_at) == (before.status, before.updated_at)


# -- ScopeVerification verbs ------------------------------------------------------------------

def test_scope_svr_accept_happy_path(scope_admin_client, admin_user, scope_verification_pending):
    response = scope_admin_client.post(
        reverse("projects:svr_accept", args=[scope_verification_pending.pk]),
        {"note": "Signed off."})
    assert response.status_code == 302
    scope_verification_pending.refresh_from_db()
    assert scope_verification_pending.acceptance_status == "accepted"
    assert scope_verification_pending.accepted_by == admin_user
    assert scope_verification_pending.accepted_at is not None
    log = AuditLog.objects.get(object_id=str(scope_verification_pending.pk), action="accept")
    assert log.changes == {"verb": "accept", "from": "pending", "to": "accepted"}


def test_scope_svr_accept_on_a_decided_row_is_refused(scope_admin_client,
                                                      scope_verification_rejected):
    before = ScopeVerification.objects.get(pk=scope_verification_rejected.pk)
    response = scope_admin_client.post(
        reverse("projects:svr_accept", args=[scope_verification_rejected.pk]), follow=True)
    after = ScopeVerification.objects.get(pk=scope_verification_rejected.pk)
    assert (after.acceptance_status, after.accepted_at) == \
        (before.acceptance_status, before.accepted_at)
    assert response.status_code == 200  # the already-decided branch redirects and renders


def test_scope_svr_reject_happy_path_persists_the_reason(scope_admin_client, admin_user,
                                                         scope_verification_pending):
    response = scope_admin_client.post(
        reverse("projects:svr_reject", args=[scope_verification_pending.pk]),
        {"note": "The exception report was incomplete."})
    assert response.status_code == 302
    scope_verification_pending.refresh_from_db()
    assert scope_verification_pending.acceptance_status == "rejected"
    assert scope_verification_pending.decision_note == "The exception report was incomplete."
    assert scope_verification_pending.accepted_by == admin_user
    log = AuditLog.objects.get(object_id=str(scope_verification_pending.pk), action="reject")
    assert log.changes == {"verb": "reject", "from": "pending", "to": "rejected"}


def test_scope_svr_reject_without_a_note_is_refused(scope_admin_client,
                                                    scope_verification_pending):
    before = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    response = scope_admin_client.post(
        reverse("projects:svr_reject", args=[scope_verification_pending.pk]),
        {"note": "   "}, follow=True)
    after = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    assert _scope_error_queued(response)
    assert after.acceptance_status == before.acceptance_status


def test_scope_svr_reject_refused_on_a_decided_row(scope_admin_client, scope_verification_accepted):
    before = ScopeVerification.objects.get(pk=scope_verification_accepted.pk)
    response = scope_admin_client.post(
        reverse("projects:svr_reject", args=[scope_verification_accepted.pk]),
        {"note": "x"}, follow=True)
    after = ScopeVerification.objects.get(pk=scope_verification_accepted.pk)
    assert _scope_error_queued(response)
    assert after.acceptance_status == before.acceptance_status


def test_scope_svr_waive_happy_path(scope_admin_client, admin_user, scope_verification_pending):
    response = scope_admin_client.post(
        reverse("projects:svr_waive", args=[scope_verification_pending.pk]))
    assert response.status_code == 302
    scope_verification_pending.refresh_from_db()
    assert scope_verification_pending.acceptance_status == "waived"
    assert scope_verification_pending.accepted_by == admin_user
    assert scope_verification_pending.accepted_at is not None
    log = AuditLog.objects.get(object_id=str(scope_verification_pending.pk), action="waive")
    assert log.changes == {"verb": "waive", "from": "pending", "to": "waived"}


def test_scope_svr_waive_refused_on_a_decided_row(scope_admin_client, scope_verification_waived):
    before = ScopeVerification.objects.get(pk=scope_verification_waived.pk)
    response = scope_admin_client.post(
        reverse("projects:svr_waive", args=[scope_verification_waived.pk]), follow=True)
    after = ScopeVerification.objects.get(pk=scope_verification_waived.pk)
    assert _scope_error_queued(response)
    assert (after.acceptance_status, after.accepted_at) == \
        (before.acceptance_status, before.accepted_at)


def test_scope_svr_accept_replay_is_refused(scope_admin_client, scope_verification_pending):
    scope_admin_client.post(reverse("projects:svr_accept", args=[scope_verification_pending.pk]))
    before = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    response = scope_admin_client.post(
        reverse("projects:svr_accept", args=[scope_verification_pending.pk]), follow=True)
    after = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    assert (after.acceptance_status, after.accepted_at) == \
        (before.acceptance_status, before.accepted_at)
    assert response.status_code == 200


# ==============================================================================================
# G. Evidence immutability — locked rows refuse edit and delete
# ==============================================================================================

def test_scope_req_verified_row_refuses_edit_and_delete(scope_admin_client,
                                                        scope_requirement_verified):
    got = scope_admin_client.get(
        reverse("projects:req_edit", args=[scope_requirement_verified.pk]), follow=True)
    assert "frozen evidence" in got.content.decode()
    posted = scope_admin_client.post(
        reverse("projects:req_delete", args=[scope_requirement_verified.pk]), follow=True)
    assert "frozen evidence" in posted.content.decode()
    assert Requirement.objects.filter(pk=scope_requirement_verified.pk).exists()


def test_scope_req_verified_row_edit_post_does_not_change_fields(scope_admin_client,
                                                                 scope_project_a,
                                                                 scope_requirement_verified):
    before = Requirement.objects.get(pk=scope_requirement_verified.pk)
    scope_admin_client.post(
        reverse("projects:req_edit", args=[scope_requirement_verified.pk]),
        _scope_requirement_payload(scope_project_a, title="Hijacked title"))
    after = Requirement.objects.get(pk=scope_requirement_verified.pk)
    assert (after.title, after.status) == (before.title, before.status)


@pytest.mark.parametrize("fixture", ["scope_item_realized", "scope_item_violated"])
def test_scope_locked_item_row_refuses_edit_and_delete(request, scope_admin_client, fixture):
    """``realized`` (and, post-C1, ``violated``) rows are closed evidence."""
    obj = request.getfixturevalue(fixture)
    got = scope_admin_client.get(reverse("projects:sci_edit", args=[obj.pk]), follow=True)
    assert "frozen evidence" in got.content.decode()
    posted = scope_admin_client.post(reverse("projects:sci_delete", args=[obj.pk]), follow=True)
    assert "frozen evidence" in posted.content.decode()
    assert ScopeItem.objects.filter(pk=obj.pk).exists()


def test_scope_implemented_change_refuses_edit_and_delete(scope_admin_client,
                                                          scope_change_implemented):
    got = scope_admin_client.get(
        reverse("projects:scr_edit", args=[scope_change_implemented.pk]), follow=True)
    assert "frozen evidence" in got.content.decode()
    posted = scope_admin_client.post(
        reverse("projects:scr_delete", args=[scope_change_implemented.pk]), follow=True)
    assert "frozen evidence" in posted.content.decode()
    assert ScopeChangeRequest.objects.filter(pk=scope_change_implemented.pk).exists()


def test_scope_decided_verification_refuses_edit_and_delete(scope_admin_client,
                                                            scope_verification_accepted):
    got = scope_admin_client.get(
        reverse("projects:svr_edit", args=[scope_verification_accepted.pk]), follow=True)
    assert "frozen evidence" in got.content.decode()
    posted = scope_admin_client.post(
        reverse("projects:svr_delete", args=[scope_verification_accepted.pk]), follow=True)
    assert "frozen evidence" in posted.content.decode()
    assert ScopeVerification.objects.filter(pk=scope_verification_accepted.pk).exists()


def test_scope_rejected_rows_are_not_locked(scope_admin_client, scope_requirement_rejected,
                                            scope_change_rejected):
    """A rejected requirement / change is NOT frozen — edit and delete stay open (only
    ``verified`` / ``implemented`` lock, per the contract's lock table)."""
    assert scope_admin_client.get(
        reverse("projects:req_edit", args=[scope_requirement_rejected.pk])).status_code == 200
    assert scope_admin_client.get(
        reverse("projects:scr_edit", args=[scope_change_rejected.pk])).status_code == 200


# ==============================================================================================
# H. Template leak scan
# ==============================================================================================

def test_scope_rendered_pages_leak_no_template_markers(request, scope_admin_client,
                                                       scope_requirement_submitted,
                                                       scope_item_open,
                                                       scope_change_submitted,
                                                       scope_verification_pending,
                                                       scope_matrix_project_a,
                                                       scope_matrix_req_traced_approved,
                                                       scope_matrix_change_m1):
    list_routes = ["req_list", "sci_list", "scr_list", "svr_list"]
    for name in list_routes:
        _scope_assert_no_leak(scope_admin_client.get(reverse(f"projects:{name}")))
    detail_routes = [("req_detail", scope_requirement_submitted),
                     ("sci_detail", scope_item_open),
                     ("scr_detail", scope_change_submitted),
                     ("svr_detail", scope_verification_pending)]
    for name, obj in detail_routes:
        _scope_assert_no_leak(scope_admin_client.get(reverse(f"projects:{name}", args=[obj.pk])))
    for name in ("req_create", "sci_create", "scr_create", "svr_create"):
        _scope_assert_no_leak(scope_admin_client.get(reverse(f"projects:{name}")))
    _scope_assert_no_leak(scope_admin_client.get(
        reverse("projects:scope_matrix") + f"?project={scope_matrix_project_a.pk}"))


# ==============================================================================================
# I. Empty state / tenant-less
# ==============================================================================================

def test_scope_tenantless_lists_render_the_empty_state(scope_tenantless_client):
    for name in ("req_list", "sci_list", "scr_list", "svr_list"):
        response = scope_tenantless_client.get(reverse(f"projects:{name}"))
        assert response.status_code == 200, name
        assert len(list(response.context["object_list"])) == 0, name
        assert "empty-state" in response.content.decode(), name


def test_scope_tenantless_matrix_renders_the_empty_panels(scope_tenantless_client):
    response = scope_tenantless_client.get(reverse("projects:scope_matrix"))
    assert response.status_code == 200
    assert response.context["wp_total"] == 0
    assert response.context["matrix_rows"] == []
    assert response.context["creep_rows"] == []
    assert response.context["coverage"]["coverage_pct"] == 0.0
    body = response.content.decode()
    assert "empty-state" in body
    assert "Pick a project" in body  # the no-?project empty panel


def test_scope_empty_tenant_lists_show_the_registry_empty_state(tenant_b, client_b):
    """A tenant with no rows at all: every register renders the ``.empty-state`` block."""
    for name in ("req_list", "sci_list", "scr_list", "svr_list"):
        response = client_b.get(reverse(f"projects:{name}"))
        assert response.status_code == 200, name
        assert "empty-state" in response.content.decode(), name
