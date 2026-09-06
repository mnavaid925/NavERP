"""Procurement 6.16 Supplier Performance & Evaluation — VIEW / CRUD integration flows.

Everything here drives the real URLconf, the real views and the real templates. The lanes next
door own the model invariants (``test_supplierperf_models.py``) and the four forms
(``test_supplierperf_forms.py``); the authorization matrix and cross-tenant IDOR are a separate
lane again and are deliberately NOT swept here — a gate is asserted only where it is part of a
view's ordinary behaviour (the ``can_generate`` / ``can_close`` context flags and the sentence
the page prints in a control's place).

What this lane is actually for, in priority order:

1. **Rendered rows, not status codes.** A wrong context key or a mistyped row-dict key returns
   **200** and renders a grid of em dashes (L8). Every register and every board is asserted on a
   seeded record's own identifier reaching the HTML, and every board whose context is a list of
   dicts has one real value chased into the markup.
2. **The guard regressions this review fixed**, each with the exact query string that broke it:
   ``?source=<junk>`` on the score register and ``?category=<junk>`` on the benchmark board both
   used to EMPTY the page instead of ignoring the filter (L11), and ``?year=0`` /
   ``?year=10000`` reached ``datetime.date(year, 1, 1)`` inside the backend as an uncaught
   ``ValueError`` — a 500 from a URL anybody can type.
3. **The one-way door.** Generate succeeds on a draft, is idempotent, refuses a closed period
   with the reason PRINTED on the page, and — the Critical — refuses an empty run so
   ``manual_override`` is never set on the strength of no measurement at all.
4. **Every POST verb 405s on GET** and moves exactly one state; a replay is refused rather than
   re-stamping.
5. **The three boards with data AND with an empty dataset.** The empty branch is where a bad
   aggregate or a missing context key hides, and seeded rows never exercise it.
6. **Query budgets on the three boards**, as a ceiling AND as a flatness comparison at two row
   counts — the ceiling says "this page is cheap", the comparison says "and its cost does not
   grow with the table", which is the actual N+1 property.
7. **The two boards agree.** The same supplier in the same period must report the same
   ``composite`` on the benchmark board and on the trend board. They diverged (34.62 against
   69.87 on one supplier, because the benchmark board published ``overall_score`` under the
   composite's name) and it was fixed; this locks it.

House rules: every reference date derives from ``timezone.localdate()`` / ``timezone.now()`` and
never ``date.today()`` (L16); every URL goes through ``reverse("procurement:<name>")``; every
assertion states an expected VALUE or COUNT rather than truthiness. Every test is
``test_supplierperf_*`` and every module-level helper ``_supplierperf_*`` so no sibling lane can
shadow anything here (L47).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.procurement import performance
from apps.procurement.models import (SupplierFeedback, SupplierImprovementPlan, SupplierKpi,
                                     SupplierKpiScore)

pytestmark = pytest.mark.django_db


# =================================================================================================
# module-level helpers — every name _supplierperf_* so a sibling lane cannot shadow one (L47)
# =================================================================================================

def _supplierperf_day(offset=0):
    """A date on the SAME basis the views use (L16) — never ``datetime.date.today()``."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _supplierperf_html(response):
    return response.content.decode()


def _supplierperf_pks(response):
    return [obj.pk for obj in response.context["object_list"]]


def _supplierperf_notes(response):
    """Every flash message on the request — works on a 302 too, the storage hangs off the
    request rather than off the (absent) context."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _supplierperf_queries(client, url, params=None):
    """Queries for ONE GET of ``url``, the whole request/response cycle included.

    Used ALONGSIDE ``django_assert_max_num_queries``, not instead of it: comparing two counts
    taken at different row counts is immune to every fixed overhead in the stack — including the
    three-query session write ``SessionTimeoutMiddleware`` performs on each authenticated
    request when it stamps ``_last_activity``.
    """
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url, params or {})
    assert response.status_code == 200, url
    return len(captured)


def _supplierperf_view_party(tenant, name, role="supplier"):
    """A counterparty WITH its PartyRole — every 6.16 supplier picker narrows on
    ``roles__role__in=("supplier", "vendor")``, so a bare Party is invisible to all of them."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _supplierperf_view_scorecard(tenant, party, **overrides):
    from apps.scm.models import SupplierScorecard
    fields = dict(tenant=tenant, party=party, period_start=_supplierperf_day(-89),
                  period_end=_supplierperf_day(), status="draft")
    fields.update(overrides)
    return SupplierScorecard.objects.create(**fields)


def _supplierperf_view_profile(tenant, party, tier="strategic", category="Precision castings"):
    from apps.scm.models import SupplierProfile
    return SupplierProfile.objects.create(tenant=tenant, party=party,
                                          onboarding_status="approved", tier=tier,
                                          category=category)


def _supplierperf_view_risk(tenant, party, score=2, **overrides):
    """One ``scm.SupplierRiskAssessment`` — the benchmark board's second axis. ``risk_index`` is
    ``editable=False`` and derived, so it is recomputed rather than typed."""
    from apps.scm.models import SupplierRiskAssessment
    fields = dict(tenant=tenant, party=party, assessment_date=_supplierperf_day(-5),
                  status="reviewed", financial_score=score, geopolitical_score=score,
                  compliance_score=score, operational_score=score)
    fields.update(overrides)
    row = SupplierRiskAssessment.objects.create(**fields)
    row.recompute_risk_level()
    return row


def _supplierperf_view_kpi(tenant, code, **overrides):
    """A VALID KPI definition — the band triple is already ordered for ``higher_is_better``."""
    fields = dict(tenant=tenant, code=code, name=f"KPI {code}", category="delivery", unit="pct",
                  direction="higher_is_better", source="manual", derived_metric="", weight=10,
                  target_value=Decimal("95"), warning_threshold=Decimal("90"),
                  critical_threshold=Decimal("85"), scoring_method="band",
                  maps_to_dimension="delivery", applies_to="all", review_frequency="quarterly",
                  display_order=10, is_active=True)
    fields.update(overrides)
    return SupplierKpi.objects.create(**fields)


def _supplierperf_view_score(tenant, scorecard, kpi, **overrides):
    """A score line with EVERY frozen column filled from the KPI — a line left at its defaults
    makes every frozen-history assertion pass vacuously."""
    fields = dict(tenant=tenant, scorecard=scorecard, kpi=kpi,
                  measured_value=Decimal("92.0000"), score=Decimal("70.00"), band="warning",
                  weight_applied=kpi.weight, target_at_time=kpi.target_value,
                  direction_at_time=kpi.direction, source_at_time=kpi.source,
                  unit_at_time=kpi.unit, kpi_name=kpi.name, kpi_category=kpi.category,
                  breakdown={"source": "fixture"}, respondent_count=0, comment="")
    fields.update(overrides)
    return SupplierKpiScore.objects.create(**fields)


def _supplierperf_view_feedback(tenant, supplier, **overrides):
    fields = dict(tenant=tenant, supplier=supplier, period_start=_supplierperf_day(-89),
                  period_end=_supplierperf_day(), respondent_kind="internal",
                  respondent_function="procurement", importance=5, status="requested")
    fields.update(overrides)
    return SupplierFeedback.objects.create(**fields)


def _supplierperf_view_plan(tenant, supplier, **overrides):
    fields = dict(tenant=tenant, supplier=supplier, title="Late deliveries",
                  severity="major", finding="Four of six shipments arrived late.",
                  start_date=_supplierperf_day(), target_close_date=_supplierperf_day(30),
                  status="draft")
    fields.update(overrides)
    return SupplierImprovementPlan.objects.create(**fields)


def _supplierperf_view_cohort(tenant, count, offset=0, period_end=None):
    """``count`` suppliers, each with a profile, a risk assessment, a scorecard on ONE shared
    period and two scored KPI lines. The shape the benchmark board is built for."""
    period_end = period_end or _supplierperf_day()
    kpi_a = SupplierKpi.objects.filter(tenant=tenant, code="COH-A").first() or \
        _supplierperf_view_kpi(tenant, "COH-A", weight=30)
    kpi_b = SupplierKpi.objects.filter(tenant=tenant, code="COH-B").first() or \
        _supplierperf_view_kpi(tenant, "COH-B", weight=10, maps_to_dimension="quality",
                               category="quality", display_order=20)
    made = []
    for index in range(offset, offset + count):
        party = _supplierperf_view_party(tenant, f"Cohort Supplier {index:03d}")
        _supplierperf_view_profile(tenant, party)
        _supplierperf_view_risk(tenant, party, score=1 + (index % 4))
        card = _supplierperf_view_scorecard(tenant, party, period_end=period_end,
                                            period_start=period_end - datetime.timedelta(days=89))
        _supplierperf_view_score(tenant, card, kpi_a, score=Decimal("80.00"), band="ok")
        _supplierperf_view_score(tenant, card, kpi_b, score=Decimal("40.00"), band="critical")
        card.delivery_score = Decimal("80.00")
        card.quality_score = Decimal("40.00")
        card.save(update_fields=["delivery_score", "quality_score", "updated_at"])
        card.recompute_overall()
        made.append((party, card))
    return made


# =================================================================================================
# 1. The five registers render, and their filters actually filter
# =================================================================================================

def test_supplierperf_kpi_register_renders_its_rows(client_a, supplierperf_kpi_manual_a,
                                                    supplierperf_kpi_derived_a,
                                                    supplierperf_kpi_survey_a):
    response = client_a.get(reverse("procurement:supplierkpi_list"))
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert "procurement/performance/kpi/list.html" in [t.name for t in response.templates]
    assert set(_supplierperf_pks(response)) == {supplierperf_kpi_manual_a.pk,
                                                supplierperf_kpi_derived_a.pk,
                                                supplierperf_kpi_survey_a.pk}
    assert "MAN-01" in html and "OTD-01" in html and "SRV-01" in html
    assert response.context["stats"] == {"total": 3, "active": 3, "derived": 1, "survey": 1,
                                         "manual": 1}


#: The three KPI fixtures, by code. MAN-01 and OTD-01 both sit in the ``delivery`` category —
#: only SRV-01 is ``service`` — so a category expectation is a SET, not a single code.
_SUPPLIERPERF_KPI_CODES = {"MAN-01", "OTD-01", "SRV-01"}


@pytest.mark.parametrize("param,value,expected", [
    ("category", "delivery", {"MAN-01", "OTD-01"}),
    ("category", "service", {"SRV-01"}),
    ("category", "esg", set()),
    ("source", "manual", {"MAN-01"}),
    ("source", "derived", {"OTD-01"}),
    ("source", "survey", {"SRV-01"}),
    ("direction", "higher_is_better", _SUPPLIERPERF_KPI_CODES),
    ("direction", "lower_is_better", set()),
    ("applies_to", "all", _SUPPLIERPERF_KPI_CODES),
    ("applies_to", "tier", set()),
    ("is_active", "True", _SUPPLIERPERF_KPI_CODES),
    ("is_active", "False", set()),
])
def test_supplierperf_kpi_register_each_filter_narrows(
        client_a, supplierperf_kpi_manual_a, supplierperf_kpi_derived_a,
        supplierperf_kpi_survey_a, param, value, expected):
    """L44 — a filter that is offered must actually filter, and to the right rows. Both sides of
    every closed vocabulary are driven: a value with matches AND one without, so a filter that
    silently matched everything would fail here too."""
    response = client_a.get(reverse("procurement:supplierkpi_list"), {param: value})
    assert response.status_code == 200
    assert {row.code for row in response.context["object_list"]} == expected


