"""Procurement 6.16 Supplier Performance & Evaluation — the evaluation register and score lines.

Two surfaces, one story:

* **The evaluation register** (``supplierevaluation_*``) is a view onto ``scm.SupplierScorecard``
  — SCM's model, FK'd and never re-declared (L36). 6.16 ships **no scorecard create route**: the
  register's "New period" button links straight out to ``scm:scorecard_create``.
* **The score register** (``supplierkpiscore_*``) is this app's own measured lines, one per
  (scorecard, KPI).

**Generating is a ONE-WAY DOOR.** ``supplierevaluation_generate`` writes the four
``scm.SupplierScorecard`` dimension columns from the KPI lines and sets ``manual_override``;
``scm.SupplierScorecard.recompute_from_signals()`` returns immediately on any row with that flag,
so from then on SCM's signal engine leaves the scorecard alone and 6.16 owns it. The sentence the
user is shown is ``performance.HANDOVER_NOTE`` — it is on the register, on the detail page, in
the button's confirm dialog and in the model's own docstring, so nobody presses it by accident.

**Two documented CRUD exemptions on ``SupplierKpiScore``** (intent, not omission):

1. **No create route and no create form.** Lines are system-written by generate; a hand-created
   line would be a measurement with no computation behind it.
2. **Edit is limited to ``measured_value`` + ``comment`` on a ``source_at_time == "manual"``
   line, and THIS VIEW is the gate** — ``supplierkpiscore_edit`` refuses and redirects before any
   form work. A two-field form and a disabled widget are UX; the authorization boundary is here.
   Delete (POST-only) does exist, so a retired KPI's stale line can be removed.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``, including the
  cross-app scorecard reads, which are 404s rather than leaks for another workspace's pk.
* **``crud_edit``'s ``success_url`` is handed to ``redirect()`` with NO args**, so a route taking
  a pk must be passed as an already-reversed PATH, not as a url name — a bare
  ``"procurement:supplierkpiscore_detail"`` would ``NoReverseMatch`` on save (§9).
* **``stats`` is ONE conditional ``aggregate()``.** The evaluation register's aggregate joins the
  score lines to count "generated", so EVERY count in it is ``distinct=True`` — without that the
  join fans the rows out and ``total`` silently becomes "number of score lines".
* **The detail page renders many lines**, so every FK a template or a ``__str__`` hops is
  ``select_related``.

**Import discipline.** Two kinds of not-yet-wired import live here, both deliberate:

1. This sub-module's own model/form come from their ENTITY modules at module top, never from
   ``apps.procurement.models`` / ``.forms`` — the package ``__init__`` re-export blocks land at
   Integrate, and a package-level import would be a star-import cycle at URLconf import time (the
   ``CostForecasts.py`` precedent).
2. ``scm`` models, ``core.Party`` and the two sibling 6.16 models the detail page lists are
   imported INSIDE the function that needs them, so this module imports cleanly on its own and
   cannot start a cycle.
"""
from django.db.models import Count, Q
from django.db.models.functions import ExtractYear
from django.urls import reverse

from apps.core.crud import as_db_int
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULES directly — see the
# module docstring.
from apps.procurement.forms.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    SupplierKpiScoreEditForm)
from apps.procurement.models.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    BAND_CHOICES, SupplierKpiScore)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import (
    DIMENSION_CHOICES, SOURCE_CHOICES, SupplierKpi)
from apps.procurement.performance import (
    DETAIL_ROW_CAP, HANDOVER_NOTE, ROW_CAP, generate_scorecard_lines)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_EVALUATION_LIST = "procurement/performance/evaluation/list.html"
TEMPLATE_EVALUATION_DETAIL = "procurement/performance/evaluation/detail.html"
TEMPLATE_LIST = "procurement/performance/kpiscore/list.html"
TEMPLATE_DETAIL = "procurement/performance/kpiscore/detail.html"
TEMPLATE_FORM = "procurement/performance/kpiscore/form.html"

