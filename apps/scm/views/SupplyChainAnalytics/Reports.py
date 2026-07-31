"""SCM 4.11 Supply Chain Analytics — the five computed report pages, one per NavERP 4.11 bullet.

``inventory_analytics`` (Inventory Dashboards) · ``spend_analytics`` (Procurement Analytics) ·
``logistics_kpis`` (Logistics KPIs) · ``margin_analytics`` (Financial Reporting) ·
``disruption_risk`` (Predictive Analytics) — each with a CSV export sibling.

**Nothing here does arithmetic.** Every figure comes out of :func:`apps.scm.analytics.compute_metric`
and every band out of :func:`apps.scm.analytics.band_for`, which is what makes it impossible for a
tile to read green while the alert behind it fires red. These views resolve a filter spec, ask the
compute layer for the group's metrics, and arrange the answers — they never write SQL of their own
over 4.1-4.10, and they write no row at all: **4.11 is read-only, it posts no ``StockMove`` and no
``JournalEntry``** (L29 — ``apps.accounting`` owns the ledger).

Structure, following ``views/DemandPlanning/Reports.py`` exactly:

* ``_filtered_<page>(request, data=None)`` resolves the spec (window, scope, page selectors) from
  ``request.GET`` — or from any other mapping — so a POST action can re-run the report against the
  **exact** filter spec the page rendered with rather than "everything".
* ``_<page>_url(data)`` rebuilds the page URL from a **whitelist** of parameter names. Echoing
  ``request.POST`` into a redirect would put ``csrfmiddlewaretoken`` (and anything else an attacker
  appended) into a URL that then lands in the browser history, the referrer header and the server
  log. The whitelist is the fix, and it is also what the "Export CSV" link is built from.

**Query budget.** Per page: one ``KpiTarget`` query, one ``KpiSnapshot`` query for the trend, one
aggregate for the alert chip, one or two small master queries for the filter dropdowns, plus the
group's resolvers. That is one grouped query per metric FAMILY, never one per tile: the targets are
fetched once and matched in Python, and the trend series for every metric on the page comes out of a
single ordered snapshot query. Supporting tables are not paginated because the resolvers already cap
their ``rows`` at ``analytics.MAX_DETAIL_ROWS`` — the cap is a ``LIMIT``, not a ``len()`` of
something already built (L40).

**Trend lines read frozen ``KpiSnapshot`` history, never a live re-walk.** That is the reason the
model exists: ``Item.average_cost`` is recomputed on every receipt and back-dated moves are legal, so
re-deriving last quarter silently rewrites the past — and a twelve-point trend would otherwise be
twelve full FIFO ledger walks on every page load. A page with no captured snapshots renders the
"capture a snapshot to start the trend" state rather than an invented one.

**Chart payloads go through ``json_script``, never ``|safe``.** Series labels are SKUs, supplier
names and carrier names — user-controlled strings. ``|safe`` on a hand-built JSON string is a stored
XSS vector the moment somebody names an item ``</script>``; ``json_script`` escapes the payload and
hands the template a ``<script type="application/json">`` block to ``JSON.parse``.

Context contract (identical on all five pages, so the shared header/filter markup is the same
everywhere)::

    page            {"key", "title", "bullet", "group", "report_url", "export_url"}
    spec            the resolved filter spec — see _base_spec()
    tiles           [compute_metric() result dicts] in catalog order, each with the extra keys
                    "target", "band_css", "primary", "unavailable"
    tile            {metric key: that same dict} — for a template that wants one by name
    has_data        False -> render the empty state
    no_tenant       True  -> the user has no workspace (the superuser); nothing was computed
    generated_at    the "as of" data-freshness stamp
    range_choices   DATE_RANGE_CHOICES for the window selector
    scope_ignored   scope filters the page had to drop (a metric narrows to ONE subject)
    scope_invalid   True when a scope id did not resolve inside this tenant
    open_alert_count / critical_alert_count / alerts_are_open  — the alert chip
    currency_notice {"mixed", "codes", "metrics"} — the mixed-currency warning
    chart_data      JSON-safe dict for {{ chart_data|json_script:"..." }}
    export_url      whitelisted CSV link
"""
import csv
from urllib.parse import urlencode

from django.http import HttpResponse
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import (_location_qs, _supplier_parties, _tms_carrier_qs)
# The inbox's own "still needs somebody" predicate. Imported rather than restated so the header chip
# and the page it links to can never drift apart (see _alert_chip).
from apps.scm.views.SupplyChainAnalytics.SupplyChainAlerts import _needs_attention_q
from apps.scm.models import (DATE_RANGE_CHOICES, ItemCategory, KpiSnapshot, KpiTarget,
                             OPEN_ALERT_STATUSES, SCOPE_FIELDS, SEVERITY_CHOICES,
                             SupplyChainAlert)
from apps.scm import analytics

# =================================================================================================
# Page table + filter whitelists
#
# One entry per NavERP 4.11 bullet. `filters` IS the whitelist: it is what _<page>_url() rebuilds a
# URL from, what the export link carries, and the only thing a redirect can ever echo back.
# =================================================================================================

#: The window a page opens on. 90 days rather than the 30 a KpiTarget defaults to, for two stated
#: reasons: a demand spike is the last 7 days measured against a longer baseline (so the window has
#: to be comfortably longer than that), and a turnover figure over 30 days is mostly noise.
DEFAULT_DATE_RANGE = "last_90"

_RANGE_KEYS = tuple(key for key, _label in DATE_RANGE_CHOICES)

#: Parameters every report page shares.
_WINDOW_FILTERS = ("date_range", "date_from", "date_to")

_INVENTORY_FILTERS = _WINDOW_FILTERS + ("category", "location")
_SPEND_FILTERS = _WINDOW_FILTERS + ("vendor", "gl_account", "org_unit")
_LOGISTICS_FILTERS = _WINDOW_FILTERS + ("carrier", "basis")
_MARGIN_FILTERS = _WINDOW_FILTERS + ("category", "customer", "channel")
_RISK_FILTERS = _WINDOW_FILTERS + ("vendor", "severity")

