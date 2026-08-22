"""Inventory 5.6 Inventory Tracking & Control — InventoryReservation views.

CRUD plus the three lifecycle verbs (release / consume / cancel). The model's action
methods own the locking and the guard; these views own the HTTP contract: POST-only
actions, refusals surfaced as flash messages (a ValidationError from a guarded action
is a user-facing "cannot", never a 500), and an audit trail written by the model
inside its transaction.

Create is hand-rolled rather than ``crud_create`` for ONE reason: ``reserved_by`` is
the acting user, which only the view knows.
"""
from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import InventoryReservationForm
from apps.inventory.models import InventoryReservation


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list/detail page renders."""
    return (InventoryReservation.objects.filter(tenant=tenant)
            .select_related("item", "location", "lot_serial", "reserved_by"))


@login_required
def reservation_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/tracking/reservation/list.html",
        search_fields=["number", "reference", "item__sku", "item__name", "notes"],
        filters=[("status", "status", False), ("location", "location_id", True)],
        extra_context={
            "status_choices": InventoryReservation.STATUS_CHOICES,
            "locations": _reserved_locations(request.tenant),
            # The list header chip: claims still holding stock back from availability.
            "active_count": InventoryReservation.objects.filter(
                tenant=request.tenant,
                status__in=InventoryReservation.ACTIVE_STATUSES).count(),
        },
    )


@login_required
def reservation_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/tracking/reservation/detail.html", {
        "obj": obj,
        # What this spot can still promise: ledger on-hand minus every active claim at it
        # (this one included while it is active) minus non-sellable classifications —
        # read live, never stored.
        "spot_on_hand": _spot_on_hand(obj),
        "other_claims": _other_active_qty(obj),
    })


@login_required
def reservation_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = InventoryReservationForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.reserved_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("inventory:reservation_list")
    else:
        form = InventoryReservationForm(tenant=request.tenant)
    return render(request, "inventory/tracking/reservation/form.html",
                  {"form": form, "is_edit": False})


@login_required
def reservation_edit(request, pk):
    return crud_edit(
        request, model=InventoryReservation, pk=pk,
        form_class=InventoryReservationForm,
        template="inventory/tracking/reservation/form.html",
        success_url="inventory:reservation_list",
    )


@login_required
@require_POST
def reservation_delete(request, pk):
    """Delete a reserved claim outright. Once consumed/cancelled the row is history and
    its number may be referenced elsewhere — those go through cancel instead."""
    obj = get_object_or_404(InventoryReservation, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} and cannot be deleted.")
        return redirect("inventory:reservation_detail", pk=obj.pk)
    return crud_delete(request, model=InventoryReservation, pk=pk,
                       success_url="inventory:reservation_list")


@login_required
@require_POST
def reservation_release(request, pk):
    return _run_action(request, pk, "release")


@login_required
@require_POST
def reservation_consume(request, pk):
    return _run_action(request, pk, "consume")


@login_required
@require_POST
def reservation_cancel(request, pk):
    return _run_action(request, pk, "cancel")


# -- module-private helpers --------------------------------------------------------------------

_ACTION_MESSAGES = {
    "release": "released to the floor.",
    "consume": "consumed.",
    "cancel": "cancelled.",
}


def _run_action(request, pk, action):
    """Run one lifecycle verb and turn its refusal into a flash message.

    A refusal is EXPECTED traffic (double-click, stale tab, someone else got there
    first), so it lands as a message on the detail page rather than an exception page.
    """
    obj = get_object_or_404(InventoryReservation, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:reservation_detail", pk=obj.pk)


def _spot_on_hand(obj):
    """Live ledger total for this claim's (item, location, lot) scope."""
    moves = obj.item.stock_moves.filter(location=obj.location)
    if obj.lot_serial_id is not None:
        moves = moves.filter(lot_serial_id=obj.lot_serial_id)
    return moves.aggregate(s=Sum("quantity"))["s"] or 0


def _other_active_qty(obj):
    """Σ OTHER active claims at the same spot — spine allocations AND sibling
    reservations — so the detail page can show what remains unclaimed beside it.

    Narrowed to the claim's lot only when it names one: an unlotted claim competes for
    the whole location pool, exactly as the reservation form's ATP check treats it.
    """
    from apps.scm.models import SalesOrderAllocation

    own = (InventoryReservation.objects.filter(
        tenant=obj.tenant_id, item=obj.item, location=obj.location,
        status__in=InventoryReservation.ACTIVE_STATUSES).exclude(pk=obj.pk))
    if obj.lot_serial_id is not None:
        own = own.filter(lot_serial_id=obj.lot_serial_id)
    held_reservations = own.aggregate(s=Sum("quantity"))["s"] or 0
    # Spine allocations are lot-blind (no lot column) — they compete for the whole pool.
    held_allocations = (SalesOrderAllocation.objects.filter(
        status__in=SalesOrderAllocation.ACTIVE_STATUSES,
        sales_order_line__item_id=obj.item_id,
        sales_order_line__sales_order__tenant_id=obj.tenant_id,
        location=obj.location)
        .aggregate(s=Sum("quantity"))["s"] or 0)
    return held_reservations + held_allocations


def _reserved_locations(tenant):
    """Locations that actually appear on this tenant's reservations — the list filter's
    dropdown. One DISTINCT query through the reverse FK, not a walk."""
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, reservations__isnull=False)
            .distinct().order_by("code"))