#: The FKs a score-line row hops in a template or in ``__str__``. One tuple, so the register and
#: the detail page cannot drift into different N+1 profiles.
_SCORE_RELATIONS = ("kpi", "scorecard", "scorecard__party")

#: Refusal sentences for the Generate button, keyed by why it is unavailable. The page PRINTS
#: these next to the disabled button — a greyed-out control that will not say why is worse than
#: no control at all.
_REFUSAL_NO_TENANT = ("Select a tenant workspace before generating — a scorecard belongs to one "
                      "workspace and the superuser has none.")
_REFUSAL_NOT_ADMIN = ("Generating hands this scorecard to Procurement permanently, so it is a "
                      "workspace-admin action — ask an admin of this workspace to press it.")

#: The range ``datetime.date`` can hold. ``period_end__year`` is the app's ONLY ``__year`` int
#: filter, and it is NOT a pk lookup — so ``crud_list``'s zero-skip (scoped to pk lookups on
#: purpose, because ``?year=0`` reads like a legitimate value) does not catch it, and
#: ``as_db_int`` range-checks against the COLUMN width rather than the calendar. Django then hands
#: the value to ``datetime.date(value, 1, 1)`` inside the backend, which raises
#: ``ValueError: year 0 is out of range`` — an uncaught 500 from a URL anybody can type. L11 says
#: a hand-edited query string skips the filter; it never raises.
_MIN_YEAR, _MAX_YEAR = 1, 9999

#: The legal ``?source=`` values. ``source_at_time`` is a FROZEN copy of the KPI's source, so it
#: is declared without ``choices`` — which means ``crud_list``'s enum guard (``_enum_values``)
#: disables itself on it and the raw GET value reaches ``.filter()``. Validating against the KPI's
#: own registry here is what keeps the two dropdowns on that register agreeing.
_SOURCE_VALUES = frozenset(value for value, _ in SOURCE_CHOICES)


def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree.

    The local-copy convention twelve sibling view modules follow (6.3, 6.12 and 6.13 each carry
    the same three lines). Without it ``can_generate`` was computed from status and tenant alone
    and offered the Generate button to every member — who then got a bare 403 from the verb.
    """
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _scorecard_model():
    """``scm.SupplierScorecard``, imported late.

    Cross-app read: kept inside a function so this module never imports ``apps.scm.models`` at
    URLconf import time — the same discipline ``recompute_from_signals`` follows in the other
    direction.
    """
    from apps.scm.models import SupplierScorecard
    return SupplierScorecard


def _supplier_parties(request):
    """The supplier/vendor cohort for the register's dropdown. ``.none()`` without a tenant."""
    from apps.core.models import Party
    if request.tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=request.tenant,
                                 roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _evaluation_qs(request):
    """Tenant-scoped scorecards with their 6.16 line count annotated, newest period first.

    The explicit ``order_by`` is NOT redundant with ``SupplierScorecard.Meta.ordering``:
    ``annotate()`` adds a GROUP BY, and Django DROPS the model ordering from a grouped query —
    so the register paginated an unordered queryset, raising ``UnorderedObjectListWarning`` on
    every request, and on MySQL a LIMIT/OFFSET over an unordered GROUP BY is undefined, meaning
    page 2 may repeat or drop rows once a tenant passes 15 periods. Restating the model's own
    ordering is the fix the app already documents twice (``AdvancedShipmentNotice``,
    ``EAuctionManagement/Auctions``).
    """
    return (_scorecard_model().objects.filter(tenant=request.tenant)
            .select_related("party")
            .annotate(line_count=Count("procurement_kpi_scores"))
            .order_by("-period_end", "-id"))


def _evaluation_years(tenant):
    """Distinct scorecard period years, newest first — the register's period filter."""
    if tenant is None:
        return []
    return list(_scorecard_model().objects.filter(tenant=tenant)
                .annotate(year=ExtractYear("period_end"))
                .values_list("year", flat=True).distinct().order_by("-year"))