#: page key -> everything the shared machinery needs to render or export it.
#:
#: ``scopes`` is ORDERED and is the precedence rule when an operator sets two of them: a metric
#: narrows to exactly ONE subject (``MetricScope`` holds one), so the first one present wins and the
#: rest are reported in ``scope_ignored`` and named on the page. Silently intersecting them is not
#: available, and silently dropping one without saying so is how a page ends up labelled with a
#: filter it did not apply (L40 §3).
_PAGES = {
    "inventory": {
        "key": "inventory", "group": "inventory", "title": "Inventory Dashboards",
        "bullet": "NavERP 4.11 — Inventory Dashboards",
        "url_name": "scm:inventory_analytics", "export_name": "scm:inventory_analytics_export",
        "template": "scm/analytics/inventory_analytics.html",
        "filters": _INVENTORY_FILTERS, "scopes": ("category", "location"),
        "filename": "inventory-analytics",
    },
    "spend": {
        "key": "spend", "group": "procurement", "title": "Procurement Analytics",
        "bullet": "NavERP 4.11 — Procurement Analytics",
        "url_name": "scm:spend_analytics", "export_name": "scm:spend_analytics_export",
        "template": "scm/analytics/spend_analytics.html",
        "filters": _SPEND_FILTERS, "scopes": ("vendor",),
        "filename": "spend-analytics",
    },
    "logistics": {
        "key": "logistics", "group": "logistics", "title": "Logistics KPIs",
        "bullet": "NavERP 4.11 — Logistics KPIs",
        "url_name": "scm:logistics_kpis", "export_name": "scm:logistics_kpis_export",
        "template": "scm/analytics/logistics_kpis.html",
        "filters": _LOGISTICS_FILTERS, "scopes": ("carrier",),
        "filename": "logistics-kpis",
    },
    "margin": {
        "key": "margin", "group": "margin", "title": "Financial Reporting",
        "bullet": "NavERP 4.11 — Financial Reporting (operational estimate)",
        "url_name": "scm:margin_analytics", "export_name": "scm:margin_analytics_export",
        "template": "scm/analytics/margin_analytics.html",
        "filters": _MARGIN_FILTERS, "scopes": ("category",),
        "filename": "margin-analytics",
    },
    "risk": {
        "key": "risk", "group": "risk", "title": "Predictive Analytics",
        "bullet": "NavERP 4.11 — Predictive Analytics (deterministic, not machine learning)",
        "url_name": "scm:disruption_risk", "export_name": "scm:disruption_risk_export",
        "template": "scm/analytics/disruption_risk.html",
        "filters": _RISK_FILTERS, "scopes": ("vendor",),
        "filename": "disruption-risk",
    },
}


# =================================================================================================
# On-page notices
#
# Every one of these is rendered as VISIBLE TEXT on its page, not left in a docstring. Each prefers
# the string the resolver itself returned (so the words beside a number are the words the code that
# produced it chose) and falls back to a constant here only when the metric could not be computed —
# because a caveat that disappears exactly when the figure is missing is a caveat nobody reads.
# The fallbacks are BUILT from the analytics constants wherever one exists, so they cannot drift.
# =================================================================================================

#: Mirrors the buckets ``_r_inv_aging_over_days_value`` builds. Used only to label an EMPTY aging
#: table — when the metric computed, the breakdown's own (ordered) bucket map is rendered instead.
AGING_BUCKET_LABELS = ("0-30", "31-60", "61-90", "91-180", "181+")

TURNOVER_BASIS_NOTE = (
    f"Turnover counts {' + '.join(analytics.COGS_MOVE_TYPES)} movements — issue is customer demand, "
    f"consumption is a work-order draw (4.8 split them deliberately) — and EXCLUDES transfer, "
    f"because an internal relocation is posted as a signed pair and would be counted twice.")

#: The netting decision, taken in ``_r_demand_spike_count`` and printed on both pages that lean on
#: the demand series (inventory and risk), per the build plan.
DEMAND_NETTING_NOTE = (
    f"The demand series is NETTED, not gross: a 4.10 restock is posted as a positive receipt "
    f"carrying a '{analytics.RETURN_REFERENCE_PREFIX}' reference and no other writer stamps one, so "
    f"returns-to-stock are subtracted from issues in the same bucket. Netting is a floor on the "
    f"correction — a return that was scrapped, or a credit-only return where nothing comes back, "
    f"leaves no receipt row to net and still inflates the series.")

SPEND_PERIOD_AXIS_NOTE = (
    "The period axis of the cube is drawn from captured KPI snapshots, not recomputed on load: "
    "purchase history is legitimately back-dated, so re-deriving an old period would silently "
    "rewrite it.")

#: The one figure on the logistics page that is a denominator choice rather than a fact. Mirrors the
#: bases ``_r_freight_cost_per_unit`` reports in ``breakdown["rates"]``.
FREIGHT_BASIS_LABELS = {
    "kg": "per kilogram", "cbm": "per cubic metre", "package": "per package",
    "shipment": "per shipment", "km": "per kilometre",
}

NOT_ML_NOTE = (
    "Every score on this page is a DETERMINISTIC weighted composite over rows that already exist, "
    "rendered with its own component arithmetic. There is no model, no training data and no "
    "inference: run it twice on the same rows and it returns the same number, and anyone can check "
    "it by hand. Machine learning is Module 10's 10.13, not this page.")

MIXED_CURRENCY_NOTE = (
    "This window spans more than one currency and there is no FX rate table in this build. Money "
    "figures are face values summed across currencies — read the per-currency split before "
    "comparing them. A rate is never invented.")

NO_TREND_NOTE = (
    "No captured snapshots yet for the targets on this page. Trend lines are drawn from frozen "
    "history so an old period cannot be silently rewritten — create a KPI target for a metric and "
    "capture a snapshot to start one.")

NO_TENANT_NOTE = (
    "This login has no tenant workspace, so there is nothing to measure. Sign in as a workspace "
    "member to see supply chain analytics.")


# =================================================================================================
# Filter-spec machinery — shared by all five pages
# =================================================================================================

def _param(data, name):
    """One GET/POST parameter as a stripped string, never None."""
    return (data.get(name) or "").strip()


def _url_with(url_name, data, fields):
    """``url_name`` plus ONLY the whitelisted parameters that are set.

    The whitelist is the point: a redirect built from ``data.urlencode()`` would carry
    ``csrfmiddlewaretoken`` — and every other parameter a caller appended — into a URL that lands in
    browser history, the ``Referer`` header and the access log.
    """
    query = urlencode({name: _param(data, name) for name in fields
                       if _param(data, name)})
    url = reverse(url_name)
    return f"{url}?{query}" if query else url


def _report_url(page, data):
    """Back to a report page with the same filters — whitelist only."""
    return _url_with(page["url_name"], data, page["filters"])


def _export_url(page, data):
    """The CSV sibling of :func:`_report_url`, carrying the same whitelisted filters."""
    return _url_with(page["export_name"], data, page["filters"])


