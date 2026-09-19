"""Projects 7.16 Reporting & Business Intelligence — the four standalone reporting pages.

Computed on read from the modules that own the data: these pages hold no table, write no row
and do no arithmetic. :mod:`apps.projects.analytics` is the single compute layer, so a figure
on the home page, a tile, a saved report and a frozen run are one answer, not four look-alikes.

* ``rbi_home`` — the landing register: the caller's board, the questions that recently ran, the
  counts that show the engine is populated, and the sibling boards 7.16 links to instead of
  re-deriving.
* ``report_library`` — the catalogue of canned kinds, each with its count of saved questions.
* ``report_standard`` — one canned kind computed for one scope and one window.
* ``exec_pack`` — the steering-committee pack, laid out for browser print (``?print=1``).

Every fetch goes through the ``analytics.visible_*`` helpers, so a private question owned by a
colleague does not exist here at all. A request with no tenant (the site superuser) gets four
legitimately empty pages, never an error.
"""
from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils.dateparse import parse_date

from apps.core.crud import as_db_int
from apps.projects import analytics
from apps.projects.models import Portfolio, ProjectReport
from apps.projects.models.ReportingBusinessIntelligence._choices import CANVAS_CHARTS
from apps.projects.views._common import login_required, render, timezone
from apps.projects.views._helpers import SECTION_AREAS, chart_config, chart_rows
from apps.projects.views._helpers import clients as client_choices
from apps.projects.views._helpers import org_units as org_unit_choices
from apps.projects.views._helpers import projects as project_choices

TEMPLATE_HOME = "projects/reporting/home.html"
TEMPLATE_LIBRARY = "projects/reporting/library.html"
TEMPLATE_STANDARD = "projects/reporting/standard.html"
TEMPLATE_EXEC_PACK = "projects/reporting/exec_pack.html"

#: The params the result filter bar echoes back, in bar order.
SCOPE_PARAMS = ("project", "portfolio", "client", "org_unit", "from", "to")

#: The windows a canned page may narrow to. ``custom`` is absent: a canned kind carries no date
#: pair of its own, so the registry alone decides its window.
RANGE_KEYS = frozenset(key for key, _label in analytics.PRESET_RANGES)

#: Sub-module number -> its NavERP title, so the sibling panel groups the boards by subject. An
#: unknown number falls back to the number itself, so a new row still renders.
SUBMODULE_TITLES = {
    "7.2": "Project Planning & Scheduling",
    "7.3": "Resource Management",
    "7.5": "Risk & Issue Management",
    "7.6": "Quality Management",
    "7.12": "Portfolio & Program Management",
    "7.13": "Agile & Scrum Management",
    "7.15": "Financial & Billing Management",
}

#: The pack's "go deeper" row: siblings that already compute these are linked, never re-derived.
PACK_DRILLS = (
    ("Portfolio dashboard", "projects:pfm_dashboard"),
    ("Project P&L", "projects:financial_pnl"),
    ("Risk analysis", "projects:risk_analysis"),
    ("Utilization dashboard", "projects:utilization_dashboard"),
)


# ---------------------------------------------------------------------------------
# shared builders
# ---------------------------------------------------------------------------------
def _resolve_url(url_name):
    """A route name -> its path, or ``""`` when the route needs an argument this page lacks.

    Dropping the link is the point: a panel of shortcuts must not take its own page down because
    a neighbour's route is per-object (the quality-review report is) or was renamed.
    """
    if not url_name:
        return ""
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return ""


def _parse_date(value):
    """A ``?as_of`` / ``?from`` / ``?to`` string as a date, or ``None``.

    Junk is a missing filter, never a traceback — the rule ``as_db_int`` states for a pk.
    """
    return parse_date((value or "").strip())


def _echo(request):
    """The filter bar's raw echo strings.

    Never the parsed int: ``?project=abc`` comes back as ``abc``, so it matches no option.
    """
    return {key: request.GET.get(key, "").strip() for key in SCOPE_PARAMS}


def _portfolios(tenant):
    """Portfolios for a scope dropdown — empty without a tenant, never an error."""
    if tenant is None:
        return Portfolio.objects.none()
    return Portfolio.objects.filter(tenant=tenant).order_by("name")


