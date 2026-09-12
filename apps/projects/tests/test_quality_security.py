"""Projects 7.6 Quality Management — SECURITY tests.

The access-control lane for the four quality registers (``QualityPlan`` / ``QualityReview`` /
``DeliverableInspection`` / ``QualityDefect``) and the two computed boards — the shape a crafted
request actually takes, from the URL side, not the shape the templates offer.

* **Role gating.** ``qpl_supersede`` is the ONE admin-gated verb: an ordinary member gets **403
  having written nothing** (``updated_at`` included). The other nine verbs are login-gated BY
  DESIGN — a member runs them all, and this lane pins that too, because widening the gate by
  accident would be as much a defect as narrowing it (every verb stamps the ACTING user, never a
  privileged one).
* **Cross-tenant scoping (IDOR).** Every ``<int:pk>`` route — GET and POST, read and destructive —
  404s on another workspace's row, and the row survives untouched. A tenant-B MEMBER on a tenant-A
  pk is also a 404: that is scope, not role. The registers' ``?project=`` lens on a foreign pk
  degrades to EMPTY, and the computed boards degrade to the caller's OWN tenant-wide figures — a
  foreign number renders nowhere.
* **Method guards.** GET on every POST-only route (the ten verbs + the four deletes) → 405; an
  anonymous POST to every verb → redirect to login, nothing written.
* **Crafted-POST boundary.** A tenant-B pk forged into any tenant-scoped FK of the four
  ModelForms (create AND edit) is refused with a FIELD error — nothing created, nothing changed;
  a forged ``accepted_by_party`` records no acceptance decision. The smuggled stamps (``status``,
  ``usage_decision``, ``approved_by``, ``created_by``, ``number``, ``tenant``, ``project_issue``,
  ``resolved_by``) keep their server values: the POSTed attacker values never reach the row.
* **Verb preconditions as security.** An acceptance decision on an unrecorded inspection, a
  second issue from an already-bridged defect, and any edit/delete/verb on a locked
  (frozen-evidence) row are all refused — the refusal IS the state machine enforcing itself
  against forged requests.

Naming (mandatory): every test is ``test_quality_*``, every module-level helper ``_quality_*``.
Scope: permissions and isolation. Page content, context keys and state machines belong to the
other three lanes.
"""
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import (
    DeliverableInspection,
    ProjectIssue,
    QualityDefect,
    QualityPlan,
    QualityReview,
)
from apps.projects.tests.conftest import (
    _quality_defect,
    _quality_inspection,
    _quality_review,
    _quality_today,
    _risk,
)

_LIST_ROUTES = ["qpl_list", "qrv_list", "qci_list", "qdf_list"]
_CREATE_ROUTES = ["qpl_create", "qrv_create", "qci_create", "qdf_create"]
_COMPUTED_ROUTES = ["quality_improvement", "quality_acceptance"]

# (detail, edit, tag) — the two GET-fetch routes of each register's <int:pk> pair.
_DETAIL_EDIT_ROUTES = [
    ("qpl_detail", "qpl_edit", "plan"),
    ("qrv_detail", "qrv_edit", "review"),
    ("qci_detail", "qci_edit", "inspection"),
    ("qdf_detail", "qdf_edit", "defect"),
]

# (route, tag) — every POST-only route: the four deletes plus the ten lifecycle verbs.
_POST_ONLY_ROUTES = [
    ("qpl_delete", "plan"),
    ("qpl_approve", "plan"), ("qpl_supersede", "plan"),
    ("qrv_delete", "review"),
    ("qrv_report", "review"), ("qrv_close", "review"),
    ("qci_delete", "inspection"),
    ("qci_record", "inspection"), ("qci_accept", "inspection"), ("qci_reject", "inspection"),
    ("qdf_delete", "defect"),
    ("qdf_resolve", "defect"), ("qdf_close", "defect"), ("qdf_raise_issue", "defect"),
]


# ==============================================================================================
# Helpers
# ==============================================================================================

def _quality_row_snapshot(row):
    """The fields a forged request must not move — per model, exactly the stamps its verbs
    write (``updated_at`` included: a refusal that still calls ``save()`` is a refusal that
    lies)."""
    if isinstance(row, QualityPlan):
        return (row.status, row.approved_by_id, row.approved_at, row.title, row.updated_at)
    if isinstance(row, QualityReview):
        return (row.status, row.closed_at, row.title, row.updated_at)
    if isinstance(row, DeliverableInspection):
        return (row.status, row.result, row.usage_decision, row.accepted_by_id,
                row.accepted_by_party_id, row.accepted_at, row.updated_at)
    return (row.status, row.resolved_by_id, row.resolved_at, row.project_issue_id,
            row.updated_at)


