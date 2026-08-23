"""Inventory 5.12 Multi-Location Management — network CRUD views + global stock page.

Five thin CRUD wrappers over apps.core.crud for the ``LocationNetwork`` [LNW-] config
row (writes tenant-admin gated; reads member-visible with ``is_admin`` hiding the
affordances), plus ONE computed page: ``global_stock``, the multi-location visibility
roll-up. Both live in this single module per the 5.12 build-wave lane split.

``global_stock`` owns ZERO writes and FOUR frozen queries — all tenant nodes once,
all tenant warehouses once, ONE StockMove grouped sum by location (quantity AND
quantity×unit_cost in the same aggregate, so valuation costs nothing extra), ONE
StockTransferLine grouped by source+destination where the transfer is in flight.
STATUS PINNED: goods-in-flight means ``status="in_transit"`` ONLY — draft /
pending_approval / approved transfers are paperwork whose units still truthfully sit
at source, and completed/cancelled ones have no flight left.

Rulings stated where they bite: aggregate sums render REAL zeros when a site has no
stock (orchestrator ruling); in-transit quantities are ADDITIVE information, never
subtracted from on-hand, because transfer legs post atomically at completion; and
there is no pagination because Paginator cannot order a hierarchy meaningfully while
the tree itself is depth-capped at 8 hops — network pages are small by construction.
"""
from decimal import Decimal

from django.db.models import F, Sum

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.MultiLocationManagement.LocationNetworks import (
    LocationNetworkForm,
)
# Through the leaf module, not the package root: this file ships during the build
# wave, before apps/inventory/models/__init__.py gains its 5.12 lines (integrate
# phase) — attribute access through the not-yet-wired package would raise at import.
from apps.inventory.models.MultiLocationManagement.LocationNetworks import (
    MAX_TREE_DEPTH,
    LocationNetwork,
)
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Location, StockMove, StockTransferLine

ZERO = Decimal("0")

#: Goods-in-flight vocabulary, frozen from scm.StockTransfer.STATUS_CHOICES: ONLY an
#: actually-departed movement counts (see module docstring for why approval rungs don't).
IN_FLIGHT_STATUSES = ("in_transit",)

_IS_ACTIVE_CHOICES = [["active", "Active"], ["inactive", "Inactive"]]


def _is_admin(user):
    """The one admin flag every template receives — same test as the decorator."""
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _scoped(tenant):
    """Tenant-scoped node queryset with the joins every list/detail page renders."""
    return (LocationNetwork.objects.filter(tenant=tenant)
            .select_related("parent", "warehouse"))


# -- LocationNetwork CRUD -------------------------------------------------------------------------

@login_required
def locationnetwork_list(request):
    qs = _scoped(request.tenant)
    node_type = request.GET.get("node_type", "").strip()
    if node_type in dict(LocationNetwork.NODE_TYPE_CHOICES):
        qs = qs.filter(node_type=node_type)
    is_active = request.GET.get("is_active", "").strip()
    if is_active == "active":
        qs = qs.filter(is_active=True)
    elif is_active == "inactive":
        qs = qs.filter(is_active=False)
    return crud_list(
        request, qs, "inventory/multilocation/locationnetwork/list.html",
        search_fields=["number", "code", "name"],
        extra_context={
            "node_type_choices": LocationNetwork.NODE_TYPE_CHOICES,
            "node_type": node_type,
            "is_active_choices": _IS_ACTIVE_CHOICES,
            "is_active": is_active,
            "is_admin": _is_admin(request.user),
        },
    )


@login_required
def locationnetwork_detail(request, pk):
    """Node detail: ancestry breadcrumb, direct children and the attached site.

    Hand-rolled rather than crud_detail for the same reason wave_detail is:
    children/path_label depend on the resolved object, and crud_detail's
    extra_context is a plain dict evaluated before the helper runs."""
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    admin = _is_admin(request.user)
    return render(request, "inventory/multilocation/locationnetwork/detail.html", {
        "obj": obj,
        "path_label": obj.path(),
        "children": obj.children.all().order_by("code"),
        "is_admin": admin,
    })


@tenant_admin_required
def locationnetwork_create(request):
    return crud_create(
        request, form_class=LocationNetworkForm,
        template="inventory/multilocation/locationnetwork/form.html",
        success_url="inventory:locationnetwork_list",
    )


@tenant_admin_required
def locationnetwork_edit(request, pk):
    return crud_edit(
        request, model=LocationNetwork, pk=pk, form_class=LocationNetworkForm,
        template="inventory/multilocation/locationnetwork/form.html",
        success_url="inventory:locationnetwork_list",
    )


@tenant_admin_required
@require_POST
def locationnetwork_delete(request, pk):
    """Deleting a parent reparents its children to roots via SET_NULL — config rows
    have no ledger legs behind them, so plain crud_delete suffices at any time."""
    return crud_delete(request, model=LocationNetwork, pk=pk,
                       success_url="inventory:locationnetwork_list")


# -- computed page ----------------------------------------------------------------------------------