def _evaluation_filters(request):
    """The register's ``crud_list`` filter tuples, with ``year`` dropped when it is not a year.

    A year outside 1-9999 cannot be compared against a date column at all — see
    :data:`_MIN_YEAR`. Dropping the tuple is the same answer ``crud_list`` gives every other
    unusable filter value: the register renders unfiltered instead of raising.
    """
    year = as_db_int(request.GET.get("year"))
    if year is None or not _MIN_YEAR <= year <= _MAX_YEAR:
        return (("supplier", "party_id", True), ("status", "status", False))
    return (("supplier", "party_id", True), ("status", "status", False),
            ("year", "period_end__year", True))


def _evaluation_stats(tenant):
    """``{total, draft, published, archived, generated}`` in ONE query.

    ``generated`` needs a join to the 6.16 score lines, and that join FANS THE ROWS OUT — a
    scorecard with twelve lines would be counted twelve times. Every count is therefore
    ``distinct=True``; dropping it on any one of them silently turns that stat into "number of
    score lines", which is a number nobody asked for and which looks plausible.
    """
    return _scorecard_model().objects.filter(tenant=tenant).aggregate(
        total=Count("pk", distinct=True),
        draft=Count("pk", filter=Q(status="draft"), distinct=True),
        published=Count("pk", filter=Q(status="published"), distinct=True),
        archived=Count("pk", filter=Q(status="archived"), distinct=True),
        generated=Count("pk", filter=Q(procurement_kpi_scores__isnull=False), distinct=True),
    )


@login_required
def supplierevaluation_list(request):
    """The evaluation register: every period document, newest period first.

    A row is ``scm.SupplierScorecard`` — SCM owns it and 6.16 ships no create route for it, so
    "New period" links out to ``scm:scorecard_create`` (L36). ``line_count`` says at a glance
    which periods have actually been generated onto.

    ``supplier`` rides the ``is_int=True`` path so a hand-edited query string cannot 500 the page
    (L11); ``status`` is validated against the model's own CHOICES by ``crud_list``. ``year``
    needs one guard more than ``is_int`` gives it — see :func:`_evaluation_filters`.
    """
    return crud_list(
        request, _evaluation_qs(request), TEMPLATE_EVALUATION_LIST,
        search_fields=("number", "party__name"),
        filters=_evaluation_filters(request),
        extra_context={
            "status_choices": _scorecard_model().STATUS_CHOICES,
            "suppliers": _supplier_parties(request),
            "year_choices": _evaluation_years(request.tenant),
            "stats": _evaluation_stats(request.tenant),
            "handover_note": HANDOVER_NOTE,
        },
    )


