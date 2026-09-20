"""Projects 7.16 Reporting & Business Intelligence — ProjectReport [REP-] views.

The saved question's whole surface in ten routes: the register, the guided builder, the live
result page, four verbs (run / freeze / favourite / delete) and two machine-readable exports.

Nothing here stores an answer except :func:`rep_freeze`. ``rep_detail``, ``rep_run``, ``rep_csv``
and ``rep_json`` all compute live through ``analytics.compute_report``, so a figure a reader sees
is the figure the modules that own it hold today. Freezing is the one act that pins a result, and
``rep_freeze`` is the ONLY writer of ``ProjectReportRun`` rows in the whole app (A1.1) — which is
why its compute, insert and stamp sit inside one transaction.

Two rules every shape below exists to keep:

* **visibility** (R7) — every fetch, the exports included, starts from
  ``analytics.visible_reports(request)``. A private question owned by a colleague does not exist
  for this caller: it is a 404, never a 403. ``crud_edit`` / ``crud_delete`` are tenant-scoped but
  NOT ACL-scoped, so those two routes carry an explicit guard-fetch of their own.
* **``last_run_at``** — written by a run or a freeze only. Opening the detail page is not evidence
  that anybody asked the question (procurement's rule for its own saved reports).
"""
from functools import partial

from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.projects import analytics
from apps.projects.forms.ReportingBusinessIntelligence.ProjectReports import ProjectReportForm
from apps.projects.models import ProjectReport, ProjectReportRun
from apps.projects.models.ReportingBusinessIntelligence._choices import CANVAS_CHARTS
from apps.projects.views._common import (
    get_object_or_404, login_required, messages, redirect, render, require_POST, timezone,
    write_audit_log,
)
from apps.projects.views._helpers import SECTION_AREAS, chart_config, chart_rows
from apps.projects.views._helpers import csv_response
from apps.projects.views._helpers import owners as owner_choices
from apps.projects.views._helpers import projects as project_choices
from apps.projects.views._helpers import redirect_back_or

TEMPLATE_LIST = "projects/reporting/report/list.html"
TEMPLATE_DETAIL = "projects/reporting/report/detail.html"
TEMPLATE_FORM = "projects/reporting/report/form.html"

#: ``crud_list``'s ``(get_param, orm_lookup, is_int)`` triples. No lookup crosses a relation:
#: ``_enum_values`` bails on a ``__`` and the junk value would then silently empty the register
#: instead of being ignored (L11). Same seven rows as ``FILTER_ECHOES``, one per filter.
REPORT_FILTERS = (
    ("report_type", "report_type", False),
    ("subject", "subject", False),
    ("chart_type", "chart_type", False),
    ("project", "project_id", True),
    ("owner", "owner_id", True),
    ("shared", "is_shared", False),
    ("favorite", "is_favorite", False),
)

#: ``(get_param, echo_key)`` for the same seven filters (R2). The param and the echo share a name
#: everywhere except ``report_type`` -> ``type_filter``, which is why this is a pair list.
FILTER_ECHOES = (
    ("report_type", "type_filter"),
    ("subject", "subject_filter"),
    ("chart_type", "chart_filter"),
    ("project", "project_filter"),
    ("owner", "owner_filter"),
    ("shared", "shared_filter"),
    ("favorite", "favorite_filter"),
)

#: Free text the register searches. Every entry is a column on this row, for the same reason the
#: filters never hop: a relation search drags a JOIN into a page whose whole job is this table.
REPORT_SEARCH_FIELDS = ["number", "name", "description", "notes"]


# ---------------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------------
def _echoes(request):
    """The register's seven filter echoes, as the stripped strings they arrived as (R2).

    Never the parsed int: ``?project=abc`` comes back as ``abc``, matches no option, and the
    dropdown renders unselected instead of lying about what narrowed the table.
    """
    return {key: request.GET.get(param, "").strip() for param, key in FILTER_ECHOES}


