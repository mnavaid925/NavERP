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

# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULES directly — see the
# module docstring.
from apps.procurement.forms.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    SupplierKpiScoreEditForm)
from apps.procurement.models.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    BAND_CHOICES, SupplierKpiScore)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import (
    DIMENSION_CHOICES, SOURCE_CHOICES, SupplierKpi)
from apps.procurement.performance import (
    HANDOVER_NOTE, ROW_CAP, generate_scorecard_lines)
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
    """Tenant-scoped scorecards with their 6.16 line count annotated."""
    return (_scorecard_model().objects.filter(tenant=request.tenant)
            .select_related("party")
            .annotate(line_count=Count("procurement_kpi_scores")))


def _evaluation_years(tenant):
    """Distinct scorecard period years, newest first — the register's period filter."""
    if tenant is None:
        return []
    return list(_scorecard_model().objects.filter(tenant=tenant)
                .annotate(year=ExtractYear("period_end"))
                .values_list("year", flat=True).distinct().order_by("-year"))


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

    ``supplier`` and ``year`` ride the ``is_int=True`` path so a hand-edited query string cannot
    500 the page (L11); ``status`` is validated against the model's own CHOICES by ``crud_list``.
    """
    return crud_list(
        request, _evaluation_qs(request), TEMPLATE_EVALUATION_LIST,
        search_fields=("number", "party__name"),
        filters=(("supplier", "party_id", True),
                 ("status", "status", False),
                 ("year", "period_end__year", True)),
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

    can_generate = obj.status == "draft" and request.tenant is not None
    if can_generate:
        refusal_reason = ""
    elif request.tenant is None:
        refusal_reason = _REFUSAL_NO_TENANT
    else:
        refusal_reason = (f"A {obj.get_status_display().lower()} scorecard is closed — only a "
                          "draft may be generated onto.")

    return render(request, TEMPLATE_EVALUATION_DETAIL, {
        "obj": obj,
        "lines": lines,
        "composite": composite,
        "dimension_map": dimension_map,
        "can_generate": can_generate,
        "refusal_reason": refusal_reason,
        "plans": list(SupplierImprovementPlan.objects
                      .filter(tenant=request.tenant, scorecard_id=obj.pk)
                      .select_related("supplier", "kpi")),
        "feedback_rows": list(SupplierFeedback.objects
                              .filter(tenant=request.tenant, scorecard_id=obj.pk)
                              .select_related("kpi", "respondent")),
        "band_choices": BAND_CHOICES,
        "handover_note": HANDOVER_NOTE,
        "row_cap": ROW_CAP,
        "truncated": truncated,
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


@login_required
def supplierkpiscore_list(request):
    """Every measured line in the workspace, grouped by the FROZEN category and KPI name.

    ``source_at_time`` is a plain CharField with **no** ``choices``, so ``crud_list``'s enum
    guard bails out and the raw value reaches ``.filter()``. That is safe — junk matches nothing
    — but it means the template's ``source_choices`` dropdown is the only thing keeping the
    offered values legal, which is why it is pinned to ``SupplierKpi.SOURCE_CHOICES`` rather than
    invented in the template.
    """
    return crud_list(
        request, _score_qs(request), TEMPLATE_LIST,
        search_fields=("kpi_name", "comment", "scorecard__number", "scorecard__party__name"),
        filters=(("band", "band", False),
                 ("source", "source_at_time", False),
                 ("kpi", "kpi_id", True),
                 ("scorecard", "scorecard_id", True)),
        extra_context={
            "band_choices": BAND_CHOICES,
            "source_choices": SOURCE_CHOICES,
            "kpis": SupplierKpi.objects.filter(tenant=request.tenant)
                                       .order_by("display_order", "code"),
            "scorecards": _scorecard_model().objects.filter(tenant=request.tenant)
                                                    .select_related("party")
                                                    .order_by("-period_end", "-id"),
            "stats": _score_stats(request.tenant),
        },
    )


@login_required
def supplierkpiscore_detail(request, pk):
    """One measured line, with the arithmetic that produced it spelled out.

    ``breakdown`` is a JSONField the resolvers fill in; it is flattened to sorted ``{key, value}``
    pairs here so the template never has to render a raw dict — and every value is ``str()``-ified
    so a nested list prints as text rather than as a Django ``dict_items`` repr.
    """
    obj = get_object_or_404(_score_qs(request), pk=pk)
    breakdown = obj.breakdown if isinstance(obj.breakdown, dict) else {}
    return crud_detail(
        request, model=SupplierKpiScore, pk=pk, template=TEMPLATE_DETAIL,
        select_related=(*_SCORE_RELATIONS, "computed_by"),
        extra_context={
            "breakdown_rows": [{"key": key, "value": str(breakdown[key])}
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

    Redirects back to the period document the line belonged to — the scorecard id is captured
    BEFORE the delete, because the row is gone by the time ``crud_delete`` returns.
    """
    obj = get_object_or_404(SupplierKpiScore.objects.only("pk", "scorecard_id", "tenant_id"),
                            pk=pk, tenant=request.tenant)
    return crud_delete(
        request, model=SupplierKpiScore, pk=pk,
        success_url=reverse("procurement:supplierevaluation_detail", args=[obj.scorecard_id]))