@login_required
def supplierevaluation_detail(request, pk):
    """One period document: its KPI lines, the composite arithmetic, and the Generate button.

    Hand-rolled ``render()`` rather than ``crud_detail`` because the object is a CROSS-APP model
    — ``crud_detail`` would need ``scm.SupplierScorecard`` imported at module top, which is the
    cycle this file's docstring is about. The lookup is still tenant-scoped, so another
    workspace's pk is a 404.

    The page shows the 6.16 composite NEXT TO the scorecard's own stored ``overall_score``. They
    are computed differently on purpose — the composite is the weighted mean of every scored
    line, the overall is SCM's blend of the four dimension columns — and showing both is how an
    operator sees that generate did what it said it would.
    """
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
        SupplierFeedback)
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierImprovementPlans import (
        SupplierImprovementPlan)

    obj = get_object_or_404(
        _scorecard_model().objects.select_related("party"), pk=pk, tenant=request.tenant)

    # Fetch cap + 1 so "was it cut?" is answered by the same query, not by a second COUNT.
    lines = list(SupplierKpiScore.objects.filter(tenant=request.tenant, scorecard=obj)
                 .select_related("kpi")[:ROW_CAP + 1])
    truncated = len(lines) > ROW_CAP
    lines = lines[:ROW_CAP]

    # The two SUPPORTING tables get the same treatment ``lines`` already had. They were
    # UNCAPPED: measured 109 ms -> 924 ms and 427 KB -> 2.28 MB of HTML on a scorecard carrying
    # 1,500 responses and 500 plans, which a supplier running a real 360 programme reaches
    # without anything unusual happening. Both models carry a deterministic ``Meta.ordering``
    # (``-start_date, -id`` and ``-period_end, -id``), so the slice takes the newest rows rather
    # than an arbitrary page — the sibling ``supplierkpi_detail`` caps its three lists the same
    # way. ``DETAIL_ROW_CAP``, not ``ROW_CAP``: these are supporting context on a page about the
    # KPI lines, and each register shows the full set.
    plans = list(SupplierImprovementPlan.objects
                 .filter(tenant=request.tenant, scorecard_id=obj.pk)
                 .select_related("supplier", "kpi")[:DETAIL_ROW_CAP + 1])
    feedback_rows = list(SupplierFeedback.objects
                         .filter(tenant=request.tenant, scorecard_id=obj.pk)
                         .select_related("kpi", "respondent")[:DETAIL_ROW_CAP + 1])
    # Kept SEPARATE from ``truncated`` rather than OR'd into it: the KPI-line warning says the
    # composite was computed over a cut list, which is not true when only the plans were cut.
    # Two flags, two honest sentences.
    related_truncated = (len(plans) > DETAIL_ROW_CAP or len(feedback_rows) > DETAIL_ROW_CAP)
    plans = plans[:DETAIL_ROW_CAP]
    feedback_rows = feedback_rows[:DETAIL_ROW_CAP]

    scored = [line for line in lines if line.score is not None]
    weight_total = sum(line.weight_applied for line in scored)
    weighted_total = None
    if weight_total:
        from decimal import Decimal
        weighted_total = (sum(line.score * line.weight_applied for line in scored)
                          / Decimal(weight_total)).quantize(Decimal("0.01"))
    composite = {"weighted_total": weighted_total, "weight_total": weight_total,
                 "scored_lines": len(scored), "total_lines": len(lines),
                 "unscored_lines": len(lines) - len(scored),
                 "overall": obj.overall_score, "grade": obj.grade}

    # Which KPIs feed each of SCM's four dimension columns, and what that column now holds.
    # Built from the FROZEN line data plus the KPI's current mapping, in one pass over `lines`.
    dimension_map = {key: {"label": label, "score": None, "kpi_count": 0,
                           "kpi_names": [], "weight_total": 0}
                     for key, label in DIMENSION_CHOICES}
    for key, entry in dimension_map.items():
        entry["score"] = getattr(obj, f"{key}_score")
    for line in lines:
        dimension = line.kpi.maps_to_dimension if line.kpi_id else ""
        entry = dimension_map.get(dimension)
        if entry is None:
            continue
        entry["kpi_count"] += 1
        entry["kpi_names"].append(line.kpi_name or line.kpi.name)
        entry["weight_total"] += line.weight_applied

    # Three conditions, and the page PRINTS whichever one refused. ``supplierevaluation_generate``
    # is @tenant_admin_required, so the admin test belongs here too: a button that renders for
    # everybody and then 403s is worse than no button.
    can_generate = (obj.status == "draft" and request.tenant is not None and _is_admin(request))
    if can_generate:
        refusal_reason = ""
    elif request.tenant is None:
        refusal_reason = _REFUSAL_NO_TENANT
    elif obj.status != "draft":
        refusal_reason = (f"A {obj.get_status_display().lower()} scorecard is closed — only a "
                          "draft may be generated onto.")
    else:
        refusal_reason = _REFUSAL_NOT_ADMIN

    return render(request, TEMPLATE_EVALUATION_DETAIL, {
        "obj": obj,
        "lines": lines,
        "composite": composite,
        "dimension_map": dimension_map,
        "can_generate": can_generate,
        "refusal_reason": refusal_reason,
        "plans": plans,
        "feedback_rows": feedback_rows,
        "band_choices": BAND_CHOICES,
        "handover_note": HANDOVER_NOTE,
        "row_cap": ROW_CAP,
        "truncated": truncated,
        "related_cap": DETAIL_ROW_CAP,
        "related_truncated": related_truncated,
    })


