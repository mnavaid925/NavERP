"""SCM 4.11 Supply Chain Analytics — ``KpiSnapshot``: reading the frozen history, and freezing more.

**NO create view, NO edit view and NO ModelForm — a DECISION, not an omission.**
This is a deliberate, documented exception to the CRUD-completeness rule, and it matches CRM 1.6's
``ReportSnapshot`` (``apps/crm/views/AnalyticsReporting/Snapshots.py``, which ships exactly
``detail`` + ``delete`` for the same reason). ``KpiSnapshot`` is **system-written**:

* the **create path is** :func:`kpisnapshot_capture`, which calls
  :func:`apps.scm.analytics.capture_snapshots` — a snapshot is only ever the output of
  ``compute_metric()``, so there is nothing for a form to collect;
* a hand-typed ``value`` would be a **fabricated measurement wearing the same badge as a computed
  one**, which destroys the single property this table has — that its numbers were really measured;
* what ships is **list + detail + delete** (POST-only), and delete exists because a bad capture run
  is the one thing a human legitimately needs to undo. Both templates say so on the page, so the gap
  reads as a decision rather than as a missing feature.

**The computation lives in ``apps/scm/analytics.py`` and nowhere else.**
:func:`kpisnapshot_capture` validates a period, calls ``capture_snapshots()`` and reports what came
back. It does not re-implement a single aggregate: a tile that says "4.2 turns" and a frozen point
that says 3.9 would both be defensible if each owned its own SQL, and neither would be trustworthy.
Import direction stays one-way — ``views -> analytics -> models -> _choices``.

**4.11 is READ-ONLY over 4.1-4.10.** Nothing here writes a ``StockMove`` or a ``JournalEntry``.

**Whitelisted parameters, everywhere a URL is built.** :data:`_LIST_FILTERS` is the ONLY thing that
is ever copied out of a request into a redirect target, an export link or a hidden field. Echoing
the whole request instead is how ``csrfmiddlewaretoken`` ends up in a query string — and from there
in browser history, proxy logs and the ``Referer`` header of every asset the next page loads.
"""
import csv
from datetime import date
from urllib.parse import urlencode

from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _date_window, _need_tenant
# The formula-injection escape the five report exports already use. Imported rather than reimplemented
# so there is ONE definition of "safe cell" across 4.11 — this file writes a KpiTarget.name and a
# dimension label, both of which carry free text a user typed or a party is named after.
# (Reports.py does not import this module, so there is no cycle.)
from apps.scm.views.SupplyChainAnalytics.Reports import _csv_safe

from apps.scm import analytics
from apps.scm.models import (BAND_CHOICES, KpiSnapshot, KpiTarget, METRIC_CHOICES,
                             METRIC_GROUP_PAGES, METRIC_META, format_metric_value)

#: The list page's filter vocabulary — and the WHITELIST every URL this module builds is limited to.
#: Named once so the page, the CSV link, the capture form's hidden fields and the post-capture
#: redirect cannot drift apart (and so none of them can carry anything else).
_LIST_FILTERS = ("q", "metric", "status_band", "kpi_target", "date_from", "date_to")

#: Rows one CSV export writes. Applied as a SLICE on the queryset (a SQL ``LIMIT``), with the total
#: taken by a separate ``.count()`` — so the guard is O(1) in the thing it guards and never has to
#: build the export in order to decide the export is too big (L40 §1).
MAX_EXPORT_ROWS = 5000

#: Periods of the same target+dimension series shown on a detail page.
MAX_TREND_ROWS = 12

#: Keys ``analytics._snapshot_payload`` stamps into every ``breakdown`` for identity/rendering. They
#: are already displayed as first-class fields on the detail page, so the "what produced this number"
#: list skips them and shows only the metric's own component arithmetic.
_BREAKDOWN_IDENTITY_KEYS = frozenset({
    "rows", "display", "label", "unit", "kind", "scope", "scope_label", "direction",
    "period_start", "period_end",
})


# =================================================================================================
# Shared queryset / filter spec — ONE definition, read by the page and by the CSV export
# =================================================================================================

def _snapshot_queryset(tenant):
    """Every snapshot for the tenant, with the two FKs a row renders already joined.

    ``select_related("kpi_target")`` is load-bearing, not decoration: the list renders the target's
    number and name on every row, so without it a 25-row page is 26 queries and a 5000-row export is
    5001. ``computed_by`` is joined for the same reason — the "captured by" column is on both the
    list and the export.
    """
    return (KpiSnapshot.objects.filter(tenant=tenant)
            .select_related("kpi_target", "computed_by"))