# The five named URL builders the plan calls for. Each is the whitelist for its own page; they
# delegate so there is ONE implementation of "which parameters may travel" rather than five copies
# that drift the first time a filter is added.
def _inventory_url(data):
    return _report_url(_PAGES["inventory"], data)


def _spend_url(data):
    return _report_url(_PAGES["spend"], data)


def _logistics_url(data):
    return _report_url(_PAGES["logistics"], data)


def _margin_url(data):
    return _report_url(_PAGES["margin"], data)


def _risk_url(data):
    return _report_url(_PAGES["risk"], data)


def _parse_window(data):
    """``(date_range key, start, end, is_custom)`` from ``date_range`` + the two overrides.

    Junk is SKIPPED rather than raised on (L11, and ``_date_window``'s posture): a hand-edited
    ``?date_to=lastweek`` must narrow nothing, and ``?date_to=2026-02-31`` is well-formed but not a
    date — ``parse_date`` raises ``ValueError`` on exactly that, which would otherwise be a 500 on a
    value anybody can type into the address bar.
    """
    key = _param(data, "date_range") or DEFAULT_DATE_RANGE
    if key not in _RANGE_KEYS:
        key = DEFAULT_DATE_RANGE
    start, end = analytics.range_bounds(key)
    custom = False
    for name, is_start in (("date_from", True), ("date_to", False)):
        raw = _param(data, name)
        if not raw:
            continue
        try:
            parsed = parse_date(raw)
        except (TypeError, ValueError):
            parsed = None
        if parsed is None:
            continue
        custom = True
        if is_start:
            start = parsed
        else:
            end = parsed
    # compute_metric clamps too; clamping here as well keeps the HEADER's printed window identical
    # to the one the resolvers actually measured.
    return key, analytics.clamp_date(start), analytics.clamp_date(end), custom


def _category_qs(tenant):
    """4.3 item categories, scoped to the tenant — the ``_item_qs``/``_location_qs`` shape.

    Local rather than in ``views/_helpers.py`` because only this module needs it (the helpers module
    is for cross-SUB-MODULE helpers). Returns ``.none()`` for a tenant-less user rather than a filter
    on NULL, so the superuser gets an empty dropdown instead of a query that can never match.
    """
    if tenant is None:
        return ItemCategory.objects.none()
    return ItemCategory.objects.filter(tenant=tenant)


#: scope value -> the tenant-scoped queryset its dropdown is drawn from. ``select_related`` where the
#: option's ``__str__`` walks a second FK (``Carrier.__str__`` reads ``self.party``), which is one
#: query per rendered option otherwise.
_SCOPE_QUERYSETS = {
    "category": _category_qs,
    "location": _location_qs,
    "carrier": _tms_carrier_qs,
    "vendor": _supplier_parties,
}


def _resolve_scope(tenant, data, kinds):
    """``(MetricScope, ignored, invalid)`` — the ONE subject this page's metrics narrow to.

    ``kinds`` is the page's ordered precedence list. The first one set wins; any other one set is
    returned in ``ignored`` so the page can say which filter it dropped instead of quietly applying
    a different one than the bar shows.

    An id that is not a digit, or does not resolve INSIDE THIS TENANT, is dropped and flagged rather
    than 404'd or handed to an int FK lookup (L11), and the figure stays network-wide — never
    another workspace's row (L40 §3: same tenant is not the same subject, and an unresolvable id is
    not a subject at all).
    """
    chosen, ignored, invalid = analytics.NETWORK, [], False
    for kind in kinds:
        raw = _param(data, kind)
        if not raw:
            continue
        if chosen is not analytics.NETWORK:
            ignored.append(kind)
            continue
        # isdecimal(), not isdigit(): '²'.isdigit() is True but int('²') raises, so a superscript in
        # ?category= / ?vendor= / ?carrier= slipped past this guard and 500'd out of the .filter()
        # below instead of landing in the scope_invalid state this branch exists to produce.
        if not raw.isdecimal():
            invalid = True
            continue
        subject = _SCOPE_QUERYSETS[kind](tenant).filter(pk=int(raw)).first()
        if subject is None:
            invalid = True
            continue
        chosen = analytics.MetricScope(kind, subject)
    return chosen, ignored, invalid


def _base_spec(request, page, data=None):
    """The resolved filter spec every ``_filtered_<page>`` builds on.

    ``data`` defaults to ``request.GET`` and is accepted explicitly so a POST action can re-run the
    report against the very filters the page rendered with (the ``safety_stock_recalculate``
    precedent) rather than against everything.
    """
    data = request.GET if data is None else data
    date_range, start, end, custom = _parse_window(data)
    scope, ignored, invalid = _resolve_scope(request.tenant, data, page["scopes"])
    return {
        "page": page,
        "date_range": date_range,
        "start": start,
        "end": end,
        "custom_window": custom,
        "window_days": analytics.window_days(start, end),
        "scope": scope,
        "scope_value": scope.value,
        "scope_label": scope.label,
        "scope_ignored": ignored,
        "scope_invalid": invalid,
        # Echoed back so a filter bar can re-render exactly what was asked for, including the
        # selectors that only narrow the tables below (see _display_filter).
        "params": {name: _param(data, name) for name in page["filters"]},
        "report_url": _report_url(page, data),
        "export_url": _export_url(page, data),
    }


def _display_filter(spec, name):
    """A selector that narrows the TABLES on the page, not the headline figures.

    ``gl_account`` / ``org_unit`` / ``customer`` / ``channel`` are cube FACES, not metric scopes: the
    closed registry narrows by category, location, carrier or supplier only (``SCOPE_CHOICES``), and
    inventing a fifth narrowing here would mean writing arithmetic this module is not allowed to
    write. So they filter the rows the resolver already returned, their options come from those same
    rows (no extra query, and no option that has no data behind it), and every page that offers one
    lists it in ``display_only_filters`` so the template can say so beside the control.
    """
    return spec["params"].get(name, "")


# =================================================================================================
# Metrics, targets, bands
# =================================================================================================

def _targets_by_metric(tenant, keys):
    """``{metric: [KpiTarget]}`` for a whole page in ONE query.

    Capped at the module's own ``MAX_SNAPSHOT_TARGETS`` as a ``LIMIT`` on the ordered query — the
    bound is applied by the database, not by measuring a list already fetched (L40 §1). The Meta
    ordering (``display_order, name, -id``) makes "the first match" deterministic.
    """
    if tenant is None or not keys:
        return {}
    mapping = {}
    targets = (KpiTarget.objects.filter(tenant=tenant, is_active=True, metric__in=keys)
               [:analytics.MAX_SNAPSHOT_TARGETS])
    for target in targets:
        mapping.setdefault(target.metric, []).append(target)
    return mapping


