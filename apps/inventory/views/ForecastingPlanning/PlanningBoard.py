"""Inventory 5.13 Inventory Forecasting & Planning — the planning board (computed page).

**Reorder Point (ROP) Calculation** and **Safety Stock Calculation** bullets. The
mathematics live on the spine: ``scm.ReorderRule.calculate()`` derives
``computed_safety_stock``/``computed_reorder_point`` from ledger history and lead-time
variability, and ``apply_computed()`` is the ONLY writer allowed to promote those into
the live parameters 4.3's alerts act on. This board re-states neither number: it is the
review lens over every rule's LIVE-vs-COMPUTED gap — which parameters are stale, by how
much, and what on-hand looks like against them — with a tenant-admin-gated Apply that
delegates to the spine's own method inside its transaction.

Demand Forecasting itself stays SCM's (L36): the board links out to
``scm:demandforecast_list`` rather than re-predicting anything.
"""
from decimal import Decimal

from django.db.models import Sum

from apps.core.crud import paginate
from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import ReorderRule

ZERO = Decimal("0")


@login_required
def planning_board(request):
    from apps.scm.models import StockMove

    rules = (ReorderRule.objects.filter(tenant=request.tenant)
             .select_related("item", "location"))

    # One grouped ledger query for current on-hand per (item, location) — the same
    # aggregate the spine's own pages read, never a stored figure.
    on_hand = {
        (row["item_id"], row["location_id"]): row["qty"]
        for row in (StockMove.objects.filter(tenant=request.tenant)
                    .values("item_id", "location_id")
                    .annotate(qty=Sum("quantity")))
        if row["qty"]
    }

    q = request.GET.get("q", "").strip()
    if q:
        needle = q.lower()
        rules = [r for r in rules if needle in r.item.sku.lower()
                 or needle in r.item.name.lower()
                 or (r.location and needle in r.location.code.lower())]

    view = request.GET.get("view", "").strip()
    rows = []
    stats = {"stale": 0, "below_rop": 0, "ok": 0}
    for r in rules:
        qty = on_hand.get((r.item_id, r.location_id), ZERO)
        has_computed = (r.computed_safety_stock or ZERO) > ZERO or \
                       (r.computed_reorder_point or ZERO) > ZERO
        live_ss, live_rop = r.safety_stock or ZERO, r.reorder_point or ZERO
        comp_ss, comp_rop = r.computed_safety_stock or ZERO, r.computed_reorder_point or ZERO
        stale = has_computed and (live_ss != comp_ss or live_rop != comp_rop)
        below = r.is_below_point(qty)
        flag, css = ("stale", "badge-amber") if stale else (
            ("watch", "badge-info") if below else ("ok", "badge-green"))
        if stale:
            stats["stale"] += 1
        elif below:
            stats["below_rop"] += 1
        else:
            stats["ok"] += 1
        rows.append({
            "rule": r,
            "on_hand": qty,
            "flag": flag,
            "css": css,
            "stale": stale,
            "below": below,
        })

    if view == "stale":
        rows = [r for r in rows if r["stale"]]
    elif view == "below":
        rows = [r for r in rows if r["below"]]

    page_obj = paginate(request, rows, per_page=15)
    return render(request, "inventory/planning/planningboard.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "view": view,
        "stats": stats,
    })


@tenant_admin_required
@require_POST
def planning_apply_computed(request, pk):
    """Promote one rule's computed SS/ROP into live via the SPINE's own writer.

    The spine's apply path is privileged on purpose: these two numbers drive 4.3's
    purchasing alerts, so flipping them is a parameter change, not a review click.
    Refusals surface as flash messages; success reports before/after.
    """
    from apps.scm.models import ReorderRule as SpineRule

    rule = get_object_or_404(SpineRule, pk=pk, tenant=request.tenant)
    before = (rule.safety_stock or ZERO, rule.reorder_point or ZERO)
    try:
        rule.apply_computed()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("inventory:planning_board")
    after = (rule.safety_stock or ZERO, rule.reorder_point or ZERO)
    write_audit_log(request.user, rule, "apply_computed",
                    {"before": list(before), "after": list(after)})
    messages.success(
        request,
        f"{rule.item.sku}: safety stock {before[0]} → {after[0]}, "
        f"reorder point {before[1]} → {after[1]}.")
    return redirect("inventory:planning_board")
