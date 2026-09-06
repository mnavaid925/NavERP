"""Procurement 6.16 Supplier Performance & Evaluation - security, permissions and isolation.

The defensive lane of the 6.16 suite, and the last of its four. The lanes next door cover what
the sub-module DOES (models / forms / views); this file only ever asks what it REFUSES, and it
asserts the refusal TWICE - the status code, and then the row itself, re-read and unchanged. A
403 that still mutated is the bug, and a status code on its own cannot see it.

Seven sections:

1. **Cross-tenant IDOR, exhaustively.** Every ``<int:pk>`` route in 6.16, aimed from tenant A at
   a tenant-B row, on GET and on POST, must return **404** - never 200 (a read across the
   boundary) and never 500 (a guard that crashed instead of refusing) - with a before/after
   snapshot proving nothing moved. The three boards need their own treatment because **supplier
   names collide across workspaces by design**: a board asserted on rendered text would pass
   while leaking, so every board vector is asserted on CONTEXT (``selected_supplier``,
   ``rows[*]["scorecard_id"]``, ``series``) instead. The two register FK filters
   (``scores/?scorecard=`` and ``feedback/?supplier=``) get the same treatment.
2. **The authorization matrix**, driven route-by-route over all **34** routes - not 33; the
   ``urls`` package docstring predates ``improvementplan_evidence``, which the I5 fix added, and
   the route table below is checked against the live URLconf so the next omission fails here
   rather than shipping untested. Anonymous is refused on every route; the two
   ``@tenant_admin_required`` verbs are **403** for an ordinary member with zero mutation; the
   eleven ``@login_required`` verbs all WORK for that same member (L44 - a lane that only ever
   asserts refusals passes just as happily on a module nobody can use).

   **Decorator order is behaviour here.** ``supplierevaluation_generate`` and
   ``improvementplan_close`` are ``@require_POST`` OVER ``@tenant_admin_required``, so a GET is
   **405 before any authentication runs at all** - even anonymous. The anonymous sweep therefore
   POSTs to those two and GETs the rest; asserting a login redirect on a GET there would be
   asserting the wrong mechanism, and it is locked by its own test below.
3. **The status gates the security review added** (I3 / I4), locked as regressions: a score line
   on a **published** scorecard is undeletable by anybody, administrator included; a **closed**
   or **cancelled** plan is neither editable nor deletable; a **submitted** response is not
   editable. Each driven as an ordinary member, each followed by the record read back unchanged.
4. **The two uncaught-500 fixes** (C1 / C4). ``?year=0`` / ``10000`` / ``99999`` reached
   ``datetime.date(year, 1, 1)`` inside the backend; a 5,000-digit ``rating`` POST passed
   ``isdecimal()`` and then blew up in ``int()``. Both are swept here over a WIDER hostile matrix
   than the views lane's parametrize - non-finite decimals, over-range integers, the Unicode
   superscript ``isdigit()`` accepts - driven by an ordinary member, and every refusal is paired
   with "and the row did not move" (L35: an absent or unparseable prerequisite is REJECTED, never
   allowed to fall through into the write).
5. **CSRF** - ``Client(enforce_csrf_checks=True)`` over all thirteen POST verbs plus the four
   create/edit POSTs. ``force_login`` authenticates the session and supplies no token, which is
   exactly the shape of a cross-site POST from a page the workspace does not control.
6. **Mass assignment through the wire.** Extra fields posted at the edit views must not bind:
   ``status``, ``outcome``, ``score``, ``band``, ``weight_applied``, the frozen ``*_at_time`` /
   ``kpi_*`` columns, ``verified_by`` / ``verified_at``, ``acknowledged_at``, ``submitted_at``,
   ``tenant`` and ``number``; and ``manual_override`` - the one-way door - cannot be flipped by a
   body posted at Generate. The sharpest one is ``supplierkpiscore_edit``: a **derived** line is
   refused by the VIEW before any form work, so the two-field form is not what holds that
   boundary.
7. **XSS / escaping** - a reflected ``?q=<script>`` on all five registers, and stored markup in
   the free-text fields of four detail pages (including a ``breakdown`` JSON value, which the
   score page flattens through ``_breakdown_value``). Apostrophes are asserted too, because
   ``confirm()`` handlers live on these pages (L42).

House rules: every reference date derives from ``timezone.localdate()`` / ``timezone.now()`` and
never ``date.today()`` (L16); every URL goes through ``reverse("procurement:<name>")``; the
multi-route sweeps use ``Client(raise_request_exception=False)`` so one 500 collects into the
failure list with its url name attached instead of aborting the pass.

Every test is ``test_supplierperf_*`` and every module-level helper ``_supplierperf_sec_*`` so
the three sibling 6.16 lanes, and any later sub-module appending nearby, cannot shadow anything
here (L41 S2 / L47).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.procurement.models import (SupplierFeedback, SupplierImprovementPlan, SupplierKpi,
                                     SupplierKpiScore)

pytestmark = pytest.mark.django_db


# =================================================================================================
# module-level helpers - every name _supplierperf_sec_* so no sibling lane can shadow one (L47)
# =================================================================================================

def _supplierperf_sec_day(offset=0):
    """A date on the SAME basis the views use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _supplierperf_sec_html(response):
    return response.content.decode()