def _scope_matches(target, scope):
    """True when ``target`` measures the same subject this page is narrowed to.

    **This is the L40 §3 check.** A target and the figure it bands must agree on more than the
    tenant: banding a network-wide turnover against thresholds somebody set for one warehouse would
    put a red tile on a number that target has never measured. Compared on the FK's ``_id`` column,
    so matching costs no query.
    """
    if target.scope != scope.value:
        return False
    field = SCOPE_FIELDS.get(scope.value)
    if field is None:  # "all" — the whole network, nothing further to agree on
        return True
    return getattr(target, f"{field}_id", None) == scope.subject_pk


def _match_target(targets, scope):
    """The first active target for this metric that measures this page's subject, or None."""
    for target in targets or ():
        if _scope_matches(target, scope):
            return target
    return None


def _compute_tiles(tenant, spec):
    """Every metric in the page's group, computed through the ONE entry point.

    A metric that cannot be narrowed the way the page is narrowed (a carrier scope on dead stock)
    comes back with ``value=None`` and the reason in ``breakdown["unavailable"]`` — deliberately not
    widened to the whole network, because that would be a different number under the same name.
    """
    tiles = []
    if tenant is None:
        return tiles
    entries = analytics.metrics_for_group(spec["page"]["group"])
    targets = _targets_by_metric(tenant, [key for key, _meta in entries])
    for key, meta in entries:
        target = _match_target(targets.get(key), spec["scope"])
        result = analytics.compute_metric(tenant, key, spec["start"], spec["end"],
                                          scope=spec["scope"], target=target)
        result["target"] = target
        # result["band"] IS analytics.band_for(target, value) — compute_metric calls it on the way
        # out, so a tile, the snapshot frozen from it and the alert raised off it are banded by one
        # function and cannot disagree. Nothing here re-decides a band.
        #
        # Colour-named theme.css classes ONLY — badge-success/-warning/-danger do not exist and
        # render as an unstyled pill with no error anywhere (L33, four recurrences). The map lives
        # on KpiSnapshot so a live tile and a stored one cannot colour the same band differently.
        result["band_css"] = KpiSnapshot.BAND_CSS.get(result["band"], "badge-muted")
        result["primary"] = meta.get("primary", False)
        result["unavailable"] = result["breakdown"].get("unavailable", "")
        tiles.append(result)
    return tiles


def _tile_map(tiles):
    """``{metric key: tile}`` so a page can pull out the one it builds a table around."""
    return {tile["metric"]: tile for tile in tiles}


def _breakdown(tile, key, default=None):
    """One breakdown value from a tile that may be missing entirely (metric not in this group)."""
    if not tile:
        return default
    value = tile["breakdown"].get(key)
    return default if value is None else value


def _rows_of(tile):
    """A tile's supporting rows — already capped at ``MAX_DETAIL_ROWS`` by the resolver."""
    return list(tile["rows"]) if tile else []


def _labelled(mapping, label_key="label", value_key="value"):
    """A breakdown's ``{label: number}`` map as ordered rows a template can loop over."""
    return [{label_key: name, value_key: amount} for name, amount in (mapping or {}).items()]


def _keep(rows, field, wanted):
    """Narrow already-computed rows by one display-only selector (see :func:`_display_filter`)."""
    if not wanted:
        return rows
    return [row for row in rows if str(row.get(field, "")) == wanted]


# =================================================================================================
# Trend, alerts, currency — one query each, shared by all five pages
# =================================================================================================

def _trend_payload(tenant, spec, tiles):
    """The Chart.js payload, drawn from FROZEN ``KpiSnapshot`` history in one ordered query.

    Only the targets that actually banded a tile contribute, so a series and the tile above it are
    guaranteed to be measuring the same subject (the :func:`_scope_matches` agreement again). The
    row cap is arithmetic — ``one target x MAX_TREND_PERIODS`` — and is applied as a ``LIMIT``.

    Everything in the payload is a str/float/None. It is rendered with ``json_script`` and never
    ``|safe``: the labels are metric names and the tenant's own data, and a hand-built JSON string
    interpolated into a ``<script>`` block is a stored-XSS hole the first time a value contains
    ``</script>``.
    """
    payload = {"labels": [], "series": [], "note": NO_TREND_NOTE, "has_data": False}
    if tenant is None:
        payload["note"] = NO_TENANT_NOTE
        return payload
    banded = [tile for tile in tiles if tile["target"] is not None]
    if not banded:
        return payload
    target_ids = [tile["target"].pk for tile in banded]
    cap = len(target_ids) * analytics.MAX_TREND_PERIODS
    rows = list(KpiSnapshot.objects
                .filter(tenant=tenant, kpi_target_id__in=target_ids, dimension_key="")
                .filter(period_end__lte=spec["end"])
                .order_by("-period_end")
                .values("metric", "period_end", "value", "status_band")[:cap])
    if not rows:
        return payload
    rows.reverse()  # oldest first for the chart's x-axis
    labels, by_metric = [], {}
    for row in rows:
        label = row["period_end"].isoformat()
        if label not in labels:
            labels.append(label)
        by_metric.setdefault(row["metric"], {})[label] = row
    labels.sort()
    series = []
    for tile in banded:
        points = by_metric.get(tile["metric"])
        if not points:
            continue
        series.append({
            "metric": tile["metric"],
            "label": tile["label"],
            "unit": tile["unit"],
            "direction": tile["direction"],
            "values": [_jsonable(points[label]["value"]) if label in points else None
                       for label in labels],
            "bands": [points[label]["status_band"] if label in points else None
                      for label in labels],
        })
    payload.update({"labels": labels, "series": series, "has_data": bool(series),
                    "note": "" if series else NO_TREND_NOTE})
    return payload


def _jsonable(value):
    """A JSON-safe float (or None) — Decimal would be serialized as a STRING by DjangoJSONEncoder,
    which Chart.js then plots as a category rather than a number."""
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _alert_chip(tenant):
    """``(open, critical)`` in ONE aggregate — the chip every analytics page header carries.

    Counted with ``_needs_attention_q()``, the SAME predicate ``supplychainalert_list`` filters by
    default — **not** ``status__in=OPEN_ALERT_STATUSES``. The two differ by exactly one case: a live
    snooze is an "open" status but is deliberately not demanding attention yet. Counting the wider
    set here made the chip read "5 open alerts" and land on an inbox showing 3, and made snoozing an
    alert leave the chip unchanged — which is the disagreement ``open_alert_count``'s own docstring
    promises cannot happen. A count that disagrees with its own destination is worse than no count.
    """
    if tenant is None:
        return 0, 0
    attention = _needs_attention_q()
    totals = (SupplyChainAlert.objects
              .filter(tenant=tenant)
              .aggregate(open=Count("id", filter=attention),
                         critical=Count("id", filter=attention & Q(severity="critical"))))
    return totals["open"] or 0, totals["critical"] or 0