# ==============================================================================================
# Anonymous access — nothing at all without a login
# ==============================================================================================

@pytest.mark.parametrize("route", _LIST_ROUTES + _CREATE_ROUTES + _COMPUTED_ROUTES)
def test_quality_anonymous_get_redirects_to_login(route, quality_anon_client):
    response = quality_anon_client.get(reverse(f"projects:{route}"))
    assert response.status_code == 302
    assert "login" in response.url, route


@pytest.mark.parametrize("route,fixture_name", [
    ("qpl_detail", "quality_plan_draft"),
    ("qrv_detail", "quality_review_planned"),
    ("qci_detail", "quality_inspection_planned"),
    ("qdf_detail", "quality_defect_open"),
])
def test_quality_anonymous_detail_redirects_to_login(route, fixture_name, quality_anon_client,
                                                     request):
    obj = request.getfixturevalue(fixture_name)
    response = quality_anon_client.get(reverse(f"projects:{route}", args=[obj.pk]))
    assert response.status_code == 302
    assert "login" in response.url, route


def test_quality_anonymous_post_to_every_verb_redirects_and_writes_nothing(
        tenant_a, quality_anon_client, quality_plan_draft, quality_plan_active,
        quality_review_planned, quality_review_reported, quality_inspection_planned,
        quality_inspection_acceptance_pending, quality_defect_open, quality_defect_resolved):
    """Every verb is login-gated: an anonymous POST bounces to login with the DB untouched —
    including ``qdf_raise_issue``, which must mint no issue for an unauthenticated request."""
    probes = [
        ("qpl_approve", quality_plan_draft, ("status", "approved_by_id")),
        ("qpl_supersede", quality_plan_active, ("status", "approved_by_id")),
        ("qrv_report", quality_review_planned, ("status", "closed_at")),
        ("qrv_close", quality_review_reported, ("status", "closed_at")),
        ("qci_record", quality_inspection_planned, ("status", "result", "usage_decision")),
        ("qci_accept", quality_inspection_acceptance_pending,
         ("status", "usage_decision", "accepted_by_id")),
        ("qci_reject", quality_inspection_acceptance_pending,
         ("status", "usage_decision", "accepted_by_id")),
        ("qdf_resolve", quality_defect_open, ("status", "resolved_by_id")),
        ("qdf_close", quality_defect_resolved, ("status", "resolved_at")),
        ("qdf_raise_issue", quality_defect_open, ("status", "project_issue_id")),
    ]
    issues_before = ProjectIssue.objects.count()
    for url_name, row, fields in probes:
        before = tuple(getattr(row, f) for f in fields)
        response = quality_anon_client.post(reverse(f"projects:{url_name}", args=[row.pk]), {})
        assert response.status_code == 302, url_name
        assert "login" in response.url, url_name
        row.refresh_from_db()
        assert tuple(getattr(row, f) for f in fields) == before, url_name
    assert ProjectIssue.objects.count() == issues_before


# ==============================================================================================
# Method guards — GET on every POST-only route is a 405, before the view body ever runs
# ==============================================================================================

def test_quality_get_on_every_post_only_route_is_405(tenant_a, quality_admin_client,
                                                     quality_plan_draft, quality_review_planned,
                                                     quality_inspection_planned,
                                                     quality_defect_open):
    """The 405 fires before the pk is even looked up, so one live row per register stands in for
    all of its POST-only routes (``qpl_supersede``'s ``@require_POST`` sits ABOVE its admin gate
    — the M2 decorator order)."""
    rows = {"plan": quality_plan_draft, "review": quality_review_planned,
            "inspection": quality_inspection_planned, "defect": quality_defect_open}
    for route, tag in _POST_ONLY_ROUTES:
        response = quality_admin_client.get(reverse(f"projects:{route}", args=[rows[tag].pk]))
        assert response.status_code == 405, route


# ==============================================================================================
# Role gating — the one admin verb 403s a member having written nothing; the other nine do not
# ==============================================================================================

def test_quality_member_supersede_403_writes_nothing(tenant_a, quality_member_client,
                                                     quality_plan_active):
    """``qpl_supersede`` is admin-only: a member's POST is 403 BEFORE any lookup — the row,
    ``updated_at`` included, is byte-for-byte as it was, and the smuggled title lands nowhere."""
    before = (quality_plan_active.status, quality_plan_active.approved_by_id,
              quality_plan_active.title, quality_plan_active.updated_at)
    response = quality_member_client.post(reverse("projects:qpl_supersede",
                                                  args=[quality_plan_active.pk]),
                                          {"title": "member override"})
    assert response.status_code == 403
    quality_plan_active.refresh_from_db()
    after = (quality_plan_active.status, quality_plan_active.approved_by_id,
             quality_plan_active.title, quality_plan_active.updated_at)
    assert after == before


