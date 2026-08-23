"""Inventory 5.7 Stock Movement & Transfers — board, approval queue and their actions.

The movement DOCUMENT is 4.3's ``scm.StockTransfer`` (L36 — extend the spine, never
re-declare it): creation/editing/completion/cancellation stay on the spine's own pages,
and its complete action still posts the paired StockMove legs. This module owns the
GOVERNANCE around that document:

* **The board** is the register over every spine transfer, classified live into
  inter- vs intra-warehouse by a warehouse-root walk over the location tree (the two
  NavERP bullets are one ledger, two lenses — nothing stores a scope column).
* **Submitting** a draft parks it at ``pending_approval`` — the spine status added for
  this workflow — optionally choosing a route.
* **The queue** resolves, per pending movement, the matching ``TransferApprovalRule``
  (scope + unit band, most-specific-wins) and replays its ``TransferApproval`` decision
  chain. Clearing the FINAL tier performs the spine's own transition to ``approved``;
  a rejection returns the movement to ``draft``. This module invents no new truth about
  stock — it gates who may move it.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.models import (
    SCOPE_INTER,
    SCOPE_INTRA,
    TransferApproval,
    TransferApprovalRule,
    TransferRoute,
)
from apps.scm.models import Location, StockMove, StockTransfer, StockTransferLine


ZERO = Decimal("0")

#: When no active rule matches a movement, ONE signature is required — a fallback
#: policy, not a bypass: nothing reaches ``approved`` with zero recorded decisions.
DEFAULT_TIER_COUNT = 1

#: Badge colour per spine status, decided in ONE place (L33 — colour-named only).
TRF_STATUS_CSS = {
    "draft": "badge-slate",
    "pending_approval": "badge-amber",
    "approved": "badge-info",
    "in_transit": "badge-muted",
    "completed": "badge-green",
    "cancelled": "badge-red",
}

SCOPE_CSS = {SCOPE_INTER: "badge-info", SCOPE_INTRA: "badge-slate"}
SCOPE_LABELS = {SCOPE_INTER: "Inter-Warehouse", SCOPE_INTRA: "Intra-Warehouse"}

#: The board's URL contract is ``?scope=inter|intra`` — what navigation's LIVE_LINKS
#: deep-link to — so GET values are aliased onto the real SCOPE_* constants here,
#: BEFORE the classify-compare in :func:`transfer_board`.
_SCOPE_FILTERS = {"inter": SCOPE_INTER, "intra": SCOPE_INTRA}


# -- shared helpers ---------------------------------------------------------------------------

def _scoped(tenant):
    return (StockTransfer.objects.filter(tenant=tenant)
            .select_related("from_location", "to_location", "route"))


def _warehouse_roots(tenant):
    """Location pk → topmost ancestor pk, walked once over the tenant's whole tree.

    Two spots share a warehouse root iff they sit under the same topmost location, so
    root equality — not type checks — is what separates an intra- from an
    inter-warehouse move. Guards a malformed self-parent cycle like Location.path()."""
    nodes = dict(Location.objects.filter(tenant=tenant)
                 .values_list("id", "parent_id"))
    roots = {}
    for start in nodes:
        node, seen = start, set()
        while node in nodes and node not in seen:
            seen.add(node)
            parent = nodes[node]
            if parent is None:
                break
            node = parent
        roots[start] = node
    return roots


def classify(from_location_id, to_location_id, roots):
    """SCOPE_INTER / SCOPE_INTRA for one movement against a :func:`_warehouse_roots` map."""
    src, dst = roots.get(from_location_id), roots.get(to_location_id)
    if src is None or dst is None:
        return SCOPE_INTRA  # unclassifiable (deleted endpoint) — never invents inter
    return SCOPE_INTRA if src == dst else SCOPE_INTER


def _units_map(tenant, transfer_pks):
    """Total units per transfer, ONE grouped query for the whole page.

    ``StockTransferLine`` carries no tenant column of its own (4.3 scopes it through
    its parent), so the filter goes via ``transfer__tenant``."""
    rows = (StockTransferLine.objects.filter(transfer__tenant=tenant,
                                             transfer_id__in=transfer_pks)
            .values("transfer_id").annotate(s=Sum("quantity")))
    return {row["transfer_id"]: row["s"] or ZERO for row in rows}


def _chain_map(tenant, transfer_pks):
    """Decision rows per transfer, oldest-first — ONE query for the whole page."""
    chains = {}
    rows = (TransferApproval.objects.filter(tenant=tenant, transfer_id__in=transfer_pks)
            .select_related("decided_by", "rule").order_by("decided_at", "id"))
    for row in rows:
        chains.setdefault(row.transfer_id, []).append(row)
    return chains


def _progress(trf, units, scope, active_rules, decisions):
    """Rule + cleared/required/next-tier for one movement, pure Python."""
    rule = TransferApprovalRule.resolve_from(active_rules, units or ZERO, scope)
    required = rule.tier_count if rule else DEFAULT_TIER_COUNT
    cleared = min(TransferApproval.cleared_tier_count(decisions), required)
    return {
        "rule": rule, "required": required, "cleared": cleared,
        "next_tier": cleared + 1, "done": cleared >= required, "decisions": decisions,
    }


# -- the board ---------------------------------------------------------------------------------

@login_required
def transfer_board(request):
    """The register over every spine transfer — the Inter/Intra-Warehouse bullets.

    Hand-rolled around :func:`paginate` rather than crud_list because each row carries
    COMPUTED context (scope classification, unit total, approval progress); enriching
    only the rendered page keeps the per-request cost flat as the register grows.
    """
    tenant = request.tenant
    qs = _scoped(tenant)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(notes__icontains=q))
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)

    scope_param = (request.GET.get("scope") or "").strip()
    roots = _warehouse_roots(tenant)
    scope_filter = _SCOPE_FILTERS.get(scope_param)
    if scope_filter:
        # Classify candidates by pk first, THEN filter — the walk touches only the
        # (from, to) id pairs, never full rows, and runs once for filter + rendering.
        pairs = list(qs.values_list("id", "from_location_id", "to_location_id"))
        keep = [pk for pk, src, dst in pairs
                if classify(src, dst, roots) == scope_filter]
        qs = qs.filter(id__in=keep)

    page_obj = paginate(request, qs.order_by("-transfer_date", "-id"), per_page=15)
    page_items = list(page_obj.object_list)
    pks = [t.pk for t in page_items]
    units_by_trf = _units_map(tenant, pks) if pks else {}
    chains = _chain_map(tenant, pks) if pks else {}
    active_rules = list(TransferApprovalRule.objects.filter(tenant=tenant, is_active=True))

    rows = []
    for trf in page_items:
        scope = classify(trf.from_location_id, trf.to_location_id, roots)
        decisions = chains.get(trf.pk, [])
        rows.append({
            "trf": trf,
            "scope": scope,
            "scope_label": SCOPE_LABELS[scope],
            "scope_css": SCOPE_CSS[scope],
            "units": units_by_trf.get(trf.pk, ZERO),
            "status_css": TRF_STATUS_CSS.get(trf.status, "badge-muted"),
            "progress": (_progress(trf, units_by_trf.get(trf.pk), scope, active_rules, decisions)
                         if trf.status == "pending_approval" else None),
            "decision_count": len(decisions),
        })

    pending_count = StockTransfer.objects.filter(tenant=tenant, status="pending_approval").count()
    return render(request, "inventory/transfers/board.html", {
        "object_list": rows,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "scope": scope_param,
        "status_choices": StockTransfer.STATUS_CHOICES,
        "pending_count": pending_count,
        "routes": _route_choices(tenant),
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


def _route_choices(tenant):
    """Active routes for the submit-time picker, lane-matched first."""
    if tenant is None:
        return TransferRoute.objects.none()
    return (TransferRoute.objects.filter(tenant=tenant, is_active=True)
            .select_related("origin_location", "destination_location")
            .order_by("name"))


# -- submit ------------------------------------------------------------------------------------

@login_required
@require_POST
def transfer_submit(request, pk):
    """Park a draft at ``pending_approval``, optionally choosing its route.

    Login-gated, not admin-gated: requesting a movement is everyone's job — AUTHORIZING
    one is the queue's, and execution stays tenant-admin gated on the spine."""
    trf = get_object_or_404(_scoped(request.tenant), pk=pk)
    if trf.status != "draft":
        messages.info(request, f"{trf.number} is already {trf.get_status_display().lower()}.")
        return redirect("inventory:transfer_board")
    if not trf.lines.exists():
        messages.error(request, f"Add at least one line to {trf.number} before submitting it.")
        return redirect("inventory:transfer_board")

    route_id = as_db_int(request.POST.get("route"))
    if route_id is not None:
        route = _route_choices(request.tenant).filter(pk=route_id).first()
        if route is None or not route.covers(trf.from_location_id, trf.to_location_id):
            messages.error(request, "That route cannot carry this movement.")
            return redirect("inventory:transfer_board")
        trf.route = route

    roots = _warehouse_roots(request.tenant)
    scope = classify(trf.from_location_id, trf.to_location_id, roots)
    units = _units_map(request.tenant, [trf.pk]).get(trf.pk, ZERO)
    rule = TransferApprovalRule.resolve(request.tenant, units, scope)

    trf.status = "pending_approval"
    trf.save(update_fields=["status", "route", "updated_at"])
    write_audit_log(request.user, trf, "update", {
        "action": "submit_for_approval", "scope": scope,
        "units": str(units), "rule": rule.name if rule else None,
        "required_tiers": rule.tier_count if rule else DEFAULT_TIER_COUNT,
    })
    messages.success(
        request,
        f"{trf.number} submitted — "
        f"{rule.tier_count if rule else DEFAULT_TIER_COUNT} approval tier(s) required.")
    return redirect("inventory:transfer_board")


