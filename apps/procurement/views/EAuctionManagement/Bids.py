"""Procurement 6.7 E-Auction Management — bidding + award/results views.

The **Live Bidding Interface**: one screen per auction where a supplier (or staff recording on
their behalf) submits lowering bids. WHO may bid is resolved server-side:

* a vendor-portal login (6.4's ``VendorPortalAccess``) is pinned to its bound supplier Party;
* any staff member of the workspace may record a bid FOR an invited supplier.

Every write runs the model rule engine inside a row-locked transaction and then calls
``extend_if_needed()`` so **Bid Extension & Rule Enforcement** fires atomically with the bid.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.procurement.forms import EaucBidForm
from apps.procurement.models import EaucBid, Eauction
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views.EAuctionManagement.Auctions import _board_ctx, staff_required


def _bound_supplier(request, auction):
    """(supplier, is_portal_user) for the signed-in user, or (None, False).

    ``(None, False)`` means a workspace STAFF member who may pick which invitee they record
    for; any other login (portal user without a binding, superuser without a tenant) is pinned
    to nothing and can never choose one.

    ANY binding row pins the login to the portal side — an active-but-unlinked row must never
    fall through to the staff branch, or that portal login could record bids as any invitee.
    """
    from apps.procurement.models import VendorPortalAccess

    access = VendorPortalAccess.for_user(request.tenant, request.user)
    if access is not None:
        return access.supplier, True
    if request.tenant is not None and getattr(request.user, "tenant_id", None) == request.tenant.pk:
        return None, False
    return None, True


def _allowed_suppliers(auction):
    return [inv.supplier for inv in auction.invites.select_related("supplier")]


@login_required
def eauc_bid(request, pk):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before bidding.")
        return redirect("dashboard:home")
    obj = get_object_or_404(
        Eauction.objects.select_related("currency"), pk=pk, tenant=request.tenant,
    )
    supplier, pinned = _bound_supplier(request, obj)
    chosen = None
    if not pinned:
        pk_str = request.POST.get("supplier") or request.GET.get("supplier") or ""
        if pk_str.isdecimal():
            candidate = next((s for s in _allowed_suppliers(obj)
                              if s.pk == int(pk_str)), None)
            chosen = candidate
    else:
        chosen = supplier

    floor = EaucBid.next_floor(obj, chosen) if chosen is not None else None
    form = EaucBidForm()
    if request.method == "POST":
        if chosen is None:
            messages.error(request, "Pick which invited supplier you are recording for.")
            return redirect("procurement:eauc_bid", pk=obj.pk)
        form = EaucBidForm(request.POST)
        if form.is_valid():
            if floor is None:
                # A silent re-render would look like the POST did nothing — say why not.
                messages.error(request,
                               "No legal bid is available for this supplier right now — "
                               "the window may have closed or their ladder is exhausted.")
                return redirect("procurement:eauc_bid", pk=obj.pk)
            bid = EaucBid(tenant=request.tenant, auction=obj, supplier=chosen,
                          amount=form.cleaned_data["amount"],
                          note=form.cleaned_data.get("note", ""),
                          placed_by=request.user)
            try:
                with transaction.atomic():
                    locked = type(obj).objects.select_for_update().get(pk=obj.pk)
                    bid.auction = locked
                    bid.full_clean(exclude=["placed_by", "number"])
                    bid.save()
                    outcome = locked.extend_if_needed()
                write_audit_log(request.user, bid, "create",
                                {"auction": locked.number, "amount": str(bid.amount)})
            except ValidationError as e:
                messages.error(request, "; ".join(
                    m for msgs in e.message_dict.values() for m in msgs))
                return redirect("procurement:eauc_bid", pk=obj.pk)
            messages.success(request, f"Bid {bid.number} recorded at {bid.amount}.")
            if outcome == "extended":
                messages.info(request,
                              f"Anti-snipe extension: the close moved to "
                              f"{timezone.localtime(locked.closes_at):%H:%M:%S} "
                              f"({locked.extensions_used}/{locked.max_extensions} used).")
            elif outcome == "capped":
                messages.warning(request, "Extension cap reached — this close stands.")
            return redirect("procurement:eauc_bid", pk=obj.pk)
    # The embedded board fragment needs the same context on first paint as its poll does.
    ctx = _board_ctx(obj)
    ctx.update({
        "form": form,
        "floor": floor,
        "chosen": chosen,
        "pinned": pinned,
        "suppliers": [] if (pinned or chosen is not None) else _allowed_suppliers(obj),
        "my_bids": (list(obj.bids.filter(supplier=chosen)[:10]) if chosen is not None else []),
    })
    return render(request, "procurement/eauctionmanagement/bids/bid.html", ctx)


@login_required
@staff_required
def eauc_results(request, pk):
    """**Post-Auction Results**: final rankings, savings vs start/reserve, award decision."""
    obj = get_object_or_404(
        Eauction.objects.select_related("currency", "awarded_supplier"),
        pk=pk, tenant=request.tenant,
    )
    best = obj.best_bid()
    below_reserve = bool(best and obj.reserve_price is not None
                         and best.amount < obj.reserve_price)
    return render(request, "procurement/eauctionmanagement/results.html", {
        "obj": obj,
        "ranked": obj.rankings(),
        "best": best,
        "savings": obj.savings_vs_start(),
        "below_reserve": below_reserve,
        "total_bids": obj.bids.count(),
    })


@login_required
@staff_required
@require_POST
def eauc_award(request, pk):
    """Record the award decision — only the current leading supplier can win.

    The decision runs under a row lock on the auction: two concurrent award POSTs must
    serialize, and the model's once-only guard catches whichever loses the race.
    """
    obj = get_object_or_404(Eauction, pk=pk, tenant=request.tenant)
    note = request.POST.get("award_note", "").strip()
    pk_str = request.POST.get("supplier", "")
    supplier = None
    if pk_str.isdecimal():
        supplier = next((inv.supplier for inv in obj.invites.select_related("supplier")
                         if inv.supplier_id == int(pk_str)), None)
    with transaction.atomic():
        locked = Eauction.objects.select_for_update().get(pk=obj.pk)
        awarded = supplier is not None and locked.award(supplier, note=note)
        obj.refresh_from_db(fields=["status", "awarded_supplier", "awarded_amount"])
    if not awarded:
        best = obj.best_bid()
        expected = best.supplier.name if best else "—"
        messages.error(request,
                       f"Award refused — only the current leading supplier ({expected}) can "
                       f"be awarded, and only once, from a closed auction.")
        return redirect("procurement:eauc_results", pk=obj.pk)
    write_audit_log(request.user, obj, "award",
                    {"supplier": supplier.name, "amount": str(obj.awarded_amount)})
    messages.success(request, f"{obj.number} awarded to {supplier.name}.")
    return redirect("procurement:eauc_results", pk=obj.pk)