def test_quality_member_runs_every_login_gated_verb(
        tenant_a, quality_member_client, member_user, quality_plan_draft, quality_review_planned,
        quality_review_reported, quality_inspection_planned, quality_inspection_in_progress,
        quality_inspection_acceptance_pending, quality_defect_open, quality_defect_in_progress,
        quality_defect_resolved):
    """The other nine verbs are login-gated BY DESIGN — a member runs them all, and every verb
    stamps the ACTING user. ``qrv_report`` succeeding for a member is the policy pin: widening
    any of these gates to admin would strand the workspace's ordinary users."""
    issues_before = ProjectIssue.objects.count()
    posts = [
        ("qpl_approve", quality_plan_draft.pk, {}),
        ("qrv_report", quality_review_planned.pk, {}),
        ("qrv_close", quality_review_reported.pk, {}),
        ("qci_record", quality_inspection_planned.pk, {"result": "pass"}),
        ("qci_accept", quality_inspection_acceptance_pending.pk, {"usage_decision": "accept"}),
        ("qci_reject", quality_inspection_in_progress.pk, {}),
        ("qdf_resolve", quality_defect_in_progress.pk,
         {"resolution_note": "Fixed and re-checked."}),
        ("qdf_close", quality_defect_resolved.pk, {}),
        ("qdf_raise_issue", quality_defect_open.pk, {}),
    ]
    for url_name, pk, data in posts:
        response = quality_member_client.post(reverse(f"projects:{url_name}", args=[pk]), data)
        assert response.status_code == 302, (url_name, response.status_code)

    quality_plan_draft.refresh_from_db()
    assert (quality_plan_draft.status, quality_plan_draft.approved_by) == ("active", member_user)
    quality_review_planned.refresh_from_db()
    assert quality_review_planned.status == "reported"
    quality_review_reported.refresh_from_db()
    assert quality_review_reported.status == "closed"
    assert quality_review_reported.closed_at is not None
    quality_inspection_planned.refresh_from_db()
    assert (quality_inspection_planned.result, quality_inspection_planned.status,
            quality_inspection_planned.usage_decision) == ("pass", "in_progress", "pending")
    quality_inspection_acceptance_pending.refresh_from_db()
    assert (quality_inspection_acceptance_pending.usage_decision,
            quality_inspection_acceptance_pending.status,
            quality_inspection_acceptance_pending.accepted_by) == ("accept", "passed", member_user)
    quality_inspection_in_progress.refresh_from_db()
    assert (quality_inspection_in_progress.usage_decision,
            quality_inspection_in_progress.status) == ("reject", "failed")
    quality_defect_in_progress.refresh_from_db()
    assert (quality_defect_in_progress.status,
            quality_defect_in_progress.resolved_by) == ("resolved", member_user)
    quality_defect_resolved.refresh_from_db()
    assert quality_defect_resolved.status == "closed"
    quality_defect_open.refresh_from_db()
    assert quality_defect_open.project_issue is not None
    assert ProjectIssue.objects.count() == issues_before + 1
    assert (quality_defect_open.project_issue.raised_by,
            quality_defect_open.project_issue.created_by) == (member_user, member_user)


def test_quality_member_reads_every_register_detail_and_computed_page(
        tenant_a, quality_member_client, quality_plan_active, quality_review_planned,
        quality_inspection_planned, quality_defect_open):
    """Read access and the CRUD pages are login-wide inside the workspace — nothing but
    ``qpl_supersede`` is admin-gated."""
    reads = [("qpl_detail", quality_plan_active.pk),
             ("qrv_detail", quality_review_planned.pk),
             ("qci_detail", quality_inspection_planned.pk),
             ("qdf_detail", quality_defect_open.pk)]
    reads += [(route, None) for route in _LIST_ROUTES + _CREATE_ROUTES + _COMPUTED_ROUTES]
    for route, pk in reads:
        url = reverse(f"projects:{route}") if pk is None else reverse(f"projects:{route}",
                                                                     args=[pk])
        response = quality_member_client.get(url)
        assert response.status_code == 200, route


# ==============================================================================================
# Cross-tenant scoping (IDOR) — 404 from the URL side, row survives untouched
# ==============================================================================================

