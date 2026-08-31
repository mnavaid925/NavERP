"""Procurement 6.14 Spend Analytics & Reporting — SpendReport + SpendReportSnapshot views.

**Custom Report Builder** bullet. Twelve routes over ONE entity file (a ``SpendReport`` and the
snapshots it owns are one subject, so they share a module the way ``Invoice`` shares one with
``InvoiceLine``): the register, one detail page that RUNS the report live, create/edit/delete, the
three verbs (``run`` / ``snapshot`` / ``favorite``), a CSV download, and the snapshot's own
detail / export / delete.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. Both models carry
  their own ``tenant`` column, so a snapshot is fetched on its own row rather than through its
  parent report.
* **``is_shared`` is ENFORCED, not merely labelled.** Every fetch in this module goes through
  ``_visible(request)`` (reports) or ``_snapshot_qs(request)`` (their frozen runs), which is
  "shared, OR mine". A colleague's private report is a 404 on list, detail, edit, delete, run,
  snapshot, favourite and export alike — the pages print "Private to the owner", so the code has
  to mean it.
* **Opening the detail page is not a run.** It computes and renders, and stamps NOTHING —
  ``last_run_at`` moves only under the explicit ``run`` / ``snapshot`` POSTs, so the stamp never
  claims a colleague ran a report they merely read.
* **Nothing here writes to ``accounting.*``** — no Bill, no JournalEntry, no Budget, no Payment
  (L29). 6.14 is a read-only analytics pass over spend that already exists.
* **``SpendReportSnapshot`` has NO form and NO create/edit view, by design** — the documented
  CRUD exemption. A snapshot exists to freeze a computed result verbatim; a hand-typed one would
  be a figure with no run behind it. It is minted ONLY by ``spendreport_snapshot`` and rendered
  AS-IS by ``spendreportsnapshot_detail``, which recomputes nothing.
* **Every exported cell goes through ``csv_safe``.** Report names, descriptions and the supplier
  / line-description labels inside a computed row are user-authored, and Excel executes a leading
  ``=``/``+``/``-``/``@``. That neutralisation is not optional.

The builder is **guided** — measure, dimensions, grain and Top-N are chosen from dropdowns. The
CSV download is a download: no BI/PowerBI connector is implemented anywhere in this sub-module,
and no label in it may claim one.
"""
import csv

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.procurement import analytics
from apps.procurement.forms.SpendAnalyticsReporting.SpendReports import SpendReportForm
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.SpendAnalyticsReporting.SpendReports import (
    BASIS_CHOICES, CHART_TYPE_CHOICES, DATE_RANGE_CHOICES, DIMENSION_CHOICES, MEASURE_CHOICES,
    SpendReport, SpendReportSnapshot)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import csv_safe

TEMPLATE_LIST = "procurement/spendanalytics/spendreport/list.html"
TEMPLATE_DETAIL = "procurement/spendanalytics/spendreport/detail.html"
TEMPLATE_FORM = "procurement/spendanalytics/spendreport/form.html"
TEMPLATE_SNAPSHOT_DETAIL = "procurement/spendanalytics/spendreportsnapshot/detail.html"

#: How many saved runs the detail page's snapshot panel lists. A cap, not a page: the panel is a
#: way back to a frozen figure, not an archive browser.
SNAPSHOT_PANEL_LIMIT = 50

#: Every hop a register row (or its ``__str__``) walks. ``owner`` is rendered per row and the four
#: filter FKs are shown as the report's "narrowed to" pills — without this each is a query PER ROW.
_ROW_RELATIONS = ("owner", "vendor", "category", "org_unit", "gl_account")

#: Printed on the list and both form pages. ONE constant so the three surfaces cannot describe the
#: builder differently — and so the description stays honest about what it is.
BUILDER_NOTE = (
    "The report builder is guided: pick a measure, up to two dimensions, a window and a Top-N cut "
    "from the dropdowns, and the result is computed live over invoiced or committed spend every "
    "time the report is opened. Nothing is stored until you take a snapshot."
)

#: Printed wherever a department breakdown appears. There is no department column on an invoice —
#: it is a nullable 3-hop chain through the purchase order — so the bucket that has no answer is
#: shown rather than dropped. A breakdown that silently drops rows makes its own total disagree
#: with the KPI beside it.
DEPARTMENT_CAVEAT = (
    "Department is resolved through the purchase order (requisition cost centre, falling back to "
    "the ship-to unit). Invoices raised without a purchase order have no department, so they are "
    "reported in an explicit \"(unassigned)\" bucket rather than dropped."
)


# -- shared helpers ------------------------------------------------------------------------------

