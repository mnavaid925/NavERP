"""SCM 4.11 Supply Chain Analytics — ``KpiTarget`` views (the goals a planner authors).

``KpiTarget`` is the one row in 4.11 a human writes: everything else on the five analytics pages is
computed live out of 4.1-4.10's transactional rows. So these are ordinary CRUD views over ordinary
intent — with two things worth knowing before reading them.

**Every number on the detail page comes from :func:`apps.scm.analytics.compute_metric`.** The view
does not run a single aggregate of its own. That is the module's whole design: the tile, this page,
the CSV export, the frozen ``KpiSnapshot`` and the ``SupplyChainAlert`` are five renderings of ONE
computation, so they cannot disagree about what the number is.

**4.11 is READ-ONLY over 4.1-4.10.** Nothing here writes a ``StockMove`` or a ``JournalEntry``. The
only write outside this table is :func:`kpitarget_snapshot`, which appends to 4.11's own
``KpiSnapshot`` — and it is ``@tenant_admin_required`` because that history is *frozen*: it is
deliberately never re-derived, so a wrong point stays wrong.

Context-var contract (pinned, L7 — templates are written by a separate agent, so every key a
template consumes is listed here, not just the list var):

* ``scm/analytics/kpitarget/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from ``crud_list``)
  plus ``metric_choices`` (GROUPED: ``[(group label, [(key, label), …]), …]``, so the dropdown needs
  ``<optgroup>``), ``group_choices``, ``scope_choices``, ``severity_choices``.
* ``scm/analytics/kpitarget/detail.html`` — ``obj``, ``result``, ``result_error``, ``band_css``,
  ``trend``, ``window_start``, ``window_end``.
* ``scm/analytics/kpitarget/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path).
"""
from apps.scm.views._common import *  # noqa: F401,F403

from apps.scm.analytics import capture_snapshots, compute_metric, range_bounds
from apps.scm.forms import KpiTargetForm
# The vocabularies come from the models package, which re-exports them from
# `models/SupplyChainAnalytics/_choices.py` — the FIXED contract (pure data, no queries, no model
# imports) that both the model layer and `analytics.py` read. Importing them rather than restating
# them is what stops a dropdown offering a metric no resolver knows, or a filter naming a scope
# `clean()` rejects.
from apps.scm.models import (BAND_CHOICES, METRIC_CHOICES, METRIC_GROUP_CHOICES, METRIC_META,
                             SCOPE_CHOICES, SEVERITY_CHOICES, KpiSnapshot, KpiTarget)

#: How many trend points the detail page shows. Twelve is a year of months, a quarter of weeks —
#: enough to read a direction, small enough that the history stays ONE bounded query. The cap is a
#: queryset SLICE, so the DATABASE applies it: it bounds what is fetched, not what is rendered
#: (L40 §1 — a guard that first builds the whole thing is the payload, not a guard).
MAX_TREND_POINTS = 12

#: ``group`` is metadata on the metric CATALOG, not a column on ``KpiTarget``, so filtering by it
#: means filtering by the metric keys that belong to it. Built once at import from the same catalog
#: the dropdown renders, so a metric added to ``_choices.py`` joins its group's filter with no edit
#: here — the alternative, a hand-maintained list, is two things that drift.
_GROUP_METRICS = {
    group: tuple(key for key, meta in METRIC_META.items() if meta["group"] == group)
    for group, _label in METRIC_GROUP_CHOICES
}

#: Words a yes/no filter dropdown may legally send. ``crud_list`` maps only the literal strings
#: ``"True"``/``"False"``; a filter bar rendering ``active``/``inactive`` (this project's house
#: style) would otherwise return EVERY row, because ``.filter(is_active="inactive")`` coerces via
#: ``bool("inactive")`` — True. Accepting both vocabularies here keeps the dropdown and the queryset
#: agreeing whichever one the template uses.
_TRUE_FILTER_VALUES = frozenset({"true", "1", "yes", "on", "active"})
_FALSE_FILTER_VALUES = frozenset({"false", "0", "no", "off", "inactive"})

#: Band key -> human words, for the flash message the capture action writes. The band's COLOUR is
#: never decided here — that is ``KpiSnapshot.BAND_CSS``, the single place a band becomes a
#: theme.css class (L33: the colour-named classes are the only ones that exist).
_BAND_LABELS = dict(BAND_CHOICES)