def test_quality_idor_get_404_on_every_detail_and_edit_route(tenant_b, quality_admin_client,
                                                             quality_plan_b, quality_review_b,
                                                             quality_inspection_b,
                                                             quality_defect_b):
    """Tenant A's admin probes every tenant-B detail/edit route → 404 — reads never leak the
    row."""
    rows = {"plan": quality_plan_b, "review": quality_review_b,
            "inspection": quality_inspection_b, "defect": quality_defect_b}
    for detail_route, edit_route, tag in _DETAIL_EDIT_ROUTES:
        for route in (detail_route, edit_route):
            response = quality_admin_client.get(reverse(f"projects:{route}",
                                                        args=[rows[tag].pk]))
            assert response.status_code == 404, (route, rows[tag].pk)


def test_quality_idor_post_404_on_every_verb_and_delete_route(tenant_b, quality_admin_client,
                                                              quality_plan_b, quality_review_b,
                                                              quality_inspection_b,
                                                              quality_defect_b):
    """The destructive and verb routes refuse cross-tenant pks identically, and every probed row
    survives with its stamps untouched."""
    rows = {"plan": quality_plan_b, "review": quality_review_b,
            "inspection": quality_inspection_b, "defect": quality_defect_b}
    snapshots = {tag: _quality_row_snapshot(row) for tag, row in rows.items()}
    for route, tag in _POST_ONLY_ROUTES:
        response = quality_admin_client.post(reverse(f"projects:{route}", args=[rows[tag].pk]),
                                             {"result": "pass", "usage_decision": "accept",
                                              "resolution_note": "forged"})
        assert response.status_code == 404, (route, rows[tag].pk)
    for tag, row in rows.items():
        row.refresh_from_db()
        assert _quality_row_snapshot(row) == snapshots[tag], tag


def test_quality_tenant_b_admin_cannot_read_tenant_a_rows(tenant_a, client_b,
                                                          quality_plan_active,
                                                          quality_review_planned,
                                                          quality_inspection_planned,
                                                          quality_defect_open):
    for route, row in (("qpl_detail", quality_plan_active),
                       ("qrv_detail", quality_review_planned),
                       ("qci_detail", quality_inspection_planned),
                       ("qdf_detail", quality_defect_open)):
        assert client_b.get(reverse(f"projects:{route}", args=[row.pk])).status_code == 404


def test_quality_tenant_b_member_on_tenant_a_pk_is_404_not_403(tenant_a, quality_member_b,
                                                               quality_plan_active):
    """A foreign-workspace member gets the same 404 an admin gets — scope hides the row before
    role is even consulted (no existence leak either way)."""
    from django.test import Client
    client = Client()
    client.force_login(quality_member_b)  # returns None — the login itself is the assertion
    assert client.get(reverse("projects:qpl_detail",
                              args=[quality_plan_active.pk])).status_code == 404


def test_quality_member_cannot_mutate_foreign_rows_through_any_verb(
        tenant_a, tenant_b, quality_member_client, quality_plan_b, quality_review_b,
        quality_inspection_b, quality_defect_b):
    """Object-level tenant write safety: one representative verb per register, POSTed by a
    tenant-A member at a tenant-B pk — 404 (scope), row untouched. The full sweep lives in the
    admin-client IDOR tests above; this pins that being a mere member changes nothing."""
    probes = [("qpl_approve", quality_plan_b), ("qrv_report", quality_review_b),
              ("qci_record", quality_inspection_b), ("qdf_resolve", quality_defect_b)]
    for url_name, row in probes:
        before = _quality_row_snapshot(row)
        response = quality_member_client.post(reverse(f"projects:{url_name}", args=[row.pk]),
                                              {"result": "pass", "resolution_note": "forged"})
        assert response.status_code == 404, url_name
        row.refresh_from_db()
        assert _quality_row_snapshot(row) == before, url_name


# ==============================================================================================
# The foreign ?project= lens — a register degrades to EMPTY, a board to the caller's OWN
# tenant-wide figures; a foreign number renders nowhere
# ==============================================================================================

def test_quality_foreign_project_filter_leaks_no_register_rows(
        tenant_a, quality_admin_client, quality_project_b, quality_plan_b, quality_review_b,
        quality_inspection_b, quality_defect_b):
    foreign_numbers = [quality_plan_b.number, quality_review_b.number,
                       quality_inspection_b.number, quality_defect_b.number]
    for route in _LIST_ROUTES:
        response = quality_admin_client.get(reverse(f"projects:{route}") +
                                            f"?project={quality_project_b.pk}")
        assert response.status_code == 200, route
        assert len(list(response.context["object_list"])) == 0, route
        body = response.content.decode()
        for number in foreign_numbers:
            assert number not in body, (route, number)