def _need_tenant(request, what):
    """Refuse a tenant-less user (the superuser has ``tenant=None``) before any write.

    Mirrors ``crud_create``'s own guard so the hand-rolled form path below cannot create orphan
    rows that no workspace can ever see again.
    """
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None


def _visible(request):
    """Every report this caller may see: the SHARED ones, plus their own private ones.

    ``is_shared`` is a real access-control claim — the list and the detail page both print
    "Private to the owner" against a report without it — so it is enforced in ONE place and every
    fetch in this module goes through it. A private report belonging to a colleague is a 404 here,
    not merely an unlabelled row: an unenforced promise is worse than no promise.

    Still tenant-scoped first: visibility narrows what a workspace member sees INSIDE their
    workspace and never widens it across one.
    """
    return (SpendReport.objects.filter(tenant=request.tenant)
            .filter(Q(is_shared=True) | Q(owner=request.user)))


def _snapshot_qs(request):
    """Snapshots of the reports this caller may see — a frozen run inherits its parent's privacy."""
    return (SpendReportSnapshot.objects.filter(tenant=request.tenant)
            .filter(report__in=_visible(request)))


def _report_qs(request):
    return _visible(request).select_related(*_ROW_RELATIONS)


def _as_list(value):
    """A JSON value coerced to a list — a stored payload is data, never trusted to be shaped."""
    return list(value) if isinstance(value, (list, tuple)) else []


def _result_table(result):
    """``(columns, rows)`` out of a computed result or a stored snapshot payload."""
    columns = [str(c) for c in _as_list((result or {}).get("columns"))]
    rows = [_as_list(row) for row in _as_list((result or {}).get("rows"))]
    return columns, rows


def _csv_response(filename, columns, rows):
    """One CSV writer for both export routes — every cell neutralised, the row count capped.

    ``csv_safe`` prefixes a leading ``=``/``+``/``-``/``@`` so a supplier name or a line
    description typed by somebody else cannot become a formula in the reader's spreadsheet.
    """
    response = HttpResponse(content_type="text/csv")
    # The filename is built from a system-assigned number / pk only — never from user text, which
    # would put a newline or a quote into a response header.
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    if columns:
        writer.writerow([csv_safe(column) for column in columns])
    for row in rows[:analytics.MAX_EXPORT_ROWS]:
        writer.writerow([csv_safe("" if cell is None else cell) for cell in row])
    return response


def _row_cap_note(report):
    return (
        f"Grouped results keep the top {report.top_n} rows of each dimension; the CSV download is "
        f"capped at {analytics.MAX_EXPORT_ROWS:,} rows."
    )