def _filtered_snapshots(request):
    """The rows the page (and therefore the export) is looking at.

    Everything is applied to the QUERYSET, before pagination and before the export's slice — a
    filter applied after the cut would report a filtered figure computed from an unfiltered page.

    ``kpi_target`` goes through ``.isdigit()`` first (L11): a hand-edited ``?kpi_target=abc`` handed
    to an int FK lookup raises inside ``.filter()`` itself and 500s a read-only page.
    """
    qs = _snapshot_queryset(request.tenant)
    q = request.GET.get("q", "").strip()
    if q:
        # `metric` is the raw registry key, which is why the human-readable words are in it
        # ("turnover" matches inv_turnover). The target's number and name are searched too because
        # that is what somebody actually types when hunting for one trend.
        qs = qs.filter(Q(metric__icontains=q) | Q(dimension_label__icontains=q)
                       | Q(kpi_target__number__icontains=q) | Q(kpi_target__name__icontains=q))
    metric = request.GET.get("metric", "").strip()
    if metric:
        qs = qs.filter(metric=metric)
    band = request.GET.get("status_band", "").strip()
    if band:
        qs = qs.filter(status_band=band)
    target = request.GET.get("kpi_target", "").strip()
    if target.isdigit():  # L11 — never hand a non-numeric GET value to an int FK filter
        qs = qs.filter(kpi_target_id=int(target))
    # The window is on `period_end` — the period a point MEASURES, not `computed_at`, the moment it
    # happened to be captured. Filtering a trend by when somebody pressed the button would put a
    # back-filled 2024 period into a "this month" answer.
    return _date_window(qs, request.GET, "period_end")


def _url_with_filters(url_name, data):
    """``url_name`` with the current filters re-attached — WHITELIST ONLY (:data:`_LIST_FILTERS`).

    Never ``urlencode(request.POST)``: the POST body carries ``csrfmiddlewaretoken``, and copying a
    whole request into a URL is exactly how a CSRF token leaks into a place it can be read from.
    """
    params = {key: (data.get(key) or "").strip() for key in _LIST_FILTERS}
    query = urlencode({key: value for key, value in params.items() if value})
    url = reverse(url_name)
    return f"{url}?{query}" if query else url


def _active_filters(data):
    """The whitelisted ``(param, value)`` pairs currently in force, for the capture form's hidden
    fields — so pressing Capture comes back to the same filtered view without the template ever
    iterating ``request.GET`` (which would re-emit whatever junk was in the URL)."""
    return [(key, (data.get(key) or "").strip()) for key in _LIST_FILTERS
            if (data.get(key) or "").strip()]


# =================================================================================================
# Read
# =================================================================================================

@login_required
def kpisnapshot_list(request):
    """The frozen history: one row per target, per period, per dimension.

    ``_filtered_snapshots`` has already applied the search, the three filters and the date window,
    so ``crud_list`` is called with neither ``search_fields`` nor ``filters`` — it is here purely for
    pagination and the pinned list context contract (``object_list`` / ``page_obj`` / ``q``, L7). The
    filter spec is a single definition because the CSV export must select exactly the rows the page
    is showing; two copies of it would silently disagree the first time one is edited.
    """
    qs = _filtered_snapshots(request)
    # ONE aggregate for the whole header, over the UNFILTERED tenant set — a "3 off target" counter
    # that quietly re-scoped itself to the current filter would say "nothing is wrong" the moment
    # somebody filtered to one metric.
    stats = KpiSnapshot.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        on_target=Count("id", filter=Q(status_band="ok")),
        off_target=Count("id", filter=Q(status_band__in=("warning", "critical"))),
        critical=Count("id", filter=Q(status_band="critical")),
        not_banded=Count("id", filter=Q(status_band="unknown")),
        last_captured=models.Max("computed_at"),
    )
    return crud_list(
        request, qs, "scm/analytics/kpisnapshot/list.html",
        extra_context={
            # Every one of these is read by a control in the filter bar. A select whose options the
            # view forgot to pass renders empty and filters nothing, which is the recurring bug the
            # filter rules in CLAUDE.md exist for.
            "metric_choices": METRIC_CHOICES,     # grouped [(group label, [(key, label), ...]), ...]
            "band_choices": BAND_CHOICES,
            # KpiTarget.__str__ is "number · name" — no FK hop, so no select_related is needed here.
            "targets": KpiTarget.objects.filter(tenant=request.tenant).order_by("name", "number"),
            "stats": stats,
            "active_target_count": KpiTarget.objects.filter(tenant=request.tenant,
                                                            is_active=True).count(),
            "active_filters": _active_filters(request.GET),
            "export_url": _url_with_filters("scm:kpisnapshot_export", request.GET),
            "today": timezone.localdate(),
            # The capture form is rendered only for the people the view will accept, rather than
            # offered to everyone and refused on submit.
            "can_capture": bool(request.user.is_superuser
                                or getattr(request.user, "is_tenant_admin", False)),
            "max_export_rows": MAX_EXPORT_ROWS,
        },
    )


