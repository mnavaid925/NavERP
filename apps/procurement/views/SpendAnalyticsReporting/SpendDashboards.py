"""Procurement 6.14 Spend Analytics & Reporting — the three COMPUTED spend pages + one CSV.

**Spend Dashboards**, **Category Spend Analysis** and **Data Export & Visualization** are the three
NavERP.md 6.14 bullets that describe a *view over spend that already exists*, not a new document.
They are rendered exactly the way 6.11's ``FulfillmentBoards.py`` and 6.12's ``ReceiptBoards.py``
render theirs: read-only pages over rows other sub-modules own, with **zero new state, zero writes
and zero migration impact**. There is no model and no form in this lane (both files carry a
docstring saying so, so a CRUD-completeness reviewer sees a reason rather than a gap).

Four decisions worth recording, because a reviewer will otherwise go looking for the missing parts:

* **There is no FX rate table anywhere in this repository.** Money is therefore summed AT FACE
  VALUE PER CURRENCY. A window holding more than one currency sets ``mixed_currency=True`` and the
  page renders ``currency_rows`` instead of one bogus total. No rate is ever invented.
* **The department axis is a 3-hop nullable chain**, ``Coalesce(requisition.org_unit, ship_to)``,
  and it is NULL for every PO-less invoice. Every department breakdown therefore renders an
  explicit ``(unassigned)`` bucket and prints ``department_caveat``. A breakdown that silently drops
  those rows would make the bars disagree with the KPI strip above them.
* **On the committed basis the category axis is rules-only.** ``scm.PurchaseOrderLine`` has no
  ``item`` FK (verified — it carries ``item_description`` + ``sku_hint`` + ``gl_account`` only), so
  a PO line can only be classified by an explicit ``SpendClassificationRule``; anything unmatched
  falls to ``(Unclassified)``. The page says so rather than faking an item join.
* **The classification engine is a set of explicit, auditable rules.** It is not, and must never be
  labelled, "AI" or "ML". Likewise the export is a CSV download — there is no BI / PowerBI
  connector, and ``bi_note`` states that verbatim on the page.

--------------------------------------------------------------------------------------------------
INTEGRATE-PHASE RECORD  -  both hand-off notes below are DONE
--------------------------------------------------------------------------------------------------
1. ``apps/procurement/analytics.py`` now EXISTS. The compute layer this lane wrote inline (it owns
   no app-root file, so it could not create that module itself) was lifted into it verbatim under
   the contracted names, and this module imports them below. Call sites are unchanged.
   ``compute_report(report)`` was added there by the Integrator - it belongs to the SpendReports
   lane's entity and is consumed by ``views/SpendAnalyticsReporting/SpendReports.py``.
2. ``csv_safe`` now lives in ``views/_helpers.py`` (Backend rule 5 - a helper shared by more than
   one sub-module), with ``_csv_safe = csv_safe`` left behind in
   ``views/DashboardPortal/SelfServiceReports.py`` so 6.1's call sites keep working. The local
   definition that used to sit in the compute layer is gone; this module imports the shared one.
"""
import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Max, Min, Sum
from django.http import HttpResponse
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.core.models import OrgUnit
from apps.procurement.views._common import *  # noqa: F401,F403
# The shared spreadsheet-injection guard (Backend rule 5) - one implementation, used by 6.1's
# self-service export and by both of this module's downloads.
from apps.procurement.views._helpers import csv_safe
from apps.scm.models import ItemCategory

# Entity MODULES, not the package: ``models/__init__`` imports these same modules, so reaching them
# through the package here could re-enter a partially-initialised module at URLconf import time —
# the 6.13 ``InvoiceDisputes.py`` precedent.
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import money
from apps.procurement.models.SpendAnalyticsReporting.SpendReports import (
    BASIS_CHOICES,
    DATE_RANGE_CHOICES,
    DIMENSION_CHOICES,
    SpendReport,
    SpendReportSnapshot,
)

ZERO = Decimal("0")


# =================================================================================================
# COMPUTE LAYER  -  imported, never re-declared
# =================================================================================================
#
# Every name below is defined ONCE in ``apps/procurement/analytics.py`` and imported here. A second
# copy of any of them would let this page and the saved-report builder disagree about what spend
# is, which is the one defect this sub-module cannot afford. The compute module owns the arithmetic
# and the vocabulary; this module owns only the GET contract and the three renders.