def test_supplierperf_kpi_register_filters_by_owner(client_a, admin_user,
                                                    supplierperf_kpi_manual_a,
                                                    supplierperf_kpi_survey_a):
    """``owner`` is the register's one FK filter, and the dropdown lists only users who actually
    own a KPI — an empty option list is more honest than one full of people who own nothing."""
    response = client_a.get(reverse("procurement:supplierkpi_list"),
                            {"owner": str(admin_user.pk)})
    assert _supplierperf_pks(response) == [supplierperf_kpi_manual_a.pk]
    assert list(response.context["owners"]) == [admin_user]


def test_supplierperf_kpi_register_search_hits_every_declared_field(client_a, tenant_a):
    by_code = _supplierperf_view_kpi(tenant_a, "SRCH-01", name="Ordinary")
    by_name = _supplierperf_view_kpi(tenant_a, "SRCH-02", name="Kerbside handover quality")
    by_note = _supplierperf_view_kpi(tenant_a, "SRCH-03", name="Ordinary",
                                     notes="Owned by the quality desk")
    by_desc = _supplierperf_view_kpi(tenant_a, "SRCH-04", name="Ordinary",
                                     description="Counted off the pallet manifest")
    url = reverse("procurement:supplierkpi_list")

    assert _supplierperf_pks(client_a.get(url, {"q": "SRCH-01"})) == [by_code.pk]
    assert _supplierperf_pks(client_a.get(url, {"q": "Kerbside"})) == [by_name.pk]
    assert _supplierperf_pks(client_a.get(url, {"q": "quality desk"})) == [by_note.pk]
    assert _supplierperf_pks(client_a.get(url, {"q": "pallet manifest"})) == [by_desc.pk]


def test_supplierperf_evaluation_register_renders_its_rows_with_the_line_count(
        client_a, supplierperf_scorecard_draft_a, supplierperf_scorecard_published_a,
        supplierperf_score_manual_a):
    response = client_a.get(reverse("procurement:supplierevaluation_list"))
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert set(_supplierperf_pks(response)) == {supplierperf_scorecard_draft_a.pk,
                                               supplierperf_scorecard_published_a.pk}
    assert supplierperf_scorecard_draft_a.number in html
    assert "Northwind Precision Castings" in html
    counts = {row.pk: row.line_count for row in response.context["object_list"]}
    assert counts[supplierperf_scorecard_draft_a.pk] == 1
    assert counts[supplierperf_scorecard_published_a.pk] == 0
    assert response.context["stats"] == {"total": 2, "draft": 1, "published": 1, "archived": 0,
                                         "generated": 1}
    assert escape(performance.HANDOVER_NOTE) in html


def test_supplierperf_evaluation_register_filters_by_status_and_supplier(
        client_a, supplierperf_supplier_a, supplierperf_scorecard_draft_a,
        supplierperf_scorecard_published_a):
    url = reverse("procurement:supplierevaluation_list")
    assert _supplierperf_pks(client_a.get(url, {"status": "published"})) == [
        supplierperf_scorecard_published_a.pk]
    assert set(_supplierperf_pks(client_a.get(
        url, {"supplier": str(supplierperf_supplier_a.pk)}))) == {
        supplierperf_scorecard_draft_a.pk, supplierperf_scorecard_published_a.pk}


def test_supplierperf_evaluation_register_filters_by_a_real_year(
        client_a, supplierperf_scorecard_draft_a):
    """The one ``__year`` filter in the app. A real year narrows; every impossible one is dropped
    below."""
    year = supplierperf_scorecard_draft_a.period_end.year
    response = client_a.get(reverse("procurement:supplierevaluation_list"), {"year": str(year)})
    assert _supplierperf_pks(response) == [supplierperf_scorecard_draft_a.pk]
    assert year in response.context["year_choices"]


def test_supplierperf_score_register_renders_its_rows(
        client_a, supplierperf_score_manual_a, supplierperf_score_derived_a):
    response = client_a.get(reverse("procurement:supplierkpiscore_list"))
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert set(_supplierperf_pks(response)) == {supplierperf_score_manual_a.pk,
                                                supplierperf_score_derived_a.pk}
    assert supplierperf_score_manual_a.kpi_name in html
    assert response.context["stats"] == {"total": 2, "ok": 0, "warning": 2, "critical": 0,
                                         "unknown": 0}


@pytest.mark.parametrize("param,value,expect", [
    ("band", "warning", 2),
    ("band", "critical", 0),
    ("source", "manual", 1),
    ("source", "derived", 1),
])
def test_supplierperf_score_register_each_filter_narrows(
        client_a, supplierperf_score_manual_a, supplierperf_score_derived_a, param, value,
        expect):
    response = client_a.get(reverse("procurement:supplierkpiscore_list"), {param: value})
    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == expect


def test_supplierperf_feedback_register_renders_its_rows(
        client_a, supplierperf_feedback_requested_a, supplierperf_feedback_submitted_a,
        supplierperf_feedback_self_a, supplierperf_feedback_overdue_a):
    response = client_a.get(reverse("procurement:supplierfeedback_list"))
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == 4
    assert supplierperf_feedback_submitted_a.number in html
    assert response.context["stats"] == {"total": 4, "requested": 2, "submitted": 2,
                                         "declined": 0, "expired": 0, "overdue": 1}


@pytest.mark.parametrize("param,value,expect", [
    ("status", "submitted", 2),
    ("status", "requested", 2),
    ("kind", "supplier_self", 1),
    ("kind", "internal", 3),
    ("function", "quality", 1),
    ("function", "procurement", 3),
])
def test_supplierperf_feedback_register_each_filter_narrows(
        client_a, supplierperf_feedback_requested_a, supplierperf_feedback_submitted_a,
        supplierperf_feedback_self_a, supplierperf_feedback_overdue_a, param, value, expect):
    response = client_a.get(reverse("procurement:supplierfeedback_list"), {param: value})
    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == expect


def test_supplierperf_feedback_register_filters_by_its_three_foreign_keys(
        client_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a, supplierperf_feedback_submitted_a,
        supplierperf_feedback_overdue_a):
    url = reverse("procurement:supplierfeedback_list")
    assert len(_supplierperf_pks(client_a.get(
        url, {"supplier": str(supplierperf_supplier_a.pk)}))) == 2
    assert _supplierperf_pks(client_a.get(url, {"kpi": str(supplierperf_kpi_survey_a.pk)})) == [
        supplierperf_feedback_submitted_a.pk]
    assert _supplierperf_pks(client_a.get(
        url, {"scorecard": str(supplierperf_scorecard_draft_a.pk)})) == [
        supplierperf_feedback_submitted_a.pk]


def test_supplierperf_plan_register_renders_its_rows_and_the_overdue_stat(
        client_a, supplierperf_plan_draft_a, supplierperf_plan_overdue_a,
        supplierperf_plan_closed_a):
    response = client_a.get(reverse("procurement:improvementplan_list"))
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == 3
    assert supplierperf_plan_overdue_a.number in html
    assert response.context["stats"] == {"total": 3, "active": 1, "monitoring": 0, "overdue": 1,
                                         "closed": 1}


def test_supplierperf_plan_register_overdue_stat_honours_a_granted_extension(
        client_a, supplierperf_plan_overdue_a):
    """The stat card coalesces ``extended_close_date`` exactly as
    ``SupplierImprovementPlan.effective_close_date`` does in Python — re-deriving "late" from the
    original target alone here would report every extended plan as overdue."""
    supplierperf_plan_overdue_a.extended_close_date = _supplierperf_day(15)
    supplierperf_plan_overdue_a.save(update_fields=["extended_close_date", "updated_at"])

    response = client_a.get(reverse("procurement:improvementplan_list"))
    assert response.context["stats"]["overdue"] == 0
    assert response.context["object_list"][0].is_overdue is False


@pytest.mark.parametrize("param,value,expect", [
    ("status", "draft", 1),
    ("status", "closed", 1),
    ("severity", "critical", 1),
    ("severity", "major", 1),
    ("outcome", "successful", 1),
    ("outcome", "failed", 0),
])
def test_supplierperf_plan_register_each_filter_narrows(
        client_a, supplierperf_plan_draft_a, supplierperf_plan_overdue_a,
        supplierperf_plan_closed_a, param, value, expect):
    response = client_a.get(reverse("procurement:improvementplan_list"), {param: value})
    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == expect


# =================================================================================================
# 2. The guard regressions — a junk query string IGNORES the filter, it never empties or 500s
# =================================================================================================

def test_supplierperf_score_register_junk_source_keeps_the_baseline_rows(
        client_a, supplierperf_score_manual_a, supplierperf_score_derived_a):
    """``source_at_time`` is a FROZEN copy declared WITHOUT ``choices``, so ``crud_list``'s enum
    guard disables itself on it and the raw GET value used to reach ``.filter()`` — matching
    nothing and wiping a register that ``?band=zzz`` on the same page rendered in full.

    The answer every other filter in the app gives an unrecognised value: skip it (L11).
    """
    url = reverse("procurement:supplierkpiscore_list")
    baseline = len(_supplierperf_pks(client_a.get(url)))
    assert baseline == 2

    for junk in ("zzz", "MANUAL", "derived; DROP", "0", "%", "manual "):
        response = client_a.get(url, {"source": junk})
        assert response.status_code == 200, junk
        assert len(_supplierperf_pks(response)) == baseline, (
            f"?source={junk!r} emptied the score register instead of skipping the filter")


def test_supplierperf_score_register_junk_band_and_fk_params_keep_the_baseline_rows(
        client_a, supplierperf_score_manual_a, supplierperf_score_derived_a):
    url = reverse("procurement:supplierkpiscore_list")
    for params in ({"band": "zzz"}, {"kpi": "abc"}, {"kpi": "0"}, {"scorecard": "²"},
                   {"scorecard": "9" * 40}, {"kpi": "-1"}):
        response = client_a.get(url, params)
        assert response.status_code == 200, params
        assert len(_supplierperf_pks(response)) == 2, params


def test_supplierperf_kpi_register_junk_category_keeps_the_baseline_rows(
        client_a, supplierperf_kpi_manual_a, supplierperf_kpi_derived_a):
    """``?category=abc`` — a hand-edited query string, a stale bookmark or a renamed choice — is
    NOT a narrowing request, so the register still renders its rows (L11)."""
    url = reverse("procurement:supplierkpi_list")
    for junk in ("abc", "DELIVERY", "1", "delivery'--", ""):
        response = client_a.get(url, {"category": junk})
        assert response.status_code == 200, junk
        assert len(_supplierperf_pks(response)) == 2, f"?category={junk!r} emptied the catalogue"


@pytest.mark.parametrize("year", ["0", "10000", "99999", "-1", "abc", "²", "9" * 40, "",
                                  "1e5", "2026.0"])