def _builder_context(pk=None):
    """The keys the guided builder needs beside ``form`` / ``is_edit`` / ``obj``.

    One builder for both routes on purpose: create and edit are the same template, and two copies
    of this dict is how an edit page stops offering a prefill the create page still has.
    """
    return {
        "report_type_choices": ProjectReport.REPORT_TYPE_CHOICES,
        # The form's own fields already carry these choices (A2.1); these copies are for the
        # "2 of 3 picked" counter and the axis pickers, which are page furniture, not validation.
        "measure_choices": ProjectReport.MEASURE_CHOICES,
        "dimension_choices": ProjectReport.DIMENSION_CHOICES,
        # D48: "start from a canned kind" prefills from the registry, and analytics owns that
        # vocabulary — a view that re-spelled the axes would be a second source of truth.
        "canned_axes": analytics.canned_axes(),
        "form_action_url": (
            reverse("projects:rep_edit", args=[pk]) if pk else reverse("projects:rep_create")
        ),
    }


# ---------------------------------------------------------------------------------
# register, builder, result
# ---------------------------------------------------------------------------------
@login_required
def rep_list(request):
    """Every question this caller may see, narrowed by search and the seven register filters."""
    qs = analytics.visible_reports(request).select_related(
        "owner", "project", "portfolio", "client", "org_unit")
    return crud_list(
        request, qs, TEMPLATE_LIST,
        search_fields=REPORT_SEARCH_FIELDS,
        filters=REPORT_FILTERS,
        extra_context={
            "report_type_choices": ProjectReport.REPORT_TYPE_CHOICES,
            "subject_choices": ProjectReport.SUBJECT_CHOICES,
            "chart_choices": ProjectReport.CHART_CHOICES,
            "projects": project_choices(request.tenant),
            "owners": owner_choices(request.tenant),
            **_echoes(request),
        },
    )


@login_required
def rep_create(request):
    """The builder. A ``?type=`` entry pre-selects the canned kind the link came from.

    Reached from the library and from ``report_standard``'s "save this as a report" CTA, both of
    which carry the question in the querystring, so the kind is read from GET and validated against
    the frozen choice list — a junk ``?type=`` is an un-preselected builder, not an error page.
    """
    initial_type = request.GET.get("type", "").strip()
    if initial_type not in dict(ProjectReport.REPORT_TYPE_CHOICES):
        initial_type = ""
    return crud_create(
        request,
        form_class=partial(ProjectReportForm, user=request.user),
        template=TEMPLATE_FORM,
        success_url="projects:rep_list",
        extra_context={
            **_builder_context(),
            "initial_type": initial_type,
        },
    )


@login_required
def rep_edit(request, pk):
    """Edit the definition. Owner and favourite are not here — they are verbs and a transfer."""
    # R7, and the reason this route is not a bare ``crud_edit`` call: the helper's own fetch is
    # ``tenant=`` scoped only, so the guard below is what 404s a colleague's private report before
    # the helper resolves the pk. The second fetch inside crud_edit is on the same tenant and is
    # harmless — the check, not the object, is what this line is for.
    get_object_or_404(analytics.visible_reports(request), pk=pk)
    return crud_edit(
        request,
        model=ProjectReport,
        pk=pk,
        form_class=ProjectReportForm,
        template=TEMPLATE_FORM,
        success_url="projects:rep_list",
        extra_context=_builder_context(pk),
    )