from apps.procurement.analytics import (  # noqa: E402  (after the module's own imports, by design)
    BI_NOTE,
    COMMITTED_CATEGORY_NOTE,
    DEFAULT_BASIS,
    DEFAULT_DIMENSION,
    DEFAULT_RANGE,
    DEPARTMENT_CAVEAT,
    ITEM_FALLBACK_NOTE,
    ITEM_SCAN_CAP,
    MAX_EXPORT_ROWS,
    MAX_GROUP_ROWS,
    UNASSIGNED_LABEL,
    _BASIS_KEYS,
    _DIMENSION_KEYS,
    _RANGE_KEYS,
    _classify_select_related,
    _date_field,
    _department_expression,
    _money,
    _num,
    _share,
    _vendor_field,
    apply_axis_filters,
    basis_lines,
    classified_pct,
    currency_split,
    monthly_trend,
    range_bounds,
    spend_cube,
    spend_kpis,
)


# -- GET parameter sanitizing -------------------------------------------------------------------
#
# Every one of these degrades a junk value to a default instead of raising. These are report URLs:
# ``?basis=xx&range=yy&vendor=abc&category=999999999999999999999`` is something anybody can type
# into the address bar, and it must render 200 with the filter skipped (L11 / L44).

def _parse_date(value):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None`` — never an exception."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _selected(request, param, allowed, default):
    value = request.GET.get(param, "").strip()
    return value if value in allowed else default


def _window(request):
    """``(basis, range_key, start, end)`` from the shared filter contract."""
    basis = _selected(request, "basis", _BASIS_KEYS, DEFAULT_BASIS)
    range_key = _selected(request, "range", _RANGE_KEYS, DEFAULT_RANGE)
    start, end = range_bounds(range_key,
                              _parse_date(request.GET.get("date_from")),
                              _parse_date(request.GET.get("date_to")))
    return basis, range_key, start, end


def _axis_pks(request):
    """The four FK filters, each guarded by ``as_db_int``."""
    return {
        "vendor_id": as_db_int(request.GET.get("vendor")),
        "category_id": as_db_int(request.GET.get("category")),
        "org_unit_id": as_db_int(request.GET.get("org_unit")),
        "gl_account_id": as_db_int(request.GET.get("gl_account")),
    }


def _no_tenant(request, what):
    """The ``inbound_tracking`` precedent: say WHY the page is empty before running a query.

    The superuser has ``tenant=None``; every queryset below is tenant-scoped, so without this the
    page would render eight zeroes and no explanation.
    """
    messages.error(request, f"Select a tenant workspace to view {what}.")
    return redirect("dashboard:home")


# =================================================================================================
# THE PAGES  —  all read-only. There is no model save anywhere in this module.
# =================================================================================================

@login_required
def spend_dashboard(request):
    """**Spend Dashboards** — the KPI strip plus four breakdowns over one spend window.

    Four axes are cut from ONE filtered line window rather than four rebuilt ones, and the category
    pass is shared with the ``classified_pct`` KPI, so the page does not classify the same lines
    twice. The committed-basis savings and cycle-time cube is SCM 4.11's
    (``scm:spend_analytics``) and is LINKED, never restated here.
    """
    if request.tenant is None:
        return _no_tenant(request, "spend analytics")

    basis, range_key, start, end = _window(request)
    lines = apply_axis_filters(basis_lines(request.tenant, basis, start, end),
                               basis, request.tenant, **_axis_pks(request))

    by_supplier = spend_cube(request.tenant, basis, start, end, "supplier", lines=lines)
    by_department = spend_cube(request.tenant, basis, start, end, "department", lines=lines)
    by_gl_account = spend_cube(request.tenant, basis, start, end, "gl_account", lines=lines)
    classified_share, unclassified_value, by_category = classified_pct(
        request.tenant, basis, start, end, lines)

    currency = currency_split(request.tenant, basis, start, end, lines=lines)
    kpis = spend_kpis(request.tenant, basis, start, end, lines,
                      by_supplier=by_supplier, classified=classified_share)

    return render(request, "procurement/spendanalytics/dashboard.html", {
        "kpis": kpis,
        "by_supplier": by_supplier,
        "by_category": by_category,
        "by_department": by_department,
        "by_gl_account": by_gl_account,
        "trend": monthly_trend(request.tenant, basis, start, end, lines=lines),
        "currency_rows": currency["rows"],
        "mixed_currency": currency["mixed_currency"],
        "basis": basis,
        "basis_choices": BASIS_CHOICES,
        "range_key": range_key,
        "date_range_choices": DATE_RANGE_CHOICES,
        "start": start,
        "end": end,
        "stats": {
            "invoice_count": kpis["invoice_count"]["value"],
            "line_count": lines.count(),
            "supplier_count": kpis["supplier_count"]["value"],
            "unclassified_value": unclassified_value,
        },
        # The link ACROSS to SCM 4.11 for committed-basis savings and cycle time. 4.11 owns that
        # cube; duplicating it here would give the workspace two answers to the same question.
        "scm_analytics_url": reverse("scm:spend_analytics"),
        "department_caveat": DEPARTMENT_CAVEAT,
        # Link OUT to 6.13's invoice detail rather than re-rendering it here.
        "drill_url_name": "procurement:supplierinvoice_detail",
        "maverick_dashboard_url": reverse("procurement:maverick_dashboard"),
        "category_spend_url": reverse("procurement:category_spend"),
        "workbench_url": reverse("procurement:classification_workbench"),
        "export_url": reverse("procurement:spend_export"),
    })