def test_supplierperf_evaluation_register_impossible_year_is_200_not_500(
        client_a, supplierperf_scorecard_draft_a, year):
    """The uncaught ``ValueError`` this review found. ``period_end__year`` is the app's only
    ``__year`` int filter and it is NOT a pk lookup, so ``crud_list``'s zero-skip does not catch
    it and ``as_db_int`` range-checks the COLUMN, not the calendar — Django then handed the value
    to ``datetime.date(value, 1, 1)`` inside the backend, which raises ``year 0 is out of range``.

    L11 says a hand-edited query string SKIPS the filter; it never raises.
    """
    response = client_a.get(reverse("procurement:supplierevaluation_list"), {"year": year})
    assert response.status_code == 200, f"?year={year!r} did not return 200"
    assert _supplierperf_pks(response) == [supplierperf_scorecard_draft_a.pk], (
        f"?year={year!r} narrowed the register instead of being ignored")


def test_supplierperf_evaluation_register_junk_supplier_and_status_keep_the_rows(
        client_a, supplierperf_scorecard_draft_a):
    url = reverse("procurement:supplierevaluation_list")
    for params in ({"supplier": "abc"}, {"supplier": "0"}, {"status": "zzz"},
                   {"status": "Draft"}, {"supplier": "9" * 40}):
        response = client_a.get(url, params)
        assert response.status_code == 200, params
        assert _supplierperf_pks(response) == [supplierperf_scorecard_draft_a.pk], params


def test_supplierperf_benchmark_board_junk_category_keeps_the_whole_cohort(client_a, tenant_a):
    """``?category=zzz`` reached the compute layer and silently emptied the whole board, while
    ``?tier=zzz`` on the SAME filter bar reset itself and rendered the full cohort. ``category``
    is free text on ``scm.SupplierProfile``, so the legal set is the tenant's own distinct
    values — computed once and reused as the dropdown, so filter and picker cannot drift."""
    _supplierperf_view_cohort(tenant_a, 3)
    url = reverse("procurement:supplier_benchmark_board")
    baseline = len(client_a.get(url).context["rows"])
    assert baseline == 3

    for junk in ("zzz", "Precision", "1", "'; DROP TABLE", "x" * 500):
        response = client_a.get(url, {"category": junk})
        assert response.status_code == 200, junk
        assert len(response.context["rows"]) == baseline, (
            f"?category={junk!r} emptied the benchmark board instead of resetting the filter")
        assert response.context["selected_category"] == ""


def test_supplierperf_benchmark_board_junk_tier_and_period_keep_the_whole_cohort(client_a,
                                                                                tenant_a):
    _supplierperf_view_cohort(tenant_a, 3)
    url = reverse("procurement:supplier_benchmark_board")
    for params in ({"tier": "zzz"}, {"tier": "STRATEGIC"}, {"period": "lol"},
                   {"period": "2026-02-31"}, {"period": ""}):
        response = client_a.get(url, params)
        assert response.status_code == 200, params
        assert len(response.context["rows"]) == 3, params


def test_supplierperf_benchmark_board_real_category_and_tier_do_narrow(client_a, tenant_a):
    """The other half of the guard: a value the dropdown DOES offer must still filter."""
    _supplierperf_view_cohort(tenant_a, 2)
    odd = _supplierperf_view_party(tenant_a, "Transactional Tooling")
    _supplierperf_view_profile(tenant_a, odd, tier="transactional", category="Tooling")
    _supplierperf_view_scorecard(tenant_a, odd)
    url = reverse("procurement:supplier_benchmark_board")

    assert len(client_a.get(url).context["rows"]) == 3
    narrowed = client_a.get(url, {"category": "Tooling"})
    assert [row["supplier_id"] for row in narrowed.context["rows"]] == [odd.pk]
    assert narrowed.context["selected_category"] == "Tooling"
    by_tier = client_a.get(url, {"tier": "transactional"})
    assert [row["supplier_id"] for row in by_tier.context["rows"]] == [odd.pk]


@pytest.mark.parametrize("params", [{"supplier": "abc"}, {"supplier": "0"}, {"supplier": "²"},
                                    {"supplier": "9" * 40}, {"kpi": "abc"}, {"kpi": "0"}])
def test_supplierperf_trend_board_junk_pickers_are_200_not_500(client_a, tenant_a, params):
    _supplierperf_view_cohort(tenant_a, 1)
    response = client_a.get(reverse("procurement:supplier_trend_board"), params)
    assert response.status_code == 200
    assert response.context["selected_supplier"] is None or "kpi" in params


@pytest.mark.parametrize("params", [{"supplier": "abc"}, {"period": "lol"},
                                    {"period": "2026-13-01"}, {"supplier": "9" * 40}])
def test_supplierperf_perception_gap_junk_pickers_are_200_not_500(client_a, tenant_a, params):
    response = client_a.get(reverse("procurement:supplier_perception_gap"), params)
    assert response.status_code == 200


# =================================================================================================
# 3. Pagination — page 2, past the end, and junk
# =================================================================================================

def test_supplierperf_kpi_register_paginates_page_two_and_past_the_end(client_a, tenant_a):
    made = [_supplierperf_view_kpi(tenant_a, f"PAG-{index:03d}", display_order=10)
            for index in range(18)]
    url = reverse("procurement:supplierkpi_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})
    past_end = client_a.get(url, {"page": "999"})
    junk = client_a.get(url, {"page": "abc"})

    assert page_one.status_code == page_two.status_code == 200
    assert len(_supplierperf_pks(page_one)) == 15
    assert len(_supplierperf_pks(page_two)) == 3
    assert len(set(_supplierperf_pks(page_one) + _supplierperf_pks(page_two))) == 18
    assert past_end.status_code == 200 and past_end.context["page_obj"].number == 2
    assert junk.status_code == 200 and junk.context["page_obj"].number == 1
    assert len(made) == 18


@pytest.mark.parametrize("name", ["supplierkpi_list", "supplierevaluation_list",
                                  "supplierkpiscore_list", "supplierfeedback_list",
                                  "improvementplan_list"])
@pytest.mark.parametrize("page", ["2", "999", "abc", "0", "-1", "9" * 40])
def test_supplierperf_every_register_survives_any_page_parameter(client_a, name, page):
    """L9 — the pagination guard, swept over all five registers on an EMPTY workspace too: a
    Paginator handed page 2 of a one-page list must fall back, not raise."""
    response = client_a.get(reverse(f"procurement:{name}"), {"page": page})
    assert response.status_code == 200, (name, page)
    assert response.context["page_obj"].number >= 1


def test_supplierperf_score_register_paginates_page_two(client_a, tenant_a,
                                                        supplierperf_scorecard_draft_a):
    for index in range(18):
        kpi = _supplierperf_view_kpi(tenant_a, f"SCP-{index:03d}")
        _supplierperf_view_score(tenant_a, supplierperf_scorecard_draft_a, kpi)
    url = reverse("procurement:supplierkpiscore_list")

    assert len(_supplierperf_pks(client_a.get(url))) == 15
    assert len(_supplierperf_pks(client_a.get(url, {"page": "2"}))) == 3


# =================================================================================================
# 4. Create / edit / delete over HTTP
# =================================================================================================

def test_supplierperf_kpi_create_saves_into_the_request_tenant(client_a, tenant_a, admin_user):
    url = reverse("procurement:supplierkpi_create")
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {
        "code": "HTTP-01", "name": "Created over HTTP", "description": "",
        "category": "quality", "unit": "pct", "direction": "higher_is_better",
        "source": "manual", "derived_metric": "", "weight": "12", "target_value": "98",
        "warning_threshold": "95", "critical_threshold": "90", "scoring_method": "band",
        "maps_to_dimension": "quality", "applies_to": "all", "applies_to_tier": "",
        "review_frequency": "quarterly", "industry_benchmark_value": "",
        "owner": str(admin_user.pk), "display_order": "50", "is_active": "on", "notes": ""})

    assert response.status_code == 302
    obj = SupplierKpi.objects.get(code="HTTP-01")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("SKP-")
    assert obj.owner_id == admin_user.pk


def test_supplierperf_kpi_detail_lists_its_measured_history_plans_and_feedback(
        client_a, supplierperf_kpi_survey_a, supplierperf_score_manual_a,
        supplierperf_feedback_submitted_a, tenant_a, supplierperf_supplier_a):
    """Three bounded, tenant-scoped lists hang off one definition. Each is capped and each
    reports its OWN truncation under its OWN key — one flag next to one cap described three
    lists, two of which are cut at 20 while the page said 50."""
    plan = _supplierperf_view_plan(tenant_a, supplierperf_supplier_a,
                                   kpi=supplierperf_kpi_survey_a)
    response = client_a.get(reverse("procurement:supplierkpi_detail",
                                    args=[supplierperf_kpi_survey_a.pk]))

    assert response.status_code == 200
    assert response.context["obj"].pk == supplierperf_kpi_survey_a.pk
    assert list(response.context["feedback_rows"]) == [supplierperf_feedback_submitted_a]
    assert list(response.context["plans"]) == [plan]
    assert response.context["row_cap"] == performance.DETAIL_ROW_CAP
    assert response.context["truncated"] is False
    assert response.context["related_truncated"] is False
    assert response.context["related_cap"] != response.context["row_cap"]
    assert escape(performance.BENCHMARK_NOTE) in _supplierperf_html(response)


def test_supplierperf_kpi_edit_retunes_the_definition_without_rewriting_history(
        client_a, supplierperf_kpi_manual_a, supplierperf_score_manual_a):
    """Editing a KPI changes the NEXT period. The score line freezes weight, target, direction,
    source and unit, so a retune leaves a closed period exactly as it was read."""
    url = reverse("procurement:supplierkpi_edit", args=[supplierperf_kpi_manual_a.pk])
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {
        "code": supplierperf_kpi_manual_a.code, "name": "Renamed after the retune",
        "description": "", "category": "cost", "unit": "days",
        "direction": "higher_is_better", "source": "manual", "derived_metric": "",
        "weight": "44", "target_value": "95", "warning_threshold": "90",
        "critical_threshold": "85", "scoring_method": "band", "maps_to_dimension": "delivery",
        "applies_to": "all", "applies_to_tier": "", "review_frequency": "annual",
        "industry_benchmark_value": "", "owner": "", "display_order": "10",
        "is_active": "on", "notes": ""})

    assert response.status_code == 302
    supplierperf_kpi_manual_a.refresh_from_db()
    supplierperf_score_manual_a.refresh_from_db()
    assert supplierperf_kpi_manual_a.weight == 44
    assert supplierperf_kpi_manual_a.name == "Renamed after the retune"
    assert supplierperf_score_manual_a.weight_applied == 20
    assert supplierperf_score_manual_a.kpi_name == "Innovation and continuous improvement"
    assert supplierperf_score_manual_a.unit_at_time == "pct"


def test_supplierperf_kpi_delete_removes_a_definition_nothing_has_measured(
        client_a, supplierperf_kpi_manual_a):
    url = reverse("procurement:supplierkpi_delete", args=[supplierperf_kpi_manual_a.pk])
    assert client_a.get(url).status_code == 405, "delete must be POST-only"
    assert SupplierKpi.objects.filter(pk=supplierperf_kpi_manual_a.pk).exists()

    response = client_a.post(url)
    assert response.status_code == 302
    assert not SupplierKpi.objects.filter(pk=supplierperf_kpi_manual_a.pk).exists()


