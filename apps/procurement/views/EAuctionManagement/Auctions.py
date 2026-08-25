"""Procurement 6.7 E-Auction Management — Eauction views.

The register (with the live/closed deep-link filters the sidebar uses), the setup CRUD, the
guarded lifecycle verbs, invite management, and the two live surfaces: the **Auction Monitoring
Console** (buyer view) with its HTMX-polled ``board`` fragment, and the buyer-side **Live
Bidding** entry floor.
"""
from functools import wraps

from django.db import transaction
from django.db.models import Count, Max, Min

from apps.core.crud import crud_list, paginate
from apps.procurement.forms import EaucInviteForm, EauctionForm
from apps.procurement.models import EaucBid, EaucInvite, Eauction
from apps.procurement.views._common import *  # noqa: F401,F403


def staff_required(view):
    """Gate every e-auction console verb to workspace staff (tenant member or superuser).

    ``login_required`` alone still admits vendor-portal logins to setup / lifecycle /
    invite / award routes; this is the staff-side complement. ``eauc_bid`` deliberately
    does NOT stack it — bidding is exactly the surface portal users must reach.
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.tenant is not None and (
            request.user.is_superuser or getattr(request.user, "tenant_id", None) == request.tenant.pk):
            return view(request, *args, **kwargs)
        messages.error(request, "This console is restricted to procurement staff.")
        return redirect("dashboard:home")

    return wrapped


def _get_auction(request, pk):
    return get_object_or_404(
        Eauction.objects.select_related("currency", "requisition", "created_by",
                                        "awarded_supplier"),
        pk=pk, tenant=request.tenant,
    )


# -- register + setup CRUD ------------------------------------------------------------------------


@login_required
@staff_required
def eauc_list(request):
    qs = (Eauction.objects.filter(tenant=request.tenant)
          .select_related("currency", "awarded_supplier")
          .annotate(n_invites=Count("invites", distinct=True),
                    n_bids=Count("bids", distinct=True)))
    # Aggregation ignores Meta.ordering; an unordered queryset makes pages unstable.
    qs = qs.order_by("-created_at", "-id")
    state = request.GET.get("state", "").strip()
    if state == "live":
        now = timezone.now()
        qs = qs.filter(status="scheduled", opens_at__lte=now, closes_at__gt=now)
    elif state == "closed":
        qs = qs.filter(status__in=("closed", "awarded"))
    return crud_list(
        request, qs, "procurement/eauctionmanagement/auctions/list.html",
        search_fields=["number", "title", "description"],
        filters=[("status", "status", False), ("auction_type", "auction_type", False)],
        extra_context={
            "type_choices": Eauction.AUCTION_TYPES,
            "status_choices": Eauction.STATUS_CHOICES,
            "state": state,
        },
    )


@login_required
@staff_required
def eauc_detail(request, pk):
    obj = _get_auction(request, pk)
    bids = list(obj.bids.select_related("supplier", "placed_by")[:100])
    invites = list(obj.invites.select_related("supplier"))
    invite_form = EaucInviteForm(tenant=request.tenant, auction=obj)
    return render(request, "procurement/eauctionmanagement/auctions/detail.html", {
        "obj": obj,
        "bids": bids,
        "invites": invites,
        "invite_form": invite_form,
        "ranked": obj.rankings(),
        "best": obj.best_bid(),
        "savings": obj.savings_vs_start(),
    })


@login_required
@staff_required
def eauc_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating auctions.")
        return redirect("dashboard:home")
    return _auction_form(request, instance=None)


@login_required
@staff_required
def eauc_edit(request, pk):
    obj = _get_auction(request, pk)
    if not obj.is_editable:
        messages.error(request, f"Auction {obj.number} is {obj.status} — only drafts can be "
                                f"edited.")
        return redirect("procurement:eauc_detail", pk=obj.pk)
    return _auction_form(request, instance=obj)


def _auction_form(request, instance):
    is_edit = instance is not None
    if request.method == "POST":
        form = EauctionForm(request.POST, request.FILES, instance=instance,
                            tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                auction = form.save(commit=False)
                auction.tenant = request.tenant
                if not is_edit:
                    auction.created_by = request.user
                auction.save()
            write_audit_log(request.user, auction, "update" if is_edit else "create")
            messages.success(request, f"Auction {auction.number or auction.title} saved.")
            return redirect("procurement:eauc_detail", pk=auction.pk)
    else:
        form = EauctionForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/eauctionmanagement/auctions/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
@staff_required
@require_POST
def eauc_delete(request, pk):
    """Deleting cascades invites AND the bid log — drafts only."""
    obj = _get_auction(request, pk)
    if not obj.is_editable:
        messages.error(request, "Only draft auctions can be deleted.")
        return redirect("procurement:eauc_detail", pk=obj.pk)
    return crud_delete(request, model=Eauction, pk=pk, success_url="procurement:eauc_list")


# -- lifecycle ------------------------------------------------------------------------------------


@login_required
@staff_required
@require_POST
def eauc_publish(request, pk):
    obj = _get_auction(request, pk)
    if obj.publish():
        write_audit_log(request.user, obj, "publish")
        opens = timezone.localtime(obj.opens_at).strftime("%b %d, %Y %H:%M")
        messages.success(request, f"{obj.number} scheduled — bidding opens {opens}.")
    else:
        messages.error(request, "Publishing needs a future close time and at least one "
                                "invited supplier.")
    return redirect("procurement:eauc_detail", pk=obj.pk)


@login_required
@staff_required
@require_POST
def eauc_cancel(request, pk):
    obj = _get_auction(request, pk)
    if obj.cancel():
        write_audit_log(request.user, obj, "cancel")
        messages.success(request, f"{obj.number} cancelled.")
    else:
        messages.error(request, "Only draft or scheduled auctions can be cancelled.")
    return redirect("procurement:eauc_detail", pk=obj.pk)


@login_required
@staff_required
@require_POST
def eauc_close(request, pk):
    obj = _get_auction(request, pk)
    if obj.close():
        write_audit_log(request.user, obj, "close")
        messages.success(request, f"{obj.number} closed — award it from the results page.")
    else:
        messages.error(request, "Only scheduled auctions can be closed.")
    return redirect("procurement:eauc_results", pk=obj.pk)


# -- invites ---------------------------------------------------------------------------------------


@login_required
@staff_required
@require_POST
def eauc_invite_add(request, pk):
    obj = _get_auction(request, pk)
    if not (obj.is_editable or obj.status == "scheduled"):
        messages.error(request, "Invitations closed when this auction left its window setup.")
        return redirect("procurement:eauc_detail", pk=obj.pk)
    form = EaucInviteForm(request.POST, tenant=request.tenant, auction=obj)
    if form.is_valid():
        invite = form.save()
        write_audit_log(request.user, obj, "update", {"invite": invite.supplier.name})
        messages.success(request, f"Invited {invite.supplier.name}.")
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect("procurement:eauc_detail", pk=obj.pk)


@login_required
@staff_required
@require_POST
def eauc_invite_remove(request, pk, i_pk):
    obj = _get_auction(request, pk)
    invite = get_object_or_404(EaucInvite, pk=i_pk, auction=obj, tenant=request.tenant)
    if obj.bids.filter(supplier=invite.supplier).exists():
        messages.error(request, "This supplier has already bid — their participation history "
                                "cannot be removed.")
        return redirect("procurement:eauc_detail", pk=obj.pk)
    invite.delete()
    write_audit_log(request.user, obj, "update", {"invite_removed": invite.supplier_id})
    messages.success(request, "Invite removed.")
    return redirect("procurement:eauc_detail", pk=obj.pk)


# -- live floor / rules / console / board -----------------------------------------------------------


def _board_ctx(obj):
    """Context for the polled ``board.html`` fragment, shared by every surface that embeds it.

    The first server-side paint must carry exactly what ``eauc_board`` renders — otherwise
    the page shows an empty frame until the first HTMX poll returns.
    """
    return {
        "obj": obj,
        "ranked": obj.rankings()[:8],
        "recent_bids": list(obj.bids.select_related("supplier")
                            .order_by("-placed_at", "-id")[:10]),
    }


@login_required
@staff_required
def eauc_floor(request):
    """The live trading floor entry: every auction currently accepting bids.

    Paginates the auction ids FIRST, then answers the whole page's leaderboards with ONE
    grouped query over ``EaucBid`` — ranking per auction in a loop is 2N+1 queries and
    falls over exactly when the floor is busiest.
    """
    now = timezone.now()
    live_ids = list(Eauction.objects
                    .filter(tenant=request.tenant, status="scheduled",
                            opens_at__lte=now, closes_at__gt=now)
                    .order_by("closes_at")
                    .values_list("pk", flat=True))
    page_obj = paginate(request, live_ids, per_page=12)
    page_ids = list(page_obj.object_list)
    ranked_by_auction = {}
    if page_ids:
        rows = (EaucBid.objects.filter(auction_id__in=page_ids)
                .values("auction_id", "supplier_id", "supplier__name")
                .annotate(best=Min("amount"), count=Count("id"),
                          last_at=Max("placed_at"))
                .order_by("auction_id", "best", "last_at"))
        for r in rows:
            ranked_by_auction.setdefault(r["auction_id"], []).append(
                {"supplier_id": r["supplier_id"], "supplier_name": r["supplier__name"],
                 "best": r["best"], "count": r["count"], "last_at": r["last_at"]})
    auctions = {a.pk: a for a in Eauction.objects.filter(pk__in=page_ids)}
    boards = [{"auction": auctions[pk], "ranked": ranked_by_auction.get(pk, [])[:5]}
              for pk in page_ids]
    return render(request, "procurement/eauctionmanagement/floor.html", {
        "object_list": boards,
        "page_obj": page_obj,
    })


@login_required
@staff_required
def eauc_rules(request):
    """**Bid Extension & Rule Enforcement** reference: the house rules the engine enforces,
    plus each recent auction's extension usage."""
    recent = (Eauction.objects.filter(tenant=request.tenant)
              .exclude(status="draft").order_by("-closes_at")[:10])
    return render(request, "procurement/eauctionmanagement/rules.html", {
        "recent": [(a, a.extensions_used, a.max_extensions) for a in recent],
    })


@login_required
@staff_required
def eauc_console(request, pk):
    """**Auction Monitoring Console**: live rankings, countdown, participation."""
    obj = _get_auction(request, pk)
    ctx = _board_ctx(obj)
    invites = list(obj.invites.select_related("supplier"))
    # The FULL leaderboard (not just the board fragment's top 8) drives the table.
    ranked = {r["supplier_id"]: r for r in obj.rankings()}
    ctx["participants"] = [{"invite": inv, "stats": ranked.get(inv.supplier_id)}
                           for inv in invites]
    return render(request, "procurement/eauctionmanagement/auctions/console.html", ctx)


@login_required
@staff_required
def eauc_board(request, pk):
    """HTMX fragment polled by the console/bid pages every few seconds."""
    obj = _get_auction(request, pk)
    return render(request, "procurement/eauctionmanagement/board.html", _board_ctx(obj))