def _sibling_boards():
    """The already-built reporting surfaces, resolved to paths and grouped by sub-module."""
    boards = []
    for entry in analytics.SIBLING_BOARDS:
        url = _resolve_url(entry["url_name"])
        if not url:
            continue
        module = entry["module"]
        boards.append({
            "label": entry["label"],
            "url": url,
            "group": SUBMODULE_TITLES.get(module, module),
            "module": module,
        })
    return boards


def _drill_rows(entries):
    """``[{"label", "url"}]`` from (label, route name) pairs, skipping what will not resolve."""
    rows = []
    for label, url_name in entries:
        url = _resolve_url(url_name)
        if url:
            rows.append({"label": label, "url": url})
    return rows


def _report_link(kind, canned):
    """Where a library row leads: the canned compute page, or the builder for an unbuilt kind."""
    name = "projects:report_standard" if canned else "projects:rep_create"
    return f"{reverse(name)}?type={kind}"


def _builder_url(kind, echo):
    """The builder, prefilled with the question this page just answered.

    Only echoes that carry something are appended, so a saved report starts from the scope the
    reader picked instead of from six empty fields.
    """
    pairs = [f"type={kind}"] + [f"{key}={echo[key]}" for key in SCOPE_PARAMS if echo[key]]
    return f"{reverse('projects:rep_create')}?{'&'.join(pairs)}"


def _quick_library():
    """The home page's canned-report grid — the registry read alone, no query."""
    rows = []
    for kind, entry in analytics.STANDARD_REPORTS.items():
        subject = entry.get("subject") or ""
        rows.append({
            "type": kind,
            "label": entry["label"],
            "subject": analytics.SUBJECTS.get(subject, subject),
            "url": _report_link(kind, True),
        })
    return rows


def _library_rows(request):
    """One row per report kind, in choice order — the library page's entire content.

    ``saved_count`` comes from ONE grouped read, and it counts what this caller may see rather
    than the whole table, so the kinds add up to the home page's own report count.
    """
    visible = analytics.visible_reports(request)
    saved = {
        row["report_type"]: row["total"]
        # The explicit order_by replaces the model's default ordering: left in, those columns join the
        # GROUP BY and the read comes back per report rather than per kind.
        for row in visible.values("report_type").annotate(total=Count("id")).order_by("report_type")
    }
    rows = []
    for kind, label in ProjectReport.REPORT_TYPE_CHOICES:
        entry = analytics.STANDARD_REPORTS.get(kind)
        subject = (entry or {}).get("subject") or ""
        rows.append({
            "type": kind,
            "label": label,
            "subject": subject,
            "subject_label": analytics.SUBJECTS.get(subject, subject),
            "description": (entry or {}).get("description") or "",
            "sections": (entry or {}).get("sections") or [],
            "is_canned": entry is not None,
            "url": _report_link(kind, entry is not None),
            "saved_count": saved.get(kind, 0),
        })
    return rows


def _attach_band_drills(bands):
    """Give each RAG band the URL its row links to.

    The compute layer hands out a route name and a pk because it must stay import-safe; resolving
    is the view's job, and each band already carries its own project.
    """
    for band in bands:
        url_name = band.pop("drill_url_name", "")
        pk = band.pop("drill_pk", None)
        band["drill_url"] = reverse(url_name, args=[pk]) if url_name and pk else ""


# ---------------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------------
@login_required
def rbi_home(request):
    """The reporting landing page: what ran, what is saved, what the engine already covers."""
    reports = analytics.visible_reports(request)
    dashboards = analytics.visible_dashboards(request)
    runs = analytics.visible_runs(request)
    return render(request, TEMPLATE_HOME, {
        "object_list": list(
            reports.select_related("owner").order_by("-last_run_at", "-id")[:5]
        ),
        "my_dashboard": analytics.home_dashboard(request),
        "recent_runs": runs.select_related("report", "generated_by")[:10],
        "dashboards": dashboards.annotate(annotation_count=Count("widgets"))[:6],
        "sibling_boards": _sibling_boards(),
        "library": _quick_library(),
        "counts": {
            "reports": reports.count(),
            "dashboards": dashboards.count(),
            "runs": runs.count(),
            "issued": runs.filter(status="issued").count(),
        },
        "can_build": request.tenant is not None,
    })


@login_required
def report_library(request):
    """The catalogue: every canned kind, its subject and how many saved questions back it."""
    library = _library_rows(request)
    return render(request, TEMPLATE_LIBRARY, {
        "library": library,
        "total_kinds": len(library),
        "sibling_boards": _sibling_boards(),
        # An unknown ``?type=`` narrows nothing: the list stays whole, the banner says why.
        "type_filter": request.GET.get("type", "").strip(),
    })