def test_supplierperf_kpi_delete_is_refused_with_a_message_when_history_protects_it(
        client_a, supplierperf_kpi_manual_a, supplierperf_score_manual_a):
    """``SupplierKpiScore.kpi`` is ``PROTECT`` on purpose. The refusal has to arrive as a MESSAGE,
    not as a 500 — retirement is ``is_active=False``, which keeps every figure ever taken."""
    response = client_a.post(reverse("procurement:supplierkpi_delete",
                                     args=[supplierperf_kpi_manual_a.pk]))

    assert response.status_code == 302
    assert SupplierKpi.objects.filter(pk=supplierperf_kpi_manual_a.pk).exists()
    assert SupplierKpiScore.objects.filter(pk=supplierperf_score_manual_a.pk).exists()
    assert any("cannot be deleted" in note for note in _supplierperf_notes(response))


def test_supplierperf_score_edit_is_refused_on_a_derived_line_before_any_form_work(
        client_a, supplierperf_score_derived_a):
    """The VIEW is the gate, not the form: a derived line is recomputed by Generate from
    evidence, and typing over it would leave a figure no resolver stands behind."""
    url = reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_derived_a.pk])
    get_response = client_a.get(url)
    post_response = client_a.post(url, {"measured_value": "1", "comment": "typed"})

    assert get_response.status_code == 302
    assert post_response.status_code == 302
    supplierperf_score_derived_a.refresh_from_db()
    assert supplierperf_score_derived_a.measured_value == Decimal("88.0000")
    assert any("Only a manual-entry line can be edited by hand" in note
               for note in _supplierperf_notes(post_response))


def test_supplierperf_score_edit_saves_a_manual_line_and_redirects_to_its_detail(
        client_a, supplierperf_score_manual_a):
    url = reverse("procurement:supplierkpiscore_edit", args=[supplierperf_score_manual_a.pk])
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {"measured_value": "97", "comment": "Counted by hand."})
    assert response.status_code == 302
    assert response["Location"] == reverse("procurement:supplierkpiscore_detail",
                                           args=[supplierperf_score_manual_a.pk])
    supplierperf_score_manual_a.refresh_from_db()
    assert supplierperf_score_manual_a.measured_value == Decimal("97.0000")
    assert supplierperf_score_manual_a.band == "ok"
    assert supplierperf_score_manual_a.score == Decimal("100.00")


def test_supplierperf_score_detail_flattens_the_breakdown_without_a_python_repr(
        client_a, tenant_a, supplierperf_scorecard_draft_a, supplierperf_kpi_derived_a):
    """``window`` is stored as ``[str(start), str(end)]``, so ``str()`` under a column headed
    *Value* printed ``['2026-05-11', '2026-08-09']`` on 40 of 41 seeded lines. A two-item
    sequence now reads as a range."""
    line = _supplierperf_view_score(
        tenant_a, supplierperf_scorecard_draft_a, supplierperf_kpi_derived_a,
        breakdown={"window": ["2026-05-11", "2026-08-09"], "rows": 12, "metric": "otd"})
    response = client_a.get(reverse("procurement:supplierkpiscore_detail", args=[line.pk]))
    rows = {row["key"]: row["value"] for row in response.context["breakdown_rows"]}

    assert response.status_code == 200
    assert rows["window"] == "2026-05-11 to 2026-08-09"
    assert rows["rows"] == "12"
    assert "['2026-05-11'" not in _supplierperf_html(response)
    assert response.context["can_edit"] is False


def test_supplierperf_score_delete_only_touches_a_draft_periods_lines(
        client_a, tenant_a, supplierperf_supplier_a, supplierperf_kpi_manual_a,
        supplierperf_scorecard_draft_a, supplierperf_score_manual_a):
    """Writing a line takes an admin AND a draft scorecard; deleting one used to be
    ``@login_required`` and nothing else, so the evidence behind a PUBLISHED grade could be
    POSTed away leaving the dimension columns standing with nothing under them."""
    published = _supplierperf_view_scorecard(tenant_a, supplierperf_supplier_a,
                                             status="published")
    frozen = _supplierperf_view_score(tenant_a, published, supplierperf_kpi_manual_a)

    refused = client_a.post(reverse("procurement:supplierkpiscore_delete", args=[frozen.pk]))
    assert refused.status_code == 302
    assert SupplierKpiScore.objects.filter(pk=frozen.pk).exists()
    assert any("cannot be deleted" in note for note in _supplierperf_notes(refused))

    assert client_a.get(reverse("procurement:supplierkpiscore_delete",
                                args=[supplierperf_score_manual_a.pk])).status_code == 405
    allowed = client_a.post(reverse("procurement:supplierkpiscore_delete",
                                    args=[supplierperf_score_manual_a.pk]))
    assert allowed.status_code == 302
    assert allowed["Location"] == reverse("procurement:supplierevaluation_detail",
                                          args=[supplierperf_scorecard_draft_a.pk])
    assert not SupplierKpiScore.objects.filter(pk=supplierperf_score_manual_a.pk).exists()


def test_supplierperf_feedback_create_stamps_the_requester_from_the_session(
        client_a, tenant_a, admin_user, supplierperf_supplier_a):
    """Hand-rolled rather than ``crud_create`` precisely so ``requested_by`` comes from
    ``request.user`` — an authorship stamp taken from the form would be a claim the requester
    could edit."""
    url = reverse("procurement:supplierfeedback_create")
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {
        "supplier": str(supplierperf_supplier_a.pk), "scorecard": "", "kpi": "",
        "period_start": _supplierperf_day(-30).isoformat(),
        "period_end": _supplierperf_day().isoformat(), "respondent_kind": "internal",
        "respondent_function": "operations", "respondent": "", "respondent_name": "R. Iqbal",
        "rating": "", "importance": "6", "due_date": _supplierperf_day(14).isoformat(),
        "comment": ""})

    assert response.status_code == 302
    obj = SupplierFeedback.objects.get(respondent_name="R. Iqbal")
    assert obj.tenant_id == tenant_a.pk
    assert obj.requested_by_id == admin_user.pk
    assert obj.status == "requested"
    assert obj.number.startswith("SFB-")


def test_supplierperf_feedback_edit_is_refused_once_the_answer_is_in(
        client_a, supplierperf_feedback_submitted_a):
    """``rating`` IS on the form, so an editable submitted response let any member overwrite an
    answer somebody gave — moving the survey aggregate and the perception-gap board silently."""
    url = reverse("procurement:supplierfeedback_edit",
                  args=[supplierperf_feedback_submitted_a.pk])
    response = client_a.get(url)

    assert response.status_code == 302
    assert any("frozen" in note for note in _supplierperf_notes(response))
    supplierperf_feedback_submitted_a.refresh_from_db()
    assert supplierperf_feedback_submitted_a.rating == 4


def test_supplierperf_feedback_edit_works_while_the_request_is_outstanding(
        client_a, supplierperf_feedback_requested_a, supplierperf_supplier_a,
        supplierperf_scorecard_draft_a, supplierperf_kpi_survey_a, member_user):
    url = reverse("procurement:supplierfeedback_edit",
                  args=[supplierperf_feedback_requested_a.pk])
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {
        "supplier": str(supplierperf_supplier_a.pk),
        "scorecard": str(supplierperf_scorecard_draft_a.pk),
        "kpi": str(supplierperf_kpi_survey_a.pk),
        "period_start": _supplierperf_day(-89).isoformat(),
        "period_end": _supplierperf_day().isoformat(), "respondent_kind": "internal",
        "respondent_function": "finance", "respondent": str(member_user.pk),
        "respondent_name": "", "rating": "", "importance": "9",
        "due_date": _supplierperf_day(3).isoformat(), "comment": "Chased twice."})

    assert response.status_code == 302
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.importance == 9
    assert supplierperf_feedback_requested_a.respondent_function == "finance"
    assert supplierperf_feedback_requested_a.status == "requested"


def test_supplierperf_plan_create_opens_a_draft(client_a, tenant_a, supplierperf_supplier_a):
    url = reverse("procurement:improvementplan_create")
    assert client_a.get(url).status_code == 200

    response = client_a.post(url, {
        "title": "Opened over HTTP", "supplier": str(supplierperf_supplier_a.pk),
        "scorecard": "", "kpi": "", "severity": "minor",
        "finding": "Two short shipments.", "root_cause": "", "corrective_actions": "",
        "support_provided": "", "success_criteria": "",
        "start_date": _supplierperf_day().isoformat(),
        "target_close_date": _supplierperf_day(45).isoformat(), "next_review_date": "",
        "extended_close_date": "", "owner": "", "supplier_owner_name": "",
        "supplier_owner_email": "", "escalated_suspension": "", "evidence_url": ""})

    assert response.status_code == 302
    obj = SupplierImprovementPlan.objects.get(title="Opened over HTTP")
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "draft"
    assert obj.outcome == ""
    assert obj.number.startswith("SIP-")


def test_supplierperf_plan_edit_and_delete_are_refused_once_the_plan_is_closed(
        client_a, supplierperf_plan_closed_a):
    """A closed plan carries ``verified_by`` / ``verified_at`` against its finding and its dates,
    so leaving it editable let any member rewrite the content a signature sits beside — and a
    closed plan IS the history an escalation stands on."""
    edit = client_a.get(reverse("procurement:improvementplan_edit",
                                args=[supplierperf_plan_closed_a.pk]))
    delete = client_a.post(reverse("procurement:improvementplan_delete",
                                   args=[supplierperf_plan_closed_a.pk]))

    assert edit.status_code == 302
    assert delete.status_code == 302
    assert SupplierImprovementPlan.objects.filter(pk=supplierperf_plan_closed_a.pk).exists()
    assert any("frozen" in note for note in _supplierperf_notes(edit))
    assert any("cannot be deleted" in note for note in _supplierperf_notes(delete))


def test_supplierperf_plan_delete_removes_an_open_plan(client_a, supplierperf_plan_draft_a):
    url = reverse("procurement:improvementplan_delete", args=[supplierperf_plan_draft_a.pk])
    assert client_a.get(url).status_code == 405
    assert SupplierImprovementPlan.objects.filter(pk=supplierperf_plan_draft_a.pk).exists()

    assert client_a.post(url).status_code == 302
    assert not SupplierImprovementPlan.objects.filter(pk=supplierperf_plan_draft_a.pk).exists()


def test_supplierperf_plan_evidence_is_served_as_an_authenticated_attachment(
        client_a, supplierperf_plan_draft_a, settings, tmp_path):
    """``evidence.url`` is a raw ``MEDIA_URL`` path served by the web server, so linking it hands
    an NCR pack to anybody who can guess a filename. Two headers do the rest: ``attachment``
    (never rendered on this origin) and ``nosniff`` (``SECURE_CONTENT_TYPE_NOSNIFF`` only applies
    outside DEBUG, so it is set explicitly)."""
    settings.MEDIA_ROOT = str(tmp_path)
    supplierperf_plan_draft_a.evidence.save("capa-pack.pdf", ContentFile(b"%PDF-1.4 evidence"),
                                            save=True)

    response = client_a.get(reverse("procurement:improvementplan_evidence",
                                    args=[supplierperf_plan_draft_a.pk]))
    try:
        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment")
        assert "capa-pack" in response["Content-Disposition"]
        assert response["X-Content-Type-Options"] == "nosniff"
        assert b"".join(response.streaming_content) == b"%PDF-1.4 evidence"
    finally:
        response.close()