@require_POST
@tenant_admin_required
def supplierevaluation_generate(request, pk):
    """Compute every applicable KPI onto this scorecard. **A ONE-WAY DOOR — read this.**

    Generating hands the scorecard permanently to Procurement 6.16. The four dimension scores are
    written from the KPI lines, ``manual_override`` is set, and SCM's signal engine
    (``scm.SupplierScorecard.recompute_from_signals()``) will skip this scorecard from then on.
    This cannot be undone from here. The same sentence (``performance.HANDOVER_NOTE``) is printed
    on the evaluation register, on this scorecard's detail page and in the confirm dialog on the
    button that posts here, so the operator has seen it three times before the write happens.

    **Refuses on a published or archived scorecard**, writing ZERO rows: a closed period is
    closed. Only a draft may be generated onto.

    Safe to press twice — ``generate_scorecard_lines`` writes through ``update_or_create`` on
    ``(tenant, scorecard, kpi)``, so a re-run refreshes the figures rather than doubling them.

    Hand-rolled save path, so this view writes its own audit row; the compute function
    deliberately writes none and emits no messages.
    """
    scorecard = get_object_or_404(
        _scorecard_model().objects.select_related("party"), pk=pk, tenant=request.tenant)
    result = generate_scorecard_lines(scorecard, request.user)

    if result["refused"]:
        messages.error(request, result["refusal_reason"])
        return redirect("procurement:supplierevaluation_detail", pk=pk)

    write_audit_log(request.user, scorecard, "generate",
                    changes={"action": "generate", "written": result["written"],
                             "skipped": result["skipped"], "alerts": result["alerts"]},
                    tenant=request.tenant)
    messages.success(
        request,
        f"Generated {result['written']} KPI line(s) — {result['skipped']} had no data in the "
        f"period and {result['alerts']} new critical crossing(s) were raised as alerts. This "
        "scorecard is now owned by Procurement; SCM's signal engine will skip it.")
    return redirect("procurement:supplierevaluation_detail", pk=pk)


def _score_qs(request):
    """The score register's base queryset — tenant-scoped, with every rendered FK joined."""
    return (SupplierKpiScore.objects.filter(tenant=request.tenant)
            .select_related(*_SCORE_RELATIONS))


def _breakdown_value(value):
    """One ``breakdown`` value as display text, never as a Python repr.

    ``str()`` on a list gives exactly that repr: ``window`` is stored as
    ``[str(start), str(end)]`` by :func:`performance._breakdown`, so under a column headed
    *Value* the user was reading ``['2026-05-11', '2026-08-09']`` on 40 of 41 seeded lines.
    The page's own contract says every value is str()-ified so nothing prints as a repr — it
    printed as text, but that text WAS a repr.

    A two-item sequence reads as a range because that is what every one of them is today; any
    other sequence falls back to a comma list rather than to brackets and quotes.
    """
    if isinstance(value, (list, tuple)):
        parts = [str(part) for part in value]
        return " to ".join(parts) if len(parts) == 2 else ", ".join(parts)
    return str(value)


def _score_stats(tenant):
    """``{total, ok, warning, critical, unknown}`` in ONE query, over the whole workspace.

    Counted over the workspace on purpose: a stat card answers "where do we stand?", which must
    not change because somebody typed a search.
    """
    return SupplierKpiScore.objects.filter(tenant=tenant).aggregate(
        total=Count("pk"),
        ok=Count("pk", filter=Q(band="ok")),
        warning=Count("pk", filter=Q(band="warning")),
        critical=Count("pk", filter=Q(band="critical")),
        unknown=Count("pk", filter=Q(band="unknown")),
    )