def _currency_notice(tiles):
    """The mixed-currency warning, gathered from whichever resolvers reported one.

    There is no FX rate table in this build, so a money figure may be a sum of face values across
    currencies. The resolvers say so in ``breakdown["mixed_currency"]``; the page has to SHOW it,
    because a total that looks like one currency and is not is worse than no total.
    """
    codes, metrics = set(), []
    for tile in tiles:
        breakdown = tile["breakdown"]
        if not breakdown.get("mixed_currency"):
            continue
        metrics.append(tile["label"])
        for code in (breakdown.get("currencies") or ()):
            codes.add(code)
        for code in (breakdown.get("by_currency") or {}):
            codes.add(code)
    return {"mixed": bool(metrics), "codes": sorted(codes), "metrics": metrics,
            "note": MIXED_CURRENCY_NOTE if metrics else ""}


# =================================================================================================
# The shared page context
# =================================================================================================

def _base_context(request, spec, tiles):
    """Every key the five templates share. Built in ONE place so the header, the filter bar and the
    empty state are identical on all five pages and so a key can never be missing on the path where
    nothing was computed."""
    open_alerts, critical_alerts = _alert_chip(request.tenant)
    tile_map = _tile_map(tiles)
    return {
        "page": spec["page"],
        "spec": spec,
        "tiles": tiles,
        "tile": tile_map,
        "primary_tiles": [tile for tile in tiles if tile["primary"]],
        "has_data": any(tile["value"] is not None for tile in tiles),
        "no_tenant": request.tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
        "generated_at": timezone.localtime(),
        "range_choices": DATE_RANGE_CHOICES,
        "date_range": spec["date_range"],
        "start": spec["start"],
        "end": spec["end"],
        "scope_label": spec["scope_label"],
        "scope_value": spec["scope_value"],
        "scope_ignored": spec["scope_ignored"],
        "scope_invalid": spec["scope_invalid"],
        "open_alert_count": open_alerts,
        "critical_alert_count": critical_alerts,
        "alerts_are_open": open_alerts > 0,
        "currency_notice": _currency_notice(tiles),
        "chart_data": _trend_payload(request.tenant, spec, tiles),
        "report_url": spec["report_url"],
        "export_url": spec["export_url"],
        "params": spec["params"],
        "display_only_filters": (),
    }


# =================================================================================================
# CSV
# =================================================================================================

#: A cell starting with one of these is executed as a FORMULA by Excel / LibreOffice when the file is
#: opened. SKUs, supplier names and carrier names are user-controlled, so a value like
#: ``=cmd|'/c calc'!A0`` in an item name would run on the machine of whoever opens the export. Every
#: cell is therefore prefixed with an apostrophe when it starts with one of these.
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    """One cell, neutralised against CSV injection (see :data:`_CSV_FORMULA_PREFIXES`).

    A cell that is simply a NUMBER is left alone even though ``-3.5`` starts with a dangerous
    character: half the figures on these pages are negative (freight variance, a loss-making
    customer's net margin, a negative adjustment) and prefixing them would turn every one into text
    in the spreadsheet that has to sum them. A number cannot carry a formula, so the escape is only
    applied to values that are not one — which is exactly the SKU / supplier-name / carrier-name
    class the injection comes from.
    """
    if value is None:
        return ""
    if value is True or value is False:
        return "yes" if value else "no"
    text = str(value)
    if not text.startswith(_CSV_FORMULA_PREFIXES):
        return text
    try:
        Decimal(text)
    except (ArithmeticError, TypeError, ValueError):
        return "'" + text
    return text


def _csv_response(filename, rows):
    """Stream ``rows`` (an iterable of sequences) as an attachment.

    ``filename`` is a page constant, never anything a caller supplied — a request-controlled
    filename is a header-injection and content-disposition problem, and there is no reason for one.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # A UTF-8 BOM, because these exports carry PROSE — the L29 notice, the "in full" definition, the
    # reason a metric could not be computed — and that prose contains em dashes and middots. Excel on
    # Windows reads a BOM-less CSV as the ANSI code page and renders every one of them as mojibake,
    # which is exactly the text a reader most needs to trust.
    response.write("\ufeff")
    writer = csv.writer(response)
    for row in rows:
        writer.writerow([_csv_safe(cell) for cell in row])
    return response


def _row_keys(rows):
    """The union of a row list's keys, in first-seen order — a deterministic CSV header."""
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    return keys


def _export_rows(spec, tiles, sections=()):
    """The CSV body: a provenance header, one line per metric, then each metric's supporting rows.

    ``sections`` are the page's own extra tables (the aging buckets, the cost stack, the risk
    components) as ``(title, rows)`` pairs, so an export carries the same tables the page shows
    rather than a thinner version somebody has to reconcile.
    """
    page = spec["page"]
    yield ["NavERP", "Supply Chain Analytics", page["title"]]
    yield ["Generated", timezone.localtime().isoformat(timespec="seconds")]
    yield ["Window", spec["start"].isoformat() if spec["start"] else "(no lower bound)",
           spec["end"].isoformat() if spec["end"] else "", dict(DATE_RANGE_CHOICES).get(
               spec["date_range"], spec["date_range"])]
    yield ["Scope", spec["scope_label"]]
    notice = _currency_notice(tiles)
    if notice["mixed"]:
        yield ["Mixed currency", ", ".join(notice["codes"]), MIXED_CURRENCY_NOTE]
    yield []
    yield ["Metric", "Label", "Unit", "Direction", "Value", "Display", "Band", "Target",
           "Warning", "Critical", "Not computable"]
    for tile in tiles:
        target = tile["target"]
        yield [tile["metric"], tile["label"], tile["unit"], tile["direction"],
               _jsonable(tile["value"]), tile["display"], tile["band"],
               getattr(target, "target_value", ""), getattr(target, "warning_threshold", ""),
               getattr(target, "critical_threshold", ""), tile["unavailable"]]
    for title, rows in sections:
        if not rows:
            continue
        yield []
        yield [title]
        keys = _row_keys(rows)
        yield keys
        for row in rows:
            yield [row.get(key, "") for key in keys]
    for tile in tiles:
        rows = tile["rows"]
        if not rows:
            continue
        yield []
        yield [f"{tile['label']} — supporting rows"]
        keys = _row_keys(rows)
        yield keys
        for row in rows:
            yield [row.get(key, "") for key in keys]


