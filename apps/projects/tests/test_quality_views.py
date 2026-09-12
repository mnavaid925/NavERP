"""Projects 7.6 Quality Management — VIEW tests.

The HTTP layer of the sub-module: 32 routes, the pages they render, **every context key the
test contract pins** (§4 of ``.claude/tasks/contract-projects-7.6.md`` as amended by
``.claude/tasks/review-projects-7.6.md``), the four registers' search/filter/lens/pagination
behaviour, the ten POST verbs' state machines, and the two computed boards' pinned figures
(§3.1/§3.2 of ``.claude/tasks/test-contract-projects-7.6.md``). Model invariants belong to
``test_quality_models.py`` and form validation to ``test_quality_forms.py``; role gating
(403), crafted-POST FKs, CSRF and anonymous access belong to ``test_quality_security.py``.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page asserts CONTENT — the row's own ``QPL-``/``QRV-``/``QCI-``/
  ``QDF-`` number in the body — and the pinned keys by name, including the computed boards'
  exact row-dict shapes and the §3 figures (maturity 3.0/"Defined"/badge-info; acceptance
  queue 1 / accepted 1 / rejected 1 / pending 8 / conditional 0).
* **A lens that silently empties a register.** The pre-scoped lenses (``?review_due=1``,
  ``?kind=assurance``, ``?kind=improvement``, ``?overdue=1``) select EXACTLY the fixture rows
  designed for them; the junk params (``?status=nope``, ``?project=0``, ``?project=abc``,
  ``?page=abc``) return the default page — never a 500, never a silently emptied register
  (L9/L11). A valid-but-FOREIGN ``?project=`` pk renders the four registers EMPTY, while the
  computed boards fall back tenant-wide (200, not 404, not empty).
* **A verb that writes when it should refuse.** All ten verbs are exercised on both sides:
  the happy paths (approve → supersede; record → accept/reject; resolve → close;
  report → close; raise-issue) and every now-forbidden source state, each of which must
  answer with a message and leave the row untouched — including the close-out amendments
  (``qrv_report`` accepts ``planned`` AND ``in_progress``; a cancelled defect is frozen like
  its QRV/QCI siblings). GET on every verb and delete route → 405.
* **A locked row that still mutates.** Superseded/closed plans, closed/cancelled reviews,
  decided/terminal inspections and resolved/closed/cancelled defects refuse edit AND delete
  with the frozen-evidence message.

Determinism (L16): every date basis is ``_quality_today()`` — never ``datetime.date.today()``.
Message assertions match ASCII SUBSTRINGs only (several messages carry U+2014 — a copy edit
must not turn into a red suite).

Naming (mandatory): every test is ``test_quality_*``, every module-level helper ``_quality_*``.
Scope: views/urls. Models, forms and permissions belong to the other three lanes.
"""
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.projects.forms import DefectResolutionForm, InspectionAcceptanceForm
from apps.projects.models import (
    DeliverableInspection,
    ProjectIssue,
    QualityDefect,
    QualityPlan,
    QualityReview,
)
from apps.projects.tests.conftest import (
    QUALITY_PAGE_SIZE,
    _quality_defect,
    _quality_fill_plans,
    _quality_inspection,
    _quality_plan,
    _quality_project,
    _quality_review,
    _quality_today,
)

DELIVERABLE_ROW_KEYS = {"wbs_node", "plan", "plan_status", "latest_inspection", "result",
                        "usage_decision", "open_defects", "acceptance_state", "badge"}

TREND_ROW_KEYS = {"period", "label", "opened", "closed", "bar_pct"}

#: L11 junk that must never 500 and never silently empty a register (only ``?page=`` may
#: lawfully change which rows render, so the marker assert skips it).
_QUALITY_JUNK_PARAMS = ["?status=nope", "?project=0", "?project=abc", "?page=abc", "?page=9999",
                        "?severity=%3Cscript%3E", "?verification_method=%C2%B2"]

#: Every verb is POST-only — a GET must be answered by ``require_POST``'s 405 before the view
#: body ever runs (including ``qpl_supersede``, whose ``@require_POST`` sits ABOVE its admin
#: gate — the M2 reorder).
_QUALITY_POST_ONLY_URLS = [
    ("quality_plan_draft", "qpl_approve"),
    ("quality_plan_draft", "qpl_supersede"),
    ("quality_review_planned", "qrv_report"),
    ("quality_review_planned", "qrv_close"),
    ("quality_inspection_planned", "qci_record"),
    ("quality_inspection_planned", "qci_accept"),
    ("quality_inspection_planned", "qci_reject"),
    ("quality_defect_open", "qdf_resolve"),
    ("quality_defect_open", "qdf_close"),
    ("quality_defect_open", "qdf_raise_issue"),
]


# ==============================================================================================
# Helpers
# ==============================================================================================

def _quality_pks(response):
    """The rendered page's row pks — the fastest exact narrowing check there is."""
    return {row.pk for row in response.context["object_list"]}


def _quality_expected_trend(defects):
    """Re-derive the improvement page's trend from the pulled rows using the view's OWN
    bucketing (``identified_date`` month; ``localdate(resolved_at)`` month; ``bar_pct`` scaled
    against the busiest single figure) — the §3.1 recipe for pinning the trend without
    depending on where the fixtures' date offsets fall in the calendar."""
    today = _quality_today()
    months = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    months.reverse()
    buckets = {m: {"opened": 0, "closed": 0} for m in months}
    for defect in defects:
        identified = defect.identified_date
        if identified is not None and (identified.year, identified.month) in buckets:
            buckets[(identified.year, identified.month)]["opened"] += 1
        if defect.resolved_at is not None:
            resolved = timezone.localdate(defect.resolved_at)
            if (resolved.year, resolved.month) in buckets:
                buckets[(resolved.year, resolved.month)]["closed"] += 1
    rows, trend_max = [], 0
    for year, month in months:
        counts = buckets[(year, month)]
        trend_max = max(trend_max, counts["opened"], counts["closed"])
        rows.append({"period": f"{year:04d}-{month:02d}", "opened": counts["opened"],
                     "closed": counts["closed"]})
    for row in rows:
        row["bar_pct"] = (round(max(row["opened"], row["closed"]) / trend_max * 100)
                          if trend_max else 0)
    return rows, trend_max


def _quality_plan_post(project, **overrides):
    data = {
        "project": project.pk, "wbs_node": "", "source_risk": "",
        "title": "Plan written by the view test",
        "description": "Written by test_quality_views.",
        "acceptance_criteria": "Zero critical defects at the acceptance inspection.",
        "verification_method": "inspection", "standard_reference": "",
        "regulatory_requirement": "", "owner": "", "planned_review_date": "",
        # L20/L22: ``status`` is OFF the form — a smuggled value must change nothing.
        "status": "active",
    }
    data.update(overrides)
    return data


def _quality_review_post(project, **overrides):
    data = {
        "project": project.pk, "wbs_node": "", "quality_plan": "",
        "title": "Review written by the view test",
        "scope": "", "review_type": "methodology_review", "checklist": "", "findings": "",
        "reviewer": "", "review_date": _quality_today().isoformat(), "maturity_score": "",
        "improvement_action": "", "improvement_owner": "", "improvement_due_date": "",
        "improvement_status": "n_a",
        # L20/L22: the verb-written stamps are OFF the form.
        "status": "closed", "closed_at": "2020-01-01",
    }
    data.update(overrides)
    return data


def _quality_inspection_post(project, **overrides):
    data = {
        "project": project.pk, "wbs_node": "", "quality_plan": "", "milestone": "",
        "title": "Inspection written by the view test",
        "description": "", "inspection_type": "review", "planned_date": "",
        "inspected_date": "", "inspector": "", "result": "pending", "findings": "",
        # L20/L22: the decision + acceptor stamps are OFF the form.
        "usage_decision": "accept", "status": "passed", "accepted_by": 999999,
    }
    data.update(overrides)
    return data


