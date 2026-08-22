"""Inventory 5.6 Inventory Tracking & Control — StockStatus views.

Thin CRUD over the shared helpers, exactly the BinCapacity shape: the list's
search/filter/pagination all run through ``crud_list``; the one bespoke surface is the
detail page's spot view (live ledger total + the sibling claims sharing its ceiling),
which reads aggregates rather than storing anything.
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import StockStatusForm
from apps.inventory.models import StockStatus


def _scoped(tenant):
    """Tenant-scoped queryset with the joins every list/detail page renders."""
    return (StockStatus.objects.filter(tenant=tenant)
            .select_related("item", "location", "lot_serial"))


@login_required
def stockstatus_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/tracking/stockstatus/list.html",
        search_fields=["item__sku", "item__name", "reason"],
        filters=[("status", "status", False), ("location", "location_id", True)],
        extra_context={
            "status_choices": StockStatus.STATUS_CHOICES,
            "locations": _classified_locations(request.tenant),
        },
    )


@login_required
def stockstatus_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # The sibling claims drawing on the SAME ceiling at this spot — the spot's ledger
    # total minus every row shown here minus this one is what stays unclassifiable.
    # Same-spot means same (item, location, lot-or-none): an unlotted claim and a
    # lot-X claim draw from different pools, so they are not each other's competitors.
    siblings = StockStatus.objects.filter(tenant=obj.tenant_id, item=obj.item,
                                          location=obj.location).exclude(pk=obj.pk)
    if obj.lot_serial_id is None:
        siblings = siblings.filter(lot_serial__isnull=True)
    else:
        siblings = siblings.filter(lot_serial_id=obj.lot_serial_id)
    return render(request, "inventory/tracking/stockstatus/detail.html", {
        "obj": obj,
        "siblings": siblings.select_related("item", "location"),
        # The same ledger aggregate the model property reads, but as ROWS — proof of
        # what physically sits here, read from the append-only book.
        "recent_moves": obj.spot_moves().select_related("item")[:10],
    })


@login_required
def stockstatus_create(request):
    return crud_create(
        request, form_class=StockStatusForm,
        template="inventory/tracking/stockstatus/form.html",
        success_url="inventory:stockstatus_list",
    )


@login_required
def stockstatus_edit(request, pk):
    return crud_edit(
        request, model=StockStatus, pk=pk, form_class=StockStatusForm,
        template="inventory/tracking/stockstatus/form.html",
        success_url="inventory:stockstatus_list",
    )


@login_required
@require_POST
def stockstatus_delete(request, pk):
    return crud_delete(request, model=StockStatus, pk=pk,
                       success_url="inventory:stockstatus_list")


# -- module-private helpers --------------------------------------------------------------------

def _classified_locations(tenant):
    """Locations that actually appear on this tenant's claims — the list filter's
    dropdown. One DISTINCT query through the reverse FK, not a walk."""
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, stock_statuses__isnull=False)
            .distinct().order_by("code"))