def _export(spec, tiles, sections=()):
    """A page's CSV, named after the page and the window it covers."""
    stamp = spec["end"].isoformat() if spec["end"] else timezone.localdate().isoformat()
    return _csv_response(f"{spec['page']['filename']}-{stamp}.csv",
                         _export_rows(spec, tiles, sections))


# =================================================================================================
# 1. Inventory Dashboards — scm:inventory_analytics
# =================================================================================================

def _filtered_inventory(request, data=None):
    """The inventory page's filter spec: window + ONE of category / location."""
    return _base_spec(request, _PAGES["inventory"], data)


def _inventory_sections(tiles):
    """The page's own tables: the standard age buckets, and the dead-stock detail.

    The buckets come from ``inv_aging_over_days_value``'s own breakdown so the boundaries printed on
    the page are the boundaries the walk used. When that metric could not be computed the bucket
    LABELS are still rendered (from :data:`AGING_BUCKET_LABELS`) with empty values — a caveat that
    vanishes exactly when the number is missing teaches people the page has no buckets.
    """
    tile_map = _tile_map(tiles)
    aging = tile_map.get("inv_aging_over_days_value")
    buckets = _breakdown(aging, "buckets", {})
    labels = list(buckets) or list(AGING_BUCKET_LABELS)
    return [{"bucket": label, "value": buckets.get(label)} for label in labels]


def _inventory_context(request, spec):
    tiles = _compute_tiles(request.tenant, spec)
    tile_map = _tile_map(tiles)
    turnover = tile_map.get("inv_turnover")
    context = _base_context(request, spec, tiles)
    context.update({
        "categories": _category_qs(request.tenant),
        "locations": _location_qs(request.tenant),
        "aging_buckets": _inventory_sections(tiles),
        "aging_days": _breakdown(tile_map.get("inv_aging_over_days_value"), "parameter_days",
                                 analytics.AGING_DAYS),
        "aging_note": _breakdown(tile_map.get("inv_aging_over_days_value"), "note", ""),
        "dead_stock_days": _breakdown(tile_map.get("inv_dead_stock_value"), "parameter_days",
                                      analytics.DEAD_STOCK_DAYS),
        "dead_stock_rows": _rows_of(tile_map.get("inv_dead_stock_value")),
        # Rendered as visible page text, not a comment: what turnover counts and what it excludes.
        "turnover_note": _breakdown(turnover, "note", TURNOVER_BASIS_NOTE),
        "turnover_move_types": list(analytics.COGS_MOVE_TYPES),
        "turnover_excludes": "transfer",
        "demand_netting_note": DEMAND_NETTING_NOTE,
        "carrying_pct": _breakdown(tile_map.get("inv_carrying_cost"), "parameter_pct",
                                   analytics.CARRYING_PCT),
    })
    return context, tiles


@login_required
def inventory_analytics(request):
    """Turnover, dead stock, the FIFO age buckets, expiry and excess — the 4.11 inventory bullet."""
    spec = _filtered_inventory(request)
    context, _tiles = _inventory_context(request, spec)
    return render(request, spec["page"]["template"], context)


@login_required
def inventory_analytics_export(request):
    """The inventory page as CSV, over the exact same whitelisted filter spec."""
    spec = _filtered_inventory(request)
    context, tiles = _inventory_context(request, spec)
    return _export(spec, tiles, sections=[
        ("Stock age buckets (days)", context["aging_buckets"]),
    ])


# =================================================================================================
# 2. Procurement Analytics — scm:spend_analytics
# =================================================================================================

def _filtered_spend(request, data=None):
    """The spend page's filter spec: window + supplier scope + the two cube-face selectors."""
    return _base_spec(request, _PAGES["spend"], data)


def _spend_context(request, spec):
    tiles = _compute_tiles(request.tenant, spec)
    tile_map = _tile_map(tiles)
    total = tile_map.get("spend_total")
    # THE SPEND CUBE — supplier x GL account x business unit x period. The first three axes are the
    # grouped aggregates spend_total already returned; the period axis is the snapshot trend
    # (chart_data), because re-deriving old periods on every page load would both cost a full pass
    # per period and silently rewrite back-dated purchase history.
    by_vendor = _rows_of(total)
    by_account = _labelled(_breakdown(total, "by_account", {}), "account", "amount")
    by_unit = _labelled(_breakdown(total, "by_business_unit", {}), "unit", "amount")
    account_pick = _display_filter(spec, "gl_account")
    unit_pick = _display_filter(spec, "org_unit")
    context = _base_context(request, spec, tiles)
    context.update({
        "vendors": _supplier_parties(request.tenant),
        "spend_cube": {
            "by_vendor": by_vendor,
            "by_account": _keep(by_account, "account", account_pick),
            "by_business_unit": _keep(by_unit, "unit", unit_pick),
            "by_currency": _labelled(_breakdown(total, "by_currency", {}), "currency", "amount"),
        },
        "gl_account_options": [row["account"] for row in by_account],
        "org_unit_options": [row["unit"] for row in by_unit],
        "display_only_filters": ("gl_account", "org_unit"),
        "period_axis_note": SPEND_PERIOD_AXIS_NOTE,
        # The caveats, on the page rather than in a docstring.
        "gl_axis_caveat": analytics.GL_AXIS_CAVEAT,
        "sku_hint_caveat": analytics.SKU_HINT_CAVEAT,
        "off_contract_caveat": _breakdown(tile_map.get("spend_off_contract_pct"), "caveat", ""),
        "spend_statuses": list(analytics.SPEND_PO_STATUSES),
        "savings_rows": _rows_of(tile_map.get("savings_negotiated")),
        "price_variance_rows": _rows_of(tile_map.get("savings_price_variance_opportunity")),
        "supplier_otd_rows": _rows_of(tile_map.get("supplier_otd_pct")),
        "supplier_score_rows": _rows_of(tile_map.get("supplier_score_avg")),
    })
    return context, tiles


@login_required
def spend_analytics(request):
    """The spend cube, savings opportunities and the supplier league — the procurement bullet."""
    spec = _filtered_spend(request)
    context, _tiles = _spend_context(request, spec)
    return render(request, spec["page"]["template"], context)


@login_required
def spend_analytics_export(request):
    """The spend page as CSV, including all three grouped cube faces."""
    spec = _filtered_spend(request)
    context, tiles = _spend_context(request, spec)
    cube = context["spend_cube"]
    return _export(spec, tiles, sections=[
        ("Spend by GL account (category axis — see the caveat)", cube["by_account"]),
        ("Spend by business unit", cube["by_business_unit"]),
        ("Spend by currency", cube["by_currency"]),
    ])


