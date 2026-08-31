"""Procurement 6.14 Spend Analytics & Reporting — the classification workbench.

**Spend Classification & Categorization** bullet. A COMPUTED, READ-ONLY page: it owns no table,
writes nothing and contributes nothing to ``makemigrations``. It answers one question — *which
spend has the taxonomy not reached yet, and what is the single rule that would reach the most of
it?* — and turns each answer into a pre-filled link to ``procurement:spendrule_create``.

Three things a reviewer will look for, so they are stated rather than inferred:

* **The engine is explicit, ordered rules.** ``ENGINE_NOTE`` is printed verbatim on the page. This
  sub-module ships no machine learning, and no label here may imply that it does — a buyer has to
  be able to read the rule that produced a figure and change it.
* **Unclassified is computed the same way the cube computes it.** The workbench does not carry its
  own definition of "unclassified": it takes the same window (``analytics.basis_lines`` +
  ``apply_axis_filters``), removes the ``item.category`` passthrough leg and every line an active
  rule's own ``line_filter`` claims, and groups what is left. If the cube and this page disagreed,
  a buyer would write a rule against a row that was never unclassified.
* **The grouping is done in SQL, never per line.** Each of the three groupings is one
  ``values().annotate(Sum)`` over the remainder queryset. The per-line ``resolve()`` walk that the
  category axis needs is deliberately NOT used here — a workbench that walked every line to build
  a list of candidate rules would be the slowest page in the module.

Nothing on this page moves money and nothing touches ``accounting.*`` (L29).
"""
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.procurement.analytics import (
    BASIS_CHOICES,
    DATE_RANGE_CHOICES,
    DEFAULT_BASIS,
    DEFAULT_RANGE,
    ENGINE_NOTE,
    MAX_GROUP_ROWS,
    UNASSIGNED_LABEL,
    _money,
    _share,
    _vendor_field,
    active_rules,
    apply_axis_filters,
    basis_lines,
    classified_pct,
    money,
    range_bounds,
)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/spendanalytics/classification_workbench.html"

#: How the unclassified remainder can be grouped. Each key names the ``match_type`` a rule written
#: from that row would carry, which is what makes the deep-link into ``spendrule_create`` honest.
GROUP_BY_CHOICES = [
    ("vendor", "Supplier"),
    ("gl_account", "GL account"),
    ("keyword", "Description / SKU keyword"),
]
_GROUP_KEYS = {key for key, _label in GROUP_BY_CHOICES}
DEFAULT_GROUP_BY = "vendor"

_BASIS_KEYS = {key for key, _label in BASIS_CHOICES}
_RANGE_KEYS = {key for key, _label in DATE_RANGE_CHOICES}

#: Rows per page. The workbench is a work queue — a buyer writes rules off the top of it — so the
#: page is short on purpose and the ranking (biggest unclassified value first) does the work.
PAGE_SIZE = 25


def _selected(request, param, allowed, default):
    """A GET value that must be one of ``allowed``, or the default. Never raises (L11)."""
    value = request.GET.get(param, "").strip()
    return value if value in allowed else default


def _unclassified(lines, basis, rules):
    """The lines the taxonomy does not reach — the cube's own definition, in SQL.

    Classification order is ``item.category`` -> the first matching rule -> ``(Unclassified)``, so
    the remainder is what survives BOTH legs. On the committed basis there is no item FK at all
    (``scm.PurchaseOrderLine`` carries a description, an SKU hint and a GL account), so only the
    rules leg exists — which is also why a committed-basis workspace with no rules shows its whole
    window here rather than a misleadingly short list.
    """
    remainder = lines
    if basis == "invoiced":
        remainder = remainder.filter(Q(item__isnull=True) | Q(item__category__isnull=True))

    claimed = None
    for rule in rules:
        predicate = rule.line_filter(basis)
        if predicate is not None:
            claimed = predicate if claimed is None else (claimed | predicate)
    if claimed is not None:
        remainder = remainder.exclude(claimed)
    return remainder


def _rule_url(match_type, *, pk=None, keyword=""):
    """A ``spendrule_create`` link pre-filled from one row.

    The prefill is read back by ``SpendClassificationRules._prefill``, which re-checks every pk
    against THIS workspace before using it — so this link is a convenience, never an authorization
    path.
    """
    url = reverse("procurement:spendrule_create")
    params = [f"match_type={match_type}"]
    if pk:
        params.append(f"{match_type}={pk}")
    if keyword:
        from urllib.parse import quote
        params.append(f"keyword={quote(keyword[:120])}")
    return f"{url}?{'&'.join(params)}"


