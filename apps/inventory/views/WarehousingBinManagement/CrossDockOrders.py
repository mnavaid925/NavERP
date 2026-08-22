"""Inventory 5.5 Warehousing & Bin Management — CrossDockOrder views.

CRUD plus the three lifecycle verbs (receive / ship / cancel). The model's action
methods own the locking and the ledger; these views own the HTTP contract: POST-only
actions, refusals surfaced as flash messages (a ValidationError from a guarded action
is a user-facing "cannot", never a 500), and an audit trail written by the model
inside its transaction.
"""
from django.core.exceptions import ValidationError

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import CrossDockOrderForm
from apps.inventory.models import CrossDockOrder


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list/detail page renders."""
    return (CrossDockOrder.objects.filter(tenant=tenant)
            .select_related("item", "lot_serial", "dock_location"))


@login_required
def crossdockorder_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/warehouse/crossdockorder/list.html",
        search_fields=["number", "item__sku", "item__name",
                       "inbound_reference", "outbound_reference"],
        filters=[("status", "status", False), ("dock", "dock_location_id", True)],
        extra_context={
            "status_choices": CrossDockOrder.STATUS_CHOICES,
            "docks": _dock_choices(request.tenant),
        },
    )


@login_required
def crossdockorder_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/warehouse/crossdockorder/detail.html", {
        "obj": obj,
        # The order's two ledger legs as rows — proof of what actually moved, read from
        # the append-only book rather than restated here.
        "moves": obj.ledger_moves()[:20],
    })


@login_required
def crossdockorder_create(request):
    return crud_create(
        request, form_class=CrossDockOrderForm,
        template="inventory/warehouse/crossdockorder/form.html",
        success_url="inventory:crossdockorder_list",
    )


@login_required
def crossdockorder_edit(request, pk):
    return crud_edit(
        request, model=CrossDockOrder, pk=pk, form_class=CrossDockOrderForm,
        template="inventory/warehouse/crossdockorder/form.html",
        success_url="inventory:crossdockorder_list",
    )


@login_required
@require_POST
def crossdockorder_delete(request, pk):
    """Delete a draft only. A received/shipped order's number is written into immutable
    StockMove rows — deleting the document would orphan its legs' provenance."""
    obj = get_object_or_404(CrossDockOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(
            request,
            f"{obj.number} has posted ledger moves and cannot be deleted — cancel it instead.")
        return redirect("inventory:crossdockorder_detail", pk=obj.pk)
    return crud_delete(request, model=CrossDockOrder, pk=pk,
                       success_url="inventory:crossdockorder_list")


@login_required
@require_POST
def crossdockorder_receive(request, pk):
    return _run_action(request, pk, "receive")


@login_required
@require_POST
def crossdockorder_ship(request, pk):
    return _run_action(request, pk, "ship")


@login_required
@require_POST
def crossdockorder_cancel(request, pk):
    return _run_action(request, pk, "cancel")


# -- module-private helpers --------------------------------------------------------------------

_ACTION_MESSAGES = {
    "receive": "received at dock.",
    "ship": "shipped.",
    "cancel": "cancelled.",
}


def _run_action(request, pk, action):
    """Run one lifecycle verb and turn its refusal into a flash message.

    The success/error split is deliberate: a refusal is EXPECTED traffic (double-click,
    stale tab, someone else got there first), so it lands as a message on the detail
    page rather than an exception page.
    """
    obj = get_object_or_404(CrossDockOrder, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}")
    return redirect("inventory:crossdockorder_detail", pk=obj.pk)


def _dock_choices(tenant):
    """Locations that actually appear on this tenant's cross-dock orders — the list
    filter's dropdown. One DISTINCT query through the reverse FK, not a walk."""
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, crossdock_orders__isnull=False)
            .distinct().order_by("code"))