@login_required
def category_spend(request):
    """**Category Spend Analysis** — the Pareto supplier league inside one category.

    Three questions a category manager actually asks, answered off one window: who am I buying this
    from (Pareto + HHI concentration + ABC bands), what am I paying for the same thing across
    suppliers (the per-item price spread), and how much of the spend is in the long tail that could
    be consolidated.
    """
    if request.tenant is None:
        return _no_tenant(request, "category spend")

    basis, range_key, start, end = _window(request)
    axis_pks = _axis_pks(request)
    category_id = axis_pks["category_id"]

    categories = ItemCategory.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    # ``category`` may legitimately be None (no filter, or a pk from another workspace) — the
    # template guards it with {% if category %}.
    category = categories.filter(pk=category_id).first() if category_id else None

    lines = apply_axis_filters(basis_lines(request.tenant, basis, start, end),
                               basis, request.tenant, **axis_pks)

    totals = lines.aggregate(
        value=Sum("line_total"),
        txns=Count("id"),
        suppliers=Count(f"{_vendor_field(basis)}", distinct=True),
    )
    net_spend = money(totals["value"] or ZERO)
    txns = totals["txns"] or 0

    # -- the Pareto supplier league ---------------------------------------------------------
    # Every supplier, not just the top N: the cumulative curve and the ABC bands are only
    # meaningful over the whole population. Display is capped afterwards.
    field = _vendor_field(basis)
    league = []
    for row in (lines.values(f"{field}_id", f"{field}__name")
                .annotate(v=Sum("line_total"), n=Count("id")).order_by("-v")):
        value = money(row["v"] or ZERO)
        league.append({
            "label": row[f"{field}__name"] or UNASSIGNED_LABEL,
            "pk": row[f"{field}_id"],
            "total": value,
            "display": _money(value),
            "share_pct": _share(value, net_spend),
            "txns": row["n"] or 0,
        })

    running = ZERO
    hhi = ZERO
    abc_buckets = {"A": [0, ZERO], "B": [0, ZERO], "C": [0, ZERO]}
    tail_rows = []
    for row in league:
        share = row["share_pct"]
        hhi += share * share
        running += share
        row["cumulative_pct"] = running.quantize(Decimal("0.1"))
        # A = the suppliers making up the first 80% of spend, B = up to 95%, C = the long tail.
        band = "A" if running <= Decimal("80") else ("B" if running <= Decimal("95") else "C")
        row["band"] = band
        abc_buckets[band][0] += 1
        abc_buckets[band][1] += row["total"]
        if band == "C":
            tail_rows.append({k: row[k] for k in ("label", "pk", "total", "display", "share_pct")})

    abc_rows = [{
        "band": band,
        "label": {"A": "A — top 80% of spend", "B": "B — next 15%",
                  "C": "C — long tail"}[band],
        "suppliers": abc_buckets[band][0],
        "value": abc_buckets[band][1],
        "display": _money(abc_buckets[band][1]),
        "share_pct": _share(abc_buckets[band][1], net_spend),
    } for band in ("A", "B", "C")]

    # The long tail is the honest consolidation figure: spend spread across suppliers who are each
    # individually immaterial. It is an OPPORTUNITY, not a saving — nothing here claims a number
    # that would be realised.
    consolidation_opportunity = abc_buckets["C"][1]
    tail_share_pct = _share(consolidation_opportunity, net_spend)

    # -- the per-item price spread ------------------------------------------------------------
    label_field = "item__name" if basis == "invoiced" else "item_description"
    item_keys = [label_field, "sku_hint", "description"] if basis == "invoiced" else [
        label_field, "sku_hint"]
    item_rows, sole_source_count = _item_spread(lines, basis, label_field, item_keys, field)

    currency = currency_split(request.tenant, basis, start, end, lines=lines)
    _classified, unclassified_value, _category_rows = classified_pct(
        request.tenant, basis, start, end, lines)

    average_price = money(Decimal(net_spend) / txns) if txns else ZERO

    return render(request, "procurement/spendanalytics/category_spend.html", {
        "categories": categories,
        "category": category,
        "rows": league[:MAX_GROUP_ROWS],
        "hhi": int(hhi),
        "trend": monthly_trend(request.tenant, basis, start, end, lines=lines),
        "item_rows": item_rows,
        "consolidation_opportunity": consolidation_opportunity,
        "sole_source_count": sole_source_count,
        "tail_rows": tail_rows[:MAX_GROUP_ROWS],
        "tail_share_pct": tail_share_pct,
        "abc_rows": abc_rows,
        "basis": basis,
        "basis_choices": BASIS_CHOICES,
        "range_key": range_key,
        "date_range_choices": DATE_RANGE_CHOICES,
        "start": start,
        "end": end,
        "stats": {
            "suppliers": totals["suppliers"] or 0,
            "txns": txns,
            "net_spend": net_spend,
            "avg_price": average_price,
        },
        "unclassified_value": unclassified_value,
        "fallback_note": ITEM_FALLBACK_NOTE,
        "committed_category_note": COMMITTED_CATEGORY_NOTE,
        "mixed_currency": currency["mixed_currency"],
        "currency_rows": currency["rows"],
        "workbench_url": reverse("procurement:classification_workbench"),
    })