def _humanize(key):
    """``dead_share_pct`` -> ``Dead share pct``. The breakdown's keys are the resolver's own, and
    there is no per-metric label table to look them up in — nor should there be, since a new metric
    must not need one."""
    return str(key).replace("_", " ").strip().capitalize() or str(key)


def _breakdown_table(breakdown):
    """``(headers, rows)`` out of the frozen ``breakdown["rows"]``.

    ``breakdown`` is a ``JSONField`` holding whatever the resolver froze, possibly months ago, and
    **every metric freezes a different row shape** (a dead-stock row is sku/quantity/value, a lane
    row is origin/destination/cost). So the columns are read off the rows themselves rather than
    declared here, and every access is isinstance-guarded: a payload written by a retired resolver —
    or edited by hand in the admin — must render as an empty table, never as a 500 on a read-only
    history page.

    The cap is applied to the SLICE before anything is built, not to the finished table.
    """
    raw = breakdown.get("rows")
    if not isinstance(raw, list):
        return [], []
    rows = [row for row in raw[:analytics.MAX_DETAIL_ROWS] if isinstance(row, dict)]
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return ([_humanize(column) for column in columns],
            [[row.get(column) for column in columns] for row in rows])


def _flatten(value):
    """A JSON value as one line of display text.

    A resolver legitimately freezes lists (``move_types``) and small maps (a currency split) among
    its components. Rendered raw, a template prints the Python repr — ``['issue', 'consumption']``
    — so they are joined here instead. Scalars pass straight through.
    """
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    return value


def _breakdown_facts(breakdown):
    """The component arithmetic behind the number, as ``(label, value)`` pairs.

    Insertion order is kept: it is the order the resolver wrote its own reasoning in, which reads
    better than alphabetical. ``None`` is dropped (a knob this metric does not take), but ``False``
    is NOT — ``truncated: false`` and ``mixed_currency: false`` are answers, not absences.
    """
    return [(_humanize(key), _flatten(value)) for key, value in breakdown.items()
            if key not in _BREAKDOWN_IDENTITY_KEYS and value is not None]


@login_required
def kpisnapshot_detail(request, pk):
    """One frozen point, with the arithmetic that produced it and the series it sits in.

    Nothing here recomputes anything. The whole point of the table is that this number is what it
    was **at capture**, so re-deriving it on render would defeat the model (see its docstring: a
    back-dated ``StockMove`` or a rolled ``average_cost`` silently rewrites the past).
    """
    obj = get_object_or_404(_snapshot_queryset(request.tenant), pk=pk)
    breakdown = obj.breakdown if isinstance(obj.breakdown, dict) else {}
    meta = METRIC_META.get(obj.metric) or {}
    headers, rows = _breakdown_table(breakdown)

    # The series this point belongs to: the same TARGET **and the same dimension** (L40 §3 — two
    # records joined by a comparison have to agree on more than the tenant; a target's roll-up and
    # its per-vendor rows are different lines and averaging them would be nonsense). Covered by the
    # (tenant, kpi_target, period_end) index and capped.
    series = KpiSnapshot.objects.filter(tenant=request.tenant, kpi_target_id=obj.kpi_target_id,
                                        dimension_key=obj.dimension_key)
    history = list(series.order_by("-period_end")[:MAX_TREND_ROWS])
    previous = series.filter(period_end__lt=obj.period_end).order_by("-period_end").first()

    delta = delta_display = None
    improved = None
    if previous is not None and previous.value is not None and obj.value is not None:
        delta = obj.value - previous.value
        delta_display = format_metric_value(delta, meta.get("unit"))
        if delta != 0:
            # `direction` is stamped on save() from the registry, so it is never blank on a stored
            # row; the fallbacks are for a metric retired from the catalog after this was frozen.
            direction = (getattr(obj.kpi_target, "direction", "")
                         or meta.get("direction") or "higher_is_better")
            improved = delta > 0 if direction == "higher_is_better" else delta < 0

    # Resolved HERE rather than with {% url %} in the template, and guarded: this is a read-only
    # history page, and it must survive a metric whose group page was renamed or whose group was
    # retired from the catalog — a frozen number is still worth reading when its report page is not.
    group_url, group_title = "", ""
    page = METRIC_GROUP_PAGES.get(meta.get("group") or "")
    if page:
        group_title = page[1]
        try:
            group_url = reverse(page[0])
        except NoReverseMatch:
            group_url = ""

    return render(request, "scm/analytics/kpisnapshot/detail.html", {
        "obj": obj,
        "meta": meta,
        "unit": meta.get("unit", ""),
        "breakdown_facts": _breakdown_facts(breakdown),
        "breakdown_headers": headers,
        "breakdown_rows": rows,
        "breakdown_truncated": bool(breakdown.get("truncated")),
        "history": history,
        "previous": previous,
        "delta": delta,
        "delta_display": delta_display,
        "improved": improved,
        "group_url": group_url,
        "group_title": group_title,
        "parameter_days": breakdown.get("parameter_days"),
        "parameter_pct": breakdown.get("parameter_pct"),
        "list_url": _url_with_filters("scm:kpisnapshot_list", request.GET),
    })