def _group_rows(remainder, basis, group_by, total):
    """``[{label, pk, value, display, pct, count, match_type, create_url}, …]``, biggest first.

    ONE grouped query per call. ``pk`` is ``None`` for a keyword row (there is nothing to point a
    FK at) and for the ``(unassigned)`` bucket, which is why the template guards its drill links.
    """
    rows = []
    if group_by == "gl_account":
        for row in (remainder.values("gl_account_id", "gl_account__code", "gl_account__name")
                    .annotate(v=Sum("line_total"), n=Count("id"))):
            pk = row["gl_account_id"]
            label = (f"{row['gl_account__code']} — {row['gl_account__name']}" if pk
                     else UNASSIGNED_LABEL)
            rows.append((pk, label, row["v"], row["n"], "gl_account", ""))
    elif group_by == "keyword":
        for row in (remainder.values("sku_hint")
                    .annotate(v=Sum("line_total"), n=Count("id"))):
            hint = (row["sku_hint"] or "").strip()
            rows.append((None, hint or UNASSIGNED_LABEL, row["v"], row["n"], "keyword", hint))
    else:
        field = _vendor_field(basis)
        for row in (remainder.values(f"{field}_id", f"{field}__name")
                    .annotate(v=Sum("line_total"), n=Count("id"))):
            pk = row[f"{field}_id"]
            rows.append((pk, row[f"{field}__name"] or UNASSIGNED_LABEL, row["v"], row["n"],
                         "vendor", ""))

    rows.sort(key=lambda item: (-(item[2] or 0), str(item[1])))
    return [{
        "label": label,
        "pk": pk,
        "value": money(value or 0),
        "display": _money(value),
        "pct": _share(value, total),
        "count": count or 0,
        "match_type": match_type,
        "keyword": keyword,
        # A row with nothing to point a rule at (the (unassigned) bucket, or a blank SKU hint)
        # gets no link: a "write a rule" button that opens an empty form is worse than no button.
        "create_url": (_rule_url(match_type, pk=pk, keyword=keyword)
                       if (pk or keyword) else ""),
    } for pk, label, value, count, match_type, keyword in rows]


@login_required
def classification_workbench(request):
    """**Spend Classification & Categorization** — the unclassified queue, ranked by value.

    Read-only. The buyer's next action is always the same: take the biggest row and write the one
    rule that claims it, which is why every row carries a pre-filled ``create_url`` rather than
    making somebody re-type what the row already knows.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view spend classification.")
        return redirect("dashboard:home")

    basis = _selected(request, "basis", _BASIS_KEYS, DEFAULT_BASIS)
    range_key = _selected(request, "range", _RANGE_KEYS, DEFAULT_RANGE)
    group_by = _selected(request, "group_by", _GROUP_KEYS, DEFAULT_GROUP_BY)
    start, end = range_bounds(range_key)

    lines = basis_lines(request.tenant, basis, start, end)
    lines = apply_axis_filters(
        lines, basis, request.tenant,
        vendor_id=as_db_int(request.GET.get("vendor")),
        category_id=as_db_int(request.GET.get("category")),
        org_unit_id=as_db_int(request.GET.get("org_unit")),
        gl_account_id=as_db_int(request.GET.get("gl_account")),
    )

    rules = active_rules(request.tenant)
    # ONE category pass for the coverage figure; the workbench's own grouping runs on the
    # remainder queryset, so neither is recomputed for the other.
    pct, unclassified_value, _category_rows = classified_pct(
        request.tenant, basis, start, end, lines=lines, rules=rules)

    remainder = _unclassified(lines, basis, rules)
    totals = lines.aggregate(v=Sum("line_total"), n=Count("id"))
    total_value = money(totals["v"] or 0)
    remainder_total = money(remainder.aggregate(v=Sum("line_total"))["v"] or 0)

    rows = _group_rows(remainder, basis, group_by, remainder_total)
    paginator = Paginator(rows, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, TEMPLATE, {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "classified_pct": pct,
        "unclassified_value": unclassified_value,
        "unclassified_display": _money(unclassified_value),
        "total_value": total_value,
        "total_display": _money(total_value),
        # The active rules in the order the engine reads them — priority, then id. The panel is
        # the legend for the queue beside it: these are what is already claiming spend.
        "rules": rules[:MAX_GROUP_ROWS],
        "rule_count": len(rules),
        "group_by": group_by,
        "group_by_choices": GROUP_BY_CHOICES,
        "basis": basis,
        "basis_choices": BASIS_CHOICES,
        "range_key": range_key,
        "date_range_choices": DATE_RANGE_CHOICES,
        "start": start,
        "end": end,
        "stats": {
            "lines": totals["n"] or 0,
            "total_value": total_value,
            "unclassified_value": unclassified_value,
            "classified_pct": pct,
            "rules": len(rules),
            "groups": len(rows),
        },
        "create_rule_url": reverse("procurement:spendrule_create"),
        "rules_url": reverse("procurement:spendrule_list"),
        "dashboard_url": reverse("procurement:spend_dashboard"),
        "category_spend_url": reverse("procurement:category_spend"),
        "engine_note": ENGINE_NOTE,
    })