def _report_form(request, instance=None):
    """Build or amend one report.

    Hand-rolled rather than ``crud_create``/``crud_edit`` for one reason: ``owner`` is an
    authorship stamp taken from ``request.user`` on CREATE only, and the shared helpers have no
    hook for it. Amending a report must never silently transfer who built it.
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = SpendReportForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not is_edit:
                obj.owner = request.user if request.user.is_authenticated else None
            obj.save()
            write_audit_log(
                request.user, obj, "update" if is_edit else "create",
                changes={name: str(form.cleaned_data.get(name))[:200]
                         for name in form.changed_data})
            messages.success(request, f"Report {obj.number} saved.")
            return redirect("procurement:spendreport_detail", pk=obj.pk)
    else:
        form = SpendReportForm(instance=instance, tenant=request.tenant)

    ctx = {
        "form": form,
        "is_edit": is_edit,
        "title": "Edit report" if is_edit else "New spend report",
        "submit_label": "Save changes" if is_edit else "Create report",
        "cancel_url": (reverse("procurement:spendreport_detail", args=[instance.pk]) if is_edit
                       else reverse("procurement:spendreport_list")),
        "builder_note": BUILDER_NOTE,
    }
    if is_edit:
        # ``obj`` is deliberately absent from the CREATE context — the form template guards
        # ``{% if obj %}`` for the pieces that only make sense once a report has a number.
        ctx["obj"] = instance
    return render(request, TEMPLATE_FORM, ctx)


# -- the register --------------------------------------------------------------------------------

@login_required
def spendreport_list(request):
    """Saved reports, favourites pinned first (model ordering)."""
    # The stat cards count what the register SHOWS, so a private report belonging to somebody
    # else is neither listed nor silently included in the totals above the list.
    base = _visible(request)
    stats = {
        "total": base.count(),
        "favorites": base.filter(is_favorite=True).count(),
        "shared": base.filter(is_shared=True).count(),
        "snapshots": _snapshot_qs(request).count(),
    }
    return crud_list(
        request, _report_qs(request), TEMPLATE_LIST,
        search_fields=("number", "name", "description"),
        # Every int/FK filter would need the ``as_db_int`` guard; these three are plain strings and
        # booleans, and ``crud_list`` already maps "True"/"False" and swallows a bogus value rather
        # than 500ing on a hand-edited query string (L11).
        filters=(("measure", "measure", False),
                 ("basis", "basis", False),
                 ("is_favorite", "is_favorite", False)),
        extra_context={
            "measure_choices": MEASURE_CHOICES,
            "basis_choices": BASIS_CHOICES,
            "dimension_choices": DIMENSION_CHOICES,
            "chart_type_choices": CHART_TYPE_CHOICES,
            "date_range_choices": DATE_RANGE_CHOICES,
            "stats": stats,
            "builder_note": BUILDER_NOTE,
        },
    )


@login_required
def spendreport_detail(request, pk):
    """Run the report LIVE and render it. Stamps nothing — see the module docstring."""
    report = get_object_or_404(_report_qs(request), pk=pk)
    result = analytics.compute_report(report)
    start, end = analytics.range_bounds(report.date_range, report.date_from, report.date_to)
    split = analytics.currency_split(report.tenant, report.basis, start, end) or {}

    snapshots = (report.snapshots.filter(tenant=request.tenant)
                 .select_related("generated_by")
                 # ``summary``/``data`` are the heavy JSON columns and the panel renders neither.
                 .only("pk", "title", "generated_at", "row_count", "report",
                       "generated_by__username", "generated_by__first_name",
                       "generated_by__last_name")[:SNAPSHOT_PANEL_LIMIT])

    return render(request, TEMPLATE_DETAIL, {
        "obj": report,
        "report": report,
        "result": result,
        "snapshots": snapshots,
        "start": start,
        "end": end,
        "mixed_currency": bool(split.get("mixed_currency")),
        "currency_rows": _as_list(split.get("rows")),
        "row_cap_note": _row_cap_note(report),
        "last_run_at": report.last_run_at,
        "export_url": reverse("procurement:spendreport_export", args=[report.pk]),
        "snapshot_url": reverse("procurement:spendreport_snapshot", args=[report.pk]),
        "run_url": reverse("procurement:spendreport_run", args=[report.pk]),
        "favorite_url": reverse("procurement:spendreport_favorite", args=[report.pk]),
        "builder_note": BUILDER_NOTE,
        # Only meaningful when an axis is the department one; empty otherwise so the template's
        # note block stays out of the way.
        "department_caveat": DEPARTMENT_CAVEAT if report.uses_department_axis else "",
    })


@login_required
def spendreport_create(request):
    guard = _need_tenant(request, "create spend reports")
    if guard is not None:
        return guard
    return _report_form(request)


@login_required
def spendreport_edit(request, pk):
    report = get_object_or_404(_visible(request), pk=pk)
    return _report_form(request, instance=report)


@login_required
@require_POST
def spendreport_delete(request, pk):
    # ``crud_delete`` takes a MODEL, not a queryset, so the visibility check happens here: a
    # colleague's private report must 404 rather than be deleted by anyone in the workspace.
    get_object_or_404(_visible(request), pk=pk)
    return crud_delete(request, model=SpendReport, pk=pk,
                       success_url="procurement:spendreport_list")


# -- verbs ---------------------------------------------------------------------------------------

@login_required
@require_POST
def spendreport_run(request, pk):
    """Record an explicit run. The figures themselves are always live — this is the stamp."""
    report = get_object_or_404(_visible(request), pk=pk)
    now = timezone.now()
    # ``.update()`` so the system stamp does not bump ``updated_at`` (auto_now) and pretend the
    # report's definition was edited.
    SpendReport.objects.filter(pk=report.pk, tenant=request.tenant).update(last_run_at=now)
    report.last_run_at = now
    write_audit_log(request.user, report, "update", {"last_run_at": str(now)})
    messages.success(request, f"{report.number} re-run.")
    return redirect("procurement:spendreport_detail", pk=report.pk)


@login_required
@require_POST
def spendreport_snapshot(request, pk):
    """Freeze the current result as a ``SpendReportSnapshot``.

    Two rows move together — the snapshot and the parent's ``last_run_at`` — so both happen
    inside one ``transaction.atomic()``: a snapshot whose parent never recorded the run would
    misreport when the figure was taken.
    """
    report = get_object_or_404(_visible(request), pk=pk)
    result = analytics.compute_report(report) or {}
    _columns, rows = _result_table(result)
    now = timezone.now()

    with transaction.atomic():
        snapshot = SpendReportSnapshot.objects.create(
            tenant=request.tenant,
            report=report,
            title=f"{report.name} — {now:%Y-%m-%d %H:%M}"[:160],
            generated_by=request.user if request.user.is_authenticated else None,
            summary=_as_list(result.get("summary")),
            # Stored verbatim and re-rendered AS-IS. Everything ``compute_report`` returns is
            # JSON-serialisable by contract, which is what makes that possible.
            data={key: result.get(key) for key in
                  ("columns", "rows", "chart_type", "chart_labels", "chart_data")},
            row_count=len(rows),
        )
        SpendReport.objects.filter(pk=report.pk, tenant=request.tenant).update(last_run_at=now)
        write_audit_log(request.user, snapshot, "create", {"report": report.number,
                                                           "row_count": len(rows)})
    messages.success(request, f"Snapshot saved — {len(rows)} row(s) frozen.")
    return redirect("procurement:spendreportsnapshot_detail", pk=snapshot.pk)


@login_required
@require_POST
def spendreport_favorite(request, pk):
    """Pin / unpin. Returns to wherever the toggle was clicked (list or detail)."""
    report = get_object_or_404(_visible(request), pk=pk)
    report.is_favorite = not report.is_favorite
    report.save(update_fields=["is_favorite", "updated_at"])
    write_audit_log(request.user, report, "update", {"is_favorite": report.is_favorite})
    messages.success(request, "Pinned to the top." if report.is_favorite else "Unpinned.")

    # "Back where you came from" has to be VALIDATED — an unchecked next/referer is an open
    # redirect, and this is a POST any logged-in page can carry.
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect("procurement:spendreport_detail", pk=report.pk)


@login_required
def spendreport_export(request, pk):
    """CSV of the report's own rows, with the report's saved filters applied.

    A download, not a feed: there is no live BI/PowerBI connector anywhere in this sub-module.
    """
    report = get_object_or_404(_visible(request), pk=pk)
    columns, rows = _result_table(analytics.compute_report(report))
    return _csv_response(f"spend-report-{report.number or report.pk}.csv", columns, rows)


# -- snapshots (no form, no create/edit — see the module docstring) -------------------------------

@login_required
def spendreportsnapshot_detail(request, pk):
    """Render a frozen run exactly as it was stored. NOTHING here is recomputed."""
    snapshot = get_object_or_404(
        _snapshot_qs(request).select_related("report", "generated_by"), pk=pk)
    data = snapshot.data if isinstance(snapshot.data, dict) else {}
    columns, rows = _result_table(data)
    chart_type = data.get("chart_type")

    return render(request, TEMPLATE_SNAPSHOT_DETAIL, {
        "obj": snapshot,
        "snapshot": snapshot,
        "report": snapshot.report,
        "summary": _as_list(snapshot.summary),
        "columns": columns,
        "rows": rows,
        "chart_type": chart_type if isinstance(chart_type, str) else "table",
        "chart_labels": _as_list(data.get("chart_labels")),
        "chart_data": _as_list(data.get("chart_data")),
        # The same series pre-zipped for the table underneath the chart. A template cannot walk
        # two parallel lists without index gymnastics that silently render the wrong cell, so the
        # pairing happens here, where a reader can check it. ``zip`` stops at the shorter list, so
        # a payload whose two arrays disagree renders the pairs it can rather than raising.
        "chart_rows": [{"label": label, "value": value} for label, value in
                       zip(_as_list(data.get("chart_labels")), _as_list(data.get("chart_data")))],
        "export_url": reverse("procurement:spendreportsnapshot_export", args=[snapshot.pk]),
        "delete_url": reverse("procurement:spendreportsnapshot_delete", args=[snapshot.pk]),
        "back_url": reverse("procurement:spendreport_detail", args=[snapshot.report_id]),
    })


@login_required
def spendreportsnapshot_export(request, pk):
    """CSV straight out of the stored payload — no recompute, so the file matches the page."""
    snapshot = get_object_or_404(_snapshot_qs(request), pk=pk)
    data = snapshot.data if isinstance(snapshot.data, dict) else {}
    columns, rows = _result_table(data)
    return _csv_response(f"spend-report-snapshot-{snapshot.pk}.csv", columns, rows)


@login_required
@require_POST
def spendreportsnapshot_delete(request, pk):
    """Discard a frozen run and return to the report that owns it."""
    snapshot = get_object_or_404(_snapshot_qs(request), pk=pk)
    report_pk = snapshot.report_id
    write_audit_log(request.user, snapshot, "delete")
    snapshot.delete()
    messages.success(request, "Snapshot deleted.")
    return redirect("procurement:spendreport_detail", pk=report_pk)