def _item_spread(lines, basis, label_field, item_keys, vendor_field):
    """``(item_rows, sole_source_count)`` — what the same thing costs across suppliers.

    ``item`` in the returned rows is a LABEL STRING, never a model instance: the fallback chain is
    the stock item's name, then the SKU hint, then the description, because a line keyed from a
    paper invoice has no item at all. That is what ``fallback_note`` tells the reader.

    One query, ordered by spend and capped at :data:`ITEM_SCAN_CAP`. The sole-source count is taken
    over the same scanned population — it counts items bought from exactly one supplier, which is
    the concentration risk a category manager is looking for.
    """
    grouped = defaultdict(lambda: {"qty": ZERO, "spend": ZERO, "lo": None, "hi": None,
                                   "vendors": set()})
    rows = (lines.values(*item_keys, f"{vendor_field}_id")
            .annotate(qty=Sum("quantity"), spend=Sum("line_total"),
                      lo=Min("unit_price"), hi=Max("unit_price"))
            .order_by("-spend")[:ITEM_SCAN_CAP])
    for row in rows:
        label = next((row.get(key) for key in item_keys if row.get(key)), "—")
        bucket = grouped[label]
        bucket["qty"] += row["qty"] or ZERO
        bucket["spend"] += row["spend"] or ZERO
        bucket["vendors"].add(row[f"{vendor_field}_id"])
        for key in ("lo", "hi"):
            value = row[key]
            if value is None:
                continue
            current = bucket[key]
            if current is None:
                bucket[key] = value
            else:
                bucket[key] = min(current, value) if key == "lo" else max(current, value)

    sole_source_count = sum(1 for data in grouped.values() if len(data["vendors"]) == 1)
    ordered = sorted(grouped.items(), key=lambda kv: -(kv[1]["spend"] or ZERO))
    item_rows = []
    for label, data in ordered[:MAX_GROUP_ROWS]:
        lo, hi = data["lo"], data["hi"]
        item_rows.append({
            "item": label,
            "qty": data["qty"],
            "spend": money(data["spend"]),
            "lo": money(lo) if lo is not None else ZERO,
            "hi": money(hi) if hi is not None else ZERO,
            "spread": money((hi - lo) if (lo is not None and hi is not None) else ZERO),
        })
    return item_rows, sole_source_count


