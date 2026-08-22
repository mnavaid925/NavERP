"""Inventory 5.5 Warehousing & Bin Management — BinCapacity views.

Thin CRUD over the shared helpers. The list's one non-declarative piece is the
over-capacity filter: utilisation compares two COLUMNS (live ledger total vs declared
limit), which ``crud_list``'s equality spec cannot express, so it is applied to the
queryset before the helper runs — as a correlated-subquery annotation, not a Python
walk, so pagination still happens in the database.
"""
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import BinCapacityForm
from apps.inventory.models import BinCapacity


def _scoped(tenant):
    """Tenant-scoped BinCapacity queryset with its location joined."""
    return BinCapacity.objects.filter(tenant=tenant).select_related("location")


@login_required
def bincapacity_list(request):
    qs = _scoped(request.tenant)
    over = request.GET.get("utilisation", "").strip()
    if over == "over":
        # Live on-hand per profiled location as ONE correlated subquery, then the
        # column-vs-column comparison. Matching on location_id alone is tenant-safe:
        # location pks are globally unique and the outer rows are already tenant-scoped.
        from apps.scm.models import StockMove
        on_hand = (StockMove.objects.filter(location_id=OuterRef("location_id"))
                   .values("location_id")
                   .annotate(q=Sum("quantity")).values("q"))
        qs = (qs.filter(max_quantity__isnull=False)
              .annotate(on_hand_qty=Subquery(on_hand,
                                             output_field=DecimalField(max_digits=16,
                                                                       decimal_places=4)))
              .filter(on_hand_qty__gte=F("max_quantity")))
    return crud_list(
        request, qs, "inventory/warehouse/bincapacity/list.html",
        search_fields=["location__code", "location__name", "notes"],
        filters=[("location", "location_id", True)],
        extra_context={
            "locations": _capacity_locations(request.tenant),
            "utilisation": over,
            "over_count": _over_capacity_count(request.tenant),
        },
    )


@login_required
def bincapacity_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/warehouse/bincapacity/detail.html", {
        "obj": obj,
        # The same ledger aggregate the model property reads, but as ROWS for the
        # recent-movements table — scoped to this bin and capped.
        "recent_moves": obj.location.stock_moves.select_related("item")[:10],
    })


@login_required
def bincapacity_create(request):
    return crud_create(
        request, form_class=BinCapacityForm,
        template="inventory/warehouse/bincapacity/form.html",
        success_url="inventory:bincapacity_list",
    )


@login_required
def bincapacity_edit(request, pk):
    return crud_edit(
        request, model=BinCapacity, pk=pk, form_class=BinCapacityForm,
        template="inventory/warehouse/bincapacity/form.html",
        success_url="inventory:bincapacity_list",
    )


@login_required
@require_POST
def bincapacity_delete(request, pk):
    return crud_delete(request, model=BinCapacity, pk=pk,
                       success_url="inventory:bincapacity_list")


# -- module-private helpers --------------------------------------------------------------------

def _capacity_locations(tenant):
    """Locations offerable in the profile form + list filter — active, code order.

    A small duplicate of the form helper's rule kept OUT of the form: views need it for
    the filter dropdown, forms need their own narrowed version; both answer the same
    question ("which locations can carry an envelope") so they must not drift silently.
    """
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, is_active=True)
            .order_by("location_type", "code"))


def _over_capacity_count(tenant):
    """How many profiles are at or past their quantity limit — the list header chip.

    One pass over a bounded table (a tenant has dozens of bins, not thousands); the
    per-row aggregate is the ledger read, which is what actually grows.
    """
    return sum(
        1 for profile in BinCapacity.objects.filter(
            tenant=tenant, max_quantity__isnull=False).select_related("location")
        if profile.quantity_utilisation is not None
        and profile.quantity_utilisation >= 100)