def _boolean_filter(qs, request, field, *params):
    """Tri-state (unset / yes / no) boolean filter, from the first GET param that resolves.

    An unrecognised value leaves the filter OFF rather than 500-ing or silently matching
    everything — the same posture ``crud_list`` takes for a hand-edited URL.
    """
    for param in params:
        raw = request.GET.get(param, "").strip().lower()
        if not raw:
            continue
        if raw in _TRUE_FILTER_VALUES:
            return qs.filter(**{field: True})
        if raw in _FALSE_FILTER_VALUES:
            return qs.filter(**{field: False})
    return qs


@login_required
def kpitarget_list(request):
    """Search + six filters over the tenant's targets.

    ``select_related`` covers the four scope FKs because the list renders ``scope_label``, which
    walks whichever one the scope points at — without it a page of 15 targets is up to 15 extra
    queries for a single column.

    There is no integer-FK filter on this page, so L11's ``.isdigit()`` guard has nothing to bite
    on yet; when one is added it goes in the ``filters`` spec below with ``is_int=True``, which is
    where ``crud_list`` applies that guard.
    """
    qs = (KpiTarget.objects.filter(tenant=request.tenant)
          .select_related("scope_category", "scope_location", "scope_carrier", "scope_vendor",
                          "owner"))

    # Applied BEFORE crud_list, which is what paginates. A filter applied after pagination would
    # page over the unfiltered set and quietly show the wrong rows on page 2.
    group = request.GET.get("group", "").strip()
    if group in _GROUP_METRICS:
        qs = qs.filter(metric__in=_GROUP_METRICS[group])
    qs = _boolean_filter(qs, request, "is_active", "is_active", "status")
    qs = _boolean_filter(qs, request, "is_alerting", "is_alerting", "alerting")

    return crud_list(
        request, qs, "scm/analytics/kpitarget/list.html",
        search_fields=["number", "name", "metric"],
        filters=[("metric", "metric", False), ("scope", "scope", False),
                 ("severity", "severity", False)],
        extra_context={
            # Grouped by report page, exactly as the sidebar reads. The template renders it with
            # <optgroup>; flattening it here would be a second vocabulary to keep in step.
            "metric_choices": METRIC_CHOICES,
            "group_choices": METRIC_GROUP_CHOICES,
            "scope_choices": SCOPE_CHOICES,
            "severity_choices": SEVERITY_CHOICES,
        },
    )


@login_required
def kpitarget_create(request):
    """``crud_create`` stamps the tenant, audits, and refuses a tenant-less user outright."""
    return crud_create(request, form_class=KpiTargetForm,
                       template="scm/analytics/kpitarget/form.html",
                       success_url="scm:kpitarget_list")


@login_required
def kpitarget_edit(request, pk):
    """Editable at any time — a target is intent, and intent is revised.

    Repointing one at another metric does NOT relabel the numbers already captured under the old
    one: ``KpiSnapshot.metric`` is denormalized precisely so the frozen history keeps saying what it
    actually measured (see that model's field comment).
    """
    return crud_edit(request, model=KpiTarget, pk=pk, form_class=KpiTargetForm,
                     template="scm/analytics/kpitarget/form.html",
                     success_url="scm:kpitarget_list")


@login_required
def kpitarget_detail(request, pk):
    """The target, its LIVE figure, and its frozen trend.

    Two different numbers sit side by side here on purpose:

    * ``result`` is computed now, over the target's own rolling ``date_range`` window;
    * ``trend`` is the stored ``KpiSnapshot`` history, frozen as each period stood. It is never
      re-derived — ``Item.average_cost`` is recomputed on every receipt and back-dated stock moves
      are legal, so recomputing last quarter's turnover would silently rewrite the past.
    """
    obj = get_object_or_404(
        KpiTarget.objects.select_related("scope_category", "scope_location", "scope_carrier",
                                         "scope_vendor", "owner"),
        pk=pk, tenant=request.tenant)

    start, end = range_bounds(obj.date_range)
    result, result_error = None, ""
    try:
        # No `scope=` argument: compute_metric reads the target's OWN resolved scope, which is the
        # one that also refuses to widen to the whole network when the scoped subject was deleted.
        result = compute_metric(request.tenant, obj.metric, start, end, target=obj)
    except ValueError as exc:
        # The registry is CLOSED and compute_metric raises on a key it cannot resolve. clean()
        # rejects that on the way in, so this only fires for a row that predates a narrowed
        # catalog — a page that must still render and say so, not a 500.
        result_error = str(exc)

    # ONE query: a slice the database applies, with the only FK the rows render joined in. The
    # related manager already constrains by kpi_target, which implies the tenant; the explicit
    # tenant filter is stated anyway so this page holds to the module-wide rule mechanically.
    #
    # Deliberately NOT narrowed to one dimension_key: a target repointed at another scope keeps its
    # older points under the old key, and each row carries the label frozen at capture
    # (`dimension_display`), so showing them tells the truth rather than hiding a scope change.
    trend = list(obj.snapshots.filter(tenant=request.tenant)
                 .select_related("computed_by")[:MAX_TREND_POINTS])
    # Meta ordering is newest-first (that is what the slice needs); a trend reads oldest to newest.
    trend.reverse()

    return render(request, "scm/analytics/kpitarget/detail.html", {
        "obj": obj,
        "result": result,
        "result_error": result_error,
        # The live figure has no KpiSnapshot row behind it, so its badge class comes from the same
        # map the stored rows use — the one place a band becomes a colour. badge-success /
        # badge-danger / badge-warning DO NOT EXIST in theme.css (L33, four recurrences).
        "band_css": KpiSnapshot.BAND_CSS.get((result or {}).get("band"), "badge-muted"),
        "trend": trend,
        "window_start": start,
        "window_end": end,
    })