@login_required
def global_stock(request):
    """Global Stock Visibility: every org-tier node rolled up over its subtree's
    warehouses, plus whatever stocked sites attach to NO node under an explicit
    "Unassigned sites" group (orphan-honest). Read-only by construction.

    Query budget: four flat queries (module docstring). Everything else — subtree
    sets, roll-ups, the q filter — happens in Python over those rows; trees are
    depth-capped at MAX_TREE_DEPTH so no malformed row can hang the render.
    """
    tenant = request.tenant

    # (1) every node, parents pre-joined so path()/tree walks never re-query.
    nodes = list(LocationNetwork.objects.filter(tenant=tenant)
                 .select_related("parent", "warehouse").order_by("code"))
    # (2) every warehouse-typed site, keyed for O(1) attachment lookups.
    warehouses = {loc.pk: loc
                  for loc in Location.objects.filter(
                      tenant=tenant, location_type="warehouse").order_by("code")}

    # (3) ONE grouped ledger read per location — quantity AND value together.
    stock_qty, stock_val = {}, {}
    if warehouses:
        for row in (StockMove.objects.filter(
                        tenant=tenant, location_id__in=warehouses)
                    .values("location_id")
                    .annotate(qty=Sum("quantity"),
                              val=Sum(F("quantity") * F("unit_cost")))):
            stock_qty[row["location_id"]] = row["qty"] or ZERO
            stock_val[row["location_id"]] = row["val"] or ZERO

    # (4) ONE grouped in-transit read by (source, destination). StockTransferLine has
    # NO tenant column of its own — always through transfer__tenant (5.7 gotcha).
    transit_out, transit_in = {}, {}
    in_transit_total = ZERO
    if tenant is not None:
        for row in (StockTransferLine.objects
                    .filter(transfer__tenant=tenant,
                            transfer__status__in=IN_FLIGHT_STATUSES)
                    .values("transfer__from_location_id",
                            "transfer__to_location_id")
                    .annotate(qty=Sum("quantity"))):
            qty = row["qty"] or ZERO
            src = row["transfer__from_location_id"]
            dst = row["transfer__to_location_id"]
            if src is not None:
                transit_out[src] = transit_out.get(src, ZERO) + qty
            if dst is not None:
                transit_in[dst] = transit_in.get(dst, ZERO) + qty
            in_transit_total += qty

    children_map = {}
    roots = []
    for n in nodes:
        if n.parent_id is None:
            roots.append(n)
        else:
            children_map.setdefault(n.parent_id, []).append(n)

    def subtree_warehouse_ids(node):
        """Warehouse pks under one node — iterative, seen-set, depth-capped, so a
        malformed self-parent row cannot loop the page (Locations.py:95 precedent).
        A warehouse attaches to at most ONE node (("tenant","warehouse") unique), so
        these sets are disjoint across siblings by construction."""
        ids, stack, seen = [], [(node, 0)], set()
        while stack:
            cur, depth = stack.pop()
            if cur.pk in seen or depth > MAX_TREE_DEPTH:
                continue
            seen.add(cur.pk)
            if cur.warehouse_id:
                ids.append(cur.warehouse_id)
            for child in reversed(children_map.get(cur.pk, [])):
                stack.append((child, depth + 1))
        return ids

    def totals_for(ids):
        qty = sum((stock_qty[pk] for pk in ids), ZERO)
        val = sum((stock_val[pk] for pk in ids), ZERO)
        return qty, val

    def make_row(node, depth):
        ids = subtree_warehouse_ids(node)
        qty, val = totals_for(ids)
        own = [warehouses[node.warehouse_id]] if node.warehouse_id else []
        return {
            "node": node,
            "path_label": node.path(),
            "depth": depth,
            "own_warehouses": own,
            "stock_total": qty,
            "stock_value": val,
            "in_transit_in": sum((transit_in.get(pk, ZERO) for pk in ids), ZERO),
            "in_transit_out": sum((transit_out.get(pk, ZERO) for pk in ids), ZERO),
        }

    # Emit every node pre-order (children already code-ordered by Meta ordering),
    # then apply ?q= bottom-up: a row survives when IT matches or any DESCENDANT
    # does — unmatched branches vanish whole, matched ones keep their ancestors as
    # context. Junk input simply matches nothing and renders an empty tree (200).
    flat = []
    stack = [(n, 0) for n in roots]
    while stack:
        node, depth = stack.pop()
        flat.append(make_row(node, depth))
        for child in reversed(children_map.get(node.pk, [])):
            stack.append((child, depth + 1))

    q = request.GET.get("q", "").strip()
    if q:
        needle = q.lower()
        keep = {}
        for row in reversed(flat):
            node = row["node"]
            hit = (needle in node.code.lower() or needle in node.name.lower()
                   or any(keep.get(child_pk) for child_pk in
                          [c.pk for c in children_map.get(node.pk, [])]))
            keep[node.pk] = hit
            row["_keep"] = hit
        flat = [row for row in flat if row.pop("_keep")]

    # Orphan honesty LAST: stocked sites no node claims surface under one pseudo-row
    # (node=None tells the template it isn't a real tier).
    attached_ids = {n.warehouse_id for n in nodes if n.warehouse_id}
    unassigned = [loc for pk, loc in warehouses.items() if pk not in attached_ids]
    if unassigned:
        un_ids = [loc.pk for loc in unassigned]
        qty, val = totals_for(un_ids)
        flat.append({
            "node": None,
            "path_label": "Unassigned sites",
            "depth": 0,
            "own_warehouses": unassigned,
            "stock_total": qty,
            "stock_value": val,
            "in_transit_in": sum((transit_in.get(pk, ZERO) for pk in un_ids), ZERO),
            "in_transit_out": sum((transit_out.get(pk, ZERO) for pk in un_ids), ZERO),
        })

    stats = {
        "sites_attached": len(attached_ids),
        "sites_unassigned": len(unassigned),
        # The grouped query's own total — attached and unattached alike; zeros are
        # real zeros, never None dressed up.
        "network_stock_total": sum(stock_qty.values(), ZERO),
        "in_transit_total": in_transit_total,
    }
    return render(request, "inventory/multilocation/global_stock.html", {
        "rows": flat,
        "stats": stats,
        "q": q,
    })