def _score_filters(request):
    """The score register's ``crud_list`` filter tuples, with ``source`` dropped when it is junk.

    ``source_at_time`` is a plain CharField with **no** ``choices`` — it is a frozen copy of the
    KPI's source, not an input — so ``crud_list``'s enum guard disables itself on it (see
    :data:`_SOURCE_VALUES`) and the raw GET value went straight into ``.filter()``. An
    unrecognised value therefore matched nothing and WIPED the register: a tenant holding 41
    measured lines was shown an empty page with its own empty-state copy, while ``?band=zzz`` on
    the very same page fell back correctly and showed all 41. Two dropdowns on one register
    disagreeing about what a bad value means.

    Dropping the tuple is the answer every other filter in the app gives a value it does not
    recognise (L11): the filter is not applied and the register still renders its rows.
    """
    filters = [("band", "band", False),
               ("kpi", "kpi_id", True),
               ("scorecard", "scorecard_id", True)]
    if request.GET.get("source", "") in _SOURCE_VALUES:
        filters.insert(1, ("source", "source_at_time", False))
    return tuple(filters)


@login_required
def supplierkpiscore_list(request):
    """Every measured line in the workspace, grouped by the FROZEN category and KPI name.

    ``band``, ``kpi`` and ``scorecard`` are guarded by ``crud_list`` itself; ``source`` needs the
    extra guard :func:`_score_filters` gives it, because the column it filters carries no
    ``choices`` for the enum guard to read.
    """
    return crud_list(
        request, _score_qs(request), TEMPLATE_LIST,
        search_fields=("kpi_name", "comment", "scorecard__number", "scorecard__party__name"),
        filters=_score_filters(request),
        extra_context={
            "band_choices": BAND_CHOICES,
            "source_choices": SOURCE_CHOICES,
            # Both pickers CAPPED and narrowed to the four values the ``<option>`` prints.
            # Uncapped they streamed every column of every row into two ``<select>``s: measured
            # at 2,007 scorecards the register went 107 -> 349 ms and the HTML 425 KB -> 623 KB,
            # +197 KB of options in one select, with the query count flat — pure row volume. The
            # KPI picker was pulling ``description`` and ``notes``, both TextFields, per option.
            # ``ROW_CAP`` is the module's own convention for exactly this (see ``_score_qs``'s
            # siblings); the filters these feed still accept a hand-typed pk beyond the cap,
            # because ``crud_list`` validates the GET value, not the dropdown.
            "kpis": SupplierKpi.objects.filter(tenant=request.tenant)
                                       .only("id", "code", "name", "display_order")
                                       .order_by("display_order", "code")[:ROW_CAP],
            "scorecards": _scorecard_model().objects.filter(tenant=request.tenant)
                                                    .select_related("party")
                                                    .only("id", "number", "period_end",
                                                          "party__name")
                                                    .order_by("-period_end", "-id")[:ROW_CAP],
            "stats": _score_stats(request.tenant),
        },
    )