def test_supplierperf_plan_evidence_without_a_file_is_a_message_not_a_500(
        client_a, supplierperf_plan_closed_a):
    """The closed fixture's proof is a LINK, not an upload — ``has_evidence`` is true and the
    download route still has nothing to hand back."""
    response = client_a.get(reverse("procurement:improvementplan_evidence",
                                    args=[supplierperf_plan_closed_a.pk]))
    assert response.status_code == 302
    assert supplierperf_plan_closed_a.has_evidence is True
    assert any("no uploaded evidence file" in note for note in _supplierperf_notes(response))


# =================================================================================================
# 5. The one-way door — supplierevaluation_generate
# =================================================================================================

def test_supplierperf_generate_is_post_only(client_a, supplierperf_scorecard_draft_a,
                                            supplierperf_kpi_manual_a):
    response = client_a.get(reverse("procurement:supplierevaluation_generate",
                                    args=[supplierperf_scorecard_draft_a.pk]))
    assert response.status_code == 405, "a prefetching browser must not fire the one-way door"
    supplierperf_scorecard_draft_a.refresh_from_db()
    assert supplierperf_scorecard_draft_a.manual_override is False
    assert SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a).count() == 0


def test_supplierperf_generate_writes_one_line_per_applicable_kpi_and_hands_the_card_over(
        client_a, supplierperf_scorecard_draft_a, supplierperf_kpi_manual_a,
        supplierperf_kpi_survey_a, supplierperf_feedback_submitted_a):
    response = client_a.post(reverse("procurement:supplierevaluation_generate",
                                     args=[supplierperf_scorecard_draft_a.pk]))

    assert response.status_code == 302
    lines = {line.kpi_id: line for line in
             SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a)}
    assert set(lines) == {supplierperf_kpi_manual_a.pk, supplierperf_kpi_survey_a.pk}
    # The survey KPI reads the ONE submitted internal response: rating 4 -> 75 on the 0-100
    # scale, importance 8, direct scoring -> 75.00 "ok".
    survey = lines[supplierperf_kpi_survey_a.pk]
    assert survey.measured_value == Decimal("75.00")
    assert survey.score == Decimal("75.00") and survey.band == "ok"
    assert survey.respondent_count == 1
    assert survey.source_at_time == "survey"
    # A manual KPI with no prior line is written EMPTY and waits for a human.
    manual = lines[supplierperf_kpi_manual_a.pk]
    assert manual.measured_value is None and manual.score is None
    assert manual.band == "unknown"

    supplierperf_scorecard_draft_a.refresh_from_db()
    assert supplierperf_scorecard_draft_a.manual_override is True
    assert supplierperf_scorecard_draft_a.responsiveness_score == Decimal("75.00")
    assert any("Generated 2 KPI line(s)" in note for note in _supplierperf_notes(response))


def test_supplierperf_generate_is_idempotent_and_never_doubles_a_scorecard(
        client_a, supplierperf_scorecard_draft_a, supplierperf_kpi_manual_a,
        supplierperf_kpi_survey_a, supplierperf_feedback_submitted_a):
    """``unique_together (tenant, scorecard, kpi)`` is the safety on the Generate button — a
    second press UPDATES each line in place."""
    url = reverse("procurement:supplierevaluation_generate",
                  args=[supplierperf_scorecard_draft_a.pk])
    client_a.post(url)
    first = {line.kpi_id: line.pk for line in
             SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a)}
    client_a.post(url)
    client_a.post(url)
    second = {line.kpi_id: line.pk for line in
              SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a)}

    assert len(first) == 2
    assert first == second, "pressing Generate again created new rows instead of updating them"


def test_supplierperf_generate_refuses_a_published_period_and_prints_the_reason(
        client_a, supplierperf_scorecard_published_a, supplierperf_kpi_manual_a):
    """A closed period is closed: ZERO rows written, ``manual_override`` untouched, and the
    sentence printed on the page the operator lands on."""
    response = client_a.post(reverse("procurement:supplierevaluation_generate",
                                     args=[supplierperf_scorecard_published_a.pk]),
                             follow=True)

    assert response.status_code == 200
    assert SupplierKpiScore.objects.filter(
        scorecard=supplierperf_scorecard_published_a).count() == 0
    supplierperf_scorecard_published_a.refresh_from_db()
    assert supplierperf_scorecard_published_a.manual_override is False
    assert any("only a draft may be generated onto" in note
               for note in _supplierperf_notes(response))
    assert "only a draft may be generated onto" in _supplierperf_html(response)


def test_supplierperf_generate_refuses_an_archived_period(
        client_a, supplierperf_scorecard_archived_a, supplierperf_kpi_manual_a):
    response = client_a.post(reverse("procurement:supplierevaluation_generate",
                                     args=[supplierperf_scorecard_archived_a.pk]))
    assert response.status_code == 302
    supplierperf_scorecard_archived_a.refresh_from_db()
    assert supplierperf_scorecard_archived_a.manual_override is False
    assert SupplierKpiScore.objects.filter(
        scorecard=supplierperf_scorecard_archived_a).count() == 0


def test_supplierperf_generate_with_no_applicable_kpi_leaves_manual_override_false(
        client_a, supplierperf_scorecard_draft_a):
    """THE Critical. Setting ``manual_override`` stops ``recompute_from_signals()`` for good, so a
    run that writes NO line would hand the scorecard to 6.16 with zero evidence AND take SCM's
    engine off it — a card that graded from signals becomes permanently unscoreable by either
    engine, and the operator is told it worked. Refusing writes nothing at all."""
    assert SupplierKpi.objects.filter(tenant=supplierperf_scorecard_draft_a.tenant).count() == 0
    response = client_a.post(reverse("procurement:supplierevaluation_generate",
                                     args=[supplierperf_scorecard_draft_a.pk]))

    assert response.status_code == 302
    supplierperf_scorecard_draft_a.refresh_from_db()
    assert supplierperf_scorecard_draft_a.manual_override is False
    assert SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a).count() == 0
    assert any("No active KPI applies to this supplier" in note
               for note in _supplierperf_notes(response))


def test_supplierperf_generate_with_only_a_tier_kpi_and_an_unprofiled_supplier_is_refused(
        client_a, tenant_a, supplierperf_supplier2_a, supplierperf_kpi_tier_a):
    """The second path into the empty run: an ``applies_to="tier"`` catalogue and a supplier with
    no ``scm.SupplierProfile``. Guessing a tier would measure it against a standard nobody
    agreed to, so ``applicable_kpis`` returns nothing and generate refuses."""
    card = _supplierperf_view_scorecard(tenant_a, supplierperf_supplier2_a)
    response = client_a.post(reverse("procurement:supplierevaluation_generate", args=[card.pk]))

    assert response.status_code == 302
    card.refresh_from_db()
    assert card.manual_override is False
    assert SupplierKpiScore.objects.filter(scorecard=card).count() == 0


def test_supplierperf_generate_never_picks_up_a_retired_kpi(
        client_a, supplierperf_scorecard_draft_a, supplierperf_kpi_manual_a,
        supplierperf_kpi_inactive_a):
    """Retirement is ``is_active=False``, never a delete — and a retired definition must stop
    being measured while every figure ever taken under it stays readable."""
    client_a.post(reverse("procurement:supplierevaluation_generate",
                          args=[supplierperf_scorecard_draft_a.pk]))
    written = set(SupplierKpiScore.objects
                  .filter(scorecard=supplierperf_scorecard_draft_a)
                  .values_list("kpi_id", flat=True))
    assert written == {supplierperf_kpi_manual_a.pk}


def test_supplierperf_evaluation_detail_shows_the_composite_beside_scms_own_blend(
        client_a, tenant_a, supplierperf_supplier_a, supplierperf_scorecard_draft_a):
    """The two are different numbers ON PURPOSE — the composite is the weighted mean of every
    scored line, the overall is SCM's blend of the four dimension columns — and showing both is
    how an operator sees that generate did what it said it would."""
    mapped = _supplierperf_view_kpi(tenant_a, "DET-A", weight=30)
    unmapped = _supplierperf_view_kpi(tenant_a, "DET-B", weight=10, maps_to_dimension="",
                                      display_order=20)
    _supplierperf_view_score(tenant_a, supplierperf_scorecard_draft_a, mapped,
                             score=Decimal("90.00"), band="ok")
    _supplierperf_view_score(tenant_a, supplierperf_scorecard_draft_a, unmapped,
                             score=Decimal("30.00"), band="critical")
    supplierperf_scorecard_draft_a.delivery_score = Decimal("90.00")
    supplierperf_scorecard_draft_a.save(update_fields=["delivery_score", "updated_at"])
    supplierperf_scorecard_draft_a.recompute_overall()

    response = client_a.get(reverse("procurement:supplierevaluation_detail",
                                    args=[supplierperf_scorecard_draft_a.pk]))
    composite = response.context["composite"]

    assert response.status_code == 200
    # (90*30 + 30*10) / 40 = 75.00
    assert composite["weighted_total"] == Decimal("75.00")
    assert composite["weight_total"] == 40
    assert composite["scored_lines"] == 2 and composite["unscored_lines"] == 0
    assert composite["overall"] == Decimal("90.00")
    assert response.context["dimension_map"]["delivery"]["kpi_count"] == 1
    assert response.context["dimension_map"]["delivery"]["score"] == Decimal("90.00")
    assert response.context["can_generate"] is True
    assert response.context["refusal_reason"] == ""


def test_supplierperf_evaluation_detail_prints_the_refusal_on_a_closed_period(
        client_a, supplierperf_scorecard_published_a):
    response = client_a.get(reverse("procurement:supplierevaluation_detail",
                                    args=[supplierperf_scorecard_published_a.pk]))
    assert response.status_code == 200
    assert response.context["can_generate"] is False
    assert "only a draft may be generated onto" in response.context["refusal_reason"]
    assert response.context["refusal_reason"] in _supplierperf_html(response)


def test_supplierperf_evaluation_detail_tells_a_member_the_button_is_an_admin_action(
        member_client, supplierperf_scorecard_draft_a):
    """A button that renders for everybody and then 403s is worse than no button, so the flag
    tests ``_is_admin`` and the page prints WHY rather than claiming the period is closed."""
    response = member_client.get(reverse("procurement:supplierevaluation_detail",
                                         args=[supplierperf_scorecard_draft_a.pk]))
    assert response.status_code == 200
    assert response.context["can_generate"] is False
    assert "workspace-admin action" in response.context["refusal_reason"]


# =================================================================================================
# 6. The state machines — three feedback verbs, five plan verbs
# =================================================================================================

@pytest.mark.parametrize("name", ["supplierfeedback_submit", "supplierfeedback_decline",
                                  "supplierfeedback_expire", "supplierfeedback_delete"])
def test_supplierperf_every_feedback_verb_405s_on_get(client_a, name,
                                                      supplierperf_feedback_requested_a):
    response = client_a.get(reverse(f"procurement:{name}",
                                    args=[supplierperf_feedback_requested_a.pk]))
    assert response.status_code == 405, f"{name} moved state on a GET"
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == "requested"
    assert SupplierFeedback.objects.filter(pk=supplierperf_feedback_requested_a.pk).exists()


def test_supplierperf_feedback_submit_files_the_answer_and_stamps_the_moment(
        client_a, supplierperf_feedback_requested_a):
    before = timezone.now()
    response = client_a.post(reverse("procurement:supplierfeedback_submit",
                                     args=[supplierperf_feedback_requested_a.pk]),
                             {"rating": "5"})

    assert response.status_code == 302
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == "submitted"
    assert supplierperf_feedback_requested_a.rating == 5
    assert supplierperf_feedback_requested_a.submitted_at >= before
    assert any("submitted at 5 out of 5" in note for note in _supplierperf_notes(response))