def test_quality_improvement_board_foreign_project_lens_leaks_nothing(
        tenant_a, tenant_b, quality_admin_client, quality_project_b, quality_review_improvement,
        quality_defect_closed):
    """A valid-but-FOREIGN ``?project=`` pk degrades the computed board to the caller's OWN
    tenant-wide figures — never to the foreign workspace. The foreign leak canaries are a
    tenant-B kaizen review (board type) and a tenant-B closed defect carrying a lesson (the
    lessons lens), each built inline so their numbers WOULD render if the tenant filter broke."""
    # Numbers are minted PER TENANT — both workspaces read QRV-00001/QDF-00001 — so burn one
    # tenant-B number per model first, making the canary's number distinct from the own-tenant
    # rows' (the per-tenant number collision the test contract warns about).
    _quality_review(tenant_b, quality_project_b, title="Foreign review number burner")
    foreign_review = _quality_review(tenant_b, quality_project_b, title="Globex kaizen event",
                                     review_type="kaizen_event")
    _quality_defect(tenant_b, quality_project_b, title="Foreign defect number burner")
    foreign_defect = _quality_defect(tenant_b, quality_project_b, title="Globex lessons defect",
                                     status="closed", disposition="repair",
                                     lessons_learned="Globex-only lesson",
                                     resolved_at=timezone.now())
    response = quality_admin_client.get(reverse("projects:quality_improvement") +
                                        f"?project={quality_project_b.pk}")
    assert response.status_code == 200
    assert response.context["project"] is None  # the foreign pk yields no project → tenant-wide
    body = response.content.decode()
    assert quality_review_improvement.number in body  # own-tenant board rows still render
    assert quality_defect_closed.number in body
    assert foreign_review.number not in body
    assert foreign_defect.number not in body


def test_quality_acceptance_board_foreign_project_lens_leaks_nothing(
        tenant_a, tenant_b, quality_admin_client, quality_project_b,
        quality_inspection_acceptance_pending):
    """Same scope trap, acceptance board: the deliverable board is empty without a project, the
    queue stays on the caller's own tenant, and a foreign acceptance inspection — inline-built
    so it WOULD queue if the tenant filter broke — never renders."""
    # Same per-tenant numbering as the improvement board: burn tenant B's QCI-00001 so the
    # canary's number cannot collide with the own-tenant queue row's.
    _quality_inspection(tenant_b, quality_project_b, title="Foreign inspection number burner")
    foreign_inspection = _quality_inspection(tenant_b, quality_project_b,
                                             title="Globex acceptance inspection",
                                             inspection_type="acceptance", result="pass",
                                             status="in_progress")
    response = quality_admin_client.get(reverse("projects:quality_acceptance") +
                                        f"?project={quality_project_b.pk}")
    assert response.status_code == 200
    assert response.context["project"] is None
    assert response.context["deliverable_rows"] == []
    body = response.content.decode()
    assert quality_inspection_acceptance_pending.number in body  # own-tenant queue row renders
    assert foreign_inspection.number not in body


# ==============================================================================================
# CSRF — a POST without a token is 403 having written nothing, on every register
# ==============================================================================================

def test_quality_post_without_csrf_token_403s_on_every_register(
        tenant_a, quality_csrf_client, quality_plan_draft, quality_review_planned,
        quality_inspection_planned, quality_defect_open):
    probes = [
        ("qpl_approve", quality_plan_draft, ("status", "approved_by_id")),
        ("qrv_report", quality_review_planned, ("status", "closed_at")),
        ("qci_record", quality_inspection_planned, ("status", "result", "usage_decision")),
        ("qdf_resolve", quality_defect_open, ("status", "resolved_by_id")),
    ]
    for url_name, row, fields in probes:
        before = tuple(getattr(row, f) for f in fields)
        response = quality_csrf_client.post(reverse(f"projects:{url_name}", args=[row.pk]),
                                            {"result": "pass", "resolution_note": "no token"})
        assert response.status_code == 403, url_name
        row.refresh_from_db()
        assert tuple(getattr(row, f) for f in fields) == before, url_name


# ==============================================================================================
# Crafted-POST boundary — a foreign pk into any tenant-scoped FK is refused, nothing written
# ==============================================================================================

def test_quality_plan_create_refuses_every_foreign_fk(
        tenant_a, tenant_b, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "source_risk": _risk(tenant_b, quality_project_b,
                                    title="Globex foreign risk").pk,
               "owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Crafted plan",
                "acceptance_criteria": "The deliverable passes first article.",
                "verification_method": "inspection"}
    count_before = QualityPlan.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(reverse("projects:qpl_create"),
                                             dict(baseline, **{field: value}))
        assert response.status_code == 200, field  # re-rendered with the field error
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    assert QualityPlan.objects.count() == count_before