@login_required
def rep_detail(request, pk):
    """The question and its LIVE answer, plus the frozen history behind it.

    Hand-written because it computes (R9). The twelve result keys are unpacked here by name — the
    same names ``standard.html`` is given — because both pages share ``_result_table.html`` and
    ``_result_chart.html``, and a dict the view merges in silence is how one of the two pages ends
    up with a blank region at HTTP 200 (L8).
    """
    obj = get_object_or_404(
        analytics.visible_reports(request).select_related(
            "owner", "project", "portfolio", "client", "org_unit"),
        pk=pk)
    result = analytics.compute_report(obj)
    chart_type = result.get("chart_type") or "table"
    chart_labels = result.get("chart_labels") or []
    chart_data = result.get("chart_data") or []
    summary = result.get("summary") or {}
    rating = result.get("rating") or ""
    # A custom report has no canned section to lay out, so it renders the generic result partials
    # only (D24). The registry is still the authority on the axes a canned kind means.
    entry = analytics.STANDARD_REPORTS.get(obj.report_type) if obj.is_canned else None
    sections = [i for i in (entry or {}).get("sections") or [] if i.get("area") in SECTION_AREAS]

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "result": result,
        "summary": summary,
        "summary_cards": analytics.summary_pairs(summary),
        "columns": result.get("columns") or [],
        "rows": result.get("rows") or [],
        "chart_type": chart_type,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "chart_config": chart_config(chart_type, chart_labels, chart_data),
        "chart_rows": chart_rows(chart_labels, chart_data),
        "canvas_charts": CANVAS_CHARTS,
        "caveats": result.get("caveats") or [],
        "truncated": bool(result.get("truncated")),
        "rating": rating,
        "rag_css": analytics.RAG_CSS.get(rating, "badge-muted"),
        "sections": sections,
        "section_templates": [
            f"projects/reporting/_standard_section_{i['area']}.html" for i in sections
        ],
        # Meta.ordering is newest-first, so this slice is the ten most recent freezes. Through
        # ``visible_runs`` rather than a raw ``tenant=`` on the reverse relation: R7 keeps this helper the
        # ONE fetch shape in the module, and the two agree here because a run inherits its parent's
        # privacy and this page's parent is already visibility-gated.
        "runs": analytics.visible_runs(request).filter(report=obj).select_related("generated_by")[:10],
        "is_owner": obj.owner_id == request.user.id,
        # Contract-pinned. The fetch above already 404s a tenant-less caller (``visible_reports`` is
        # empty without a tenant), so the template's gate is belt-and-braces, not a live branch.
        "can_run": request.tenant is not None,
        "freeze_url": reverse("projects:rep_freeze", args=[obj.pk]),
        "csv_url": reverse("projects:rep_csv", args=[obj.pk]),
        "json_url": reverse("projects:rep_json", args=[obj.pk]),
        "run_url": reverse("projects:rep_run", args=[obj.pk]),
    })


# ---------------------------------------------------------------------------------
# verbs (POST only)
# ---------------------------------------------------------------------------------
@login_required
@require_POST
def rep_delete(request, pk):
    """Drop the definition. Its frozen runs go with it (CASCADE, A1.6).

    No context: the helper only redirects. The guard-fetch is here for the same reason as
    ``rep_edit``'s — ``crud_delete``'s fetch is tenant-scoped, not ACL-scoped. The confirm dialog's
    "and its N frozen runs" count is read off the row's own data attribute, not a context key, so
    this page never pays for a count it only shows to the one person clicking.
    """
    get_object_or_404(analytics.visible_reports(request), pk=pk)
    return crud_delete(request, model=ProjectReport, pk=pk, success_url="projects:rep_list")


@login_required
@require_POST
def rep_run(request, pk):
    """Ask the question now: compute, stamp, and land on the page that shows the answer.

    Nothing is stored — a run is an event, not a result. That is the difference between this and
    ``rep_freeze``, and the reason the register's "last run" column can be honest.
    """
    obj = get_object_or_404(analytics.visible_reports(request), pk=pk)
    result = analytics.compute_report(obj)
    # D32: the payload carries no ``row_count`` key — a stored answer that repeats what its own rows
    # say is a number that can disagree with them.
    row_count = len(result.get("rows") or [])
    # .update(), not obj.save(): auto_now on updated_at would let "somebody pressed Run" claim that
    # the definition changed, which is exactly what the audit trail is read for (A1.0).
    ProjectReport.objects.filter(pk=obj.pk, tenant=request.tenant).update(
        last_run_at=timezone.now())
    write_audit_log(request.user, obj, "update", changes={"verb": "run", "rows": row_count})
    messages.success(request, f"{obj.number} ran — {row_count} rows.")
    return redirect("projects:rep_detail", pk=obj.pk)


@login_required
@require_POST
def rep_freeze(request, pk):
    """Pin this answer: the ONLY writer of ``ProjectReportRun`` rows in the entire app (A1.1).

    Compute, insert and the ``last_run_at`` stamp are one transaction: a run whose payload saved
    but whose parent still says "never run" (or the other way round) is a record nobody can trust.
    Nothing recomputes a frozen run afterwards — that immutability is the whole reason this table
    exists, since "amber for six weeks" is derivable from nothing else.
    """
    obj = get_object_or_404(analytics.visible_reports(request), pk=pk)
    # resolve_window with the report's own as-of anchor mirrors what compute_report did (it reads
    # the same spec["as_of"]), so the frozen period cannot disagree with the frozen rows. The
    # payload's own ``window`` is off-limits here: json_safe already turned those dates to strings.
    window = analytics.resolve_window(obj, as_of=obj.as_of)
    with transaction.atomic():
        result = analytics.compute_report(obj)
        rows = result.get("rows") or []
        run = ProjectReportRun.objects.create(
            tenant=request.tenant,
            report=obj,
            title=obj.name,
            period_from=window["start"],
            period_to=window["end"],
            as_of=obj.as_of or timezone.localdate(),
            generated_by=request.user,
            summary=result.get("summary") or {},
            # ``summary`` has its own column so a run's KPI strip reads without unpickling the
            # register; every other key the engine returned is stored verbatim (R5 — no view-side
            # conversion), which is what keeps a run self-describing after its report is edited.
            data={key: value for key, value in result.items() if key != "summary"},
            row_count=len(rows),
            narrative=analytics.narrative_seed(request.tenant, obj, result),
        )
        ProjectReport.objects.filter(pk=obj.pk, tenant=request.tenant).update(
            last_run_at=timezone.now())
    write_audit_log(request.user, run, "freeze", changes={"verb": "freeze", "rows": len(rows)})
    messages.success(request, f"Frozen {obj.number} — {len(rows)} rows.")
    return redirect("projects:run_detail", pk=run.pk)


