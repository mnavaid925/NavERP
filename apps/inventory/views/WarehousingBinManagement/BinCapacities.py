"""Inventory 5.5 Warehousing & Bin Management — BinCapacity views.

Thin CRUD over the shared helpers. The list's one non-declarative piece is the
over-capacity filter: utilisation compares two COLUMNS (live ledger total vs declared
limit), which ``crud_list``'s equality spec cannot express, so every row's on-hand is
annotated once as a correlated subquery on the scoped queryset and the filter becomes
a plain column-vs-column comparison — pagination still happens in the database.
"""
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import BinCapacityForm
from apps.inventory.models import BinCapacity


def _on_hand_subquery():
    """Live on-hand per profiled location as ONE correlated subquery.

    Matching on location_id alone is tenant-safe: location pks are globally unique and
    the outer rows are already tenant-scoped.
    """
    from apps.scm.models import StockMove
    return (StockMove.objects.filter(location_id=OuterRef("location_id"))
            .values("location_id")
            .annotate(q=Sum("quantity")).values("q"))


def _scoped(tenant):
    """Tenant-scoped BinCapacity queryset with its location joined and each row's live
    ledger on-hand carried as ``on_hand_qty`` — every rendered cell reads the annotation
    instead of re-aggregating the bin's whole move history per row."""
    return (BinCapacity.objects.filter(tenant=tenant)
            .select_related("location")
            .annotate(on_hand_qty=Subquery(
                _on_hand_subquery(),
                output_field=DecimalField(max_digits=16, decimal_places=4))))


@login_required
def bincapacity_list(request):
    qs = _scoped(request.tenant)
    over = request.GET.get("utilisation", "").strip()
    if over == "over":
        # Column-vs-column comparison over the annotation _scoped already carries.
        # RAW on_hand_qty vs max_quantity — deliberately NOT the rounded display figure,
        # so a 99.96%-full bin can never disagree between this filter, the map and the chip.
        qs = qs.filter(max_quantity__isnull=False,
                       on_hand_qty__gte=F("max_quantity"))
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
        # The same ledger rows the model property aggregates, but as ROWS for the
        # recent-movements table — explicitly tenant-scoped like ledger_moves(), capped.
        "recent_moves": obj.location.stock_moves.filter(
            tenant=request.tenant).select_related("item")[:10],
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

    ONE annotated COUNT: the same correlated-subquery on-hand the list rows carry,
    compared RAW against ``max_quantity`` — the identical comparison the
    ``?utilisation=over`` filter applies, so the chip and the filter can never
    disagree on a boundary row (a 99.96%-full bin rounds to 100.0 for display but is
    still counted, consistently, as under).
    """
    return (_scoped(tenant)
            .filter(max_quantity__isnull=False, on_hand_qty__gte=F("max_quantity"))
            .count())