def test_quality_review_create_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "reviewer": admin_b.pk,
               "improvement_owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Crafted review",
                "review_type": "methodology_review", "review_date": _quality_today().isoformat(),
                "improvement_status": "n_a"}
    count_before = QualityReview.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(reverse("projects:qrv_create"),
                                             dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    assert QualityReview.objects.count() == count_before


def test_quality_inspection_create_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b, quality_milestone_b):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "milestone": quality_milestone_b.pk,
               "inspector": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Crafted inspection",
                "inspection_type": "review", "result": "pending"}
    count_before = DeliverableInspection.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(reverse("projects:qci_create"),
                                             dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    assert DeliverableInspection.objects.count() == count_before


def test_quality_defect_create_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b, quality_inspection_b):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "inspection": quality_inspection_b.pk,
               "owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Crafted defect",
                "description": "The output fails the acceptance criterion.",
                "defect_category": "other", "severity": "minor", "disposition": "open",
                "identified_date": _quality_today().isoformat()}
    count_before = QualityDefect.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(reverse("projects:qdf_create"),
                                             dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    assert QualityDefect.objects.count() == count_before


def test_quality_plan_edit_refuses_every_foreign_fk(
        tenant_a, tenant_b, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_draft):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "source_risk": _risk(tenant_b, quality_project_b,
                                    title="Globex foreign risk").pk,
               "owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Forged title",
                "acceptance_criteria": "Forged criteria.",
                "verification_method": "inspection"}
    count_before = QualityPlan.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(
            reverse("projects:qpl_edit", args=[quality_plan_draft.pk]),
            dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    quality_plan_draft.refresh_from_db()
    assert quality_plan_draft.title != baseline["title"]  # the forged title landed nowhere
    assert quality_plan_draft.project_id == quality_project_a.pk
    assert QualityPlan.objects.count() == count_before


def test_quality_review_edit_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b, quality_review_planned):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "reviewer": admin_b.pk,
               "improvement_owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Forged title",
                "review_type": "methodology_review", "review_date": _quality_today().isoformat(),
                "improvement_status": "n_a"}
    count_before = QualityReview.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(
            reverse("projects:qrv_edit", args=[quality_review_planned.pk]),
            dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    quality_review_planned.refresh_from_db()
    assert quality_review_planned.title != baseline["title"]
    assert quality_review_planned.project_id == quality_project_a.pk
    assert QualityReview.objects.count() == count_before


def test_quality_inspection_edit_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b, quality_milestone_b, quality_inspection_planned):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "milestone": quality_milestone_b.pk,
               "inspector": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Forged title",
                "inspection_type": "review", "result": "pending"}
    count_before = DeliverableInspection.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(
            reverse("projects:qci_edit", args=[quality_inspection_planned.pk]),
            dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    quality_inspection_planned.refresh_from_db()
    assert quality_inspection_planned.title != baseline["title"]
    assert quality_inspection_planned.project_id == quality_project_a.pk
    assert DeliverableInspection.objects.count() == count_before


def test_quality_defect_edit_refuses_every_foreign_fk(
        tenant_a, quality_admin_client, admin_b, quality_project_a, quality_project_b,
        quality_wbs_node_b, quality_plan_b, quality_inspection_b, quality_defect_open):
    foreign = {"project": quality_project_b.pk, "wbs_node": quality_wbs_node_b.pk,
               "quality_plan": quality_plan_b.pk, "inspection": quality_inspection_b.pk,
               "owner": admin_b.pk}
    baseline = {"project": quality_project_a.pk, "title": "Forged title",
                "description": "Forged description.", "defect_category": "other",
                "severity": "minor", "disposition": "open",
                "identified_date": _quality_today().isoformat()}
    count_before = QualityDefect.objects.count()
    for field, value in foreign.items():
        response = quality_admin_client.post(
            reverse("projects:qdf_edit", args=[quality_defect_open.pk]),
            dict(baseline, **{field: value}))
        assert response.status_code == 200, field
        assert field in response.context["form"].errors, (field,
                                                          dict(response.context["form"].errors))
    quality_defect_open.refresh_from_db()
    assert quality_defect_open.title != baseline["title"]
    assert quality_defect_open.project_id == quality_project_a.pk
    assert QualityDefect.objects.count() == count_before


def test_quality_accept_crafted_foreign_party_records_no_decision(
        tenant_a, quality_admin_client, quality_inspection_acceptance_pending,
        quality_client_party_b):
    """A tenant-B party pk forged into ``accepted_by_party``: the form's workspace-scoped
    queryset refuses it, so the accept verb writes no decision and no acceptor stamp."""
    row = quality_inspection_acceptance_pending
    before = (row.usage_decision, row.status, row.accepted_by_id, row.accepted_by_party_id,
              row.accepted_at, row.acceptance_note)
    response = quality_admin_client.post(reverse("projects:qci_accept", args=[row.pk]),
                                         {"usage_decision": "accept",
                                          "accepted_by_party": quality_client_party_b.pk,
                                          "acceptance_note": "forged sign-off"})
    assert response.status_code == 302  # refused with an error message, bounced to the detail
    row.refresh_from_db()
    assert (row.usage_decision, row.status, row.accepted_by_id, row.accepted_by_party_id,
            row.accepted_at, row.acceptance_note) == before


# ==============================================================================================
# Smuggled stamps — the POSTed attacker values never reach the row
# ==============================================================================================

def test_quality_plan_create_keeps_server_stamps(tenant_a, tenant_b, quality_admin_client,
                                                 admin_user, admin_b, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qpl_create"), {
        "project": quality_project_a.pk, "title": "Smuggled plan",
        "acceptance_criteria": "Server stamps win.", "verification_method": "inspection",
        "status": "active", "approved_by": admin_b.pk, "created_by": admin_b.pk,
        "number": "QPL-99999", "tenant": tenant_b.pk,
    })
    assert response.status_code == 302
    plan = QualityPlan.objects.get(title="Smuggled plan")
    assert plan.status == "draft"  # the smuggled "active" never reached the row
    assert plan.approved_by_id is None and plan.approved_at is None
    assert plan.created_by == admin_user  # the ACTING user, never the POSTed one
    assert plan.tenant_id == tenant_a.pk  # the session tenant, never the POSTed one
    assert plan.number != "QPL-99999" and re.fullmatch(r"QPL-\d{5}", plan.number)