# -- the queue ---------------------------------------------------------------------------------

@login_required
def transfer_queue(request):
    """Movements parked at ``pending_approval`` with their live chain progress."""
    tenant = request.tenant
    pending = list(_scoped(tenant).filter(status="pending_approval")
                   .order_by("-transfer_date", "-id")[:100])
    roots = _warehouse_roots(tenant)
    pks = [t.pk for t in pending]
    units_by_trf = _units_map(tenant, pks) if pks else {}
    chains = _chain_map(tenant, pks) if pks else {}
    active_rules = list(TransferApprovalRule.objects.filter(tenant=tenant, is_active=True))

    queue = []
    for trf in pending:
        scope = classify(trf.from_location_id, trf.to_location_id, roots)
        queue.append({
            "trf": trf,
            "scope_label": SCOPE_LABELS[scope],
            "scope_css": SCOPE_CSS[scope],
            "units": units_by_trf.get(trf.pk, ZERO),
            "progress": _progress(trf, units_by_trf.get(trf.pk), scope,
                                  active_rules, chains.get(trf.pk, [])),
        })

    recent = (TransferApproval.objects.filter(tenant=tenant)
              .select_related("transfer", "decided_by", "rule")
              .order_by("-decided_at", "-id")[:12])
    return render(request, "inventory/transfers/queue.html", {
        "queue": queue,
        "recent": recent,
        "default_tiers": DEFAULT_TIER_COUNT,
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


def _decide(request, pk, tier, approving):
    """Record one tier's decision; the two URL verbs are thin wrappers around this.

    Tenant-admin gated like scm's complete: clearing tiers authorizes a physical stock
    movement. The whole read-guard-write runs under ``select_for_update`` on the TRANSFER
    row: two admins hitting the same next tier serialize, and the loser re-reads the
    chain the winner just extended. There is deliberately no ``(transfer, tier)``
    uniqueness to fall back on — that constraint bricks every rejected-then-resubmitted
    chain — sequential integrity here is the lock's job.
    """
    with transaction.atomic():
        trf = get_object_or_404(
            StockTransfer.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if trf.status != "pending_approval":
            messages.info(request, "This movement is not awaiting approval.")
            return redirect("inventory:transfer_queue")

        decisions = list(TransferApproval.objects
                         .filter(tenant=request.tenant, transfer=trf)
                         .order_by("decided_at", "id"))
        cleared = TransferApproval.cleared_tier_count(decisions)
        if tier != cleared + 1:
            messages.error(request, f"Tier {cleared + 1} must be decided first.")
            return redirect("inventory:transfer_queue")

        roots = _warehouse_roots(request.tenant)
        scope = classify(trf.from_location_id, trf.to_location_id, roots)
        units = _units_map(request.tenant, [trf.pk]).get(trf.pk, ZERO)
        rule = TransferApprovalRule.resolve(request.tenant, units, scope)
        required = rule.tier_count if rule else DEFAULT_TIER_COUNT

        decision_row = TransferApproval.objects.create(
            tenant=request.tenant, transfer=trf, rule=rule, tier=tier,
            decision="approved" if approving else "rejected",
            decided_by=request.user, decided_at=timezone.now(),
            note=(request.POST.get("note") or "").strip()[:2000],
        )
        write_audit_log(request.user, decision_row, "create",
                        {"action": "tier_approve" if approving else "tier_reject",
                         "tier": tier})
        if approving:
            if tier >= required:
                # The spine's own governed state — scm.complete accepts exactly this.
                trf.status = "approved"
                trf.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, trf, "update", {"action": "approve"})
                messages.success(
                    request,
                    f"{trf.number} approved — execute it from its SCM page; "
                    f"all {required} tier(s) cleared.")
            else:
                messages.success(
                    request, f"Tier {tier} of {required} recorded for {trf.number}.")
        else:
            trf.status = "draft"  # back to the requester; amend and resubmit
            trf.save(update_fields=["status", "updated_at"])
            write_audit_log(request.user, trf, "update", {"action": "reject"})
            messages.success(
                request, f"{trf.number} returned to draft — amend and resubmit it.")
    return redirect("inventory:transfer_queue")


@login_required
def transfer_detail_panel(request, pk):
    """A focused governance panel for ONE movement: lines with source coverage, the
    decision chain, its route, and the ledger legs the spine has posted so far."""
    trf = get_object_or_404(_scoped(request.tenant), pk=pk)
    lines = list(trf.lines.select_related("item", "lot_serial"))
    # Same per-(item, lot) coverage figure scm's own detail shows — resolved in ONE
    # grouped query so an approver sees what the source can actually cover.
    qty_map = {
        (row["item_id"], row["lot_serial_id"]): (row["q"] or ZERO)
        for row in (StockMove.objects
                    .filter(tenant=request.tenant, location=trf.from_location,
                            item_id__in=[ln.item_id for ln in lines] or [0])
                    .values("item_id", "lot_serial_id").annotate(q=Sum("quantity")))
    }
    line_rows = []
    for ln in lines:
        if ln.lot_serial_id:
            available = qty_map.get((ln.item_id, ln.lot_serial_id), ZERO)
        else:  # untracked line — the item's whole balance at this location, across lots
            available = sum((v for (i, _), v in qty_map.items() if i == ln.item_id), ZERO)
        line_rows.append({"line": ln, "available": available})

    roots = _warehouse_roots(request.tenant)
    scope = classify(trf.from_location_id, trf.to_location_id, roots)
    decisions = list(TransferApproval.objects
                     .filter(tenant=request.tenant, transfer=trf)
                     .select_related("decided_by", "rule").order_by("decided_at", "id"))
    units = sum((ln.quantity for ln in lines), ZERO)
    return render(request, "inventory/transfers/panel.html", {
        "obj": trf,
        "line_rows": line_rows,
        "units": units,
        "scope": scope,
        "scope_label": SCOPE_LABELS[scope],
        "scope_css": SCOPE_CSS[scope],
        "status_css": TRF_STATUS_CSS.get(trf.status, "badge-muted"),
        "decisions": decisions,
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=trf.number)
                  .select_related("item", "location").order_by("-moved_at", "-id")[:20]
                  if trf.number else []),
        "progress": _progress(trf, units, scope,
                              list(TransferApprovalRule.objects.filter(
                                  tenant=request.tenant, is_active=True)), decisions),
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@tenant_admin_required
@require_POST
def transfer_tier_approve(request, pk, tier):
    return _decide(request, pk, tier, approving=True)


@tenant_admin_required
@require_POST
def transfer_tier_reject(request, pk, tier):
    return _decide(request, pk, tier, approving=False)