def _quality_defect_post(project, **overrides):
    data = {
        "project": project.pk, "wbs_node": "", "quality_plan": "", "inspection": "",
        "title": "Defect written by the view test",
        "description": "The output fails the acceptance criterion.",
        "defect_category": "other", "severity": "minor", "disposition": "open", "owner": "",
        "identified_date": _quality_today().isoformat(), "due_date": "", "lessons_learned": "",
        # L20/L22: the bridge and the resolver stamps are OFF the form.
        "status": "resolved", "project_issue": 999999,
    }
    data.update(overrides)
    return data


def _quality_frozen_refusal(client, obj, *, edit_url_name, delete_url_name, detail_url_name):
    """A locked row refuses edit AND delete: the frozen-evidence message, a redirect back to
    the detail page, and the row byte-for-byte as it was."""
    model = type(obj)
    got = client.get(reverse(edit_url_name, args=[obj.pk]), follow=True)
    assert got.status_code == 200
    assert "frozen evidence" in got.content.decode(), edit_url_name
    assert got.request["PATH_INFO"] == reverse(detail_url_name, args=[obj.pk])
    posted = client.post(reverse(delete_url_name, args=[obj.pk]), follow=True)
    assert "frozen evidence" in posted.content.decode(), delete_url_name
    assert model.objects.filter(pk=obj.pk).exists()
    after = model.objects.get(pk=obj.pk)
    assert (after.title, after.status) == (obj.title, obj.status)


# ==============================================================================================
# Registers — content, pinned context keys, filters, lenses, search, pagination
# ==============================================================================================