def test_quality_review_create_keeps_server_stamps(tenant_a, tenant_b, quality_admin_client,
                                                   admin_user, admin_b, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qrv_create"), {
        "project": quality_project_a.pk, "title": "Smuggled review",
        "review_type": "methodology_review", "review_date": _quality_today().isoformat(),
        "improvement_status": "n_a",
        "status": "closed", "closed_at": "2020-01-01T00:00", "created_by": admin_b.pk,
        "number": "QRV-99999", "tenant": tenant_b.pk,
    })
    assert response.status_code == 302
    review = QualityReview.objects.get(title="Smuggled review")
    assert review.status == "planned" and review.closed_at is None
    assert review.created_by == admin_user
    assert review.tenant_id == tenant_a.pk
    assert review.number != "QRV-99999" and re.fullmatch(r"QRV-\d{5}", review.number)


def test_quality_inspection_create_keeps_server_stamps(tenant_a, tenant_b, quality_admin_client,
                                                       admin_user, admin_b, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qci_create"), {
        "project": quality_project_a.pk, "title": "Smuggled inspection",
        "inspection_type": "review", "result": "pending",
        "status": "passed", "usage_decision": "accept", "accepted_by": admin_b.pk,
        "created_by": admin_b.pk, "number": "QCI-99999", "tenant": tenant_b.pk,
    })
    assert response.status_code == 302
    inspection = DeliverableInspection.objects.get(title="Smuggled inspection")
    assert inspection.status == "planned" and inspection.usage_decision == "pending"
    assert inspection.accepted_by_id is None and inspection.accepted_by_party_id is None
    assert inspection.accepted_at is None
    assert inspection.created_by == admin_user
    assert inspection.tenant_id == tenant_a.pk
    assert inspection.number != "QCI-99999" and re.fullmatch(r"QCI-\d{5}", inspection.number)


def test_quality_defect_create_keeps_server_stamps(tenant_a, tenant_b, quality_admin_client,
                                                   admin_user, admin_b, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qdf_create"), {
        "project": quality_project_a.pk, "title": "Smuggled defect",
        "description": "Server stamps win.", "defect_category": "other", "severity": "minor",
        "disposition": "open", "identified_date": _quality_today().isoformat(),
        "status": "resolved", "project_issue": 999999, "resolved_by": admin_b.pk,
        "created_by": admin_b.pk, "number": "QDF-99999", "tenant": tenant_b.pk,
    })
    assert response.status_code == 302
    defect = QualityDefect.objects.get(title="Smuggled defect")
    assert defect.status == "open" and defect.project_issue_id is None
    assert defect.resolved_by_id is None and defect.resolved_at is None
    assert defect.created_by == admin_user
    assert defect.tenant_id == tenant_a.pk
    assert defect.number != "QDF-99999" and re.fullmatch(r"QDF-\d{5}", defect.number)