@pytest.mark.parametrize("posted", ["0", "6", "-1", "abc", "²", "9" * 5000, "3.5"])
def test_supplierperf_feedback_submit_refuses_a_rating_off_the_scale(
        client_a, supplierperf_feedback_requested_a, posted):
    """The 5,000-digit case is the one that 500'd: ``isdecimal()`` is True for it and ``int()``
    then raises ``Exceeds the limit (4300) for integer string conversion``. ``as_db_int``
    length-checks BEFORE it parses — this verb goes through no form, so nothing else did."""
    response = client_a.post(reverse("procurement:supplierfeedback_submit",
                                     args=[supplierperf_feedback_requested_a.pk]),
                             {"rating": posted})
    assert response.status_code == 302, f"rating={posted[:12]!r} did not return a redirect"
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == "requested"
    assert supplierperf_feedback_requested_a.rating is None
    assert any("not one of the ratings on the 1-5 scale" in note
               for note in _supplierperf_notes(response))


def test_supplierperf_feedback_submit_uses_the_rating_already_on_the_row(
        client_a, tenant_a, supplierperf_supplier_a):
    """A paper survey filed complete on the create page carries its rating already, so the verb
    takes it from the row when the POST body has none."""
    row = _supplierperf_view_feedback(tenant_a, supplierperf_supplier_a, rating=3,
                                      respondent_name="Filed offline")
    response = client_a.post(reverse("procurement:supplierfeedback_submit", args=[row.pk]))

    assert response.status_code == 302
    row.refresh_from_db()
    assert row.status == "submitted" and row.rating == 3


@pytest.mark.parametrize("verb,expected", [("supplierfeedback_decline", "declined"),
                                           ("supplierfeedback_expire", "expired")])
def test_supplierperf_feedback_decline_and_expire_close_an_outstanding_request(
        client_a, supplierperf_feedback_requested_a, verb, expected):
    """Kept apart on purpose: declined means somebody said no, expired means the window closed.
    Collapsing them would make the response rate unreadable."""
    response = client_a.post(reverse(f"procurement:{verb}",
                                     args=[supplierperf_feedback_requested_a.pk]))
    assert response.status_code == 302
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == expected
    assert supplierperf_feedback_requested_a.submitted_at is None


@pytest.mark.parametrize("verb", ["supplierfeedback_submit", "supplierfeedback_decline",
                                  "supplierfeedback_expire"])
def test_supplierperf_feedback_verbs_refuse_a_replay_on_a_closed_response(
        client_a, supplierperf_feedback_submitted_a, verb):
    """A crafted POST cannot re-submit a declined request or expire a submitted answer — the
    closed response gets a message naming what it already is."""
    response = client_a.post(reverse(f"procurement:{verb}",
                                     args=[supplierperf_feedback_submitted_a.pk]),
                             {"rating": "1"})
    assert response.status_code == 302
    supplierperf_feedback_submitted_a.refresh_from_db()
    assert supplierperf_feedback_submitted_a.status == "submitted"
    assert supplierperf_feedback_submitted_a.rating == 4, "a replay overwrote a filed answer"
    assert any("is already submitted" in note for note in _supplierperf_notes(response))


def test_supplierperf_feedback_delete_removes_a_request_raised_by_mistake(
        client_a, supplierperf_feedback_overdue_a):
    response = client_a.post(reverse("procurement:supplierfeedback_delete",
                                     args=[supplierperf_feedback_overdue_a.pk]))
    assert response.status_code == 302
    assert not SupplierFeedback.objects.filter(pk=supplierperf_feedback_overdue_a.pk).exists()


def test_supplierperf_feedback_detail_flags_what_can_still_happen(
        client_a, supplierperf_feedback_requested_a, supplierperf_feedback_submitted_a):
    open_page = client_a.get(reverse("procurement:supplierfeedback_detail",
                                     args=[supplierperf_feedback_requested_a.pk]))
    closed_page = client_a.get(reverse("procurement:supplierfeedback_detail",
                                       args=[supplierperf_feedback_submitted_a.pk]))

    assert (open_page.context["can_submit"], open_page.context["can_decline"],
            open_page.context["can_expire"]) == (True, True, True)
    assert (closed_page.context["can_submit"], closed_page.context["can_decline"],
            closed_page.context["can_expire"]) == (False, False, False)


@pytest.mark.parametrize("name", ["improvementplan_activate", "improvementplan_monitor",
                                  "improvementplan_acknowledge", "improvementplan_close",
                                  "improvementplan_cancel", "improvementplan_delete"])
def test_supplierperf_every_plan_verb_405s_on_get(client_a, name, supplierperf_plan_draft_a):
    response = client_a.get(reverse(f"procurement:{name}", args=[supplierperf_plan_draft_a.pk]))
    assert response.status_code == 405, f"{name} moved state on a GET"
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "draft"
    assert SupplierImprovementPlan.objects.filter(pk=supplierperf_plan_draft_a.pk).exists()


def test_supplierperf_plan_walks_draft_to_active_to_monitoring_to_closed(
        client_a, admin_user, supplierperf_plan_draft_a):
    """The whole lifecycle over HTTP, one verb at a time, asserted on the ROW."""
    pk = supplierperf_plan_draft_a.pk

    assert client_a.post(reverse("procurement:improvementplan_activate",
                                 args=[pk])).status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "active"

    assert client_a.post(reverse("procurement:improvementplan_monitor",
                                 args=[pk])).status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "monitoring"

    closed = client_a.post(reverse("procurement:improvementplan_close", args=[pk]),
                           {"outcome": "failed", "closure_note": "Two more late shipments."})
    assert closed.status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "closed"
    assert supplierperf_plan_draft_a.outcome == "failed"
    assert supplierperf_plan_draft_a.closure_note == "Two more late shipments."
    assert supplierperf_plan_draft_a.actual_close_date == timezone.localdate()
    assert supplierperf_plan_draft_a.verified_by_id == admin_user.pk
    assert supplierperf_plan_draft_a.verified_at is not None


def test_supplierperf_plan_activate_is_draft_only_and_refuses_a_replay(
        client_a, supplierperf_plan_overdue_a):
    """Re-activating a plan already being worked would reset nothing and mean nothing."""
    response = client_a.post(reverse("procurement:improvementplan_activate",
                                     args=[supplierperf_plan_overdue_a.pk]))
    assert response.status_code == 302
    supplierperf_plan_overdue_a.refresh_from_db()
    assert supplierperf_plan_overdue_a.status == "active"
    assert any("only a plan that is draft can be activated" in note
               for note in _supplierperf_notes(response))


def test_supplierperf_plan_monitor_is_active_only(client_a, supplierperf_plan_draft_a):
    response = client_a.post(reverse("procurement:improvementplan_monitor",
                                     args=[supplierperf_plan_draft_a.pk]))
    assert response.status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "draft"


def test_supplierperf_plan_acknowledge_stamps_once_and_never_re_stamps(
        client_a, admin_user, supplierperf_plan_draft_a):
    """The ONE verb that moves no status: acknowledgement is evidence the plan was put to the
    supplier, and the FIRST date is the one that counts."""
    url = reverse("procurement:improvementplan_acknowledge", args=[supplierperf_plan_draft_a.pk])
    assert client_a.post(url).status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    first_stamp = supplierperf_plan_draft_a.acknowledged_at

    assert supplierperf_plan_draft_a.status == "draft", "acknowledge must move no status"
    assert supplierperf_plan_draft_a.acknowledged_by_id == admin_user.pk
    assert first_stamp is not None

    replay = client_a.post(url)
    assert replay.status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.acknowledged_at == first_stamp, "the stamp was re-written"
    assert any("was already acknowledged" in note for note in _supplierperf_notes(replay))


def test_supplierperf_plan_close_is_refused_on_a_draft(client_a, supplierperf_plan_draft_a):
    """There is nothing to verify on a plan that never started — cancel it instead."""
    response = client_a.post(reverse("procurement:improvementplan_close",
                                     args=[supplierperf_plan_draft_a.pk]),
                             {"outcome": "successful"})
    assert response.status_code == 302
    supplierperf_plan_draft_a.refresh_from_db()
    assert supplierperf_plan_draft_a.status == "draft"
    assert supplierperf_plan_draft_a.outcome == ""
    assert supplierperf_plan_draft_a.verified_at is None


def test_supplierperf_plan_close_caps_the_closure_note_at_four_thousand_characters(
        client_a, supplierperf_plan_overdue_a):
    """``closure_note`` is ``editable=False``, so no form and no ``full_clean()`` stands between
    the POST body and the column. A >64 KB body would hit MySQL's ``TEXT`` ceiling as an uncaught
    ``DataError`` — or, worse, be silently truncated under a signature."""
    response = client_a.post(reverse("procurement:improvementplan_close",
                                     args=[supplierperf_plan_overdue_a.pk]),
                             {"outcome": "extended", "closure_note": "x" * 70000})
    assert response.status_code == 302
    supplierperf_plan_overdue_a.refresh_from_db()
    assert supplierperf_plan_overdue_a.status == "closed"
    assert len(supplierperf_plan_overdue_a.closure_note) == 4000


def test_supplierperf_plan_close_refuses_a_replay_on_a_closed_plan(
        client_a, supplierperf_plan_closed_a):
    before = supplierperf_plan_closed_a.outcome
    response = client_a.post(reverse("procurement:improvementplan_close",
                                     args=[supplierperf_plan_closed_a.pk]),
                             {"outcome": "failed", "closure_note": "Re-signed."})
    assert response.status_code == 302
    supplierperf_plan_closed_a.refresh_from_db()
    assert supplierperf_plan_closed_a.outcome == before == "successful"
    assert supplierperf_plan_closed_a.closure_note == ""


def test_supplierperf_plan_cancel_withdraws_an_open_plan_without_an_outcome(
        client_a, supplierperf_plan_overdue_a):
    """Cancelled is not a failed closure: a cancelled plan carries NO outcome, because it has no
    ending to record. Collapsing the two would make the success rate unreadable."""
    response = client_a.post(reverse("procurement:improvementplan_cancel",
                                     args=[supplierperf_plan_overdue_a.pk]))
    assert response.status_code == 302
    supplierperf_plan_overdue_a.refresh_from_db()
    assert supplierperf_plan_overdue_a.status == "cancelled"
    assert supplierperf_plan_overdue_a.outcome == ""
    assert supplierperf_plan_overdue_a.is_overdue is False, "a cancelled plan stops being late"

    replay = client_a.post(reverse("procurement:improvementplan_cancel",
                                   args=[supplierperf_plan_overdue_a.pk]))
    supplierperf_plan_overdue_a.refresh_from_db()
    assert replay.status_code == 302
    assert supplierperf_plan_overdue_a.status == "cancelled"