@login_required
@require_POST
def kpitarget_delete(request, pk):
    """Delete the target — and say what goes with it.

    ``KpiSnapshot.kpi_target`` is ``CASCADE``, so the frozen trend points go too. That is the right
    cascade (a snapshot's meaning is its target's) but it is a larger consequence than "Deleted
    successfully." admits, and those figures cannot be re-derived later — which is the entire reason
    the snapshot table exists. Alerts SURVIVE: ``SupplyChainAlert.kpi_target`` is ``SET_NULL``, and
    an acknowledged exception is the record of a human decision, not a child of the target.
    """
    obj = get_object_or_404(KpiTarget, pk=pk, tenant=request.tenant)
    frozen = obj.snapshots.filter(tenant=request.tenant).count()
    if frozen:
        messages.info(request, f"{frozen} frozen trend point(s) were removed with {obj.number} — "
                               "those figures cannot be re-derived.")
    return crud_delete(request, model=KpiTarget, pk=pk, success_url="scm:kpitarget_list")


@tenant_admin_required
@require_POST
def kpitarget_snapshot(request, pk):
    """Freeze THIS target's current period now, without waiting for the batch capture.

    Admin-gated for the same reason the batch is: it writes ``KpiSnapshot``, and a snapshot is
    *frozen history* — deliberately never recomputed, so every trend line, every band and every
    comparison drawn from it inherits whatever this run wrote.

    The work is ``analytics.capture_snapshots`` with a one-target list, never a hand-rolled write:
    that function owns the period arithmetic (the target's own ``period_grain`` bucket, not its
    rolling ``date_range`` — rolling windows overlap and a trend of them is meaningless), the
    idempotent ``update_or_create`` on the model's unique key, the refusal to store a
    not-computable figure as ``0``, and the ``last_evaluated_at`` stamp. It also re-checks that the
    target belongs to this tenant, which is the belt to this view's ``get_object_or_404`` braces.
    """
    obj = get_object_or_404(KpiTarget, pk=pk, tenant=request.tenant)
    if not obj.is_active:
        messages.error(request, "The batch capture skips an inactive target, so capturing one by "
                                "hand would give it points only where somebody pressed this "
                                "button. Reactivate the target first.")
        return redirect("scm:kpitarget_detail", pk=pk)

    summary = capture_snapshots(request.tenant, targets=[obj], user=request.user)
    # One target in, so at most one detail row out — and an empty list is still handled, because a
    # skipped capture reports its reason there and there alone.
    detail = (summary.get("details") or [{}])[0]
    created, updated = summary.get("created", 0), summary.get("updated", 0)

    if not (created or updated):
        messages.error(request, detail.get("skipped")
                       or "Nothing was captured — this metric returned no value for the period.")
        return redirect("scm:kpitarget_detail", pk=pk)

    band = detail.get("band") or "unknown"
    write_audit_log(request.user, obj, "update", {
        "action": "capture_snapshot",
        "metric": obj.metric,
        "period_start": detail.get("period_start"),
        "period_end": detail.get("period_end"),
        "value": detail.get("value"),
        "band": band,
        "created": bool(created),
    })
    messages.success(
        request,
        f"{'Captured' if created else 'Re-captured'} {obj.number} at {detail.get('value')} "
        f"({_BAND_LABELS.get(band, band)}) for {detail.get('period_start')} to "
        f"{detail.get('period_end')}.")
    return redirect("scm:kpitarget_detail", pk=pk)