# ==============================================================================================
# Verb preconditions as security — the state machine refuses forged evidence
# ==============================================================================================

def test_quality_accept_refuses_a_pending_result_inspection(
        tenant_a, quality_admin_client, quality_project_a):
    """An acceptance decision on an inspection whose result was never recorded would create
    evidence with nothing behind it — both decision verbs refuse before any stamp is written."""
    pending = _quality_inspection(tenant_a, quality_project_a,
                                  title="Unrecorded acceptance inspection",
                                  inspection_type="acceptance")
    for url_name, data in (("qci_accept", {"usage_decision": "accept"}), ("qci_reject", {})):
        response = quality_admin_client.post(reverse(f"projects:{url_name}", args=[pending.pk]),
                                             data)
        assert response.status_code == 302, url_name
        pending.refresh_from_db()
        assert (pending.usage_decision, pending.status, pending.accepted_by_id,
                pending.accepted_at, pending.accepted_by_party_id) == \
            ("pending", "planned", None, None, None), url_name


def test_quality_raise_issue_refuses_an_already_bridged_defect(
        tenant_a, quality_admin_client, quality_defect_bridged):
    """The bridge is one fact: a defect that already became an issue cannot mint a second one —
    the ProjectIssue count is the security assertion."""
    issues_before = ProjectIssue.objects.count()
    bridge_before = quality_defect_bridged.project_issue_id
    response = quality_admin_client.post(reverse("projects:qdf_raise_issue",
                                                 args=[quality_defect_bridged.pk]), {})
    assert response.status_code == 302
    quality_defect_bridged.refresh_from_db()
    assert quality_defect_bridged.project_issue_id == bridge_before
    assert ProjectIssue.objects.count() == issues_before


def test_quality_locked_rows_refuse_edit_delete_and_mutating_verbs(
        tenant_a, quality_admin_client, quality_plan_superseded, quality_review_closed,
        quality_inspection_accepted, quality_defect_closed, quality_defect_cancelled):
    """Locked rows are frozen evidence: edit bounces to the detail page, delete redirects there
    too (never to the list — nothing was deleted), and the mutating verbs refuse them as well.
    A decided inspection, a closed review, a superseded plan and a closed/cancelled defect all
    survive byte-for-byte."""
    issues_before = ProjectIssue.objects.count()
    lanes = [
        (quality_plan_superseded, "qpl", ("status", "approved_by_id")),
        (quality_review_closed, "qrv", ("status", "closed_at")),
        (quality_inspection_accepted, "qci",
         ("status", "usage_decision", "accepted_by_id", "accepted_at")),
        (quality_defect_closed, "qdf", ("status", "resolved_by_id")),
        (quality_defect_cancelled, "qdf", ("status", "resolved_by_id")),
    ]
    for row, prefix, fields in lanes:
        before = tuple(getattr(row, f) for f in fields)
        detail_url = reverse(f"projects:{prefix}_detail", args=[row.pk])
        got = quality_admin_client.get(reverse(f"projects:{prefix}_edit", args=[row.pk]))
        assert got.status_code == 302, prefix
        assert got.url == detail_url, prefix  # refused — bounced back to the frozen row
        posted = quality_admin_client.post(reverse(f"projects:{prefix}_delete", args=[row.pk]), {})
        assert posted.status_code == 302, prefix
        assert posted.url == detail_url, prefix  # a deletion redirects to the list, not here
        row.refresh_from_db()
        assert tuple(getattr(row, f) for f in fields) == before, prefix
        assert type(row).objects.filter(pk=row.pk).exists(), prefix

    # The verbs refuse frozen evidence too: no late record on a decided inspection, no late
    # resolution or second issue bridge on a cancelled defect.
    record = quality_admin_client.post(reverse("projects:qci_record",
                                               args=[quality_inspection_accepted.pk]),
                                       {"result": "pass"})
    assert record.status_code == 302
    resolve = quality_admin_client.post(reverse("projects:qdf_resolve",
                                                args=[quality_defect_cancelled.pk]),
                                        {"resolution_note": "late stamp"})
    assert resolve.status_code == 302
    raise_issue = quality_admin_client.post(reverse("projects:qdf_raise_issue",
                                                    args=[quality_defect_cancelled.pk]), {})
    assert raise_issue.status_code == 302
    quality_inspection_accepted.refresh_from_db()
    quality_defect_cancelled.refresh_from_db()
    assert (quality_inspection_accepted.status, quality_inspection_accepted.result) == \
        ("passed", "pass")
    assert (quality_defect_cancelled.status, quality_defect_cancelled.resolved_by_id) == \
        ("cancelled", None)
    assert ProjectIssue.objects.count() == issues_before