@login_required
def report_standard(request):
    """One canned kind for one scope and window — every canned kind renders through here."""
    kind = request.GET.get("type", "").strip()
    if kind not in analytics.STANDARD_REPORTS:
        kind = analytics.CANNED_FALLBACK

    echo = _echo(request)
    as_of = _parse_date(request.GET.get("as_of")) or timezone.localdate()
    params = {
        "project_id": as_db_int(echo["project"]),
        "portfolio_id": as_db_int(echo["portfolio"]),
        "client_id": as_db_int(echo["client"]),
        "org_unit_id": as_db_int(echo["org_unit"]),
        "as_of": as_of,
    }
    # ``from`` / ``to`` are echoes for the bar and the builder link only: a canned kind's window
    # comes from the registry, so an explicit pair is not among the parameters it accepts.
    window = request.GET.get("range", "").strip()
    if window in RANGE_KEYS:
        params["date_range"] = window

    result = analytics.standard_report(kind, request.tenant, params)
    entry = analytics.STANDARD_REPORTS[kind]
    subject = entry.get("subject") or ""
    sections = [i for i in entry.get("sections") or [] if i.get("area") in SECTION_AREAS]
    chart_type = result.get("chart_type") or "table"
    chart_labels = result.get("chart_labels") or []
    chart_data = result.get("chart_data") or []
    summary = result.get("summary") or {}

    return render(request, TEMPLATE_STANDARD, {
        "kind": kind,
        "kind_meta": {
            "label": entry["label"],
            "subject": analytics.SUBJECTS.get(subject, subject),
            "description": entry.get("description") or "",
            "sections": sections,
            "drill": _resolve_url(entry.get("drill_url_name")),
        },
        "sections": sections,
        "section_templates": [
            f"projects/reporting/_standard_section_{i['area']}.html" for i in sections
        ],
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
        "truncated": result.get("truncated") or False,
        "as_of": as_of,
        "active_filters": echo,
        "projects": project_choices(request.tenant),
        "portfolios": _portfolios(request.tenant),
        "clients": client_choices(request.tenant),
        "org_units": org_unit_choices(request.tenant),
        "report_types": ProjectReport.REPORT_TYPE_CHOICES,
        "range_choices": analytics.PRESET_RANGES,
        "save_report_url": _builder_url(kind, echo),
        "export_urls": [],
    })


@login_required
def exec_pack(request):
    """The steering pack — RAG bands, the money and the commentary, laid out for the printer."""
    echo = {
        "portfolio": request.GET.get("portfolio", "").strip(),
        "project": request.GET.get("project", "").strip(),
    }
    portfolio_id = as_db_int(echo["portfolio"])
    portfolio = (
        Portfolio.objects.filter(tenant=request.tenant, pk=portfolio_id).first()
        if portfolio_id else None
    )
    as_of = _parse_date(request.GET.get("as_of")) or timezone.localdate()

    pack = analytics.exec_pack(
        request.tenant,
        portfolio=portfolio,
        project=as_db_int(echo["project"]),
        as_of=as_of,
    )
    bands = pack.get("bands") or []
    _attach_band_drills(bands)
    chart_type = pack.get("chart_type") or "table"
    chart_labels = pack.get("chart_labels") or []
    chart_data = pack.get("chart_data") or []
    summary = pack.get("summary") or {}
    # The run ordering is newest-first, so this first row IS the latest issued steering pack.
    narrative_run = analytics.visible_runs(request).filter(
        report__report_type="steering_pack", status="issued"
    ).first()

    return render(request, TEMPLATE_EXEC_PACK, {
        "bands": bands,
        "rag_series": pack.get("rag_history") or [],
        "chart_config": chart_config(chart_type, chart_labels, chart_data),
        "chart_rows": chart_rows(chart_labels, chart_data),
        "canvas_charts": CANVAS_CHARTS,
        "summary": summary,
        "summary_cards": analytics.summary_pairs(summary),
        "narrative_run": narrative_run,
        "narrative": narrative_run.narrative if narrative_run else "",
        "as_of": as_of,
        "portfolio": portfolio,
        "active_filters": echo,
        "portfolios": _portfolios(request.tenant),
        "projects": project_choices(request.tenant),
        "print_mode": request.GET.get("print") == "1",
        "drills": _drill_rows(PACK_DRILLS),
    })
