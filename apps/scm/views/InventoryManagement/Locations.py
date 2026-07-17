"""SCM 4.3 Inventory Management — Location views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import Location, StockMove
from apps.scm.forms import LocationForm


@login_required
def location_list(request):
    qs = Location.objects.filter(tenant=request.tenant).select_related("parent")
    return crud_list(
        request, qs, "scm/inventory/location/list.html",
        search_fields=["code", "name"],
        filters=[("location_type", "location_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": Location.LOCATION_TYPES},
    )


@login_required
def location_create(request):
    if _need_tenant(request):
        return redirect("scm:location_list")
    return crud_create(request, form_class=LocationForm, template="scm/inventory/location/form.html",
                       success_url="scm:location_list")


@login_required
def location_edit(request, pk):
    return crud_edit(request, model=Location, pk=pk, form_class=LocationForm,
                     template="scm/inventory/location/form.html", success_url="scm:location_list")


@login_required
def location_detail(request, pk):
    obj = get_object_or_404(Location.objects.select_related("parent"), pk=pk, tenant=request.tenant)
    # On-hand by item at this location, derived from the ledger in one grouped query.
    by_item = (StockMove.objects.filter(tenant=request.tenant, location=obj)
               .values("item__sku", "item__name")
               .annotate(qty=Sum("quantity"))
               .order_by("item__sku"))
    return render(request, "scm/inventory/location/detail.html", {
        "obj": obj,
        "path": obj.path(),
        "children": obj.children.all(),
        "on_hand_value": obj.on_hand_value(),
        "by_item": [row for row in by_item if row["qty"]],
    })


@login_required
@require_POST
def location_delete(request, pk):
    obj = get_object_or_404(Location, pk=pk, tenant=request.tenant)
    if obj.stock_moves.exists():
        messages.error(request, "This location has stock movements and cannot be deleted — deactivate it instead.")
        return redirect("scm:location_detail", pk=pk)
    return crud_delete(request, model=Location, pk=pk, success_url="scm:location_list")