@login_required
@require_POST
def rep_favorite(request, pk):
    """Star it, unstar it. The register's own order puts favourites first.

    A toggle, never a checkbox on the record form: an edit form rendered before somebody else
    starred it would save the star back off and lose their change.
    """
    obj = get_object_or_404(analytics.visible_reports(request), pk=pk)
    new = not obj.is_favorite
    ProjectReport.objects.filter(pk=obj.pk, tenant=request.tenant).update(is_favorite=new)
    write_audit_log(request.user, obj, "toggle",
                    changes={"verb": "favorite", "is_favorite": str(new)})
    messages.success(request, "Added to favourites." if new else "Removed from favourites.")
    # Back to wherever the star was clicked — the register or a detail page — not to a fixed route.
    return redirect_back_or(request, "projects:rep_list")


# ---------------------------------------------------------------------------------
# exports (GET, non-HTML)
# ---------------------------------------------------------------------------------
@login_required
def rep_csv(request, pk):
    """The live answer as a download. Computed for this request, so it is not the frozen run's file.

    ``csv_response`` is the one writer for both 7.16 exports: it puts every cell through
    ``csv_safe`` (a report cell is people-typed text, and ``=cmd|...`` executes on the reader's
    machine) and caps the row set at ``analytics.MAX_EXPORT_ROWS``. The filename is header material
    and reaches the reader's browser unparsed, so it carries the system-assigned ``number`` and
    never ``obj.name`` — a newline or a quote in a report title would otherwise become a second
    header line.
    """
    obj = get_object_or_404(analytics.visible_reports(request), pk=pk)
    result = analytics.compute_report(obj)
    row_count = len(result.get("rows") or [])
    write_audit_log(request.user, obj, "export", changes={"verb": "csv", "rows": row_count})
    return csv_response(f"{obj.number}.csv", result.get("columns") or [], result.get("rows") or [])


@login_required
def rep_json(request, pk):
    """The live answer as the envelope a machine reads: meta / columns / rows / summary / chart.

    This is the payload 7.18's token feed hangs off — the shape is pinned here so Integration & API
    Hub has something to point a share token at. The feed itself, its tokens and their expiry are
    7.18's job: there is no unauthenticated access to this route today, it is ``@login_required``
    and ACL-scoped like every other fetch in this module.

    No ``safe=True`` dance: analytics is the only layer that converts (R5), so a ``Decimal`` or a
    ``date`` reaching this dict is a build failure to fix upstream, not something to patch here.
    """
    obj = get_object_or_404(analytics.visible_reports(request), pk=pk)
    result = analytics.compute_report(obj)
    rows = result.get("rows") or []
    write_audit_log(request.user, obj, "export", changes={"verb": "json"})
    return JsonResponse({
        "meta": {
            "report": obj.number,
            "name": obj.name,
            "kind": obj.report_type,
            "scope": obj.scope_label,
            "window": obj.window_label,
            "generated_at": timezone.now().isoformat(),
            "row_count": len(rows),
            "truncated": bool(result.get("truncated")),
        },
        "columns": result.get("columns") or [],
        "rows": rows,
        "summary": result.get("summary") or {},
        "chart": {
            "type": result.get("chart_type") or "table",
            "labels": result.get("chart_labels") or [],
            "data": result.get("chart_data") or [],
        },
        "caveats": result.get("caveats") or [],
    })