def test_supplierperf_plan_detail_flags_exactly_which_verbs_are_open(
        client_a, supplierperf_plan_draft_a, supplierperf_plan_closed_a):
    draft = client_a.get(reverse("procurement:improvementplan_detail",
                                 args=[supplierperf_plan_draft_a.pk]))
    closed = client_a.get(reverse("procurement:improvementplan_detail",
                                  args=[supplierperf_plan_closed_a.pk]))

    assert draft.context["can_activate"] is True
    assert draft.context["can_monitor"] is False
    assert draft.context["can_acknowledge"] is True
    assert draft.context["can_close"] is False
    assert draft.context["can_cancel"] is True
    assert draft.context["close_refusal"] == ""

    assert closed.context["can_activate"] is False
    assert closed.context["can_cancel"] is False
    assert closed.context["can_close"] is False
    assert closed.context["is_overdue"] is False


def test_supplierperf_plan_detail_tells_a_member_that_closing_is_an_admin_action(
        member_client, supplierperf_plan_overdue_a):
    """Non-empty ONLY when the admin rule is what hid the form — a draft or closed plan has no
    close form for anybody, and printing "ask an admin" there would offer a route that does not
    exist."""
    response = member_client.get(reverse("procurement:improvementplan_detail",
                                         args=[supplierperf_plan_overdue_a.pk]))
    assert response.status_code == 200
    assert response.context["can_close"] is False
    assert "workspace-admin action" in response.context["close_refusal"]
    assert response.context["close_refusal"] in _supplierperf_html(response)


# =================================================================================================
# 7. The three boards — with data, and with nothing at all
# =================================================================================================

def test_supplierperf_benchmark_board_ranks_the_cohort(client_a, tenant_a):
    made = _supplierperf_view_cohort(tenant_a, 3)
    response = client_a.get(reverse("procurement:supplier_benchmark_board"))
    rows = response.context["rows"]
    html = _supplierperf_html(response)

    assert response.status_code == 200
    assert len(rows) == 3
    # (80*30 + 40*10) / 40 = 70.00 for every supplier in the cohort.
    assert {row["composite"] for row in rows} == {Decimal("70.00")}
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert response.context["cohort"]["count"] == 3
    assert response.context["cohort"]["scored"] == 3
    assert response.context["cohort"]["average"] == Decimal("70.00")
    assert response.context["cohort"]["best"] == Decimal("70.00")
    assert made[0][0].name in html
    assert escape(performance.BENCHMARK_NOTE) in html
    # The quadrant label/css pair is stamped onto every placed row.
    assert all(row["quadrant_label"] for row in rows if row["quadrant"])


def test_supplierperf_benchmark_board_renders_the_empty_branch_with_every_cohort_key(client_a):
    """The empty branch is where a bad aggregate hides. ``_empty_cohort()`` exists so the
    no-tenant and no-period paths hand the template the SAME keys the populated branch does — a
    missing key renders as the empty string and ships looking like a blank statistic (L8)."""
    response = client_a.get(reverse("procurement:supplier_benchmark_board"))

    assert response.status_code == 200
    assert response.context["rows"] == []
    assert response.context["periods"] == []
    assert response.context["selected_period"] is None
    assert response.context["cohort"] == {"count": 0, "scored": 0, "average": None,
                                          "best": None, "worst": None}
    assert response.context["category_choices"] == []
    assert response.context["truncated"] is False
    assert escape(performance.BENCHMARK_NOTE) in _supplierperf_html(response)


def test_supplierperf_benchmark_board_honours_a_hand_typed_period_with_no_scorecards(
        client_a, tenant_a):
    """The parsed value wins even when it is not in the picker — an honestly empty cohort rather
    than a different period's numbers under the date the reader asked for."""
    _supplierperf_view_cohort(tenant_a, 2)
    response = client_a.get(reverse("procurement:supplier_benchmark_board"),
                            {"period": _supplierperf_day(-400).isoformat()})

    assert response.status_code == 200
    assert response.context["selected_period"] == _supplierperf_day(-400)
    assert response.context["rows"] == []
    assert response.context["cohort"]["count"] == 0


def test_supplierperf_trend_board_plots_one_supplier_across_its_periods(client_a, tenant_a):
    party = _supplierperf_view_party(tenant_a, "Trend Supplier")
    kpi = _supplierperf_view_kpi(tenant_a, "TRN-01", weight=20)
    for offset in (180, 90, 0):
        card = _supplierperf_view_scorecard(
            tenant_a, party, period_end=_supplierperf_day(-offset),
            period_start=_supplierperf_day(-offset - 89))
        _supplierperf_view_score(tenant_a, card, kpi, score=Decimal("60.00"), band="warning")

    response = client_a.get(reverse("procurement:supplier_trend_board"),
                            {"supplier": str(party.pk)})
    series = response.context["series"]

    assert response.status_code == 200
    assert response.context["selected_supplier"] == party
    assert len(series) == 3
    assert [point["period_end"] for point in series] == sorted(
        point["period_end"] for point in series), "the series must read oldest to newest"
    assert {point["composite"] for point in series} == {Decimal("60.00")}
    assert series[0]["delta"] is None and series[1]["delta"] == Decimal("0.00")
    assert len(response.context["kpi_series"]) == 1
    assert response.context["kpi_series"][0]["kpi_code"] == "TRN-01"
    assert response.context["period_cap"] == performance.PERIOD_CAP
    assert "Trend Supplier" in _supplierperf_html(response)


def test_supplierperf_trend_board_renders_the_empty_branch_with_no_supplier_chosen(client_a):
    response = client_a.get(reverse("procurement:supplier_trend_board"))

    assert response.status_code == 200
    assert response.context["selected_supplier"] is None
    assert response.context["series"] == []
    assert response.context["kpi_series"] == []
    assert response.context["periods"] == []
    assert response.context["truncated"] is False
    assert list(response.context["suppliers"]) == []


def test_supplierperf_trend_board_renders_a_supplier_with_no_scorecard_at_all(
        client_a, supplierperf_supplier_a):
    """Chosen supplier, nothing to plot — the branch a seeded dataset never reaches."""
    response = client_a.get(reverse("procurement:supplier_trend_board"),
                            {"supplier": str(supplierperf_supplier_a.pk)})
    assert response.status_code == 200
    assert response.context["selected_supplier"] == supplierperf_supplier_a
    assert response.context["series"] == []
    assert response.context["kpi_series"] == []


def test_supplierperf_trend_board_narrows_to_one_kpi(client_a, tenant_a):
    party = _supplierperf_view_party(tenant_a, "Two-KPI Supplier")
    wanted = _supplierperf_view_kpi(tenant_a, "TRN-A")
    other = _supplierperf_view_kpi(tenant_a, "TRN-B", display_order=20)
    card = _supplierperf_view_scorecard(tenant_a, party)
    _supplierperf_view_score(tenant_a, card, wanted, score=Decimal("80.00"), band="ok")
    _supplierperf_view_score(tenant_a, card, other, score=Decimal("20.00"), band="critical")

    response = client_a.get(reverse("procurement:supplier_trend_board"),
                            {"supplier": str(party.pk), "kpi": str(wanted.pk)})

    assert response.context["selected_kpi"] == wanted
    assert [bucket["kpi_code"] for bucket in response.context["kpi_series"]] == ["TRN-A"]
    assert response.context["series"][0]["composite"] == Decimal("80.00")
    assert other.pk not in {bucket["kpi_id"] for bucket in response.context["kpi_series"]}


def test_supplierperf_perception_gap_reports_both_sides_and_the_delta(
        client_a, supplierperf_supplier_a, supplierperf_feedback_submitted_a,
        supplierperf_feedback_self_a, supplierperf_kpi_survey_a):
    """``delta = self_avg - internal_avg``, so a POSITIVE delta is the supplier rating itself
    higher than we rate it — the conversation worth having. Rating 4 -> 75, rating 5 -> 100."""
    response = client_a.get(reverse("procurement:supplier_perception_gap"),
                            {"supplier": str(supplierperf_supplier_a.pk)})
    gap_rows = response.context["gap_rows"]

    assert response.status_code == 200
    assert len(gap_rows) == 1
    row = gap_rows[0]
    assert row["kpi_id"] == supplierperf_kpi_survey_a.pk
    assert row["internal_avg"] == Decimal("75.00") and row["internal_count"] == 1
    assert row["self_avg"] == Decimal("100.00") and row["self_count"] == 1
    assert row["delta"] == Decimal("25.00")
    assert row["delta_css"] == "badge-red"
    assert response.context["selected_period"]["period_end"] == _supplierperf_day()
    assert supplierperf_kpi_survey_a.name in _supplierperf_html(response)


def test_supplierperf_perception_gap_renders_the_empty_branch_with_no_supplier(client_a):
    response = client_a.get(reverse("procurement:supplier_perception_gap"))

    assert response.status_code == 200
    assert response.context["selected_supplier"] is None
    assert response.context["gap_rows"] == []
    assert response.context["periods"] == []
    assert response.context["selected_period"] is None
    assert response.context["truncated"] is False


def test_supplierperf_perception_gap_offers_no_window_when_nothing_was_submitted(
        client_a, supplierperf_supplier_a, supplierperf_feedback_requested_a):
    """Windows are read from the FEEDBACK rows, not from the scorecards: a window in which
    nobody answered is a dead option, and offering it renders a board that looks like a bug."""
    response = client_a.get(reverse("procurement:supplier_perception_gap"),
                            {"supplier": str(supplierperf_supplier_a.pk)})
    assert response.status_code == 200
    assert response.context["selected_supplier"] == supplierperf_supplier_a
    assert response.context["periods"] == []
    assert response.context["selected_period"] is None
    assert response.context["gap_rows"] == []


def test_supplierperf_perception_gap_counts_a_zero_importance_respondent_without_weighting_them(
        client_a, tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a):
    """Importance WEIGHTS, it does not gate: a response filed at 0 contributes nothing to the
    mean and is still counted, so a page can honestly say how many people answered."""
    _supplierperf_view_feedback(tenant_a, supplierperf_supplier_a,
                                kpi=supplierperf_kpi_survey_a, rating=5, importance=0,
                                status="submitted", submitted_at=timezone.now(),
                                respondent_name="Filed at zero weight")
    _supplierperf_view_feedback(tenant_a, supplierperf_supplier_a,
                                kpi=supplierperf_kpi_survey_a, rating=1, importance=4,
                                status="submitted", submitted_at=timezone.now(),
                                respondent_name="Filed at weight four")

    response = client_a.get(reverse("procurement:supplier_perception_gap"),
                            {"supplier": str(supplierperf_supplier_a.pk)})
    row = response.context["gap_rows"][0]

    assert row["internal_count"] == 2, "the zero-weight respondent was dropped from the count"
    assert row["internal_avg"] == Decimal("0.00"), "the zero-weight rating moved the mean"
    assert row["self_avg"] is None and row["self_count"] == 0


# =================================================================================================
# 8. The regression the two boards now share — one supplier, one period, ONE composite
# =================================================================================================