# =================================================================================================
# 3. Logistics KPIs — scm:logistics_kpis
# =================================================================================================

def _filtered_logistics(request, data=None):
    """The logistics page's filter spec: window + carrier scope + the freight cost basis."""
    return _base_spec(request, _PAGES["logistics"], data)


def _logistics_context(request, spec):
    tiles = _compute_tiles(request.tenant, spec)
    tile_map = _tile_map(tiles)
    freight = tile_map.get("freight_cost_per_unit")
    rates = _breakdown(freight, "rates", {})
    default_basis = _breakdown(freight, "basis_key", "")
    basis = _display_filter(spec, "basis")
    if basis not in rates:
        basis = default_basis
    context = _base_context(request, spec, tiles)
    context.update({
        "carriers": _tms_carrier_qs(request.tenant),
        # THE CARRIER SCORECARD ROW: on-time %, average transit against the rate card's promise,
        # cost per kilogram, billing variance % and exception count — one row per carrier.
        "carrier_scorecard": _rows_of(tile_map.get("carrier_otd_trend")),
        "scorecard_window_note": _breakdown(tile_map.get("carrier_otd_trend"), "window_caveat", ""),
        "scorecard_source": _breakdown(tile_map.get("carrier_otd_trend"), "source", ""),
        # "In full" is defined exactly once in the whole repo, in analytics; printed here beside the
        # number so nobody has to guess what OTIF measured.
        "in_full_definition": analytics.IN_FULL_DEFINITION,
        "otif_caveat": _breakdown(tile_map.get("otif_pct"), "caveat", ""),
        "otif_failures": _rows_of(tile_map.get("otif_pct")),
        "freight_bases": [{"key": key, "label": FREIGHT_BASIS_LABELS.get(key, key),
                           "rate": rate, "selected": key == basis}
                          for key, rate in rates.items()],
        "basis": basis,
        "basis_label": FREIGHT_BASIS_LABELS.get(basis, basis),
        "basis_rate": rates.get(basis),
        "basis_note": _breakdown(freight, "note", ""),
        "audited_statuses": list(analytics.AUDITED_FREIGHT_MATCH_STATUSES),
        "display_only_filters": ("basis",),
        "freight_league": _rows_of(freight),
        "utilization_rows": _rows_of(tile_map.get("equipment_utilization_pct")),
        "otd_rows": _rows_of(tile_map.get("otd_pct")),
    })
    return context, tiles


@login_required
def logistics_kpis(request):
    """On-time delivery, OTIF, freight cost per unit, utilization and the carrier scorecard."""
    spec = _filtered_logistics(request)
    context, _tiles = _logistics_context(request, spec)
    return render(request, spec["page"]["template"], context)


@login_required
def logistics_kpis_export(request):
    """The logistics page as CSV, carrier scorecard included."""
    spec = _filtered_logistics(request)
    context, tiles = _logistics_context(request, spec)
    return _export(spec, tiles, sections=[
        ("Carrier scorecard", context["carrier_scorecard"]),
        ("Freight cost per unit — every basis", context["freight_bases"]),
    ])


# =================================================================================================
# 4. Financial Reporting — scm:margin_analytics
#
# L29, and it is rendered ON the page: SCM posts no JournalEntry. apps.accounting owns the ledger and
# its Balance Sheet / P&L are the reportable figures. This page is an OPERATIONAL margin estimate
# over SCM rows — which item, which customer, which lane — and is explicitly not the statutory P&L.
# =================================================================================================

def _filtered_margin(request, data=None):
    """The margin page's filter spec: window + category scope + the customer/channel cuts."""
    return _base_spec(request, _PAGES["margin"], data)


def _margin_context(request, spec):
    tiles = _compute_tiles(request.tenant, spec)
    tile_map = _tile_map(tiles)
    gross = tile_map.get("gross_margin_pct")
    cost_to_serve = tile_map.get("margin_after_cost_to_serve_pct")
    customer_pick = _display_filter(spec, "customer")
    channel_pick = _display_filter(spec, "channel")
    by_customer = _labelled(_breakdown(gross, "by_customer", {}), "customer", "margin_pct")
    by_channel = _labelled(_breakdown(gross, "by_channel", {}), "channel", "margin_pct")
    context = _base_context(request, spec, tiles)
    context.update({
        "categories": _category_qs(request.tenant),
        # The L29 notice and the way out of it — both rendered, both linked.
        "operational_estimate_note": analytics.OPERATIONAL_ESTIMATE_NOTE,
        "balance_sheet_url": reverse("accounting:balance_sheet"),
        "profit_loss_url": reverse("accounting:profit_and_loss"),
        "cost_stack": _rows_of(tile_map.get("supply_cost_stack")),
        "cost_stack_total": (tile_map.get("supply_cost_stack") or {}).get("value"),
        "double_count_guard": _breakdown(tile_map.get("supply_cost_stack"),
                                         "double_count_guard", ""),
        "handling_rate_per_line": _breakdown(tile_map.get("supply_cost_stack"),
                                             "handling_rate_per_line",
                                             analytics.HANDLING_COST_PER_PICK_LINE),
        "handling_rate_per_unit": _breakdown(tile_map.get("supply_cost_stack"),
                                             "handling_rate_per_unit",
                                             analytics.HANDLING_COST_PER_PICK_UNIT),
        "item_margins": _rows_of(gross),
        "by_category": _labelled(_breakdown(gross, "by_category", {}), "category", "margin_pct"),
        # `by_customer` itself is NOT passed to the template: the page already ranks customers by
        # margin-after-cost-to-serve, which is the figure worth acting on, and a second gross-margin
        # customer table beside it invites reading the wrong one. The local is still computed
        # because `customer_options` (the filter dropdown) is derived from it.
        "by_channel": _keep(by_channel, "channel", channel_pick),
        "customer_ranking": _keep(_rows_of(cost_to_serve), "customer", customer_pick),
        "allocation_note": _breakdown(cost_to_serve, "allocation", ""),
        "revenue_basis": _breakdown(gross, "revenue_basis", ""),
        "cogs_basis": _breakdown(gross, "cogs_basis", ""),
        "unmapped_note": _breakdown(gross, "unmapped_note", ""),
        "customer_options": [row["customer"] for row in by_customer],
        "channel_options": [row["channel"] for row in by_channel],
        "display_only_filters": ("customer", "channel"),
    })
    return context, tiles