# =================================================================================================
# Write — the two paths that exist, and nothing else
# =================================================================================================

@login_required
@require_POST
def kpisnapshot_delete(request, pk):
    """Delete ONE frozen point — the only correction a human can make to this table.

    ``@login_required`` rather than ``@tenant_admin_required``, matching CRM's ``snapshot_delete``:
    capture is admin-gated because it writes the history *everyone's* trend line reads, in one batch,
    across every target at once; removing a single bad point is an ordinary correction by whoever
    can already see it. ``crud_delete`` re-fetches tenant-scoped (so a cross-tenant pk is a 404, not
    a delete), writes the audit row BEFORE the delete, and only mutates on POST.
    """
    return crud_delete(request, model=KpiSnapshot, pk=pk, success_url="scm:kpisnapshot_list")


def _requested_period_end(data):
    """``(period_end, error)`` for a capture — today when nothing was asked for.

    A **future** date is refused rather than clamped: the grain bucket containing it has not
    finished, so the value frozen against it is a part-period measured as though it were a whole one
    — and a trend line cannot tell the two apart afterwards, which is precisely the drift this table
    exists to prevent. Junk is refused too, rather than skipped the way ``_date_window`` skips it:
    that one narrows a read, this one WRITES, and silently capturing "today" when somebody asked for
    a specific closed period is a wrong answer wearing a success message.
    """
    raw = (data.get("period_end") or "").strip()
    if not raw:
        return timezone.localdate(), ""
    try:
        requested = date.fromisoformat(raw)
    except ValueError:
        return None, "That is not a date — pick the day the period you want to freeze ends on."
    if requested > timezone.localdate():
        return None, ("That period has not finished yet. Freezing it now would store a part-period "
                      "as though it were a whole one, and nothing later could tell the difference.")
    # Keeps the date inside the range the bucket arithmetic in analytics.py can survive.
    return analytics.clamp_date(requested), ""