def test_supplierperf_benchmark_and_trend_boards_report_the_same_composite(client_a, tenant_a):
    """I1, locked. The benchmark board used to publish ``overall_score`` under the composite's
    NAME, so all five seeded suppliers read differently across the two pages — one of them 34.62
    (grade F) here and 69.87 there — and rank, percentile and quadrant all rode the wrong figure.

    The two numbers are DIFFERENT THINGS and both are published: ``composite`` is the weighted
    mean of the scorecard's own KPI lines, ``overall`` is SCM's blend of the four dimension
    columns. This test is only meaningful because the fixture makes them differ.
    """
    party = _supplierperf_view_party(tenant_a, "Agreement Test Castings")
    _supplierperf_view_profile(tenant_a, party)
    _supplierperf_view_risk(tenant_a, party, score=2)
    card = _supplierperf_view_scorecard(tenant_a, party)
    mapped = _supplierperf_view_kpi(tenant_a, "AGR-A", weight=30)
    unmapped = _supplierperf_view_kpi(tenant_a, "AGR-B", weight=10, maps_to_dimension="",
                                      display_order=20)
    _supplierperf_view_score(tenant_a, card, mapped, score=Decimal("90.00"), band="ok")
    _supplierperf_view_score(tenant_a, card, unmapped, score=Decimal("30.00"), band="critical")
    card.delivery_score = Decimal("90.00")
    card.save(update_fields=["delivery_score", "updated_at"])
    card.recompute_overall()

    benchmark = client_a.get(reverse("procurement:supplier_benchmark_board"))
    trend = client_a.get(reverse("procurement:supplier_trend_board"),
                         {"supplier": str(party.pk)})
    bench_row = next(row for row in benchmark.context["rows"] if row["supplier_id"] == party.pk)
    trend_point = next(point for point in trend.context["series"]
                       if point["period_end"] == card.period_end)

    # (90*30 + 30*10) / 40 = 75.00 on BOTH pages.
    assert bench_row["composite"] == Decimal("75.00")
    assert trend_point["composite"] == bench_row["composite"], (
        "the benchmark board and the trend board disagree about the same supplier in the same "
        "period")
    # SCM's own blend rides beside it under `overall`, never instead of it — and it is a
    # different number, which is what makes the assertion above worth making.
    assert bench_row["overall"] == Decimal("90.00")
    assert trend_point["overall"] == bench_row["overall"]
    assert bench_row["composite"] != bench_row["overall"]
    assert bench_row["grade"] == trend_point["grade"] == "A"


def test_supplierperf_benchmark_ranks_on_the_composite_not_on_scms_blend(client_a, tenant_a):
    """The consequence of I1 that a single-supplier test cannot show: the ORDER itself was wrong.

    ``low`` beats ``high`` on the KPI lines (70.00 against 45.00) while losing on
    ``overall_score`` (40.00 against 90.00), so ranking on the wrong figure inverts the board.
    """
    kpi_mapped = _supplierperf_view_kpi(tenant_a, "RNK-A", weight=10)
    kpi_free = _supplierperf_view_kpi(tenant_a, "RNK-B", weight=10, maps_to_dimension="",
                                      display_order=20)
    period = _supplierperf_day()

    high = _supplierperf_view_party(tenant_a, "High Overall Ltd")
    high_card = _supplierperf_view_scorecard(tenant_a, high, period_end=period)
    _supplierperf_view_score(tenant_a, high_card, kpi_mapped, score=Decimal("90.00"), band="ok")
    _supplierperf_view_score(tenant_a, high_card, kpi_free, score=Decimal("0.00"),
                             band="critical")
    high_card.delivery_score = Decimal("90.00")
    high_card.save(update_fields=["delivery_score", "updated_at"])
    high_card.recompute_overall()

    low = _supplierperf_view_party(tenant_a, "Low Overall Ltd")
    low_card = _supplierperf_view_scorecard(tenant_a, low, period_end=period)
    _supplierperf_view_score(tenant_a, low_card, kpi_mapped, score=Decimal("40.00"),
                             band="critical")
    _supplierperf_view_score(tenant_a, low_card, kpi_free, score=Decimal("100.00"), band="ok")
    low_card.delivery_score = Decimal("40.00")
    low_card.save(update_fields=["delivery_score", "updated_at"])
    low_card.recompute_overall()

    response = client_a.get(reverse("procurement:supplier_benchmark_board"))
    ordered = [(row["supplier_name"], row["composite"], row["overall"], row["rank"])
               for row in response.context["rows"]]

    assert ordered == [("Low Overall Ltd", Decimal("70.00"), Decimal("40.00"), 1),
                       ("High Overall Ltd", Decimal("45.00"), Decimal("90.00"), 2)]
    assert response.context["cohort"]["best"] == Decimal("70.00")
    assert response.context["cohort"]["worst"] == Decimal("45.00")


def test_supplierperf_benchmark_cohort_statistics_are_computed_after_the_filter_not_before(
        client_a, tenant_a):
    """I7 — the tier/category narrowing happens in the QUERYSET, before the row cap, so every
    cohort statistic is computed over the FILTERED population. Applied after the slice it once
    turned a 13-supplier cohort averaging 55.14 into 6 suppliers averaging 10.00."""
    _supplierperf_view_cohort(tenant_a, 2)
    weak = _supplierperf_view_party(tenant_a, "Weak Transactional Ltd")
    _supplierperf_view_profile(tenant_a, weak, tier="transactional", category="Fasteners")
    weak_card = _supplierperf_view_scorecard(tenant_a, weak)
    weak_kpi = SupplierKpi.objects.get(tenant=tenant_a, code="COH-A")
    _supplierperf_view_score(tenant_a, weak_card, weak_kpi, score=Decimal("10.00"),
                             band="critical")

    everything = client_a.get(reverse("procurement:supplier_benchmark_board"))
    strategic = client_a.get(reverse("procurement:supplier_benchmark_board"),
                             {"tier": "strategic"})

    assert everything.context["cohort"] == {"count": 3, "scored": 3,
                                            "average": Decimal("50.00"),
                                            "best": Decimal("70.00"),
                                            "worst": Decimal("10.00")}
    assert strategic.context["cohort"] == {"count": 2, "scored": 2,
                                           "average": Decimal("70.00"),
                                           "best": Decimal("70.00"),
                                           "worst": Decimal("70.00")}


# =================================================================================================
# 9. Query budgets — a ceiling AND the flatness property the ceiling cannot prove
# =================================================================================================

def test_supplierperf_benchmark_board_query_budget_is_flat_in_the_size_of_the_cohort(
        client_a, tenant_a, django_assert_max_num_queries):
    """Measured at 12 full-page queries and proved flat from 5 to 302 suppliers. The ceiling
    leaves a little headroom over that; an N+1 over even a ten-supplier cohort blows straight
    through it, and the comparison below catches one that hides under the ceiling."""
    url = reverse("procurement:supplier_benchmark_board")
    _supplierperf_view_cohort(tenant_a, 3)
    small = _supplierperf_queries(client_a, url)

    _supplierperf_view_cohort(tenant_a, 12, offset=3)
    with django_assert_max_num_queries(16):
        response = client_a.get(url)

    assert response.status_code == 200
    assert len(response.context["rows"]) == 15
    assert _supplierperf_queries(client_a, url) == small, (
        "five times the cohort cost more queries — the benchmark board grew an N+1")


def test_supplierperf_trend_board_query_budget_is_flat_in_the_number_of_periods(
        client_a, tenant_a, django_assert_max_num_queries):
    """``trend_series`` reads the scorecards once and every line across all of them once
    (``scorecard_id__in=…``), never one query per period."""
    party = _supplierperf_view_party(tenant_a, "Flat Trend Ltd")
    kpi = _supplierperf_view_kpi(tenant_a, "FLT-01")
    url = reverse("procurement:supplier_trend_board")
    params = {"supplier": str(party.pk)}

    def add(count, offset=0):
        for index in range(offset, offset + count):
            card = _supplierperf_view_scorecard(
                tenant_a, party, period_end=_supplierperf_day(-30 * index),
                period_start=_supplierperf_day(-30 * index - 89))
            _supplierperf_view_score(tenant_a, card, kpi, score=Decimal("55.00"),
                                     band="warning")

    add(3)
    small = _supplierperf_queries(client_a, url, params)
    add(12, offset=3)

    with django_assert_max_num_queries(16):
        response = client_a.get(url, params)

    assert response.status_code == 200
    assert len(response.context["series"]) == 15
    assert _supplierperf_queries(client_a, url, params) == small, (
        "five times the periods cost more queries — the trend board grew an N+1")


def test_supplierperf_perception_gap_query_budget_is_flat_in_the_number_of_responses(
        client_a, tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        django_assert_max_num_queries):
    """One grouped read over the window's submitted responses, bucketed in Python by KPI and
    side — not two loops, and never one query per respondent."""
    url = reverse("procurement:supplier_perception_gap")
    params = {"supplier": str(supplierperf_supplier_a.pk)}

    def add(count, offset=0):
        for index in range(offset, offset + count):
            _supplierperf_view_feedback(
                tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                rating=1 + (index % 5), importance=5, status="submitted",
                submitted_at=timezone.now(), respondent_name=f"Respondent {index:03d}")

    add(3)
    small = _supplierperf_queries(client_a, url, params)
    add(12, offset=3)

    with django_assert_max_num_queries(15):
        response = client_a.get(url, params)

    assert response.status_code == 200
    assert response.context["gap_rows"][0]["internal_count"] == 15
    assert _supplierperf_queries(client_a, url, params) == small, (
        "five times the responses cost more queries — the perception board grew an N+1")


def test_supplierperf_score_register_query_budget_is_flat_in_the_number_of_lines(
        client_a, tenant_a, supplierperf_scorecard_draft_a, django_assert_max_num_queries):
    """The register joins ``kpi``, ``scorecard`` and the CHAINED ``scorecard__party`` — every FK
    a row or a ``__str__`` hops (L18). Fifteen rows on one page is exactly where a missing
    ``select_related`` becomes 1+N."""
    url = reverse("procurement:supplierkpiscore_list")
    for index in range(3):
        kpi = _supplierperf_view_kpi(tenant_a, f"QRY-{index:03d}")
        _supplierperf_view_score(tenant_a, supplierperf_scorecard_draft_a, kpi)
    small = _supplierperf_queries(client_a, url)

    for index in range(3, 15):
        kpi = _supplierperf_view_kpi(tenant_a, f"QRY-{index:03d}")
        _supplierperf_view_score(tenant_a, supplierperf_scorecard_draft_a, kpi)

    with django_assert_max_num_queries(16):
        response = client_a.get(url)

    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == 15
    assert _supplierperf_queries(client_a, url) == small, (
        "five times the lines cost more queries — the score register grew an N+1")


def test_supplierperf_plan_register_query_budget_is_flat_in_the_number_of_plans(
        client_a, tenant_a, supplierperf_supplier_a, admin_user, supplierperf_suspension_a,
        django_assert_max_num_queries):
    """Every row carries an owner, a scorecard, a KPI and a suspension pointer — the shape that
    HIDES the N+1 when any of them is null, so each one is set here."""
    url = reverse("procurement:improvementplan_list")
    kpi = _supplierperf_view_kpi(tenant_a, "PLN-01")
    card = _supplierperf_view_scorecard(tenant_a, supplierperf_supplier_a)

    def add(count, offset=0):
        for index in range(offset, offset + count):
            _supplierperf_view_plan(tenant_a, supplierperf_supplier_a,
                                    title=f"Plan {index:03d}", owner=admin_user, kpi=kpi,
                                    scorecard=card,
                                    escalated_suspension=supplierperf_suspension_a)

    add(3)
    small = _supplierperf_queries(client_a, url)
    add(12, offset=3)

    with django_assert_max_num_queries(16):
        response = client_a.get(url)

    assert response.status_code == 200
    assert len(_supplierperf_pks(response)) == 15
    assert _supplierperf_queries(client_a, url) == small, (
        "five times the plans cost more queries — the PIP register grew an N+1")