def _supplierperf_sec_notes(response):
    """Every flash message on the request - works on a 302 too, the storage hangs off the
    request rather than off the (absent) context."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _supplierperf_sec_sweep_client(user):
    """A client that RETURNS a 500 instead of re-raising it.

    Used for every multi-route sweep so one broken route collects into the failure list with its
    url name attached, rather than aborting the pass and hiding every route behind it.
    """
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


def _supplierperf_sec_login(user):
    client = Client()
    client.force_login(user)
    return client


def _supplierperf_sec_snapshot(obj, *fields):
    """``{field: value}`` re-read from the database - the "unchanged" baseline."""
    obj.refresh_from_db()
    return {name: getattr(obj, name) for name in fields}


def _supplierperf_sec_assert_unchanged(obj, before):
    """Re-read ``obj`` and assert every snapshotted column is still exactly what it was."""
    obj.refresh_from_db()
    for name, value in before.items():
        assert getattr(obj, name) == value, (
            f"{obj.__class__.__name__}.{name} changed on a refused request: "
            f"{value!r} -> {getattr(obj, name)!r}")


def _supplierperf_sec_sweep(client, cases, expected=404):
    """Drive every ``(url_name, args, method, data)`` case and collect the mismatches.

    Returns ``[(url_name, status_code), ...]`` for every case whose status was not ``expected``,
    so one failure names every offending route at once instead of one per re-run.
    """
    failures = []
    for url_name, args, method, data in cases:
        url = reverse(f"procurement:{url_name}", args=args)
        response = (client.post(url, data or {}) if method == "post" else client.get(url))
        if response.status_code != expected:
            failures.append((url_name, response.status_code))
    return failures


# -- rows the shared conftest does not mint ------------------------------------------------------
#
# The 27 ``supplierperf_*`` fixtures next door cover every shape this lane needs EXCEPT the ones a
# refusal test consumes destructively (every verb is one-shot, so the member-reachability sweep
# needs a fresh row per verb) and the two states no fixture holds (a ``cancelled`` plan, and a
# scorecard on a period tenant A has never scored). Those are built here rather than appended to a
# conftest shared with 57 sibling modules and three concurrent peer sessions.

def _supplierperf_sec_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole - every 6.16 supplier picker narrows on
    ``roles__role__in=("supplier", "vendor")``, so a bare Party is invisible to all of them."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _supplierperf_sec_scorecard(tenant, party, **overrides):
    from apps.scm.models import SupplierScorecard
    fields = dict(tenant=tenant, party=party, period_start=_supplierperf_sec_day(-89),
                  period_end=_supplierperf_sec_day(), status="draft")
    fields.update(overrides)
    return SupplierScorecard.objects.create(**fields)


def _supplierperf_sec_kpi(tenant, code, **overrides):
    """A VALID KPI definition - the band triple is already ordered for ``higher_is_better``."""
    fields = dict(tenant=tenant, code=code, name=f"KPI {code}", category="delivery", unit="pct",
                  direction="higher_is_better", source="manual", derived_metric="", weight=10,
                  target_value=Decimal("95"), warning_threshold=Decimal("90"),
                  critical_threshold=Decimal("85"), scoring_method="band",
                  maps_to_dimension="delivery", applies_to="all", review_frequency="quarterly",
                  display_order=10, is_active=True)
    fields.update(overrides)
    return SupplierKpi.objects.create(**fields)


def _supplierperf_sec_score(tenant, scorecard, kpi, **overrides):
    """A score line with EVERY frozen column filled from the KPI - a line left at its defaults
    makes every frozen-history assertion pass vacuously."""
    fields = dict(tenant=tenant, scorecard=scorecard, kpi=kpi,
                  measured_value=Decimal("92.0000"), score=Decimal("70.00"), band="warning",
                  weight_applied=kpi.weight, target_at_time=kpi.target_value,
                  direction_at_time=kpi.direction, source_at_time=kpi.source,
                  unit_at_time=kpi.unit, kpi_name=kpi.name, kpi_category=kpi.category,
                  breakdown={"source": "fixture"}, respondent_count=0, comment="")
    fields.update(overrides)
    return SupplierKpiScore.objects.create(**fields)


def _supplierperf_sec_feedback(tenant, supplier, **overrides):
    fields = dict(tenant=tenant, supplier=supplier, period_start=_supplierperf_sec_day(-89),
                  period_end=_supplierperf_sec_day(), respondent_kind="internal",
                  respondent_function="procurement", importance=5, status="requested")
    fields.update(overrides)
    return SupplierFeedback.objects.create(**fields)


def _supplierperf_sec_plan(tenant, supplier, **overrides):
    fields = dict(tenant=tenant, supplier=supplier, title="Late deliveries", severity="major",
                  finding="Four of six shipments arrived late.",
                  start_date=_supplierperf_sec_day(),
                  target_close_date=_supplierperf_sec_day(30), status="draft")
    fields.update(overrides)
    return SupplierImprovementPlan.objects.create(**fields)


# -- POST payload builders -----------------------------------------------------------------------
#
# Each one is a payload the form ACCEPTS, so what a refusal test proves is the guard under test
# and not a validation error that would have refused an administrator too.

def _supplierperf_sec_kpi_payload(code="SEC-01", **overrides):
    payload = {
        "code": code, "name": "Crafted KPI", "description": "", "category": "delivery",
        "unit": "pct", "direction": "higher_is_better", "source": "manual",
        "derived_metric": "", "weight": "10", "target_value": "95",
        "warning_threshold": "90", "critical_threshold": "85", "scoring_method": "band",
        "maps_to_dimension": "delivery", "applies_to": "all", "applies_to_tier": "",
        "review_frequency": "quarterly", "industry_benchmark_value": "", "owner": "",
        "display_order": "10", "is_active": "on", "notes": ""}
    payload.update(overrides)
    return payload


def _supplierperf_sec_score_payload(**overrides):
    payload = {"measured_value": "91.5000", "comment": "Corrected from the paper return."}
    payload.update(overrides)
    return payload


def _supplierperf_sec_feedback_payload(supplier_pk, **overrides):
    payload = {
        "supplier": str(supplier_pk), "scorecard": "", "kpi": "",
        "period_start": _supplierperf_sec_day(-30).isoformat(),
        "period_end": _supplierperf_sec_day().isoformat(), "respondent_kind": "internal",
        "respondent_function": "operations", "respondent": "", "respondent_name": "R. Iqbal",
        "rating": "", "importance": "6", "due_date": _supplierperf_sec_day(14).isoformat(),
        "comment": ""}
    payload.update(overrides)
    return payload


def _supplierperf_sec_plan_payload(supplier_pk, **overrides):
    payload = {
        "title": "Crafted plan", "supplier": str(supplier_pk), "scorecard": "", "kpi": "",
        "severity": "minor", "finding": "Two short shipments.", "root_cause": "",
        "corrective_actions": "", "support_provided": "", "success_criteria": "",
        "start_date": _supplierperf_sec_day().isoformat(),
        "target_close_date": _supplierperf_sec_day(45).isoformat(), "next_review_date": "",
        "extended_close_date": "", "owner": "", "supplier_owner_name": "",
        "supplier_owner_email": "", "escalated_suspension": "", "evidence_url": ""}
    payload.update(overrides)
    return payload


# ============================================================== 1. cross-tenant IDOR
#
# Logged in as tenant A's administrator, every ``<int:pk>`` route in 6.16 pointed at a tenant-B
# row must return 404 - never 200 (a read across the boundary) and never 500 (a guard that
# crashed instead of refusing). The sweeps use ``raise_request_exception=False`` so a 500 is
# collected with its url name rather than aborting the pass, and every sweep is followed by a
# before/after snapshot: a 404 that still mutated is the bug the status code cannot see.
#
# The board vectors are section 1's sharp edge and live at the end: party names collide across
# workspaces BY DESIGN (both tenants may have a "Northwind"), so a board asserted on rendered
# text would pass while leaking. Every board assertion here reads CONTEXT.

def test_supplierperf_foreign_kpi_pk_is_404_on_every_route(
        admin_user, tenant_b, supplierperf_kpi_b):
    """All four KPI routes refuse tenant B's definition, and it survives byte-identical.

    ``supplierperf_kpi_b`` deliberately carries the SAME ``code`` as tenant A's own MAN-01 - the
    ``unique_together ("tenant", "code")`` case - so a view that resolved a KPI by code, or that
    forgot the tenant on the pk lookup, would hand back a plausible-looking row rather than an
    obvious one.
    """
    client = _supplierperf_sec_sweep_client(admin_user)
    pk = supplierperf_kpi_b.pk
    before = _supplierperf_sec_snapshot(supplierperf_kpi_b, "name", "code", "weight",
                                        "is_active", "target_value")

    failures = _supplierperf_sec_sweep(client, [
        ("supplierkpi_detail", [pk], "get", None),
        ("supplierkpi_edit", [pk], "get", None),
        ("supplierkpi_edit", [pk], "post", _supplierperf_sec_kpi_payload(code="MAN-01")),
        ("supplierkpi_delete", [pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant KPI routes did not 404: {failures}"
    assert SupplierKpi.objects.filter(pk=pk, tenant=tenant_b).exists()
    _supplierperf_sec_assert_unchanged(supplierperf_kpi_b, before)


def test_supplierperf_foreign_scorecard_pk_is_404_on_the_evaluation_routes(
        admin_user, tenant_b, supplierperf_scorecard_b, supplierperf_kpi_b):
    """The evaluation register's two pk routes refuse tenant B's period document.

    ``supplierevaluation_generate`` is the one that matters: it is the module's ONE-WAY DOOR, so
    a cross-tenant hit would not just read another workspace's scorecard, it would permanently
    hand it to Procurement and set ``manual_override`` on it. The POST is driven by a tenant
    ADMINISTRATOR precisely so ``@tenant_admin_required`` passes and the tenant scope of the pk
    lookup is what is under test.
    """
    client = _supplierperf_sec_sweep_client(admin_user)
    pk = supplierperf_scorecard_b.pk
    before = _supplierperf_sec_snapshot(supplierperf_scorecard_b, "status", "manual_override",
                                        "overall_score", "delivery_score", "grade")

    failures = _supplierperf_sec_sweep(client, [
        ("supplierevaluation_detail", [pk], "get", None),
        ("supplierevaluation_generate", [pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant evaluation routes did not 404: {failures}"
    _supplierperf_sec_assert_unchanged(supplierperf_scorecard_b, before)
    assert supplierperf_scorecard_b.manual_override is False
    assert SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_b).count() == 0


def test_supplierperf_foreign_score_pk_is_404_on_every_route(
        admin_user, tenant_b, supplierperf_score_b):
    """All four score-line routes refuse tenant B's measured line, and the figure survives."""
    client = _supplierperf_sec_sweep_client(admin_user)
    pk = supplierperf_score_b.pk
    before = _supplierperf_sec_snapshot(supplierperf_score_b, "measured_value", "score", "band",
                                        "comment", "weight_applied", "source_at_time")

    failures = _supplierperf_sec_sweep(client, [
        ("supplierkpiscore_detail", [pk], "get", None),
        ("supplierkpiscore_edit", [pk], "get", None),
        ("supplierkpiscore_edit", [pk], "post", _supplierperf_sec_score_payload()),
        ("supplierkpiscore_delete", [pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant score routes did not 404: {failures}"
    assert SupplierKpiScore.objects.filter(pk=pk, tenant=tenant_b).exists()
    _supplierperf_sec_assert_unchanged(supplierperf_score_b, before)


def test_supplierperf_foreign_feedback_pk_is_404_on_every_route(
        admin_user, tenant_b, supplierperf_feedback_b, supplierperf_supplier_b):
    """All seven response routes refuse tenant B's 360 answer.

    The three lifecycle verbs are POSTed with a real rating so the refusal under test is the
    tenant guard and not the "pick a rating" one that would have refused anybody.
    """
    client = _supplierperf_sec_sweep_client(admin_user)
    pk = supplierperf_feedback_b.pk
    before = _supplierperf_sec_snapshot(supplierperf_feedback_b, "status", "rating",
                                        "submitted_at", "importance", "comment")

    failures = _supplierperf_sec_sweep(client, [
        ("supplierfeedback_detail", [pk], "get", None),
        ("supplierfeedback_edit", [pk], "get", None),
        ("supplierfeedback_edit", [pk], "post",
         _supplierperf_sec_feedback_payload(supplierperf_supplier_b.pk)),
        ("supplierfeedback_submit", [pk], "post", {"rating": "5"}),
        ("supplierfeedback_decline", [pk], "post", {}),
        ("supplierfeedback_expire", [pk], "post", {}),
        ("supplierfeedback_delete", [pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant feedback routes did not 404: {failures}"
    assert SupplierFeedback.objects.filter(pk=pk, tenant=tenant_b).exists()
    _supplierperf_sec_assert_unchanged(supplierperf_feedback_b, before)


def test_supplierperf_foreign_plan_pk_is_404_on_every_route(
        admin_user, tenant_b, supplierperf_plan_b, supplierperf_supplier_b):
    """All ten plan routes refuse tenant B's PIP, **including ``improvementplan_evidence``**.

    The evidence download is the route the ``urls`` docstring's "33 routes" count still misses:
    it was added by the I5 fix (a raw ``MEDIA_URL`` link hands an NCR pack to anybody who can
    guess a filename), and an authenticated download view that forgot its tenant scope would
    hand tenant B's attachment straight to tenant A. It is ``@login_required`` and scoped by
    ``get_object_or_404(..., tenant=request.tenant)``; this is that scope, driven over HTTP.

    ``improvementplan_close`` is POSTed by an ADMINISTRATOR so ``@tenant_admin_required`` passes
    and the pk's tenant scope is what refuses, with a real ``outcome`` so the outcome guard is
    not what answers either.
    """
    client = _supplierperf_sec_sweep_client(admin_user)
    pk = supplierperf_plan_b.pk
    before = _supplierperf_sec_snapshot(
        supplierperf_plan_b, "status", "outcome", "title", "finding", "acknowledged_at",
        "verified_at", "verified_by_id", "actual_close_date", "closure_note")

    failures = _supplierperf_sec_sweep(client, [
        ("improvementplan_detail", [pk], "get", None),
        ("improvementplan_edit", [pk], "get", None),
        ("improvementplan_edit", [pk], "post",
         _supplierperf_sec_plan_payload(supplierperf_supplier_b.pk)),
        ("improvementplan_evidence", [pk], "get", None),
        ("improvementplan_activate", [pk], "post", {}),
        ("improvementplan_monitor", [pk], "post", {}),
        ("improvementplan_acknowledge", [pk], "post", {}),
        ("improvementplan_close", [pk], "post", {"outcome": "successful",
                                                 "closure_note": "Signed elsewhere."}),
        ("improvementplan_cancel", [pk], "post", {}),
        ("improvementplan_delete", [pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant plan routes did not 404: {failures}"
    assert SupplierImprovementPlan.objects.filter(pk=pk, tenant=tenant_b).exists()
    _supplierperf_sec_assert_unchanged(supplierperf_plan_b, before)


def test_supplierperf_foreign_plan_evidence_download_hands_back_no_bytes(
        admin_user, supplierperf_plan_b, settings, tmp_path):
    """The evidence route with a REAL file behind it - 404, and not one byte of it.

    The sweep above 404s on a plan with no upload, which a view that resolved the row correctly
    and then fell into the "no evidence" branch would also do. This one puts an actual file on
    tenant B's plan first, so the only way to a 404 is refusing the ROW.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    supplierperf_plan_b.evidence.save("globex-ncr.pdf", ContentFile(b"%PDF-1.4 globex secret"),
                                      save=True)
    client = _supplierperf_sec_sweep_client(admin_user)

    response = client.get(reverse("procurement:improvementplan_evidence",
                                  args=[supplierperf_plan_b.pk]))

    assert response.status_code == 404
    assert b"globex secret" not in response.content
    assert "Content-Disposition" not in response


def test_supplierperf_no_register_ever_contains_the_other_workspaces_rows(
        client_a, supplierperf_kpi_manual_a, supplierperf_kpi_b, supplierperf_scorecard_draft_a,
        supplierperf_scorecard_b, supplierperf_score_manual_a, supplierperf_score_b,
        supplierperf_feedback_requested_a, supplierperf_feedback_b, supplierperf_plan_draft_a,
        supplierperf_plan_b):
    """Each of the five registers holds tenant A's row and NOT tenant B's.

    Asserted on ``object_list`` primary keys rather than on rendered text: the two workspaces'
    rows carry colliding codes (both own "MAN-01") and colliding numbers, so a substring test
    against the HTML would be satisfied by the wrong row.
    """
    expected = {
        "supplierkpi_list": (supplierperf_kpi_manual_a.pk, supplierperf_kpi_b.pk),
        "supplierevaluation_list": (supplierperf_scorecard_draft_a.pk,
                                    supplierperf_scorecard_b.pk),
        "supplierkpiscore_list": (supplierperf_score_manual_a.pk, supplierperf_score_b.pk),
        "supplierfeedback_list": (supplierperf_feedback_requested_a.pk,
                                  supplierperf_feedback_b.pk),
        "improvementplan_list": (supplierperf_plan_draft_a.pk, supplierperf_plan_b.pk),
    }

    for url_name, (mine, theirs) in expected.items():
        response = client_a.get(reverse(f"procurement:{url_name}"))
        assert response.status_code == 200, url_name
        pks = [obj.pk for obj in response.context["object_list"]]
        assert mine in pks, f"{url_name} lost its own workspace's row"
        assert theirs not in pks, f"{url_name} leaked a tenant-B row"


def test_supplierperf_score_register_foreign_scorecard_filter_returns_zero_rows(
        client_a, supplierperf_score_manual_a, supplierperf_score_b, supplierperf_scorecard_b):
    """``scores/?scorecard=<B pk>`` is a legal integer that must simply match nothing.

    ``crud_list`` parses it (it IS a plausible pk) and applies it to a queryset already narrowed
    to ``tenant=request.tenant`` - so the correct answer is an honestly empty register, not a
    fallback to the unfiltered one. The pair below is what tells those two apart: the same
    register filtered by tenant A's OWN scorecard still returns its row.
    """
    url = reverse("procurement:supplierkpiscore_list")

    foreign = client_a.get(url, {"scorecard": str(supplierperf_scorecard_b.pk)})
    assert foreign.status_code == 200
    assert [obj.pk for obj in foreign.context["object_list"]] == []

    own = client_a.get(url, {"scorecard": str(supplierperf_score_manual_a.scorecard_id)})
    assert [obj.pk for obj in own.context["object_list"]] == [supplierperf_score_manual_a.pk]


def test_supplierperf_feedback_register_foreign_supplier_filter_returns_zero_rows(
        client_a, supplierperf_feedback_requested_a, supplierperf_feedback_b,
        supplierperf_supplier_a, supplierperf_supplier_b):
    """``feedback/?supplier=<B party>`` matches nothing, while A's own supplier still matches."""
    url = reverse("procurement:supplierfeedback_list")

    foreign = client_a.get(url, {"supplier": str(supplierperf_supplier_b.pk)})
    assert foreign.status_code == 200
    assert [obj.pk for obj in foreign.context["object_list"]] == []

    own = client_a.get(url, {"supplier": str(supplierperf_supplier_a.pk)})
    assert supplierperf_feedback_requested_a.pk in [obj.pk for obj in own.context["object_list"]]


def test_supplierperf_plan_register_foreign_owner_and_kpi_filters_return_zero_rows(
        client_a, supplierperf_plan_draft_a, supplierperf_plan_b, supplierperf_kpi_b, admin_b):
    """The PIP register's two other FK filters, aimed across the boundary.

    ``?owner=<B admin>`` and ``?kpi=<B KPI>`` are both valid integers pointing at rows tenant A
    may not see. Neither may return tenant B's plan, and neither may 500.
    """
    url = reverse("procurement:improvementplan_list")

    for params in ({"owner": str(admin_b.pk)}, {"kpi": str(supplierperf_kpi_b.pk)}):
        response = client_a.get(url, params)
        assert response.status_code == 200, params
        assert [obj.pk for obj in response.context["object_list"]] == [], params

    unfiltered = client_a.get(url)
    assert [obj.pk for obj in unfiltered.context["object_list"]] == [supplierperf_plan_draft_a.pk]


def test_supplierperf_benchmark_board_foreign_period_renders_an_empty_cohort(
        client_a, tenant_b, supplierperf_supplier_b, supplierperf_supplier_a):
    """``?period=<a period only tenant B has scored>`` - asserted on CONTEXT, not on text.

    Tenant B is given a scorecard on a window tenant A has never scored. The board must honour
    the hand-typed period (a bookmarked filter that finds nothing is honest) and report an empty
    cohort - with ``rows`` empty and every ``cohort`` key present, because a missing key renders
    as the empty string and ships a broken statistic looking like a blank one (L8).
    """
    foreign_end = _supplierperf_sec_day(-200)
    _supplierperf_sec_scorecard(tenant_b, supplierperf_supplier_b, period_end=foreign_end,
                                period_start=foreign_end - datetime.timedelta(days=89))

    response = client_a.get(reverse("procurement:supplier_benchmark_board"),
                            {"period": foreign_end.isoformat()})

    assert response.status_code == 200
    assert response.context["selected_period"] == foreign_end
    assert list(response.context["rows"]) == []
    cohort = response.context["cohort"]
    assert cohort["count"] == 0 and cohort["scored"] == 0
    assert cohort["average"] is None and cohort["best"] is None and cohort["worst"] is None


def test_supplierperf_benchmark_board_never_ranks_a_foreign_scorecard(
        client_a, tenant_a, tenant_b, supplierperf_supplier_a, supplierperf_supplier_b,
        supplierperf_kpi_manual_a):
    """Both workspaces scored on the SAME period; tenant A's cohort carries only A's card.

    This is the vector rendered text cannot see. Tenant B's supplier is named identically to
    tenant A's on purpose - two workspaces may legitimately trade with the same company, and the
    ``Party`` rows are separate - so the assertion is on ``rows[*]["scorecard_id"]``, the one
    value that is unambiguously one workspace's or the other's.
    """
    from apps.scm.models import SupplierScorecard

    twin = _supplierperf_sec_party(tenant_b, supplierperf_supplier_a.name)
    kpi_b = _supplierperf_sec_kpi(tenant_b, "MAN-01")
    card_a = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a)
    card_b = _supplierperf_sec_scorecard(tenant_b, twin)
    _supplierperf_sec_score(tenant_a, card_a, supplierperf_kpi_manual_a, score=Decimal("80.00"))
    _supplierperf_sec_score(tenant_b, card_b, kpi_b, score=Decimal("10.00"))
    assert SupplierScorecard.objects.filter(period_end=card_a.period_end).count() == 2

    response = client_a.get(reverse("procurement:supplier_benchmark_board"),
                            {"period": card_a.period_end.isoformat()})

    assert response.status_code == 200
    scorecard_ids = [row["scorecard_id"] for row in response.context["rows"]]
    assert card_a.pk in scorecard_ids, "the board lost tenant A's own scorecard"
    assert card_b.pk not in scorecard_ids, "the benchmark board ranked a tenant-B scorecard"
    assert response.context["cohort"]["count"] == 1


def test_supplierperf_trend_board_foreign_supplier_leaves_the_selection_empty(
        client_a, tenant_b, supplierperf_supplier_b, supplierperf_kpi_b):
    """``trend/?supplier=<B party>&kpi=<B KPI>`` selects neither and plots nothing.

    ``selected_supplier`` is resolved off the tenant-scoped picker queryset, so a foreign pk
    resolves to ``None`` and the compute layer is never reached. Asserted on the context because
    the page renders the supplier's NAME, which may legitimately exist in both workspaces.
    """
    card = _supplierperf_sec_scorecard(tenant_b, supplierperf_supplier_b)
    _supplierperf_sec_score(tenant_b, card, supplierperf_kpi_b, score=Decimal("99.00"))

    response = client_a.get(reverse("procurement:supplier_trend_board"),
                            {"supplier": str(supplierperf_supplier_b.pk),
                             "kpi": str(supplierperf_kpi_b.pk)})

    assert response.status_code == 200
    assert response.context["selected_supplier"] is None
    assert response.context["selected_kpi"] is None
    assert list(response.context["series"]) == []
    assert list(response.context["kpi_series"]) == []
    assert supplierperf_supplier_b not in list(response.context["suppliers"])


def test_supplierperf_perception_gap_foreign_supplier_offers_no_window_and_no_rows(
        client_a, tenant_b, supplierperf_supplier_b, supplierperf_feedback_b):
    """``perception-gap/?supplier=<B party>`` selects nobody, so it can compare nothing.

    ``_feedback_windows`` reads the SUBMITTED responses of the request's own tenant, so tenant
    B's submitted answer must not become a selectable window on tenant A's board either - the
    period picker is itself a disclosure surface.
    """
    response = client_a.get(reverse("procurement:supplier_perception_gap"),
                            {"supplier": str(supplierperf_supplier_b.pk),
                             "period": supplierperf_feedback_b.period_end.isoformat()})

    assert response.status_code == 200
    assert response.context["selected_supplier"] is None
    assert list(response.context["gap_rows"]) == []
    assert list(response.context["periods"]) == []


def test_supplierperf_plan_create_rejects_a_crafted_foreign_supplier_over_http(
        client_a, tenant_a, supplierperf_supplier_b, supplierperf_scorecard_b):
    """A crafted POST naming tenant B's party and scorecard is a FIELD ERROR, not a row.

    The narrowed ``<select>`` is UX; the boundary is ``_reject_foreign`` in the form's ``clean``
    plus the model's own same-tenant guards. Driven over HTTP here because that is the shape an
    attacker actually sends - a hand-edited form body, never the rendered dropdown.
    """
    response = client_a.post(reverse("procurement:improvementplan_create"),
                             _supplierperf_sec_plan_payload(
                                 supplierperf_supplier_b.pk,
                                 scorecard=str(supplierperf_scorecard_b.pk),
                                 title="Crafted across the boundary"))

    assert response.status_code == 200, "a crafted cross-tenant FK was accepted and redirected"
    form = response.context["form"]
    assert "supplier" in form.errors
    assert "scorecard" in form.errors
    assert not SupplierImprovementPlan.objects.filter(
        title="Crafted across the boundary").exists()


def test_supplierperf_feedback_create_rejects_a_crafted_foreign_supplier_over_http(
        client_a, tenant_a, supplierperf_supplier_b, supplierperf_kpi_b, admin_b):
    """The hand-rolled create view refuses tenant B's party, KPI and respondent alike.

    ``supplierfeedback_create`` does not go through ``crud_create`` (it stamps ``requested_by``
    from the session), so its cross-tenant guard is the form's and has to be asserted through
    this view specifically rather than inherited from the shared helper's coverage.
    """
    response = client_a.post(reverse("procurement:supplierfeedback_create"),
                             _supplierperf_sec_feedback_payload(
                                 supplierperf_supplier_b.pk,
                                 kpi=str(supplierperf_kpi_b.pk),
                                 respondent=str(admin_b.pk),
                                 respondent_name="Crafted respondent"))

    assert response.status_code == 200
    form = response.context["form"]
    assert "supplier" in form.errors
    assert not SupplierFeedback.objects.filter(respondent_name="Crafted respondent").exists()


def test_supplierperf_kpi_edit_rejects_a_crafted_foreign_owner_over_http(
        client_a, supplierperf_kpi_manual_a, admin_b):
    """``owner`` is the KPI form's one tenant-scoped choice, and it refuses tenant B's user."""
    before = _supplierperf_sec_snapshot(supplierperf_kpi_manual_a, "owner_id", "name")

    response = client_a.post(
        reverse("procurement:supplierkpi_edit", args=[supplierperf_kpi_manual_a.pk]),
        _supplierperf_sec_kpi_payload(code=supplierperf_kpi_manual_a.code,
                                      name="Renamed by the crafted post",
                                      owner=str(admin_b.pk)))

    assert response.status_code == 200
    assert "owner" in response.context["form"].errors
    _supplierperf_sec_assert_unchanged(supplierperf_kpi_manual_a, before)


# ============================================================== 2. the authorization matrix
#
# 34 routes x 3 principals. The route table below is the lane's single source of truth and is
# checked against the LIVE URLconf by the first test, so a 35th route added next week fails here
# rather than shipping with no permission coverage at all - which is exactly how
# ``improvementplan_evidence`` (route 34, added by the I5 fix) ended up outside a "33 routes"
# docstring.
#
# Three kinds:
#   "read"  - @login_required, GET, 200 for any member of the workspace.
#   "verb"  - @login_required over @require_POST: POST, and an ordinary member MAY use it.
#   "admin" - @require_POST over @tenant_admin_required: POST, 403 for a member.
#
# The ORDER of those last two decorator stacks is behaviour, not decoration. On an "admin" route
# ``@require_POST`` is OUTER, so a GET is 405 BEFORE authentication runs at all - anonymous
# included. The anonymous sweep therefore POSTs to the two admin routes and GETs everything else;
# a GET there would assert 405 and prove nothing about authentication.

_SUPPLIERPERF_SEC_READS = (
    ("supplierkpi_list", ()),
    ("supplierkpi_create", ()),
    ("supplierkpi_detail", ("kpi",)),
    ("supplierkpi_edit", ("kpi",)),
    ("supplierevaluation_list", ()),
    ("supplierevaluation_detail", ("scorecard",)),
    ("supplierkpiscore_list", ()),
    ("supplierkpiscore_detail", ("score",)),
    ("supplierkpiscore_edit", ("score",)),
    ("supplierfeedback_list", ()),
    ("supplierfeedback_create", ()),
    ("supplierfeedback_detail", ("feedback",)),
    ("supplierfeedback_edit", ("feedback",)),
    ("improvementplan_list", ()),
    ("improvementplan_create", ()),
    ("improvementplan_detail", ("plan",)),
    ("improvementplan_edit", ("plan",)),
    ("improvementplan_evidence", ("plan",)),
    ("supplier_benchmark_board", ()),
    ("supplier_trend_board", ()),
    ("supplier_perception_gap", ()),
)

_SUPPLIERPERF_SEC_VERBS = (
    ("supplierkpi_delete", ("kpi",), {}),
    ("supplierkpiscore_delete", ("score",), {}),
    ("supplierfeedback_submit", ("feedback",), {"rating": "4"}),
    ("supplierfeedback_decline", ("feedback",), {}),
    ("supplierfeedback_expire", ("feedback",), {}),
    ("supplierfeedback_delete", ("feedback",), {}),
    ("improvementplan_activate", ("plan",), {}),
    ("improvementplan_monitor", ("plan",), {}),
    ("improvementplan_acknowledge", ("plan",), {}),
    ("improvementplan_cancel", ("plan",), {}),
    ("improvementplan_delete", ("plan",), {}),
)

_SUPPLIERPERF_SEC_ADMIN_VERBS = (
    ("supplierevaluation_generate", ("scorecard",), {}),
    ("improvementplan_close", ("plan",), {"outcome": "successful",
                                          "closure_note": "Signed off."}),
)


def _supplierperf_sec_declared_route_names():
    """Every url NAME the 6.16 URL package actually declares, read off the live patterns."""
    from apps.procurement.urls.SupplierPerformanceEvaluation import urlpatterns
    return [pattern.name for pattern in urlpatterns]


def _supplierperf_sec_cases(pks, kinds=("read", "verb", "admin")):
    """The route table as ``(url_name, args, method, data)`` tuples, resolved against ``pks``.

    ``pks`` maps the four slot names the table uses (``kpi`` / ``scorecard`` / ``score`` /
    ``feedback`` / ``plan``) onto real primary keys, so one table drives the anonymous sweep, the
    member sweep and the CSRF sweep without any of them re-listing 34 routes.
    """
    cases = []
    if "read" in kinds:
        cases += [(name, [pks[slot] for slot in slots], "get", None)
                  for name, slots in _SUPPLIERPERF_SEC_READS]
    if "verb" in kinds:
        cases += [(name, [pks[slot] for slot in slots], "post", data)
                  for name, slots, data in _SUPPLIERPERF_SEC_VERBS]
    if "admin" in kinds:
        cases += [(name, [pks[slot] for slot in slots], "post", data)
                  for name, slots, data in _SUPPLIERPERF_SEC_ADMIN_VERBS]
    return cases


def test_supplierperf_the_route_table_covers_every_declared_route():
    """The lane's route table and the URLconf agree - **34 routes, not the docstring's 33**.

    ``apps/procurement/urls/SupplierPerformanceEvaluation/__init__.py`` still says 33; the I5
    security fix added ``improvementplan_evidence`` and the count was never updated. That is a
    documentation defect rather than a code one, but the reason it matters is exactly what this
    test prevents: a route nobody counted is a route nobody swept for permissions.
    """
    declared = _supplierperf_sec_declared_route_names()
    covered = {name for name, _slots in _SUPPLIERPERF_SEC_READS}
    covered |= {name for name, _slots, _data in _SUPPLIERPERF_SEC_VERBS}
    covered |= {name for name, _slots, _data in _SUPPLIERPERF_SEC_ADMIN_VERBS}

    assert len(declared) == 34, f"6.16 declares {len(declared)} routes, not 34: {declared}"
    assert len(set(declared)) == 34, "two 6.16 routes share a url name"
    assert covered == set(declared), (
        f"routes with no permission coverage: {sorted(set(declared) - covered)}; "
        f"table entries that do not exist: {sorted(covered - set(declared))}")


def _supplierperf_sec_matrix_rows(tenant, supplier, admin):
    """One row per entity for the permission sweeps, in the state each sweep needs.

    The score line is MANUAL (``supplierkpiscore_edit`` refuses anything else before it renders),
    the response is REQUESTED and the plan is a DRAFT with an evidence file on it - so every
    "read" route in the table answers 200 for a user who is allowed to see it, and a refusal in
    the sweep is a permission refusal rather than a status gate.
    """
    kpi = _supplierperf_sec_kpi(tenant, "MTX-01", owner=admin)
    card = _supplierperf_sec_scorecard(tenant, supplier)
    score = _supplierperf_sec_score(tenant, card, kpi)
    feedback = _supplierperf_sec_feedback(tenant, supplier, respondent_name="Matrix respondent",
                                          rating=3)
    plan = _supplierperf_sec_plan(tenant, supplier, title="Matrix plan", owner=admin)
    plan.evidence.save("matrix-evidence.pdf", ContentFile(b"%PDF-1.4 matrix"), save=True)
    return {"kpi": kpi.pk, "scorecard": card.pk, "score": score.pk,
            "feedback": feedback.pk, "plan": plan.pk}


def test_supplierperf_anonymous_is_redirected_to_login_on_every_route(
        tenant_a, admin_user, supplierperf_supplier_a, settings, tmp_path):
    """Not one of the 34 routes answers an anonymous caller.

    The two admin verbs are POSTed rather than GET: ``@require_POST`` sits OUTSIDE
    ``@tenant_admin_required`` on both, so a GET is 405 before any authentication happens and a
    login-redirect assertion there would be testing the method guard by accident. The next test
    pins that 405 explicitly, so the pair covers both halves of the decorator stack.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    pks = _supplierperf_sec_matrix_rows(tenant_a, supplierperf_supplier_a, admin_user)
    client = Client(raise_request_exception=False)

    failures = []
    for url_name, args, method, data in _supplierperf_sec_cases(pks):
        url = reverse(f"procurement:{url_name}", args=args)
        response = client.post(url, data or {}) if method == "post" else client.get(url)
        if response.status_code != 302 or "/login" not in response.get("Location", ""):
            failures.append((url_name, response.status_code, response.get("Location", "")))

    assert failures == [], f"routes that answered an anonymous caller: {failures}"
    # ...and nothing an anonymous POST touched actually moved.
    assert SupplierKpi.objects.filter(pk=pks["kpi"]).exists()
    assert SupplierKpiScore.objects.filter(pk=pks["score"]).exists()
    assert SupplierFeedback.objects.get(pk=pks["feedback"]).status == "requested"
    plan = SupplierImprovementPlan.objects.get(pk=pks["plan"])
    assert plan.status == "draft" and plan.acknowledged_at is None and plan.verified_by_id is None


def test_supplierperf_a_get_on_the_two_admin_verbs_is_405_before_any_auth_check(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, settings, tmp_path):
    """``@require_POST`` is the OUTER decorator on Generate and Close - method beats identity.

    All three principals get the same 405 on a GET, the anonymous one included: the method guard
    answers before ``@tenant_admin_required`` (and before the ``@login_required`` inside it) ever
    runs. Worth pinning rather than assuming, because the sibling nine verbs stack the two the
    other way round and DO redirect an anonymous GET to the login page - reading one stack's
    behaviour off the other is how a sweep ends up asserting the wrong mechanism.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    pks = _supplierperf_sec_matrix_rows(tenant_a, supplierperf_supplier_a, admin_user)
    plan_before = _supplierperf_sec_snapshot(
        SupplierImprovementPlan.objects.get(pk=pks["plan"]), "status", "outcome", "verified_at")

    clients = {"anonymous": Client(raise_request_exception=False),
               "member": _supplierperf_sec_sweep_client(member_user),
               "tenant admin": _supplierperf_sec_sweep_client(admin_user)}

    failures = []
    for label, client in clients.items():
        for url_name, slot in (("supplierevaluation_generate", "scorecard"),
                               ("improvementplan_close", "plan")):
            response = client.get(reverse(f"procurement:{url_name}", args=[pks[slot]]))
            if response.status_code != 405:
                failures.append((label, url_name, response.status_code))

    assert failures == [], f"a GET on an admin verb did not return 405: {failures}"
    _supplierperf_sec_assert_unchanged(
        SupplierImprovementPlan.objects.get(pk=pks["plan"]), plan_before)
    assert SupplierKpiScore.objects.filter(scorecard_id=pks["scorecard"]).count() == 1


def test_supplierperf_member_is_refused_on_the_two_admin_verbs_with_no_mutation(
        member_user, tenant_a, supplierperf_supplier_a, supplierperf_kpi_manual_a,
        supplierperf_scorecard_draft_a):
    """403 for an ordinary member on Generate and Close - and nothing moved either time.

    Both are aimed at rows an ADMINISTRATOR could legitimately act on (a draft scorecard with an
    applicable KPI behind it, and an active plan), so the refusal under test is the permission
    gate and not the status gate that would have refused anybody. The views lane already asserts
    the UX half - ``can_generate`` False and ``can_close`` False with the reason printed - and
    this is the half that matters: the server refuses the POST whether or not the button rendered.
    """
    plan = _supplierperf_sec_plan(tenant_a, supplierperf_supplier_a, title="Member cannot close",
                                  status="active")
    plan_before = _supplierperf_sec_snapshot(plan, "status", "outcome", "verified_by_id",
                                             "verified_at", "actual_close_date", "closure_note")
    card_before = _supplierperf_sec_snapshot(supplierperf_scorecard_draft_a, "status",
                                             "manual_override", "delivery_score", "overall_score")
    client = _supplierperf_sec_sweep_client(member_user)

    failures = _supplierperf_sec_sweep(client, [
        ("supplierevaluation_generate", [supplierperf_scorecard_draft_a.pk], "post", {}),
        ("improvementplan_close", [plan.pk], "post", {"outcome": "successful",
                                                      "closure_note": "Closed by a member."}),
    ], expected=403)

    assert failures == [], f"a non-admin reached an admin-gated 6.16 verb: {failures}"
    _supplierperf_sec_assert_unchanged(plan, plan_before)
    _supplierperf_sec_assert_unchanged(supplierperf_scorecard_draft_a, card_before)
    assert supplierperf_scorecard_draft_a.manual_override is False, (
        "a refused Generate still walked through the one-way door")
    assert SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a).count() == 0


def test_supplierperf_member_reaches_every_read_surface_with_a_200(
        member_user, tenant_a, admin_user, supplierperf_supplier_a, settings, tmp_path):
    """L44's positive half: all 21 read routes answer an ordinary member of the workspace.

    Without this pass a module that 403'd everybody would satisfy every refusal test in the file
    while being unusable. ``improvementplan_evidence`` carries a real uploaded file so its 200 is
    the attachment itself rather than the "no evidence" redirect.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    pks = _supplierperf_sec_matrix_rows(tenant_a, supplierperf_supplier_a, admin_user)
    client = _supplierperf_sec_sweep_client(member_user)

    failures = []
    for url_name, args, _method, _data in _supplierperf_sec_cases(pks, kinds=("read",)):
        response = client.get(reverse(f"procurement:{url_name}", args=args))
        if response.status_code != 200:
            failures.append((url_name, response.status_code))
        response.close()

    assert failures == [], f"a member of the workspace was refused a read surface: {failures}"


def test_supplierperf_member_can_drive_all_eleven_login_required_verbs(
        member_user, tenant_a, supplierperf_supplier_a):
    """The eleven ``@login_required`` verbs are NOT administrator-only, and each one lands.

    Every verb is one-shot, so each gets its own freshly minted row in exactly the state the verb
    accepts; the assertion is the state AFTER, not the status code, because a 302 back to the
    detail page is also what a refusal returns. Closing the loop on section 2: a member may do
    all eleven of these and neither of the two above.
    """
    client = _supplierperf_sec_login(member_user)
    card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a)
    kpi_free = _supplierperf_sec_kpi(tenant_a, "VRB-01")
    kpi_scored = _supplierperf_sec_kpi(tenant_a, "VRB-02", display_order=20)
    line = _supplierperf_sec_score(tenant_a, card, kpi_scored)
    responses = {name: _supplierperf_sec_feedback(tenant_a, supplierperf_supplier_a, rating=3,
                                                  respondent_name=f"Verb {name}")
                 for name in ("submit", "decline", "expire", "delete")}
    plans = {name: _supplierperf_sec_plan(tenant_a, supplierperf_supplier_a,
                                          title=f"Verb {name}",
                                          status="active" if name == "monitor" else "draft")
             for name in ("activate", "monitor", "acknowledge", "cancel", "delete")}

    posts = [
        ("supplierkpi_delete", kpi_free.pk, {}),
        ("supplierkpiscore_delete", line.pk, {}),
        ("supplierfeedback_submit", responses["submit"].pk, {"rating": "5"}),
        ("supplierfeedback_decline", responses["decline"].pk, {}),
        ("supplierfeedback_expire", responses["expire"].pk, {}),
        ("supplierfeedback_delete", responses["delete"].pk, {}),
        ("improvementplan_activate", plans["activate"].pk, {}),
        ("improvementplan_monitor", plans["monitor"].pk, {}),
        ("improvementplan_acknowledge", plans["acknowledge"].pk, {}),
        ("improvementplan_cancel", plans["cancel"].pk, {}),
        ("improvementplan_delete", plans["delete"].pk, {}),
    ]
    statuses = {}
    for url_name, pk, data in posts:
        statuses[url_name] = client.post(
            reverse(f"procurement:{url_name}", args=[pk]), data).status_code

    assert set(statuses.values()) == {302}, f"a member verb did not redirect: {statuses}"
    assert not SupplierKpi.objects.filter(pk=kpi_free.pk).exists()
    assert not SupplierKpiScore.objects.filter(pk=line.pk).exists()
    assert SupplierFeedback.objects.get(pk=responses["submit"].pk).status == "submitted"
    assert SupplierFeedback.objects.get(pk=responses["decline"].pk).status == "declined"
    assert SupplierFeedback.objects.get(pk=responses["expire"].pk).status == "expired"
    assert not SupplierFeedback.objects.filter(pk=responses["delete"].pk).exists()
    assert SupplierImprovementPlan.objects.get(pk=plans["activate"].pk).status == "active"
    assert SupplierImprovementPlan.objects.get(pk=plans["monitor"].pk).status == "monitoring"
    assert (SupplierImprovementPlan.objects.get(pk=plans["acknowledge"].pk).acknowledged_at
            is not None)
    assert SupplierImprovementPlan.objects.get(pk=plans["cancel"].pk).status == "cancelled"
    assert not SupplierImprovementPlan.objects.filter(pk=plans["delete"].pk).exists()


def test_supplierperf_member_can_create_and_edit_through_the_four_form_views(
        member_user, tenant_a, supplierperf_supplier_a, supplierperf_score_manual_a,
        supplierperf_plan_draft_a):
    """The create/edit POSTs are member work too - no 6.16 form view is administrator-only.

    The pair to the sweep above: the eleven verbs LAND for a member and so do the writes behind
    the four forms, which is what makes the two 403s in this module a deliberate boundary rather
    than an inconsistency.
    """
    client = _supplierperf_sec_login(member_user)

    created = client.post(reverse("procurement:supplierkpi_create"),
                          _supplierperf_sec_kpi_payload(code="MBR-01", name="Member's KPI"))
    plan_edit = client.post(
        reverse("procurement:improvementplan_edit", args=[supplierperf_plan_draft_a.pk]),
        _supplierperf_sec_plan_payload(supplierperf_supplier_a.pk,
                                       title="Edited by a member"))
    score_edit = client.post(
        reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_manual_a.pk]),
        _supplierperf_sec_score_payload(measured_value="93.0000"))
    feedback_create = client.post(reverse("procurement:supplierfeedback_create"),
                                  _supplierperf_sec_feedback_payload(
                                      supplierperf_supplier_a.pk,
                                      respondent_name="Raised by a member"))

    assert [created.status_code, plan_edit.status_code, score_edit.status_code,
            feedback_create.status_code] == [302, 302, 302, 302]
    assert SupplierKpi.objects.filter(tenant=tenant_a, code="MBR-01").exists()
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.title == "Edited by a member"
    supplierperf_score_manual_a.refresh_from_db()
    assert supplierperf_score_manual_a.measured_value == Decimal("93.0000")
    assert SupplierFeedback.objects.filter(tenant=tenant_a,
                                           respondent_name="Raised by a member").exists()


# ============================================================== 3. the status gates (I3 / I4)
#
# Three gates the security review added, locked here as regressions. Each is driven by an
# ordinary MEMBER, because "any member could do this" is what each finding actually said, and
# each is followed by the record read back unchanged - a redirect that still wrote is the bug.

@pytest.mark.parametrize("card_status", ["published", "archived"])
def test_supplierperf_a_closed_periods_score_line_is_undeletable_by_anyone(
        tenant_a, member_user, admin_user, supplierperf_supplier_a, card_status):
    """**I3.** Writing a score line takes an admin AND a draft; deleting one took neither.

    A member could POST away the measured evidence behind a PUBLISHED grade, leaving the four
    dimension columns and ``overall_score`` standing with nothing under them - the exact
    invariant ``generate_scorecard_lines`` refuses on a published card to protect.

    Both principals are swept, and the ADMINISTRATOR is the important half: the fix is a status
    gate, not a permission gate, so a tenant administrator must be refused too. If this ever
    starts passing for the admin only, the gate has quietly become a permission check.
    """
    card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a, status=card_status)
    kpi = _supplierperf_sec_kpi(tenant_a, f"GATE-{card_status[:3].upper()}")
    line = _supplierperf_sec_score(tenant_a, card, kpi)
    before = _supplierperf_sec_snapshot(line, "measured_value", "score", "band")
    url = reverse("procurement:supplierkpiscore_delete", args=[line.pk])

    for label, user in (("member", member_user), ("tenant admin", admin_user)):
        response = _supplierperf_sec_login(user).post(url)
        assert response.status_code == 302, f"{label} got {response.status_code}"
        assert SupplierKpiScore.objects.filter(pk=line.pk).exists(), (
            f"{label} deleted a score line off a {card_status} scorecard")
        assert any("cannot be deleted" in note
                   for note in _supplierperf_sec_notes(response)), label

    _supplierperf_sec_assert_unchanged(line, before)


def test_supplierperf_a_draft_periods_score_line_is_still_deletable(
        tenant_a, member_user, supplierperf_supplier_a):
    """The L44 pair to the gate above: on a DRAFT period the bin still works, for a member.

    A gate asserted only by its refusals is indistinguishable from a delete route that never
    worked at all.
    """
    card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a)
    line = _supplierperf_sec_score(tenant_a, card, _supplierperf_sec_kpi(tenant_a, "GATE-DRF"))

    response = _supplierperf_sec_login(member_user).post(
        reverse("procurement:supplierkpiscore_delete", args=[line.pk]))

    assert response.status_code == 302
    assert not SupplierKpiScore.objects.filter(pk=line.pk).exists()


@pytest.mark.parametrize("plan_status,outcome", [("closed", "successful"), ("cancelled", "")])
def test_supplierperf_member_cannot_edit_or_delete_a_frozen_plan(
        tenant_a, member_user, supplierperf_supplier_a, plan_status, outcome):
    """**I4, plan half.** A closed plan is SIGNED and a cancelled one is history.

    A closed plan carries ``verified_by`` / ``verified_at`` against its finding, its root cause,
    its corrective actions and its dates - so an editable closed plan let any member rewrite the
    content a signature sits beside, and a deletable one erased the record an escalation stands
    on ("after two failed plans" means nothing once the plans are gone).

    Four requests: the edit form itself, the edit POST, the delete POST, and then the row.
    ``cancelled`` is the case no conftest fixture holds, and it is the one that would have been
    missed - ``OPEN_STATUSES`` excludes both, and a gate written as ``!= "closed"`` would pass
    every closed-plan assertion while leaving cancelled plans wide open.
    """
    plan = _supplierperf_sec_plan(
        tenant_a, supplierperf_supplier_a, title="Frozen plan", status=plan_status,
        outcome=outcome, start_date=_supplierperf_sec_day(-90),
        target_close_date=_supplierperf_sec_day(-30),
        actual_close_date=_supplierperf_sec_day(-32) if plan_status == "closed" else None)
    before = _supplierperf_sec_snapshot(plan, "title", "finding", "status", "outcome",
                                        "target_close_date", "severity")
    client = _supplierperf_sec_login(member_user)

    form_page = client.get(reverse("procurement:improvementplan_edit", args=[plan.pk]))
    edit_post = client.post(reverse("procurement:improvementplan_edit", args=[plan.pk]),
                            _supplierperf_sec_plan_payload(supplierperf_supplier_a.pk,
                                                           title="Rewritten after signing"))
    delete_post = client.post(reverse("procurement:improvementplan_delete", args=[plan.pk]))

    assert form_page.status_code == 302, "the edit form rendered for a frozen plan"
    assert edit_post.status_code == 302
    assert delete_post.status_code == 302
    assert SupplierImprovementPlan.objects.filter(pk=plan.pk).exists()
    _supplierperf_sec_assert_unchanged(plan, before)
    assert any("frozen" in note for note in _supplierperf_sec_notes(edit_post))
    assert any("cannot be deleted" in note for note in _supplierperf_sec_notes(delete_post))


@pytest.mark.parametrize("status", ["submitted", "declined", "expired"])
def test_supplierperf_member_cannot_edit_a_closed_response(
        tenant_a, member_user, supplierperf_supplier_a, status):
    """**I4, response half.** ``rating`` IS on the form, so an editable closed response let any
    member overwrite an answer somebody gave.

    Not being able to move the STATUS was never the point - the payload is not the status. An
    edited rating bypasses the submit verb's own validation and silently moves both the survey
    aggregate and the perception-gap board. All three closed statuses are swept: the gate is
    ``!= "requested"``, and a gate written as ``== "submitted"`` would leave declined and expired
    rows editable while passing the obvious test.
    """
    row = _supplierperf_sec_feedback(
        tenant_a, supplierperf_supplier_a, status=status, rating=2, importance=5,
        respondent_name="Closed respondent",
        submitted_at=timezone.now() if status == "submitted" else None)
    before = _supplierperf_sec_snapshot(row, "status", "rating", "importance",
                                        "respondent_name", "comment")
    client = _supplierperf_sec_login(member_user)

    form_page = client.get(reverse("procurement:supplierfeedback_edit", args=[row.pk]))
    edit_post = client.post(reverse("procurement:supplierfeedback_edit", args=[row.pk]),
                            _supplierperf_sec_feedback_payload(supplierperf_supplier_a.pk,
                                                               rating="5", importance="10"))

    assert form_page.status_code == 302, "the edit form rendered for a closed response"
    assert edit_post.status_code == 302
    _supplierperf_sec_assert_unchanged(row, before)
    assert row.rating == 2, "a closed response's answer was overwritten"
    assert any("frozen" in note for note in _supplierperf_sec_notes(edit_post))


# ============================================================== 4. the two uncaught-500 fixes
#
# C1 (``?year=``) and C4 (a 5,000-digit ``rating``) were both reachable by anybody who could type
# a URL or post a form, and ``DEBUG`` defaults to True in ``settings.py``, so a deployment with
# no ``.env`` rendered a full technical 500 - stack frames, settings, local variables - from
# either. Both are swept here over a WIDER hostile matrix than the views lane's parametrize, by
# an ordinary MEMBER, with ``raise_request_exception=False`` so a regression collects the
# offending value instead of aborting the run.
#
# L35 is the second half of every case below: an unparseable or absent prerequisite must be
# REJECTED, never allowed to fall through into the write with a default.

_SUPPLIERPERF_SEC_HOSTILE_NUMBERS = (
    "0", "-1", "10000", "99999", "abc", "²", "9" * 40, "9" * 5000, "1e400", "NaN",
    "Infinity", "-Infinity", "3.5", "0x10", " ", "",
)


def test_supplierperf_evaluation_register_survives_every_hostile_year(
        member_user, supplierperf_scorecard_draft_a):
    """**C1.** ``period_end__year`` is the app's only ``__year`` int filter and it is NOT a pk
    lookup, so ``crud_list``'s zero-skip does not catch it and ``as_db_int`` range-checks the
    COLUMN width rather than the calendar. Django then handed the value to
    ``datetime.date(value, 1, 1)`` inside the backend, which raises ``year 0 is out of range``.

    Sixteen hostile values, every one of them typeable into an address bar, and each must return
    **200 with the register intact** - L11 says a hand-edited query string SKIPS the filter, it
    never raises and it never silently empties the page either.
    """
    client = _supplierperf_sec_sweep_client(member_user)
    url = reverse("procurement:supplierevaluation_list")

    failures = []
    for value in _SUPPLIERPERF_SEC_HOSTILE_NUMBERS:
        response = client.get(url, {"year": value})
        if response.status_code != 200:
            failures.append((value[:16], response.status_code))
        elif [obj.pk for obj in response.context["object_list"]] != [
                supplierperf_scorecard_draft_a.pk]:
            failures.append((value[:16], "emptied the register"))

    assert failures == [], f"?year= hostile values that were not handled: {failures}"


def test_supplierperf_every_register_survives_a_five_thousand_character_search(
        member_user, supplierperf_kpi_manual_a, supplierperf_scorecard_draft_a,
        supplierperf_score_manual_a, supplierperf_feedback_requested_a,
        supplierperf_plan_draft_a):
    """A 5,000-character ``?q=`` against every ``icontains`` chain is 200, not a 500.

    Each register searches three to four columns with ``Q(...__icontains=...)``; an unbounded
    term is the cheapest thing an anonymous-ish caller can throw at that, and the answer has to
    be an empty result set rather than a driver error.
    """
    client = _supplierperf_sec_sweep_client(member_user)
    term = "é" * 5000

    failures = []
    for url_name in ("supplierkpi_list", "supplierevaluation_list", "supplierkpiscore_list",
                     "supplierfeedback_list", "improvementplan_list"):
        response = client.get(reverse(f"procurement:{url_name}"), {"q": term})
        if response.status_code != 200:
            failures.append((url_name, response.status_code))
        elif list(response.context["object_list"]):
            failures.append((url_name, "matched something"))

    assert failures == [], f"registers that could not take a long search term: {failures}"


def test_supplierperf_feedback_submit_refuses_every_hostile_rating_without_mutating(
        member_user, tenant_a, supplierperf_supplier_a):
    """**C4.** ``isdecimal()`` is True for 5,000 digits and ``int()`` then raises
    ``Exceeds the limit (4300) for integer string conversion`` - an uncaught 500 any member with
    an open response's pk could fire at will. This verb goes through NO form, so nothing else was
    applying the guard ``crud_list`` applies to every GET filter.

    A fresh row per value, because the point is not only the status code: after each refusal the
    response must still be ``requested`` with ``rating`` and ``submitted_at`` untouched. The two
    blank values are the L35 case - an absent rating is REFUSED with a message, never defaulted
    into an answer nobody gave.
    """
    client = _supplierperf_sec_sweep_client(member_user)

    failures = []
    for value in _SUPPLIERPERF_SEC_HOSTILE_NUMBERS:
        row = _supplierperf_sec_feedback(tenant_a, supplierperf_supplier_a,
                                         respondent_name=f"Hostile {value[:8]!r}")
        response = client.post(
            reverse("procurement:supplierfeedback_submit", args=[row.pk]), {"rating": value})
        row.refresh_from_db()
        if response.status_code != 302:
            failures.append((value[:16], response.status_code))
        elif row.status != "requested" or row.rating is not None or row.submitted_at is not None:
            failures.append((value[:16], f"filed as {row.status}/{row.rating}"))

    assert failures == [], f"hostile ratings that were not refused cleanly: {failures}"


def test_supplierperf_plan_close_refuses_every_hostile_outcome_without_signing(
        client_a, tenant_a, supplierperf_supplier_a):
    """Close is admin-only AND outcome-validated, and the second half is the one L35 is about.

    ``outcome`` is read straight out of the POST body (this verb goes through no form either) and
    is checked against the model's own ``OUTCOME_CHOICES``. A missing, misspelt, wrong-cased or
    absurdly long value must be REFUSED with a message - never allowed to fall through and stamp
    ``verified_by`` / ``verified_at`` against an ending nobody named. A signature over a blank
    outcome is exactly what this field exists to prevent.
    """
    hostile = ["", "   ", "successfull", "SUCCESSFUL", "closed", "9" * 5000, "NaN",
               "<script>alert(1)</script>", "successful,failed"]
    failures = []

    for index, value in enumerate(hostile):
        plan = _supplierperf_sec_plan(tenant_a, supplierperf_supplier_a,
                                      title=f"Hostile close {index}", status="active")
        response = client_a.post(reverse("procurement:improvementplan_close", args=[plan.pk]),
                                 {"outcome": value, "closure_note": "Signed anyway?"})
        plan.refresh_from_db()
        if response.status_code != 302:
            failures.append((value[:16], response.status_code))
        elif (plan.status != "active" or plan.outcome != "" or plan.verified_by_id is not None
                or plan.verified_at is not None or plan.closure_note != ""):
            failures.append((value[:16], f"closed as {plan.status}/{plan.outcome!r}"))

    assert failures == [], f"hostile outcomes that were not refused cleanly: {failures}"


def test_supplierperf_plan_close_still_works_with_a_real_outcome(
        client_a, tenant_a, supplierperf_supplier_a):
    """The L44 pair: a legitimate administrator close lands and signs, so the sweep above is a
    guard rather than a verb that refuses everything."""
    plan = _supplierperf_sec_plan(tenant_a, supplierperf_supplier_a, title="Legitimate close",
                                  status="monitoring")

    response = client_a.post(reverse("procurement:improvementplan_close", args=[plan.pk]),
                             {"outcome": "failed", "closure_note": "Two periods, no movement."})

    assert response.status_code == 302
    plan.refresh_from_db()
    assert plan.status == "closed" and plan.outcome == "failed"
    assert plan.verified_by_id is not None and plan.verified_at is not None


def test_supplierperf_score_edit_refuses_a_non_finite_or_over_range_measured_value(
        member_user, supplierperf_score_manual_a):
    """``measured_value`` is ``max_digits=16, decimal_places=4`` and it comes off a form - so the
    right answer is a FIELD ERROR on a re-rendered page, never a 500 and never a stored value.

    ``NaN`` and ``Infinity`` are the ones worth naming: ``Decimal`` parses both happily, and a
    non-finite measurement written to the column poisons every aggregate that reads it
    afterwards (L35). The over-``max_digits`` value is the other half - 20 integer digits is a
    perfectly ordinary paste and must not reach the driver.
    """
    client = _supplierperf_sec_sweep_client(member_user)
    url = reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_manual_a.pk])
    before = _supplierperf_sec_snapshot(supplierperf_score_manual_a, "measured_value", "score",
                                        "band")

    failures = []
    for value in ("NaN", "Infinity", "-Infinity", "1e400", "9" * 20, "abc", "9" * 5000):
        response = client.post(url, _supplierperf_sec_score_payload(measured_value=value))
        if response.status_code != 200:
            failures.append((value[:16], response.status_code))
        elif "measured_value" not in response.context["form"].errors:
            failures.append((value[:16], "accepted without a field error"))

    assert failures == [], f"hostile measured_value inputs that were not refused: {failures}"
    _supplierperf_sec_assert_unchanged(supplierperf_score_manual_a, before)


# ============================================================== 5. CSRF
#
# ``force_login`` authenticates the session and supplies no CSRF cookie or form token, which is
# exactly the shape of a cross-site POST from a page the workspace does not control. Every
# mutating route in 6.16 must reject it - the thirteen POST verbs and the four create/edit POSTs
# alike - and nothing may move.

def test_supplierperf_every_mutating_route_rejects_a_post_with_no_csrf_token(
        admin_user, tenant_a, supplierperf_supplier_a, settings, tmp_path):
    """All seventeen mutating endpoints, swept under ``enforce_csrf_checks=True``.

    Driven as the tenant ADMINISTRATOR so the two ``@tenant_admin_required`` verbs would sail
    through their permission gate: what refuses them here is the CSRF middleware, which runs
    before the view is ever called and therefore before ``@require_POST`` and
    ``@tenant_admin_required`` both.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    pks = _supplierperf_sec_matrix_rows(tenant_a, supplierperf_supplier_a, admin_user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    cases = _supplierperf_sec_cases(pks, kinds=("verb", "admin")) + [
        ("supplierkpi_create", [], "post", _supplierperf_sec_kpi_payload(code="CSRF-01")),
        ("supplierkpi_edit", [pks["kpi"]], "post", _supplierperf_sec_kpi_payload(code="MTX-01")),
        ("supplierkpiscore_edit", [pks["score"]], "post", _supplierperf_sec_score_payload()),
        ("supplierfeedback_create", [], "post",
         _supplierperf_sec_feedback_payload(supplierperf_supplier_a.pk)),
        ("supplierfeedback_edit", [pks["feedback"]], "post",
         _supplierperf_sec_feedback_payload(supplierperf_supplier_a.pk)),
        ("improvementplan_create", [], "post",
         _supplierperf_sec_plan_payload(supplierperf_supplier_a.pk, title="CSRF plan")),
        ("improvementplan_edit", [pks["plan"]], "post",
         _supplierperf_sec_plan_payload(supplierperf_supplier_a.pk, title="CSRF edit")),
    ]
    failures = _supplierperf_sec_sweep(client, cases, expected=403)

    assert failures == [], f"a mutating route accepted a POST with no CSRF token: {failures}"

    # Nothing moved: no row deleted, no lifecycle advanced, no row created.
    assert SupplierKpi.objects.filter(pk=pks["kpi"]).exists()
    assert SupplierKpi.objects.get(pk=pks["kpi"]).name == "KPI MTX-01"
    assert SupplierKpiScore.objects.filter(pk=pks["score"]).exists()
    assert SupplierFeedback.objects.get(pk=pks["feedback"]).status == "requested"
    plan = SupplierImprovementPlan.objects.get(pk=pks["plan"])
    assert plan.status == "draft" and plan.title == "Matrix plan"
    assert plan.acknowledged_at is None and plan.verified_by_id is None
    assert not SupplierKpi.objects.filter(code="CSRF-01").exists()
    assert not SupplierImprovementPlan.objects.filter(title="CSRF plan").exists()
    assert SupplierKpiScore.objects.filter(scorecard_id=pks["scorecard"]).count() == 1


# ============================================================== 6. mass assignment through the wire
#
# A field left off ``Meta.fields`` is not a boundary until something proves the wire agrees. The
# forms lane asserts the exclusions at the FORM layer; this section posts the excluded names in a
# real request body and reads the row back, because that is the shape an attacker sends - a
# hand-edited body, never the rendered page.

def test_supplierperf_score_edit_binds_only_measured_value_and_comment(
        member_user, tenant_a, supplierperf_score_manual_a, supplierperf_supplier_a,
        supplierperf_kpi_survey_a):
    """Fifteen extra names posted at the two-field edit form, and not one of them lands.

    ``score`` and ``band`` are the derivations the whole register is read on; the seven
    ``*_at_time`` / ``kpi_*`` columns are the FROZEN history that makes a closed period readable
    after a retune; ``scorecard`` and ``kpi`` are the line's identity, and rebinding either would
    move a measurement onto a different period or a different definition without changing a
    single visible figure.
    """
    other_card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a,
                                             period_end=_supplierperf_sec_day(-120),
                                             period_start=_supplierperf_sec_day(-209))
    before = _supplierperf_sec_snapshot(
        supplierperf_score_manual_a, "score", "band", "weight_applied", "target_at_time",
        "direction_at_time", "source_at_time", "unit_at_time", "kpi_name", "kpi_category",
        "respondent_count", "scorecard_id", "kpi_id", "tenant_id", "computed_by_id")

    response = _supplierperf_sec_login(member_user).post(
        reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_manual_a.pk]),
        _supplierperf_sec_score_payload(
            measured_value="88.0000", comment="Legitimate correction.",
            score="100.00", band="ok", weight_applied="99", target_at_time="1",
            direction_at_time="lower_is_better", source_at_time="derived", unit_at_time="days",
            kpi_name="Rewritten", kpi_category="quality", respondent_count="42",
            scorecard=str(other_card.pk), kpi=str(supplierperf_kpi_survey_a.pk),
            tenant="", computed_by=str(member_user.pk), breakdown="{}"))

    assert response.status_code == 302
    supplierperf_score_manual_a.refresh_from_db()
    # The two fields the form DOES own moved...
    assert supplierperf_score_manual_a.measured_value == Decimal("88.0000")
    assert supplierperf_score_manual_a.comment == "Legitimate correction."
    # ...and nothing else did.
    _supplierperf_sec_assert_unchanged(supplierperf_score_manual_a, before)


def test_supplierperf_score_edit_refuses_a_derived_line_entirely_the_gate_is_the_view(
        member_user, supplierperf_score_derived_a):
    """A derived line is refused BEFORE any form work - the two-field form is not the boundary.

    A derived or survey line is recomputed by Generate from evidence; typing over it would leave
    a number on the scorecard that no resolver and no respondent stands behind, and the next run
    would silently overwrite it anyway. So the view fetches the row FIRST and refuses anything
    but ``source_at_time == "manual"``: a crafted POST against a derived line's pk never reaches
    the form at all, which is why a two-field ``Meta.fields`` would not have been enough on its
    own. The GET is asserted too - the edit page must not even render for this line.
    """
    before = _supplierperf_sec_snapshot(supplierperf_score_derived_a, "measured_value", "comment",
                                        "score", "band", "source_at_time")
    client = _supplierperf_sec_login(member_user)
    url = reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_derived_a.pk])

    form_page = client.get(url)
    posted = client.post(url, _supplierperf_sec_score_payload(measured_value="11.0000",
                                                              comment="Typed over a resolver."))

    assert form_page.status_code == 302, "the edit form rendered for a derived line"
    assert posted.status_code == 302
    assert "form" not in (form_page.context or {})
    _supplierperf_sec_assert_unchanged(supplierperf_score_derived_a, before)
    assert any("Only a manual-entry line" in note for note in _supplierperf_sec_notes(posted))


def test_supplierperf_plan_edit_ignores_status_outcome_and_every_signature_stamp(
        member_user, supplierperf_plan_draft_a, supplierperf_supplier_a):
    """``status`` / ``outcome`` and the acknowledgement + verification stamps are not form fields.

    The five verbs own the lifecycle and the sign-off; an edit that could write ``closed`` +
    ``successful`` + ``verified_by`` would be a member signing their own supplier off, and an
    editable ``acknowledged_at`` would stop the acknowledgement being evidence of anything.
    ``number`` and ``tenant`` ride along in the same body: the row must keep its own.
    """
    plan = supplierperf_plan_draft_a
    before = _supplierperf_sec_snapshot(plan, "status", "outcome", "acknowledged_at",
                                        "acknowledged_by_id", "verified_at", "verified_by_id",
                                        "actual_close_date", "closure_note", "number",
                                        "tenant_id")

    response = _supplierperf_sec_login(member_user).post(
        reverse("procurement:improvementplan_edit", args=[plan.pk]),
        _supplierperf_sec_plan_payload(
            supplierperf_supplier_a.pk, title="Legitimately retitled",
            status="closed", outcome="successful",
            actual_close_date=_supplierperf_sec_day().isoformat(),
            acknowledged_at=timezone.now().isoformat(),
            acknowledged_by=str(member_user.pk),
            verified_at=timezone.now().isoformat(), verified_by=str(member_user.pk),
            closure_note="Signed by the edit form.", number="SIP-99999", tenant=""))

    assert response.status_code == 302
    plan.refresh_from_db()
    assert plan.title == "Legitimately retitled"      # the field the form DOES own moved
    _supplierperf_sec_assert_unchanged(plan, before)
    assert plan.status == "draft" and plan.outcome == ""


def test_supplierperf_feedback_edit_ignores_status_and_every_raise_and_file_stamp(
        member_user, supplierperf_feedback_requested_a, supplierperf_supplier_a, admin_user):
    """``status``, ``requested_by``, ``requested_at`` and ``submitted_at`` are not form fields.

    An edit that could write ``submitted`` would bypass the submit verb's rating validation
    entirely and move the survey aggregate; a writable ``requested_by`` would make the raise
    stamp a claim the requester could edit, which is the whole reason the create view is
    hand-rolled instead of using ``crud_create``.
    """
    row = supplierperf_feedback_requested_a
    before = _supplierperf_sec_snapshot(row, "status", "submitted_at", "requested_at",
                                        "requested_by_id", "number", "tenant_id")

    response = _supplierperf_sec_login(member_user).post(
        reverse("procurement:supplierfeedback_edit", args=[row.pk]),
        _supplierperf_sec_feedback_payload(
            supplierperf_supplier_a.pk, respondent_name="Legitimately renamed",
            status="submitted", submitted_at=timezone.now().isoformat(),
            requested_at=timezone.now().isoformat(), requested_by=str(admin_user.pk),
            number="SFB-99999", tenant=""))

    assert response.status_code == 302
    row.refresh_from_db()
    assert row.respondent_name == "Legitimately renamed"
    _supplierperf_sec_assert_unchanged(row, before)
    assert row.status == "requested"


def test_supplierperf_kpi_create_and_edit_ignore_tenant_and_the_auto_number(
        member_user, tenant_a, tenant_b, supplierperf_kpi_manual_a):
    """``tenant`` and ``number`` are stamped, never posted - on the create AND on the edit.

    A bindable ``tenant`` would let a member mint a row straight into another workspace; a
    bindable ``number`` would let two rows in one workspace claim the same identifier, which the
    ``unique_together ("tenant", "number")`` exists to stop.
    """
    client = _supplierperf_sec_login(member_user)
    before = _supplierperf_sec_snapshot(supplierperf_kpi_manual_a, "tenant_id", "number")

    created = client.post(reverse("procurement:supplierkpi_create"),
                          _supplierperf_sec_kpi_payload(code="MASS-01",
                                                        tenant=str(tenant_b.pk),
                                                        number="SKP-99999"))
    edited = client.post(
        reverse("procurement:supplierkpi_edit", args=[supplierperf_kpi_manual_a.pk]),
        _supplierperf_sec_kpi_payload(code=supplierperf_kpi_manual_a.code,
                                      name="Renamed legitimately",
                                      tenant=str(tenant_b.pk), number="SKP-88888"))

    assert created.status_code == 302 and edited.status_code == 302
    minted = SupplierKpi.objects.get(code="MASS-01")
    assert minted.tenant_id == tenant_a.pk, "a crafted tenant landed a row in another workspace"
    assert minted.number != "SKP-99999" and minted.number.startswith("SKP-")
    supplierperf_kpi_manual_a.refresh_from_db()
    assert supplierperf_kpi_manual_a.name == "Renamed legitimately"
    _supplierperf_sec_assert_unchanged(supplierperf_kpi_manual_a, before)


def test_supplierperf_generate_body_cannot_set_manual_override_or_the_dimension_scores(
        client_a, tenant_a, supplierperf_supplier_a):
    """The one-way door takes NO input: Generate reads its figures from the KPI lines only.

    ``supplierevaluation_generate`` posts nothing by design, so every column it writes is
    computed. A body naming ``delivery_score``, ``overall_score``, ``grade`` and ``status`` must
    change none of them - the dimension column has to equal the score of the line the run
    actually wrote, and the scorecard must still be a draft afterwards. ``manual_override`` is
    asserted as True because the RUN sets it: this test is about where the value came from, not
    about suppressing it.
    """
    card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a)
    kpi = _supplierperf_sec_kpi(tenant_a, "GEN-01")
    _supplierperf_sec_score(tenant_a, card, kpi, measured_value=Decimal("92.0000"),
                            score=None, band="unknown")

    # The posted figures are deliberately values the compute CANNOT produce for this line
    # (measured 92 against a 95/90/85 band scores 100.00), so "it came from the body" and "it
    # came from the KPI line" cannot be confused for each other.
    response = client_a.post(reverse("procurement:supplierevaluation_generate", args=[card.pk]),
                             {"delivery_score": "7.77", "quality_score": "7.77",
                              "overall_score": "7.77", "grade": "F", "status": "published",
                              "manual_override": "false", "number": "SCR-99999"})

    assert response.status_code == 302
    card.refresh_from_db()
    line = SupplierKpiScore.objects.get(tenant=tenant_a, scorecard=card, kpi=kpi)
    assert card.manual_override is True                 # set by the run, not by the body
    assert card.status == "draft"                       # the posted status did not bind
    assert card.number != "SCR-99999"
    assert card.delivery_score == line.score            # the LINE is where the figure came from
    assert card.delivery_score != Decimal("7.77")
    assert card.overall_score != Decimal("7.77")
    assert card.quality_score is None                   # no KPI feeds it - never a phantom value


# ============================================================== 7. XSS and escaping
#
# Django auto-escapes, so what this section actually guards is the day somebody reaches for
# ``|safe`` or ``mark_safe`` on one of these fields. The apostrophe matters as much as the angle
# brackets: ``confirm()`` handlers live on these pages (L42), and an unescaped ``'`` in a supplier
# name or a plan title breaks straight out of one.

_SUPPLIERPERF_SEC_XSS = "<script>alert('supplierperf-xss')</script>"


def test_supplierperf_a_reflected_search_term_is_escaped_on_every_register(
        client_a, supplierperf_kpi_manual_a, supplierperf_scorecard_draft_a,
        supplierperf_score_manual_a, supplierperf_feedback_requested_a,
        supplierperf_plan_draft_a):
    """``?q=<script>`` comes back into the search input escaped on all five registers."""
    failures = []
    for url_name in ("supplierkpi_list", "supplierevaluation_list", "supplierkpiscore_list",
                     "supplierfeedback_list", "improvementplan_list"):
        response = client_a.get(reverse(f"procurement:{url_name}"),
                                {"q": _SUPPLIERPERF_SEC_XSS})
        html = _supplierperf_sec_html(response)
        if response.status_code != 200:
            failures.append((url_name, response.status_code))
        elif _SUPPLIERPERF_SEC_XSS in html:
            failures.append((url_name, "reflected the raw payload"))
        elif escape(_SUPPLIERPERF_SEC_XSS) not in html:
            failures.append((url_name, "did not echo the term at all"))

    assert failures == [], f"registers that mishandled a reflected search term: {failures}"


def test_supplierperf_stored_markup_is_escaped_on_the_kpi_detail_page(client_a, tenant_a):
    """A KPI's ``name``, ``description`` and ``notes`` all render escaped.

    ``description`` and ``notes`` go through ``|linebreaksbr``, which escapes under autoescape -
    so this is also the test that fails the day one of them is switched to ``|safe``.
    """
    kpi = _supplierperf_sec_kpi(tenant_a, "XSS-01", name=f"KPI {_SUPPLIERPERF_SEC_XSS}",
                                description=f"Described {_SUPPLIERPERF_SEC_XSS}",
                                notes=f"Noted {_SUPPLIERPERF_SEC_XSS}")

    response = client_a.get(reverse("procurement:supplierkpi_detail", args=[kpi.pk]))
    html = _supplierperf_sec_html(response)

    assert response.status_code == 200
    assert _SUPPLIERPERF_SEC_XSS not in html
    assert html.count(escape(_SUPPLIERPERF_SEC_XSS)) >= 3
    assert "&#x27;" in html or "&#39;" in html


def test_supplierperf_stored_markup_is_escaped_on_the_plan_detail_page(
        client_a, tenant_a, supplierperf_supplier_a):
    """A plan's ``title``, ``finding``, ``root_cause`` and ``supplier_owner_name`` render escaped.

    The plan detail page carries the delete confirm dialog, so an unescaped apostrophe in the
    title is a broken ``onclick`` as well as a stored-XSS vector (L42).
    """
    plan = _supplierperf_sec_plan(
        tenant_a, supplierperf_supplier_a, title=f"Plan {_SUPPLIERPERF_SEC_XSS}",
        finding=f"Found {_SUPPLIERPERF_SEC_XSS}", root_cause=f"Because {_SUPPLIERPERF_SEC_XSS}",
        supplier_owner_name=f"O'Brien {_SUPPLIERPERF_SEC_XSS}")

    response = client_a.get(reverse("procurement:improvementplan_detail", args=[plan.pk]))
    html = _supplierperf_sec_html(response)

    assert response.status_code == 200
    assert _SUPPLIERPERF_SEC_XSS not in html
    assert html.count(escape(_SUPPLIERPERF_SEC_XSS)) >= 4


def test_supplierperf_stored_markup_is_escaped_on_the_feedback_detail_page(
        client_a, tenant_a, supplierperf_supplier_a):
    """A response's ``respondent_name`` and ``comment`` render escaped.

    The comment is the one field a genuinely external party's words end up in, which makes it the
    likeliest place for markup to arrive from outside the workspace at all.
    """
    row = _supplierperf_sec_feedback(
        tenant_a, supplierperf_supplier_a, respondent_name=f"D. O'Neill {_SUPPLIERPERF_SEC_XSS}",
        comment=f"Said {_SUPPLIERPERF_SEC_XSS}", rating=3)

    response = client_a.get(reverse("procurement:supplierfeedback_detail", args=[row.pk]))
    html = _supplierperf_sec_html(response)

    assert response.status_code == 200
    assert _SUPPLIERPERF_SEC_XSS not in html
    assert html.count(escape(_SUPPLIERPERF_SEC_XSS)) >= 2


def test_supplierperf_stored_markup_is_escaped_in_the_score_breakdown(
        client_a, tenant_a, supplierperf_supplier_a):
    """The ``breakdown`` JSON is flattened to text by ``_breakdown_value`` - and stays escaped.

    Worth its own test because this value never passes through a form or a model field's
    validation: the resolvers write the dict, the template prints ``{{ row.value }}``, and a
    ``|safe`` there would publish whatever a derived-metric resolver happened to put in it. The
    nested list is included because ``_breakdown_value`` joins sequences itself rather than
    letting Django ``str()`` them into a Python repr.
    """
    card = _supplierperf_sec_scorecard(tenant_a, supplierperf_supplier_a)
    kpi = _supplierperf_sec_kpi(tenant_a, "XSS-02")
    line = _supplierperf_sec_score(
        tenant_a, card, kpi, comment=f"Commented {_SUPPLIERPERF_SEC_XSS}",
        breakdown={"note": _SUPPLIERPERF_SEC_XSS,
                   "window": [_SUPPLIERPERF_SEC_XSS, "2026-08-09"]})

    response = client_a.get(reverse("procurement:supplierkpiscore_detail", args=[line.pk]))
    html = _supplierperf_sec_html(response)

    assert response.status_code == 200
    assert _SUPPLIERPERF_SEC_XSS not in html
    assert html.count(escape(_SUPPLIERPERF_SEC_XSS)) >= 3
    assert "[&#x27;" not in html and "['" not in html      # M5: never a Python repr