@login_required
def supplierkpiscore_detail(request, pk):
    """One measured line, with the arithmetic that produced it spelled out.

    ``breakdown`` is a JSONField the resolvers fill in; it is flattened to sorted ``{key, value}``
    pairs here so the template never has to render a raw dict, and every value goes through
    :func:`_breakdown_value` so a nested sequence reads as text rather than as a Python repr.

    The pre-fetch is a CHEAP PROBE — ``.only(…)`` on the four columns it actually reads, with no
    joins — because ``crud_detail`` fetches the row again a few lines later with the full
    ``select_related``. Using ``_score_qs`` here paid for that three-table join TWICE (2 of the
    page's 9 queries were the same row). Both sibling detail views already probe narrow for this
    reason; this one had forked from them.
    """
    obj = get_object_or_404(
        SupplierKpiScore.objects.only("pk", "tenant_id", "source_at_time", "breakdown"),
        pk=pk, tenant=request.tenant)
    breakdown = obj.breakdown if isinstance(obj.breakdown, dict) else {}
    return crud_detail(
        request, model=SupplierKpiScore, pk=pk, template=TEMPLATE_DETAIL,
        select_related=(*_SCORE_RELATIONS, "computed_by"),
        extra_context={
            "breakdown_rows": [{"key": key, "value": _breakdown_value(breakdown[key])}
                               for key in sorted(breakdown)],
            # The Actions sidebar's Edit button. Same rule the edit VIEW enforces — the button is
            # the UX half of it, never the boundary.
            "can_edit": obj.source_at_time == "manual",
        },
    )


@login_required
def supplierkpiscore_edit(request, pk):
    """Correct a MANUAL-entry line's figure and comment. **The gate is here, not on the form.**

    A derived or survey line is recomputed by Generate from evidence; typing over it would leave
    a number on the scorecard that no resolver and no respondent stands behind, and it would be
    silently overwritten on the next run anyway. So this view fetches the row FIRST and refuses
    anything but ``source_at_time == "manual"`` before any form work happens — a crafted POST
    against a derived line's pk never reaches the form.

    ``crud_edit`` hands ``success_url`` straight to ``redirect()`` with no arguments, so a route
    taking a pk must be an already-reversed PATH: passing the url NAME here would raise
    ``NoReverseMatch`` at save time, not at import time (§9).
    """
    obj = get_object_or_404(SupplierKpiScore.objects.select_related("kpi"), pk=pk,
                            tenant=request.tenant)
    if obj.source_at_time != "manual":
        messages.error(request, "Only a manual-entry line can be edited by hand — derived and "
                                "survey lines are recomputed by Generate.")
        return redirect("procurement:supplierkpiscore_detail", pk=pk)

    return crud_edit(
        request, model=SupplierKpiScore, pk=pk, form_class=SupplierKpiScoreEditForm,
        template=TEMPLATE_FORM,
        success_url=reverse("procurement:supplierkpiscore_detail", args=[pk]))


@login_required
@require_POST
def supplierkpiscore_delete(request, pk):
    """Remove a stale line — a retired KPI's, or one generated before a definition was fixed.

    Deleting a line does NOT re-derive the scorecard's dimension columns: those were written by
    the generate run that produced the line, and silently re-blending them from a hand-deleted
    subset would change a published figure behind the operator's back. Re-press Generate on a
    draft to rebuild them from what is actually there.

    **Draft periods only.** Writing a line takes an admin AND a draft scorecard; deleting one
    was ``@login_required`` and nothing else, so any member could POST away the measured
    evidence behind a PUBLISHED grade — leaving the four dimension columns and ``overall_score``
    standing with nothing under them, which is the invariant ``generate_scorecard_lines``
    refuses on a published card to protect. A closed period is closed for the delete route too.

    Redirects back to the period document the line belonged to — the scorecard id is captured
    BEFORE the delete, because the row is gone by the time ``crud_delete`` returns.
    """
    obj = get_object_or_404(
        SupplierKpiScore.objects.select_related("scorecard")
        .only("pk", "tenant_id", "scorecard__status", "scorecard__number"),
        pk=pk, tenant=request.tenant)
    if obj.scorecard.status != "draft":
        messages.error(
            request,
            f"{obj.scorecard.number} is {obj.scorecard.get_status_display().lower()} — its "
            "measured lines are the evidence behind a figure the supplier has already been "
            "shown, so they cannot be deleted. Only a draft period's lines can.")
        return redirect("procurement:supplierevaluation_detail", pk=obj.scorecard_id)
    return crud_delete(
        request, model=SupplierKpiScore, pk=pk,
        success_url=reverse("procurement:supplierevaluation_detail", args=[obj.scorecard_id]))