#: How many rows the export PAGE previews. Also the register row limit it asks for, so the page
#: never builds rows it will not draw.
_PREVIEW_ROWS = 25

#: The export register's fixed columns when no dimension is chosen. Kept as one constant so the
#: preview on the page and the CSV that downloads can never show different headers.
_REGISTER_COLUMNS = ["Date", "Document", "Supplier", "Description", "SKU", "GL Account",
                     "Department", "Currency", "Quantity", "Unit price", "Line total"]


def _dimension_label(dimension):
    return dict(DIMENSION_CHOICES).get(dimension, dimension)


def _export_dataset(tenant, basis, start, end, dimension, lines, row_limit=MAX_EXPORT_ROWS):
    """``(columns, rows, total_rows)`` — exactly what the page previews and the CSV downloads.

    Two shapes, chosen by ``dimension``:

    * a **dimension** produces the aggregated cube (one row per group) — a pivot-ready extract;
    * ``none`` produces the **line-level register** (one row per spend line), capped at
      ``row_limit`` (:data:`MAX_EXPORT_ROWS` by default).

    ``row_limit`` bounds the register BEFORE the rows are built, which is the whole point: the
    export PAGE previews 25 rows, and slicing after materialising five thousand of them pays the
    entire download's cost on every page view (L40). It deliberately does NOT touch the cube
    branch — that branch's ``total_rows`` is the true group count and must stay so.

    ``rows`` are lists of plain scalars aligned to ``columns``, so the preview table and
    ``csv.writer`` consume the same structure and cannot drift.
    """
    if dimension != "none":
        cube = spend_cube(tenant, basis, start, end, dimension, top_n=MAX_EXPORT_ROWS, lines=lines)
        columns = [_dimension_label(dimension), "Spend", "Share %", "Transactions"]
        rows = [[row["label"], row["display"], str(row["pct"]), row["count"]] for row in cube]
        return columns, rows, len(rows)

    total_rows = lines.count()
    # The register row builder below reads the DOCUMENT's own currency on both bases and its
    # vendor on the committed basis — hops ``_classify_select_related`` does not carry, because
    # the classification walk has no use for a currency. Without them a 5,000-row export is
    # 5,000-10,000 extra queries. Widened HERE rather than in the shared helper, so the
    # classification pass keeps its narrow join list.
    document_relations = (("invoice__currency",) if basis == "invoiced"
                          else ("purchase_order__vendor", "purchase_order__currency"))
    fetched = (lines
               .select_related(*_classify_select_related(basis), "gl_account",
                               *document_relations)
               .annotate(_dept=_department_expression(basis))
               .order_by("-" + _date_field(basis), "-id")[:row_limit])
    fetched = list(fetched)

    names = dict(OrgUnit.objects.filter(
        tenant=tenant, pk__in=[line._dept for line in fetched if line._dept]
    ).values_list("id", "name"))

    rows = []
    for line in fetched:
        if basis == "invoiced":
            document = line.invoice
            when = document.invoice_date
            reference = document.invoice_number or document.number
            vendor = document.vendor
            currency = document.currency
            description = line.description
        else:
            document = line.purchase_order
            when = getattr(line, "doc_date", None) or document.order_date
            reference = document.number
            vendor = document.vendor
            currency = document.currency
            description = line.item_description
        rows.append([
            when or "",
            reference or "",
            vendor.name if vendor is not None else "",
            description or "",
            line.sku_hint or "",
            f"{line.gl_account.code} — {line.gl_account.name}" if line.gl_account_id else "",
            names.get(line._dept, UNASSIGNED_LABEL) if line._dept else UNASSIGNED_LABEL,
            currency.code if currency is not None else "",
            line.quantity,
            line.unit_price,
            line.line_total,
        ])
    return list(_REGISTER_COLUMNS), rows, total_rows