def test_quality_plans_list_renders_rows_and_pinned_context(tenant_a, quality_admin_client,
                                                            quality_plan_draft,
                                                            quality_plan_active,
                                                            quality_project_a):
    response = quality_admin_client.get(reverse("projects:qpl_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert quality_plan_draft.number in body
    assert quality_plan_active.number in body
    for key in ("object_list", "page_obj", "q", "projects", "status_choices",
                "verification_method_choices", "owners"):
        assert key in response.context, key
    assert response.context["q"] == ""


def test_quality_reviews_list_renders_rows_and_pinned_context(tenant_a, quality_admin_client,
                                                              quality_review_planned,
                                                              quality_review_reported):
    response = quality_admin_client.get(reverse("projects:qrv_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert quality_review_planned.number in body
    assert quality_review_reported.number in body
    for key in ("projects", "review_type_choices", "status_choices",
                "improvement_status_choices", "owners"):
        assert key in response.context, key


def test_quality_inspections_list_renders_rows_and_pinned_context(tenant_a, quality_admin_client,
                                                                  quality_inspection_planned,
                                                                  quality_inspection_accepted):
    response = quality_admin_client.get(reverse("projects:qci_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert quality_inspection_planned.number in body
    assert quality_inspection_accepted.number in body
    for key in ("projects", "inspection_type_choices", "result_choices",
                "usage_decision_choices", "status_choices", "owners"):
        assert key in response.context, key


def test_quality_defects_list_renders_rows_and_pinned_context(tenant_a, quality_admin_client,
                                                              quality_defect_open,
                                                              quality_defect_closed):
    response = quality_admin_client.get(reverse("projects:qdf_list"))
    assert response.status_code == 200
    body = response.content.decode()
    assert quality_defect_open.number in body
    assert quality_defect_closed.number in body  # terminal rows stay visible on the register
    for key in ("projects", "severity_choices", "status_choices", "disposition_choices",
                "defect_category_choices", "owners", "inspections"):
        assert key in response.context, key


def test_quality_plan_filters_narrow_like_the_orm(tenant_a, quality_admin_client,
                                                  quality_plan_draft, quality_plan_active,
                                                  quality_plan_superseded, quality_project_a):
    base = reverse("projects:qpl_list")
    unfiltered = quality_admin_client.get(base)
    assert len(list(unfiltered.context["object_list"])) == 3  # the narrowing is provable
    for param, expected in (("?status=active", {quality_plan_active.pk}),
                            ("?status=draft", {quality_plan_draft.pk}),
                            ("?status=superseded", {quality_plan_superseded.pk})):
        response = quality_admin_client.get(base + param)
        assert _quality_pks(response) == expected, param
    scoped = quality_admin_client.get(base + f"?project={quality_project_a.pk}")
    assert len(list(scoped.context["object_list"])) == 3


def test_quality_plan_review_due_lens_selects_only_the_overdue_row(tenant_a, quality_admin_client,
                                                                   quality_plan_draft,
                                                                   quality_plan_active,
                                                                   quality_plan_review_overdue):
    base = reverse("projects:qpl_list")
    for lens in ("?review_due=1", "?overdue=1"):
        response = quality_admin_client.get(base + lens)
        assert _quality_pks(response) == {quality_plan_review_overdue.pk}, lens


def test_quality_review_kind_lenses_select_their_families(
        tenant_a, quality_admin_client, quality_review_planned, quality_review_in_progress,
        quality_review_reported, quality_review_closed, quality_review_cancelled,
        quality_review_improvement, quality_review_improvement_overdue,
        quality_review_improvement_done, quality_review_maturity):
    base = reverse("projects:qrv_list")
    assurance = quality_admin_client.get(base + "?kind=assurance")
    assert _quality_pks(assurance) == {quality_review_planned.pk,
                                       quality_review_in_progress.pk,
                                       quality_review_reported.pk,
                                       quality_review_closed.pk,
                                       quality_review_cancelled.pk}
    improvement = quality_admin_client.get(base + "?kind=improvement")
    assert _quality_pks(improvement) == {quality_review_improvement.pk,
                                         quality_review_improvement_overdue.pk,
                                         quality_review_improvement_done.pk,
                                         quality_review_maturity.pk}
    stale = quality_admin_client.get(base + "?kind=nope")  # unrecognised kind narrows nothing
    assert len(list(stale.context["object_list"])) == 9
    by_status = quality_admin_client.get(base + "?status=reported")
    assert _quality_pks(by_status) == {quality_review_reported.pk}
    by_type = quality_admin_client.get(base + "?review_type=gate_review")
    assert _quality_pks(by_type) == {quality_review_reported.pk}


def test_quality_review_overdue_lens_selects_the_open_kaizen(
        tenant_a, quality_admin_client, quality_review_improvement,
        quality_review_improvement_overdue, quality_review_improvement_done):
    response = quality_admin_client.get(reverse("projects:qrv_list") + "?overdue=1")
    # The finished action is OUT (done), the future-dated one is OUT (not yet due).
    assert _quality_pks(response) == {quality_review_improvement_overdue.pk}


def test_quality_inspection_filters_and_overdue_lens(
        tenant_a, quality_admin_client, quality_inspection_planned,
        quality_inspection_in_progress, quality_inspection_accepted, quality_inspection_rejected,
        quality_inspection_acceptance_pending, quality_inspection_overdue):
    base = reverse("projects:qci_list")
    by_result = quality_admin_client.get(base + "?result=pass")
    assert _quality_pks(by_result) == {quality_inspection_in_progress.pk,
                                       quality_inspection_accepted.pk,
                                       quality_inspection_acceptance_pending.pk}
    by_decision = quality_admin_client.get(base + "?usage_decision=accept")
    assert _quality_pks(by_decision) == {quality_inspection_accepted.pk}
    by_status = quality_admin_client.get(base + "?status=failed")
    assert _quality_pks(by_status) == {quality_inspection_rejected.pk}
    by_type = quality_admin_client.get(base + "?inspection_type=acceptance")
    assert _quality_pks(by_type) == {quality_inspection_accepted.pk,
                                     quality_inspection_acceptance_pending.pk}
    # The lens reads never-executed: the recorded rows with past planned dates are OUT.
    overdue = quality_admin_client.get(base + "?overdue=1")
    assert _quality_pks(overdue) == {quality_inspection_overdue.pk}


def test_quality_defect_filters_and_overdue_lens(
        tenant_a, quality_admin_client, quality_defect_open, quality_defect_in_progress,
        quality_defect_resolved, quality_defect_cancelled, quality_defect_overdue,
        quality_defect_bridged):
    base = reverse("projects:qdf_list")
    by_severity = quality_admin_client.get(base + "?severity=major")
    assert _quality_pks(by_severity) == {quality_defect_open.pk, quality_defect_bridged.pk}
    by_status = quality_admin_client.get(base + "?status=open")
    assert _quality_pks(by_status) == {quality_defect_open.pk, quality_defect_overdue.pk,
                                       quality_defect_bridged.pk}
    observation = quality_admin_client.get(base + "?severity=observation")
    assert _quality_pks(observation) == {quality_defect_cancelled.pk}
    by_category = quality_admin_client.get(base + "?defect_category=documentation")
    assert _quality_pks(by_category) == {quality_defect_overdue.pk}
    by_disposition = quality_admin_client.get(base + "?disposition=rework")
    assert _quality_pks(by_disposition) == {quality_defect_in_progress.pk}
    overdue = quality_admin_client.get(base + "?overdue=1")
    assert _quality_pks(overdue) == {quality_defect_overdue.pk}


def test_quality_foreign_project_filter_renders_registers_empty(
        tenant_a, quality_admin_client, quality_project_a, quality_project_b,
        quality_plan_draft, quality_review_planned, quality_inspection_planned,
        quality_defect_open):
    """A valid-but-FOREIGN pk FILTER is 200 EMPTY on the four registers (never a 404)."""
    for url_name in ("qpl_list", "qrv_list", "qci_list", "qdf_list"):
        response = quality_admin_client.get(reverse(f"projects:{url_name}") +
                                            f"?project={quality_project_b.pk}")
        assert response.status_code == 200, url_name
        assert len(list(response.context["object_list"])) == 0, url_name
        own = quality_admin_client.get(reverse(f"projects:{url_name}") +
                                       f"?project={quality_project_a.pk}")
        assert len(list(own.context["object_list"])) == 1, url_name


def test_quality_search_hits_known_substrings(tenant_a, quality_admin_client,
                                              quality_plan_draft, quality_plan_active,
                                              quality_review_reported, quality_review_planned,
                                              quality_inspection_planned,
                                              quality_inspection_conditional,
                                              quality_defect_closed, quality_defect_open):
    searches = [
        ("qpl_list", "?q=depot", {quality_plan_draft.pk}),       # title
        ("qrv_list", "?q=sign-off", {quality_review_reported.pk}),  # findings
        ("qci_list", "?q=first-article", {quality_inspection_planned.pk}),  # title
        ("qdf_list", "?q=barcode", {quality_defect_closed.pk}),  # resolution_note
    ]
    for url_name, param, expected in searches:
        response = quality_admin_client.get(reverse(f"projects:{url_name}") + param)
        assert response.status_code == 200, url_name
        assert _quality_pks(response) == expected, url_name


def test_quality_registers_junk_params_return_the_default_page(tenant_a, quality_admin_client,
                                                               quality_plan_draft,
                                                               quality_review_planned,
                                                               quality_inspection_planned,
                                                               quality_defect_open):
    for url_name, marker in (("qpl_list", quality_plan_draft.number),
                             ("qrv_list", quality_review_planned.number),
                             ("qci_list", quality_inspection_planned.number),
                             ("qdf_list", quality_defect_open.number)):
        for junk in _QUALITY_JUNK_PARAMS:
            response = quality_admin_client.get(reverse(f"projects:{url_name}") + junk)
            assert response.status_code == 200, (url_name, junk)
            if "page=" not in junk:
                assert marker in response.content.decode(), (url_name, junk)


def test_quality_plans_page_two_holds_the_overflow(tenant_a, quality_admin_client,
                                                   quality_project_a):
    _quality_fill_plans(tenant_a, quality_project_a, QUALITY_PAGE_SIZE + 1)
    first_page = quality_admin_client.get(reverse("projects:qpl_list"))
    assert first_page.status_code == 200
    assert len(list(first_page.context["object_list"])) == QUALITY_PAGE_SIZE
    second_page = quality_admin_client.get(reverse("projects:qpl_list") + "?page=2")
    assert second_page.status_code == 200
    assert 1 <= len(list(second_page.context["object_list"])) <= QUALITY_PAGE_SIZE
    assert not _quality_pks(first_page) & _quality_pks(second_page)
    junk_page = quality_admin_client.get(reverse("projects:qpl_list") + "?page=abc")  # L9
    assert junk_page.status_code == 200
    assert _quality_pks(junk_page) == _quality_pks(first_page)


# ==============================================================================================
# Detail pages — the pinned extra context keys
# ==============================================================================================

def test_quality_plan_detail_renders_linked_querysets(tenant_a, quality_admin_client,
                                                      quality_project_a, quality_plan_active):
    review = _quality_review(tenant_a, quality_project_a, title="A linked review",
                             quality_plan=quality_plan_active)
    inspection = _quality_inspection(tenant_a, quality_project_a, title="A linked inspection",
                                     quality_plan=quality_plan_active)
    defect = _quality_defect(tenant_a, quality_project_a, title="A linked defect",
                             quality_plan=quality_plan_active)
    response = quality_admin_client.get(reverse("projects:qpl_detail",
                                                args=[quality_plan_active.pk]))
    assert response.status_code == 200
    assert response.context["obj"].pk == quality_plan_active.pk
    assert {r.pk for r in response.context["linked_reviews"]} == {review.pk}
    assert {i.pk for i in response.context["linked_inspections"]} == {inspection.pk}
    assert {d.pk for d in response.context["linked_defects"]} == {defect.pk}
    body = response.content.decode()
    assert quality_plan_active.number in body
    assert "A linked review" in body


def test_quality_review_detail_renders_the_row(tenant_a, quality_admin_client,
                                               quality_review_reported):
    response = quality_admin_client.get(reverse("projects:qrv_detail",
                                                args=[quality_review_reported.pk]))
    assert response.status_code == 200
    assert response.context["obj"].pk == quality_review_reported.pk
    body = response.content.decode()
    assert quality_review_reported.number in body
    assert "Two sign-off artefacts were missing" in body


def test_quality_inspection_detail_carries_the_accept_form_and_choices(
        tenant_a, quality_admin_client, quality_inspection_acceptance_pending):
    response = quality_admin_client.get(reverse("projects:qci_detail",
                                                args=[quality_inspection_acceptance_pending.pk]))
    assert response.status_code == 200
    assert isinstance(response.context["accept_form"], InspectionAcceptanceForm)
    assert response.context["result_choices"] == DeliverableInspection.RESULT_CHOICES
    assert list(response.context["defects"]) == []
    assert quality_inspection_acceptance_pending.number in response.content.decode()


def test_quality_defect_detail_carries_the_resolution_form(tenant_a, quality_admin_client,
                                                           quality_defect_resolved):
    response = quality_admin_client.get(reverse("projects:qdf_detail",
                                                args=[quality_defect_resolved.pk]))
    assert response.status_code == 200
    assert isinstance(response.context["resolution_form"], DefectResolutionForm)
    body = response.content.decode()
    assert quality_defect_resolved.number in body
    assert "Template fixed and re-deployed" in body


def test_quality_defect_detail_renders_the_issue_bridge(tenant_a, quality_admin_client,
                                                        quality_defect_bridged):
    response = quality_admin_client.get(reverse("projects:qdf_detail",
                                                args=[quality_defect_bridged.pk]))
    assert response.status_code == 200
    assert quality_defect_bridged.project_issue.number in response.content.decode()


# ==============================================================================================
# Create views — number minting, authorship stamp, ?project= initial, smuggled-field guard
# ==============================================================================================

def test_quality_create_get_seeds_the_project_initial(tenant_a, quality_admin_client,
                                                      quality_project_a):
    for url_name in ("qpl_create", "qrv_create", "qci_create", "qdf_create"):
        response = quality_admin_client.get(reverse(f"projects:{url_name}") +
                                            f"?project={quality_project_a.pk}")
        assert response.status_code == 200, url_name
        assert response.context["form"].initial.get("project") == quality_project_a.pk, url_name


def test_quality_plan_create_posts_a_draft_and_stamps_the_author(tenant_a, quality_admin_client,
                                                                 admin_user, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qpl_create"),
                                         _quality_plan_post(quality_project_a))
    assert response.status_code == 302
    obj = QualityPlan.objects.get(tenant=tenant_a, title="Plan written by the view test")
    assert obj.created_by == admin_user
    assert obj.status == "draft"  # the smuggled "active" never reached the row
    assert re.fullmatch(r"QPL-\d{5}", obj.number)
    assert response.url == reverse("projects:qpl_detail", args=[obj.pk])


def test_quality_review_create_posts_a_planned_review(tenant_a, quality_admin_client, admin_user,
                                                      quality_project_a):
    response = quality_admin_client.post(reverse("projects:qrv_create"),
                                         _quality_review_post(quality_project_a))
    assert response.status_code == 302
    obj = QualityReview.objects.get(tenant=tenant_a, title="Review written by the view test")
    assert obj.created_by == admin_user
    assert obj.status == "planned" and obj.closed_at is None  # smuggled stamps ignored
    assert re.fullmatch(r"QRV-\d{5}", obj.number)
    assert response.url == reverse("projects:qrv_detail", args=[obj.pk])


def test_quality_inspection_create_posts_an_undecided_inspection(tenant_a, quality_admin_client,
                                                                 admin_user, quality_project_a):
    response = quality_admin_client.post(reverse("projects:qci_create"),
                                         _quality_inspection_post(quality_project_a))
    assert response.status_code == 302
    obj = DeliverableInspection.objects.get(tenant=tenant_a,
                                            title="Inspection written by the view test")
    assert obj.created_by == admin_user
    assert obj.usage_decision == "pending" and obj.status == "planned"
    assert obj.accepted_by_id is None  # the smuggled acceptor never reached the row
    assert re.fullmatch(r"QCI-\d{5}", obj.number)
    assert response.url == reverse("projects:qci_detail", args=[obj.pk])


def test_quality_defect_create_posts_an_open_defect(tenant_a, quality_admin_client, admin_user,
                                                    quality_project_a):
    response = quality_admin_client.post(reverse("projects:qdf_create"),
                                         _quality_defect_post(quality_project_a))
    assert response.status_code == 302
    obj = QualityDefect.objects.get(tenant=tenant_a, title="Defect written by the view test")
    assert obj.created_by == admin_user
    assert obj.status == "open" and obj.project_issue_id is None
    assert re.fullmatch(r"QDF-\d{5}", obj.number)
    assert response.url == reverse("projects:qdf_detail", args=[obj.pk])


@pytest.mark.parametrize("url_name", ["qpl_create", "qrv_create", "qci_create", "qdf_create"])
def test_quality_create_invalid_post_rerenders_with_errors(tenant_a, quality_admin_client,
                                                           url_name):
    response = quality_admin_client.post(reverse(f"projects:{url_name}"), {})
    assert response.status_code == 200
    assert response.context["form"].errors


def test_quality_create_tenantless_redirects_home(quality_tenantless_client, tenant_a,
                                                  quality_project_a):
    response = quality_tenantless_client.post(reverse("projects:qpl_create"), {})
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")


# ==============================================================================================
# Edit / delete — the CRUD pair, POST-only deletes, and the frozen-row guards
# ==============================================================================================

def test_quality_plan_edit_prefills_and_saves(tenant_a, quality_admin_client, quality_project_a,
                                              quality_plan_draft):
    got = quality_admin_client.get(reverse("projects:qpl_edit", args=[quality_plan_draft.pk]))
    assert got.status_code == 200
    assert got.context["form"].initial["title"] == quality_plan_draft.title
    assert got.context["is_edit"] is True
    response = quality_admin_client.post(
        reverse("projects:qpl_edit", args=[quality_plan_draft.pk]),
        _quality_plan_post(quality_project_a, title="Edited acceptance criteria"), follow=True)
    assert response.status_code == 200
    quality_plan_draft.refresh_from_db()
    assert quality_plan_draft.title == "Edited acceptance criteria"


def test_quality_review_edit_saves(tenant_a, quality_admin_client, quality_project_a,
                                   quality_review_planned):
    response = quality_admin_client.post(
        reverse("projects:qrv_edit", args=[quality_review_planned.pk]),
        _quality_review_post(quality_project_a, title="Edited review title"), follow=True)
    assert response.status_code == 200
    quality_review_planned.refresh_from_db()
    assert quality_review_planned.title == "Edited review title"
    assert quality_review_planned.status == "planned"  # status stays OFF the form


def test_quality_delete_is_post_only_and_lands_on_the_list(tenant_a, quality_project_a,
                                                           quality_admin_client):
    lanes = [
        (_quality_plan(tenant_a, quality_project_a, title="Deletable plan"), "qpl"),
        (_quality_review(tenant_a, quality_project_a, title="Deletable review"), "qrv"),
        (_quality_inspection(tenant_a, quality_project_a, title="Deletable inspection"), "qci"),
        (_quality_defect(tenant_a, quality_project_a, title="Deletable defect"), "qdf"),
    ]
    for obj, prefix in lanes:
        got = quality_admin_client.get(reverse(f"projects:{prefix}_delete", args=[obj.pk]))
        assert got.status_code == 405, prefix  # deletes are POST-only
        posted = quality_admin_client.post(reverse(f"projects:{prefix}_delete", args=[obj.pk]))
        assert posted.status_code == 302, prefix
        assert posted.url == reverse(f"projects:{prefix}_list"), prefix
        assert not type(obj).objects.filter(pk=obj.pk).exists(), prefix


def test_quality_locked_plans_refuse_edit_and_delete(tenant_a, quality_admin_client,
                                                     quality_plan_superseded,
                                                     quality_plan_closed):
    for plan in (quality_plan_superseded, quality_plan_closed):
        _quality_frozen_refusal(quality_admin_client, plan,
                                edit_url_name="projects:qpl_edit",
                                delete_url_name="projects:qpl_delete",
                                detail_url_name="projects:qpl_detail")


def test_quality_locked_reviews_refuse_edit_and_delete(tenant_a, quality_admin_client,
                                                       quality_review_closed,
                                                       quality_review_cancelled):
    for review in (quality_review_closed, quality_review_cancelled):
        _quality_frozen_refusal(quality_admin_client, review,
                                edit_url_name="projects:qrv_edit",
                                delete_url_name="projects:qrv_delete",
                                detail_url_name="projects:qrv_detail")


def test_quality_locked_inspections_refuse_edit_and_delete(tenant_a, quality_admin_client,
                                                           quality_inspection_accepted,
                                                           quality_inspection_rejected,
                                                           quality_inspection_cancelled):
    """Terminal statuses AND a taken decision both freeze the row."""
    for inspection in (quality_inspection_accepted, quality_inspection_rejected,
                       quality_inspection_cancelled):
        _quality_frozen_refusal(quality_admin_client, inspection,
                                edit_url_name="projects:qci_edit",
                                delete_url_name="projects:qci_delete",
                                detail_url_name="projects:qci_detail")


def test_quality_locked_defects_refuse_edit_and_delete(tenant_a, quality_admin_client,
                                                       quality_defect_resolved,
                                                       quality_defect_closed,
                                                       quality_defect_cancelled):
    """The M1 amendment: ``cancelled`` locks the defect like its QRV/QCI siblings."""
    for defect in (quality_defect_resolved, quality_defect_closed, quality_defect_cancelled):
        _quality_frozen_refusal(quality_admin_client, defect,
                                edit_url_name="projects:qdf_edit",
                                delete_url_name="projects:qdf_delete",
                                detail_url_name="projects:qdf_detail")


# ==============================================================================================
# QualityPlan verbs — approve (login-gated) and supersede (admin-gated, POST-only above it)
# ==============================================================================================

def test_quality_plan_approve_activates_a_draft_and_stamps_the_approver(
        tenant_a, quality_member_client, quality_member, quality_plan_draft):
    response = quality_member_client.post(reverse("projects:qpl_approve",
                                                  args=[quality_plan_draft.pk]), follow=True)
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == reverse("projects:qpl_detail",
                                                    args=[quality_plan_draft.pk])
    quality_plan_draft.refresh_from_db()
    assert quality_plan_draft.status == "active"
    assert quality_plan_draft.approved_by == quality_member
    assert quality_plan_draft.approved_at is not None
    assert f"Approved {quality_plan_draft.number}" in response.content.decode()
    assert AuditLog.objects.filter(object_id=str(quality_plan_draft.pk),
                                   action="update").exists()
    stamp = quality_plan_draft.approved_at
    replay = quality_member_client.post(reverse("projects:qpl_approve",
                                                args=[quality_plan_draft.pk]), follow=True)
    assert "Only a draft plan can be approved." in replay.content.decode()
    quality_plan_draft.refresh_from_db()
    assert quality_plan_draft.approved_at == stamp  # a replay writes nothing


def test_quality_plan_approve_refuses_a_non_draft(tenant_a, quality_admin_client,
                                                  quality_plan_active):
    before = QualityPlan.objects.get(pk=quality_plan_active.pk)
    response = quality_admin_client.post(reverse("projects:qpl_approve",
                                                 args=[quality_plan_active.pk]), follow=True)
    assert "Only a draft plan can be approved." in response.content.decode()
    after = QualityPlan.objects.get(pk=quality_plan_active.pk)
    assert (after.status, after.approved_at) == (before.status, before.approved_at)


def test_quality_plan_supersede_retires_an_active_plan(tenant_a, quality_admin_client,
                                                       quality_plan_active):
    response = quality_admin_client.post(reverse("projects:qpl_supersede",
                                                 args=[quality_plan_active.pk]), follow=True)
    assert response.status_code == 200
    quality_plan_active.refresh_from_db()
    assert quality_plan_active.status == "superseded"
    assert AuditLog.objects.filter(object_id=str(quality_plan_active.pk),
                                   action="update").exists()
    replay = quality_admin_client.post(reverse("projects:qpl_supersede",
                                               args=[quality_plan_active.pk]), follow=True)
    assert "Only an active plan can be superseded." in replay.content.decode()


def test_quality_plan_supersede_gates_the_member(quality_member_client, quality_plan_active):
    """The M2 decorator order: a member's GET is 405 (require_POST first), the POST is 403."""
    got = quality_member_client.get(reverse("projects:qpl_supersede",
                                            args=[quality_plan_active.pk]))
    assert got.status_code == 405
    posted = quality_member_client.post(reverse("projects:qpl_supersede",
                                                args=[quality_plan_active.pk]))
    assert posted.status_code == 403
    quality_plan_active.refresh_from_db()
    assert quality_plan_active.status == "active"


# ==============================================================================================
# QualityReview verbs — report (planned OR in_progress, the close-out amendment) and close
# ==============================================================================================

def test_quality_review_report_accepts_planned_and_in_progress(
        tenant_a, quality_member_client, quality_review_planned, quality_review_in_progress):
    for review in (quality_review_planned, quality_review_in_progress):
        response = quality_member_client.post(reverse("projects:qrv_report",
                                                      args=[review.pk]), follow=True)
        assert response.status_code == 200
        review.refresh_from_db()
        assert review.status == "reported"
        assert f"Reported {review.number}" in response.content.decode()
        assert AuditLog.objects.filter(object_id=str(review.pk), action="update").exists()


def test_quality_review_report_refuses_a_reported_review(tenant_a, quality_admin_client,
                                                         quality_review_reported):
    response = quality_admin_client.post(reverse("projects:qrv_report",
                                                 args=[quality_review_reported.pk]), follow=True)
    assert "Only a planned or in-progress review can be reported." in response.content.decode()
    quality_review_reported.refresh_from_db()
    assert quality_review_reported.status == "reported"


def test_quality_review_close_stamps_closed_at_and_refuses_a_replay(
        tenant_a, quality_member_client, quality_review_reported):
    response = quality_member_client.post(reverse("projects:qrv_close",
                                                  args=[quality_review_reported.pk]), follow=True)
    assert response.status_code == 200
    quality_review_reported.refresh_from_db()
    assert quality_review_reported.status == "closed"
    assert quality_review_reported.closed_at is not None
    assert f"Closed {quality_review_reported.number}" in response.content.decode()
    assert AuditLog.objects.filter(object_id=str(quality_review_reported.pk),
                                   action="close").exists()
    stamp = quality_review_reported.closed_at
    replay = quality_member_client.post(reverse("projects:qrv_close",
                                                args=[quality_review_reported.pk]), follow=True)
    assert "Only a reported review can be closed." in replay.content.decode()
    quality_review_reported.refresh_from_db()
    assert quality_review_reported.closed_at == stamp


def test_quality_review_close_refuses_an_unreported_review(tenant_a, quality_admin_client,
                                                           quality_review_planned):
    response = quality_admin_client.post(reverse("projects:qrv_close",
                                                 args=[quality_review_planned.pk]), follow=True)
    assert "Only a reported review can be closed." in response.content.decode()
    quality_review_planned.refresh_from_db()
    assert quality_review_planned.status == "planned"


# ==============================================================================================
# DeliverableInspection verbs — record (row stays live), accept / reject (decision + status)
# ==============================================================================================

def test_quality_inspection_record_keeps_the_row_live(tenant_a, quality_member_client,
                                                      quality_inspection_planned,
                                                      quality_inspection_on_hold):
    response = quality_member_client.post(reverse("projects:qci_record",
                                                  args=[quality_inspection_planned.pk]),
                                          {"result": "pass"}, follow=True)
    assert response.status_code == 200
    quality_inspection_planned.refresh_from_db()
    assert quality_inspection_planned.result == "pass"
    assert quality_inspection_planned.inspected_date == _quality_today()  # the default stamp
    assert quality_inspection_planned.status == "in_progress"  # NEVER terminal
    assert quality_inspection_planned.usage_decision == "pending"  # still open for the decision
    assert f"Recorded Pass on {quality_inspection_planned.number}" in response.content.decode()
    assert AuditLog.objects.filter(object_id=str(quality_inspection_planned.pk),
                                   action="update").exists()
    on_hold = quality_member_client.post(reverse("projects:qci_record",
                                                 args=[quality_inspection_on_hold.pk]),
                                         {"result": "fail",
                                          "inspected_date": _quality_today().isoformat()},
                                         follow=True)
    quality_inspection_on_hold.refresh_from_db()
    assert quality_inspection_on_hold.status == "in_progress"  # on_hold → in_progress too
    assert quality_inspection_on_hold.result == "fail"


def test_quality_inspection_record_refuses_pending_and_unknown_results(
        tenant_a, quality_admin_client, quality_inspection_planned):
    for bad in ("pending", "excellent"):
        response = quality_admin_client.post(reverse("projects:qci_record",
                                                     args=[quality_inspection_planned.pk]),
                                             {"result": bad}, follow=True)
        assert "Record a result of pass, fail" in response.content.decode(), bad
    quality_inspection_planned.refresh_from_db()
    assert quality_inspection_planned.result == "pending"
    assert quality_inspection_planned.status == "planned"


def test_quality_inspection_accept_takes_the_decision_and_locks(
        tenant_a, quality_admin_client, admin_user, quality_inspection_acceptance_pending,
        quality_client_party_a):
    response = quality_admin_client.post(reverse("projects:qci_accept",
                                                 args=[quality_inspection_acceptance_pending.pk]),
                                         {"usage_decision": "accept",
                                          "accepted_by_party": quality_client_party_a.pk,
                                          "acceptance_note": "Signed off against the criteria."},
                                         follow=True)
    assert response.status_code == 200
    quality_inspection_acceptance_pending.refresh_from_db()
    inspection = quality_inspection_acceptance_pending
    assert inspection.usage_decision == "accept"
    assert inspection.accepted_by == admin_user
    assert inspection.accepted_by_party == quality_client_party_a
    assert inspection.accepted_at is not None
    assert inspection.acceptance_note == "Signed off against the criteria."
    assert inspection.status == "passed"
    assert "Accepted" in response.content.decode()
    assert AuditLog.objects.filter(object_id=str(inspection.pk), action="accept").exists()


def test_quality_inspection_accept_refuses_an_unrecorded_result(tenant_a, quality_admin_client,
                                                                quality_project_a):
    obj = _quality_inspection(tenant_a, quality_project_a,
                              title="Not yet executed acceptance", inspection_type="acceptance")
    response = quality_admin_client.post(reverse("projects:qci_accept", args=[obj.pk]),
                                         {"usage_decision": "accept"}, follow=True)
    assert "Record the inspection result" in response.content.decode()
    obj.refresh_from_db()
    assert obj.usage_decision == "pending" and obj.status == "planned"
    assert obj.accepted_by_id is None


def test_quality_inspection_reject_fails_the_deliverable(tenant_a, quality_member_client,
                                                         quality_inspection_acceptance_pending):
    response = quality_member_client.post(reverse("projects:qci_reject",
                                                  args=[quality_inspection_acceptance_pending.pk]),
                                          follow=True)
    assert response.status_code == 200
    quality_inspection_acceptance_pending.refresh_from_db()
    assert quality_inspection_acceptance_pending.usage_decision == "reject"
    assert quality_inspection_acceptance_pending.status == "failed"
    assert AuditLog.objects.filter(object_id=str(quality_inspection_acceptance_pending.pk),
                                   action="reject").exists()


# ==============================================================================================
# QualityDefect verbs — resolve (note required), close, raise-issue (the 7.5 bridge)
# ==============================================================================================

def test_quality_defect_resolve_stamps_the_resolver(tenant_a, quality_member_client,
                                                    quality_member, quality_defect_open,
                                                    quality_defect_in_progress):
    for defect in (quality_defect_open, quality_defect_in_progress):  # legal from BOTH live
        response = quality_member_client.post(reverse("projects:qdf_resolve", args=[defect.pk]),
                                              {"root_cause": "The jig was mis-set.",
                                               "resolution_note": "Re-set and re-measured."},
                                              follow=True)
        assert response.status_code == 200
        defect.refresh_from_db()
        assert defect.status == "resolved"
        assert defect.resolved_by == quality_member
        assert defect.resolved_at is not None
        assert defect.root_cause == "The jig was mis-set."
        assert f"Resolved {defect.number}" in response.content.decode()
        assert AuditLog.objects.filter(object_id=str(defect.pk), action="resolve").exists()


def test_quality_defect_resolve_requires_a_resolution_note(tenant_a, quality_admin_client,
                                                           quality_defect_open):
    response = quality_admin_client.post(reverse("projects:qdf_resolve",
                                                 args=[quality_defect_open.pk]),
                                         {"root_cause": "Something."}, follow=True)
    assert "required" in response.content.decode().lower()
    quality_defect_open.refresh_from_db()
    assert quality_defect_open.status == "open"
    assert quality_defect_open.resolved_by_id is None
    assert quality_defect_open.resolution_note == ""


def test_quality_defect_close_retires_a_resolved_defect(tenant_a, quality_member_client,
                                                        quality_defect_resolved):
    response = quality_member_client.post(reverse("projects:qdf_close",
                                                  args=[quality_defect_resolved.pk]), follow=True)
    assert response.status_code == 200
    quality_defect_resolved.refresh_from_db()
    assert quality_defect_resolved.status == "closed"
    assert f"Closed {quality_defect_resolved.number}" in response.content.decode()
    assert AuditLog.objects.filter(object_id=str(quality_defect_resolved.pk),
                                   action="close").exists()
    replay = quality_member_client.post(reverse("projects:qdf_close",
                                                args=[quality_defect_resolved.pk]), follow=True)
    assert "Only a resolved defect can be closed." in replay.content.decode()


def test_quality_defect_close_refuses_an_open_defect(tenant_a, quality_admin_client,
                                                     quality_defect_open):
    response = quality_admin_client.post(reverse("projects:qdf_close",
                                                 args=[quality_defect_open.pk]), follow=True)
    assert "Only a resolved defect can be closed." in response.content.decode()
    quality_defect_open.refresh_from_db()
    assert quality_defect_open.status == "open"


def test_quality_defect_raise_issue_bridges_and_maps_major_to_high(
        tenant_a, quality_member_client, quality_member, quality_defect_open):
    before = ProjectIssue.objects.filter(tenant=tenant_a).count()
    response = quality_member_client.post(reverse("projects:qdf_raise_issue",
                                                  args=[quality_defect_open.pk]), follow=True)
    assert response.status_code == 200
    quality_defect_open.refresh_from_db()
    issue = quality_defect_open.project_issue
    assert issue is not None
    assert issue.severity == "high"  # the band mapping: major → high
    assert issue.project_id == quality_defect_open.project_id
    assert issue.raised_by == quality_member and issue.created_by == quality_member
    assert issue.identified_date == _quality_today()
    assert ProjectIssue.objects.filter(tenant=tenant_a).count() == before + 1
    body = response.content.decode()
    assert f"raised as issue {issue.number}" in body  # the message names BOTH numbers
    assert quality_defect_open.number in body
    assert AuditLog.objects.filter(object_id=str(issue.pk), action="create").exists()
    assert AuditLog.objects.filter(object_id=str(quality_defect_open.pk),
                                   action="update").exists()


def test_quality_defect_raise_issue_maps_minor_to_medium(tenant_a, quality_admin_client,
                                                         quality_project_a):
    defect = _quality_defect(tenant_a, quality_project_a, title="A minor punch item")
    quality_admin_client.post(reverse("projects:qdf_raise_issue", args=[defect.pk]))
    defect.refresh_from_db()
    assert defect.project_issue.severity == "medium"


def test_quality_defect_raise_issue_refuses_a_second_bridge(tenant_a, quality_admin_client,
                                                            quality_defect_bridged):
    existing = quality_defect_bridged.project_issue
    before = ProjectIssue.objects.filter(tenant=tenant_a).count()
    response = quality_admin_client.post(reverse("projects:qdf_raise_issue",
                                                 args=[quality_defect_bridged.pk]), follow=True)
    assert "already raised issue" in response.content.decode()
    assert existing.number in response.content.decode()
    assert ProjectIssue.objects.filter(tenant=tenant_a).count() == before  # no second mint
    quality_defect_bridged.refresh_from_db()
    assert quality_defect_bridged.project_issue_id == existing.pk


def test_quality_defect_raise_issue_refuses_a_cancelled_defect(tenant_a, quality_admin_client,
                                                               quality_defect_cancelled):
    """The M1 amendment: ``is_locked`` now includes ``cancelled``, so the bridge refuses it."""
    before = ProjectIssue.objects.filter(tenant=tenant_a).count()
    response = quality_admin_client.post(reverse("projects:qdf_raise_issue",
                                                 args=[quality_defect_cancelled.pk]), follow=True)
    assert "frozen evidence" in response.content.decode()
    assert ProjectIssue.objects.filter(tenant=tenant_a).count() == before
    quality_defect_cancelled.refresh_from_db()
    assert quality_defect_cancelled.status == "cancelled"
    assert quality_defect_cancelled.project_issue_id is None


def test_quality_verbs_are_post_only(tenant_a, quality_admin_client, request):
    for fixture_name, url_name in _QUALITY_POST_ONLY_URLS:
        obj = request.getfixturevalue(fixture_name)
        response = quality_admin_client.get(reverse(f"projects:{url_name}", args=[obj.pk]))
        assert response.status_code == 405, (fixture_name, url_name)
    # The 405s fired before any view body ran — nothing moved.
    assert QualityPlan.objects.get(pk=request.getfixturevalue("quality_plan_draft").pk) \
        .status == "draft"
    assert QualityDefect.objects.get(pk=request.getfixturevalue("quality_defect_open").pk) \
        .project_issue_id is None


# ==============================================================================================
# The computed boards — §3.1 / §3.2 of the test contract
# ==============================================================================================

def test_quality_improvement_board_pins_the_contract_figures(
        tenant_a, quality_admin_client, quality_project_a, quality_wbs_node_a,
        quality_review_planned, quality_review_in_progress, quality_review_reported,
        quality_review_closed, quality_review_cancelled, quality_review_improvement,
        quality_review_improvement_overdue, quality_review_improvement_done,
        quality_review_maturity, quality_defect_open, quality_defect_in_progress,
        quality_defect_resolved, quality_defect_closed, quality_defect_cancelled,
        quality_defect_overdue, quality_defect_bridged):
    response = quality_admin_client.get(reverse("projects:quality_improvement") +
                                        f"?project={quality_project_a.pk}")
    assert response.status_code == 200
    for key in ("projects", "project", "improvement_rows", "maturity", "defect_trend_rows",
                "defect_trend_max", "lessons", "lessons_count", "open_defect_count",
                "improvement_open_count"):
        assert key in response.context, key
    assert response.context["project"] == quality_project_a

    rows = response.context["improvement_rows"]
    assert len(rows) == 3  # the board's TWO types — the maturity_assessment row is OUT
    assert {r.pk for r in rows} == {quality_review_improvement.pk,
                                    quality_review_improvement_overdue.pk,
                                    quality_review_improvement_done.pk}
    assert quality_review_maturity.pk not in {r.pk for r in rows}

    maturity = response.context["maturity"]
    assert maturity["has_score"] is True  # the M9 amendment — a falsy 0.0 must still render
    assert maturity["score"] == 3.0
    assert maturity["band"] == "Defined"
    assert maturity["badge"] == "badge-info"
    assert maturity["reviews_scored"] == 1
    assert maturity["defects_total"] == 7
    assert maturity["defects_closed"] == 2  # resolved counts as dispositioned
    assert maturity["closure_pct"] == 29

    defects = [quality_defect_open, quality_defect_in_progress, quality_defect_resolved,
               quality_defect_closed, quality_defect_cancelled, quality_defect_overdue,
               quality_defect_bridged]
    expected_rows, expected_max = _quality_expected_trend(defects)
    trend_rows = response.context["defect_trend_rows"]
    assert len(trend_rows) == 6
    for row in trend_rows:
        assert set(row.keys()) == TREND_ROW_KEYS
        assert re.fullmatch(r"[A-Z][a-z]{2} \d{4}", row["label"])
    assert [(r["period"], r["opened"], r["closed"], r["bar_pct"]) for r in trend_rows] == \
           [(r["period"], r["opened"], r["closed"], r["bar_pct"]) for r in expected_rows]
    assert response.context["defect_trend_max"] == expected_max
    assert sum(r["opened"] for r in trend_rows) == 7
    assert sum(r["closed"] for r in trend_rows) == 2

    lessons = response.context["lessons"]
    assert response.context["lessons_count"] == 1
    assert len(lessons) == 1
    assert lessons[0]["obj"].pk == quality_defect_closed.pk
    assert lessons[0]["lesson"] == quality_defect_closed.lessons_learned

    assert response.context["open_defect_count"] == 4
    assert response.context["improvement_open_count"] == 2

    body = response.content.decode()
    assert "3.0 / 5" in body
    assert "Defined" in body
    assert "2 of 7 dispositioned (29%)" in body
    assert "Audit barcode ranges" in body


def test_quality_improvement_maturity_recipe_edges_on_throwaway_hosts(tenant_a,
                                                                      quality_admin_client):
    """The §3.1 band recipes, each on its own isolated host so the figures cannot drift."""
    empty_host = _quality_project(tenant_a, name="Recipe empty host", code="QHP-E1")
    zero_host = _quality_project(tenant_a, name="Recipe zero host", code="QHP-E2")
    _quality_defect(tenant_a, zero_host, title="The only open defect")
    optimizing_host = _quality_project(tenant_a, name="Recipe optimizing host", code="QHP-E3")
    _quality_defect(tenant_a, optimizing_host, title="Fully dispositioned", status="resolved",
                    resolved_at=timezone.now(), resolution_note="Fixed.")
    managed_host = _quality_project(tenant_a, name="Recipe managed host", code="QHP-E4")
    _quality_defect(tenant_a, managed_host, title="Half of the punch list", status="resolved",
                    resolved_at=timezone.now(), resolution_note="Fixed.")
    _quality_defect(tenant_a, managed_host, title="The other half")

    empty = quality_admin_client.get(reverse("projects:quality_improvement") +
                                     f"?project={empty_host.pk}")
    assert empty.context["maturity"]["has_score"] is False  # no band computed from nothing
    assert empty.context["maturity"]["score"] is None
    assert empty.context["maturity"]["badge"] == "badge-muted"
    assert "Not enough data yet" in empty.content.decode()

    zero = quality_admin_client.get(reverse("projects:quality_improvement") +
                                    f"?project={zero_host.pk}")
    assert zero.context["maturity"]["has_score"] is True  # the M9 edge — 0.0 is a real score
    assert zero.context["maturity"]["score"] == 0.0
    assert zero.context["maturity"]["band"] == "Initial"
    assert zero.context["maturity"]["badge"] == "badge-red"
    assert "0.0 / 5" in zero.content.decode()

    optimizing = quality_admin_client.get(reverse("projects:quality_improvement") +
                                          f"?project={optimizing_host.pk}")
    assert optimizing.context["maturity"]["closure_pct"] == 100
    assert optimizing.context["maturity"]["score"] == 5.0
    assert optimizing.context["maturity"]["band"] == "Optimizing"
    assert optimizing.context["maturity"]["badge"] == "badge-green"

    managed = quality_admin_client.get(reverse("projects:quality_improvement") +
                                       f"?project={managed_host.pk}")
    assert managed.context["maturity"]["closure_pct"] == 50
    assert managed.context["maturity"]["score"] == 2.5
    assert managed.context["maturity"]["band"] == "Managed"
    assert managed.context["maturity"]["badge"] == "badge-amber"


def test_quality_improvement_project_lens_narrows_and_bad_ids_fall_back(
        tenant_a, quality_admin_client, quality_project_b):
    """``?project=<pk>`` narrows every figure; junk AND a valid-but-FOREIGN pk fall back to
    the tenant-wide page — 200, not 404, not empty (the §3.1 scope trap)."""
    host = _quality_project(tenant_a, name="Lens host", code="QHP-L1")
    kaizen = _quality_review(tenant_a, host, title="Lens kaizen", review_type="kaizen_event",
                             improvement_action="Do the thing", improvement_status="planned")
    _quality_defect(tenant_a, host, title="Lens open defect")
    _quality_defect(tenant_a, host, title="Lens closed defect", status="closed",
                    lessons_learned="Lens lesson recorded.")
    url = reverse("projects:quality_improvement")

    narrowed = quality_admin_client.get(url + f"?project={host.pk}")
    assert narrowed.status_code == 200
    assert narrowed.context["project"] == host
    assert [r.pk for r in narrowed.context["improvement_rows"]] == [kaizen.pk]
    assert narrowed.context["maturity"]["defects_total"] == 2
    assert narrowed.context["open_defect_count"] == 1
    assert narrowed.context["lessons_count"] == 1
    assert narrowed.context["improvement_open_count"] == 1

    for junk in ("?project=999999", "?project=abc"):
        response = quality_admin_client.get(url + junk)
        assert response.status_code == 200, junk
        assert response.context["project"] is None, junk
        assert response.context["maturity"]["defects_total"] == 2  # tenant-wide, not empty
        assert len(response.context["improvement_rows"]) == 1

    foreign = quality_admin_client.get(url + f"?project={quality_project_b.pk}")
    assert foreign.status_code == 200
    assert foreign.context["project"] is None
    assert foreign.context["maturity"]["defects_total"] == 2


def test_quality_acceptance_board_pins_the_deliverable_row_and_counts(
        tenant_a, quality_admin_client, quality_project_a, quality_wbs_node_a,
        quality_plan_active, quality_defect_open, quality_inspection_planned,
        quality_inspection_in_progress, quality_inspection_on_hold,
        quality_inspection_conditional, quality_inspection_not_applicable,
        quality_inspection_cancelled, quality_inspection_accepted, quality_inspection_rejected,
        quality_inspection_acceptance_pending, quality_inspection_overdue):
    response = quality_admin_client.get(reverse("projects:quality_acceptance") +
                                        f"?project={quality_project_a.pk}")
    assert response.status_code == 200
    for key in ("projects", "project", "deliverable_rows", "acceptance_queue",
                "acceptance_queue_count", "accepted_count", "conditional_count",
                "rejected_count", "pending_count"):
        assert key in response.context, key

    rows = response.context["deliverable_rows"]
    assert len(rows) == 1
    row = rows[0]
    assert set(row.keys()) == DELIVERABLE_ROW_KEYS
    assert row["wbs_node"] == quality_wbs_node_a
    assert row["plan"] == quality_plan_active
    assert row["plan_status"] == "active"
    assert row["latest_inspection"]["pk"] == quality_inspection_accepted.pk
    assert row["latest_inspection"]["number"] == quality_inspection_accepted.number
    assert row["result"] == "pass"
    assert row["usage_decision"] == "accept"
    assert row["open_defects"] == 1  # quality_defect_open, anchored to the node
    assert row["acceptance_state"] == "accepted"
    assert row["badge"] == "badge-green"

    queue = list(response.context["acceptance_queue"])
    assert [i.pk for i in queue] == [quality_inspection_acceptance_pending.pk]
    assert response.context["acceptance_queue_count"] == 1
    assert response.context["accepted_count"] == 1
    assert response.context["conditional_count"] == 0  # decisions, not result="conditional" rows
    assert response.context["rejected_count"] == 1
    assert response.context["pending_count"] == 8  # every undecided row incl. cancelled/on_hold

    body = response.content.decode()
    assert quality_plan_active.number in body
    assert quality_wbs_node_a.name in body
    assert quality_inspection_acceptance_pending.number in body  # the queue row renders


def test_quality_acceptance_without_a_project_is_empty_by_design(
        tenant_a, quality_admin_client, quality_project_a, quality_wbs_node_a,
        quality_plan_active, quality_defect_open, quality_inspection_planned,
        quality_inspection_in_progress, quality_inspection_on_hold,
        quality_inspection_conditional, quality_inspection_not_applicable,
        quality_inspection_cancelled, quality_inspection_accepted, quality_inspection_rejected,
        quality_inspection_acceptance_pending, quality_inspection_overdue):
    response = quality_admin_client.get(reverse("projects:quality_acceptance"))
    assert response.status_code == 200
    assert response.context["project"] is None
    assert response.context["deliverable_rows"] == []  # the board is empty, not a blur
    assert "Pick a project" in response.content.decode()
    # …while the queue and the counts stay tenant-wide.
    assert [i.pk for i in response.context["acceptance_queue"]] == \
        [quality_inspection_acceptance_pending.pk]
    assert response.context["acceptance_queue_count"] == 1
    assert response.context["accepted_count"] == 1
    assert response.context["rejected_count"] == 1
    assert response.context["conditional_count"] == 0
    assert response.context["pending_count"] == 8


def test_quality_acceptance_foreign_project_falls_back_tenant_wide(
        tenant_a, quality_admin_client, quality_project_b, quality_inspection_acceptance_pending,
        quality_inspection_accepted):
    url = reverse("projects:quality_acceptance")
    for param in (f"?project={quality_project_b.pk}", "?project=abc"):
        response = quality_admin_client.get(url + param)
        assert response.status_code == 200, param  # the scope trap — never a 404, never a 500
        assert response.context["project"] is None, param
        assert response.context["deliverable_rows"] == []
        assert response.context["acceptance_queue_count"] == 1  # tenant-wide figures
        assert response.context["accepted_count"] == 1
        assert response.context["pending_count"] == 1
        assert response.context["rejected_count"] == 0


# ==============================================================================================
# Cross-tenant isolation and anonymous access
# ==============================================================================================

@pytest.mark.parametrize("fixture_name,detail_url,list_url", [
    ("quality_plan_b", "qpl_detail", "qpl_list"),
    ("quality_review_b", "qrv_detail", "qrv_list"),
    ("quality_inspection_b", "qci_detail", "qci_list"),
    ("quality_defect_b", "qdf_detail", "qdf_list"),
])
def test_quality_cross_tenant_rows_are_404_or_absent(tenant_a, quality_admin_client, request,
                                                     fixture_name, detail_url, list_url):
    obj = request.getfixturevalue(fixture_name)
    detail = quality_admin_client.get(reverse(f"projects:{detail_url}", args=[obj.pk]))
    assert detail.status_code == 404
    listing = quality_admin_client.get(reverse(f"projects:{list_url}"))
    assert listing.status_code == 200
    assert obj.number not in listing.content.decode()


@pytest.mark.parametrize("url_name", ["qpl_list", "qrv_list", "qci_list", "qdf_list",
                                      "quality_improvement", "quality_acceptance"])
def test_quality_anon_is_redirected_to_login(quality_anon_client, url_name):
    response = quality_anon_client.get(reverse(f"projects:{url_name}"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_quality_anon_detail_is_redirected_to_login(quality_anon_client):
    response = quality_anon_client.get(reverse("projects:qpl_detail", args=[1]))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_quality_tenantless_client_gets_empty_pages_and_create_redirects_home(
        tenant_a, quality_tenantless_client, quality_project_a):
    _quality_plan(tenant_a, quality_project_a, title="Visible only to tenant A")
    for url_name in ("qpl_list", "qrv_list", "qci_list", "qdf_list"):
        response = quality_tenantless_client.get(reverse(f"projects:{url_name}"))
        assert response.status_code == 200, url_name
        assert len(list(response.context["object_list"])) == 0, url_name
    improvement = quality_tenantless_client.get(reverse("projects:quality_improvement"))
    assert improvement.status_code == 200
    assert improvement.context["maturity"]["has_score"] is False  # the boards are 0-safe
    assert improvement.context["improvement_rows"] == []
    acceptance = quality_tenantless_client.get(reverse("projects:quality_acceptance"))
    assert acceptance.status_code == 200
    assert acceptance.context["deliverable_rows"] == []
    assert "Pick a project" in acceptance.content.decode()