@tenant_admin_required
@require_POST
def kpisnapshot_capture(request):
    """Freeze one period for EVERY active target. **This is the create path for this model.**

    ``@tenant_admin_required``: it writes the frozen history every trend line, tile arrow and alert
    comparison in 4.11 reads, for the whole workspace, in one press.

    The computation is **not** re-implemented here — :func:`apps.scm.analytics.capture_snapshots`
    owns it, including its own ``transaction.atomic()``, its ``MAX_SNAPSHOT_TARGETS`` cap (checked
    with a ``.count()`` before a single target is fetched) and the ``update_or_create`` on
    ``(tenant, kpi_target, period_start, dimension_key)`` that makes a re-run **update** the period
    rather than stack a second row. This view validates the period, calls it, and reports back
    honestly — including the targets that captured nothing and why, which is the difference between
    a gap in a trend and a fabricated zero.
    """
    if _need_tenant(request):
        return redirect("scm:kpisnapshot_list")
    period_end, error = _requested_period_end(request.POST)
    if error:
        messages.error(request, error)
        return redirect(_url_with_filters("scm:kpisnapshot_list", request.POST))

    summary = analytics.capture_snapshots(request.tenant, period_end=period_end,
                                          user=request.user)
    if not summary["targets"]:
        messages.info(request, "There are no active KPI targets to capture. A snapshot is always "
                               "the frozen output of one target's own metric, so create a target "
                               "first — there is deliberately no way to type a value in by hand.")
        return redirect(_url_with_filters("scm:kpisnapshot_list", request.POST))

    messages.success(
        request,
        f"Captured {summary['created']} new and refreshed {summary['updated']} existing snapshot(s) "
        f"for the period ending {summary['period_end']}, across {summary['targets']} target(s). "
        f"Re-running the same period updates those rows — it never stacks a second one.")
    if summary["capped"]:
        messages.warning(
            request,
            f"Only the first {analytics.MAX_SNAPSHOT_TARGETS} of {summary['available']} active "
            f"targets were evaluated. Deactivate the targets nobody reads, or capture in batches — "
            f"the cap is there so one press cannot run thousands of ledger walks.")
    if summary["skipped"]:
        reasons = [f"{detail.get('name') or detail.get('target') or 'a target'}: {detail['skipped']}"
                   for detail in summary["details"] if detail.get("skipped")]
        shown = " · ".join(reasons[:5])
        more = f" (and {len(reasons) - 5} more)" if len(reasons) > 5 else ""
        messages.warning(request, f"{summary['skipped']} target(s) froze nothing{more} — "
                                  f"a metric with no value is left as a gap, never stored as a "
                                  f"zero. {shown}")
    # A batch action has no single subject row: obj=None with an explicit tenant is this codebase's
    # shape for one (safety_stock_recalculate, crm HealthScores.recompute).
    write_audit_log(request.user, None, "create",
                    {"action": "kpisnapshot_capture", "period_end": summary["period_end"],
                     "targets": summary["targets"], "created": summary["created"],
                     "updated": summary["updated"], "skipped": summary["skipped"]},
                    tenant=request.tenant)
    return redirect(_url_with_filters("scm:kpisnapshot_list", request.POST))


# =================================================================================================
# Export
# =================================================================================================

#: The export's columns, in order. ``value`` is written as the raw ``Decimal`` (all four decimal
#: places) NEXT TO the unit-formatted ``display`` string: a spreadsheet needs the number, a reader
#: needs "12.30 turns", and collapsing the two loses one of them.
_EXPORT_HEADER = ["Period start", "Period end", "Metric", "Metric label", "Target", "Target name",
                  "Dimension", "Value", "Display", "Target at capture", "Band", "Captured at",
                  "Captured by"]


@login_required
def kpisnapshot_export(request):
    """The filtered snapshots as CSV — the same rows, in the same order, as the page.

    Two things worth stating because both have shipped as bugs elsewhere:

    * **The filename is a server-side literal plus a server-side date.** No request value reaches a
      response header, so there is nothing to inject a newline into and no way to smuggle a
      parameter (or a CSRF token) into a Content-Disposition.
    * **The cap is a SQL ``LIMIT``, and the total is a separate ``COUNT``.** Neither builds the
      export in order to decide the export is too big (L40 §1). When the cap bites, the file says so
      in its last row — a silently short CSV is a wrong answer that looks like a complete one.
    """
    qs = _filtered_snapshots(request)
    total = qs.count()
    rows = list(qs[:MAX_EXPORT_ROWS])
    truncated = total > MAX_EXPORT_ROWS

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="kpi-snapshots-{timezone.localdate().isoformat()}.csv"')
    writer = csv.writer(response)
    writer.writerow(_EXPORT_HEADER)
    for obj in rows:
        target = obj.kpi_target if obj.kpi_target_id else None
        # Every cell through _csv_safe. target.name is free text off the KpiTarget form and
        # dimension_display carries a party or carrier name, so a target called
        # `=cmd|'/c calc'!A0` would otherwise execute on the machine of whoever opens the file.
        writer.writerow([_csv_safe(cell) for cell in (
            obj.period_start.isoformat() if obj.period_start else "",
            obj.period_end.isoformat() if obj.period_end else "",
            obj.metric,
            obj.metric_label,
            target.number if target else "",
            target.name if target else "",
            obj.dimension_display,
            obj.value if obj.value is not None else "",
            obj.display,
            obj.target_value_at_time if obj.target_value_at_time is not None else "",
            obj.get_status_band_display(),
            timezone.localtime(obj.computed_at).strftime("%Y-%m-%d %H:%M") if obj.computed_at else "",
            obj.computed_by.get_username() if obj.computed_by_id else "",
        )])
    if truncated:
        writer.writerow([])
        writer.writerow([f"TRUNCATED: this file holds the first {MAX_EXPORT_ROWS} of {total} "
                         f"matching snapshots, newest period first. Narrow the metric, the target "
                         f"or the date window and export again."])
    return response