@login_required
def spend_export(request):
    """**Data Export & Visualization** — the export PAGE.

    A sidebar bullet must land on a page, not on a bare download, so this renders the filter bar,
    a live row count, a 25-row preview of exactly what will download, and the saved reports and
    snapshots the workspace already has. The download link hangs off it and reads the SAME GET
    parameters, so the file honours whatever the reader is looking at.

    ``bi_note`` is printed verbatim: this is a CSV download. There is no BI / PowerBI connector in
    this changeset and no label may imply one.
    """
    if request.tenant is None:
        return _no_tenant(request, "the spend export")

    basis, range_key, start, end = _window(request)
    dimension = _selected(request, "dimension", _DIMENSION_KEYS, DEFAULT_DIMENSION)
    lines = apply_axis_filters(basis_lines(request.tenant, basis, start, end),
                               basis, request.tenant, **_axis_pks(request))

    # The page shows a 25-row preview, so it builds 25 rows — not five thousand it then slices.
    # ``total_rows`` comes from its own ``lines.count()`` inside the helper, so the "Showing N of
    # M" note is unaffected by the limit.
    columns, rows, total_rows = _export_dataset(
        request.tenant, basis, start, end, dimension, lines, row_limit=_PREVIEW_ROWS)

    reports = (SpendReport.objects.filter(tenant=request.tenant)
               .select_related("owner", "vendor", "category", "org_unit", "gl_account"))
    snapshots = (SpendReportSnapshot.objects.filter(tenant=request.tenant)
                 .select_related("report", "generated_by")[:10])

    capped = min(total_rows, MAX_EXPORT_ROWS)
    showing_note = f"Showing {_num(capped)} of {_num(total_rows)} rows"
    if total_rows > MAX_EXPORT_ROWS:
        showing_note += (f" — the download is capped at {_num(MAX_EXPORT_ROWS)} rows. "
                         "Narrow the date range or the filters to export the rest.")

    return render(request, "procurement/spendanalytics/export.html", {
        "reports": reports,
        "snapshots": snapshots,
        "basis": basis,
        "basis_choices": BASIS_CHOICES,
        "range_key": range_key,
        "date_range_choices": DATE_RANGE_CHOICES,
        "dimension": dimension,
        "dimension_choices": DIMENSION_CHOICES,
        "start": start,
        "end": end,
        "row_count": total_rows,
        "max_rows": MAX_EXPORT_ROWS,
        "showing_note": showing_note,
        # The template appends the current querystring to this so the download honours the
        # filters the reader can see.
        "download_url": reverse("procurement:spend_export_download"),
        "bi_note": BI_NOTE,
        "stats": {
            "reports": reports.count(),
            "snapshots": SpendReportSnapshot.objects.filter(tenant=request.tenant).count(),
            "rows": total_rows,
            "max_rows": MAX_EXPORT_ROWS,
        },
        "preview_rows": rows[:_PREVIEW_ROWS],
        "preview_columns": columns,
    })


@login_required
def spend_export_download(request):
    """The CSV itself — same GET parameters, same rows, same order as the page's preview.

    WARNING, and the reason ``csv_safe`` wraps every cell: supplier names, line descriptions and
    GL account names are user-authored, and a spreadsheet EXECUTES a cell that opens with ``=``,
    ``+``, ``-`` or ``@``. A crafted supplier name is a formula-injection payload the moment this
    file is opened, so the escaping is not optional and must not be "optimised" away.
    """
    if request.tenant is None:
        return _no_tenant(request, "the spend export")

    basis, range_key, start, end = _window(request)
    dimension = _selected(request, "dimension", _DIMENSION_KEYS, DEFAULT_DIMENSION)
    lines = apply_axis_filters(basis_lines(request.tenant, basis, start, end),
                               basis, request.tenant, **_axis_pks(request))
    columns, rows, total_rows = _export_dataset(
        request.tenant, basis, start, end, dimension, lines)

    # The cap is stated in the filename as well as on the page, so a file that was truncated says
    # so even after it has been detached from the page that produced it.
    suffix = f"-first{MAX_EXPORT_ROWS}" if total_rows > MAX_EXPORT_ROWS else ""
    filename = f"spend-{basis}-{start:%Y%m%d}-{end:%Y%m%d}{suffix}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([csv_safe(column) for column in columns])
    for row in rows:
        writer.writerow([csv_safe(cell) for cell in row])
    return response