@login_required
def margin_analytics(request):
    """Gross margin, margin after cost-to-serve and the supply cost stack — an OPERATIONAL estimate."""
    spec = _filtered_margin(request)
    context, _tiles = _margin_context(request, spec)
    return render(request, spec["page"]["template"], context)


@login_required
def margin_analytics_export(request):
    """The margin page as CSV. The L29 notice travels with it — an exported number outlives its page."""
    spec = _filtered_margin(request)
    context, tiles = _margin_context(request, spec)
    return _export(spec, tiles, sections=[
        ("NOT THE STATUTORY P&L", [{"notice": analytics.OPERATIONAL_ESTIMATE_NOTE}]),
        ("Supply chain cost stack", context["cost_stack"]),
        ("Customer profitability after cost-to-serve", context["customer_ranking"]),
        ("Margin by category", context["by_category"]),
        ("Margin by channel", context["by_channel"]),
    ])


# =================================================================================================
# 5. Predictive Analytics — scm:disruption_risk
#
# Honest framing, non-negotiable and rendered on the page: every score here is a DETERMINISTIC,
# fully explainable weighted composite over rows that already exist, shown with each component's own
# points and evidence. No model, no training data, no inference, and the page never says "AI".
# Genuine ML/AutoML is Module 10's 10.13.
# =================================================================================================

def _filtered_risk(request, data=None):
    """The risk page's filter spec: window + supplier scope + the alert-queue severity selector."""
    return _base_spec(request, _PAGES["risk"], data)


def _risk_components(tile):
    """The disruption composite's components as ordered rows — points, weight, contribution, evidence.

    Labels are derived from the component key rather than a hard-coded list, so a component added to
    ``DISRUPTION_WEIGHTS`` renders without an edit here (and cannot render blank).
    """
    components = _breakdown(tile, "components", {})
    rows = []
    for key, entry in components.items():
        rows.append({
            "key": key,
            "label": key.replace("_", " ").capitalize(),
            "points": entry.get("points"),
            "weight": entry.get("weight"),
            "contribution": entry.get("contribution"),
            "scored": entry.get("scored", False),
            "explanation": entry.get("explanation", ""),
            "evidence": entry.get("evidence") or {},
        })
    return rows


def _open_alerts(tenant, severity):
    """The exception queue, RANKED BY IMPACT VALUE — not by count.

    The Meta ordering is ``-impact_value, -raised_at``, which is the whole point of the table: a
    hundred trivial exceptions must not bury the one worth six figures. ``select_related`` covers the
    six subject FKs because ``subject_label`` walks them, and the list is capped at the same
    ``MAX_DETAIL_ROWS`` every supporting table on these pages uses — the full queue is the alert
    inbox's job, not this page's.
    """
    if tenant is None:
        return []
    qs = (SupplyChainAlert.objects
          .filter(tenant=tenant, status__in=OPEN_ALERT_STATUSES)
          .select_related("item", "party", "carrier", "shipment", "purchase_order", "location",
                          "kpi_target", "assigned_to"))
    if severity in dict(SEVERITY_CHOICES):
        qs = qs.filter(severity=severity)
    return list(qs[:analytics.MAX_DETAIL_ROWS])


def _risk_context(request, spec):
    tiles = _compute_tiles(request.tenant, spec)
    tile_map = _tile_map(tiles)
    disruption = tile_map.get("supplier_disruption_score")
    spike = tile_map.get("demand_spike_count")
    severity = _display_filter(spec, "severity")
    context = _base_context(request, spec, tiles)
    context.update({
        "vendors": _supplier_parties(request.tenant),
        "severity_choices": SEVERITY_CHOICES,
        "severity": severity,
        "display_only_filters": ("severity",),
        # The honest-framing notice — the resolver's own words when it computed, the constant when
        # it could not. Either way it is on the page.
        "method_note": _breakdown(disruption, "method", NOT_ML_NOTE),
        "not_ml_note": NOT_ML_NOTE,
        "reuse_note": _breakdown(disruption, "reuse", ""),
        "risk_components": _risk_components(disruption),
        "risk_weights": _breakdown(disruption, "weights", {}),
        "components_scored": _breakdown(disruption, "components_scored", 0),
        "components_total": _breakdown(disruption, "components_total", 0),
        # ONLY at network scope. `_r_supplier_disruption_score` returns two different row shapes:
        # per-supplier signal rows when no supplier is chosen, and this supplier's own weighted
        # COMPONENT rows when one is — and the component shape is already rendered above from
        # `risk_components`. Handing the league the component rows made every column of the supplier
        # table blank (they share no keys), which renders as a table of dashes rather than an error.
        "supplier_league": _rows_of(disruption) if not spec["params"].get("vendor") else [],
        "spike_rows": _rows_of(spike),
        "spike_threshold_pct": _breakdown(spike, "parameter_pct", analytics.SPIKE_PCT),
        "spike_window_days": analytics.SPIKE_SHORT_DAYS,
        "demand_netting_note": DEMAND_NETTING_NOTE,
        "stockout_rows": _rows_of(tile_map.get("projected_stockout_count")),
        "shipments_at_risk_rows": _rows_of(tile_map.get("shipments_at_risk_count")),
        # Ranked by impact_value — the exception queue, not an alert count.
        "open_alerts": _open_alerts(request.tenant, severity),
        "alert_rank_note": ("Open exceptions are ranked by value at risk, not by how many there "
                            "are — a hundred trivial ones must not bury the one that matters."),
    })
    return context, tiles


@login_required
def disruption_risk(request):
    """Supplier disruption, demand spikes, projected stockouts and the ranked exception queue."""
    spec = _filtered_risk(request)
    context, _tiles = _risk_context(request, spec)
    return render(request, spec["page"]["template"], context)


@login_required
def disruption_risk_export(request):
    """The risk page as CSV, with every component's arithmetic — a score nobody can check is not
    worth exporting either."""
    spec = _filtered_risk(request)
    context, tiles = _risk_context(request, spec)
    return _export(spec, tiles, sections=[
        ("How this score is computed", [{"method": context["method_note"]}]),
        ("Disruption score components", [
            {"component": row["label"], "points": row["points"], "weight": row["weight"],
             "contribution": row["contribution"], "scored": row["scored"],
             "explanation": row["explanation"]}
            for row in context["risk_components"]]),
        ("Open exceptions by value at risk", [
            {"number": alert.number, "raised": alert.raised_at.date().isoformat(),
             "type": alert.get_alert_type_display(), "severity": alert.get_severity_display(),
             "status": alert.get_status_display(), "subject": alert.subject_label,
             "impact_value": alert.impact_value, "title": alert.title}
            for alert in context["open_alerts"]]),
    ])
