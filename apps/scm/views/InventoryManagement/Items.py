"""SCM 4.3 Inventory Management — Item master views (+ ItemCategory / UOM masters)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import Item, ItemCategory, UOM, Location, StockMove
from apps.scm.forms import ItemForm, ItemCategoryForm, UOMForm


# =============================================================================== Item
@login_required
def item_list(request):
    qs = Item.objects.filter(tenant=request.tenant).select_related("category", "uom")
    return crud_list(
        request, qs, "scm/inventory/item/list.html",
        search_fields=["sku", "name", "description"],
        filters=[("item_type", "item_type", False), ("category", "category_id", True),
                 ("tracking", "tracking", False)],
        extra_context={
            "type_choices": Item.ITEM_TYPES,
            "tracking_choices": Item.TRACKING_CHOICES,
            "categories": ItemCategory.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def item_create(request):
    if _need_tenant(request):
        return redirect("scm:item_list")
    return crud_create(request, form_class=ItemForm, template="scm/inventory/item/form.html",
                       success_url="scm:item_list")


@login_required
def item_edit(request, pk):
    return crud_edit(request, model=Item, pk=pk, form_class=ItemForm,
                     template="scm/inventory/item/form.html", success_url="scm:item_list")


@login_required
def item_detail(request, pk):
    obj = get_object_or_404(Item.objects.select_related("category", "uom"), pk=pk, tenant=request.tenant)
    # On-hand per location, derived from the StockMove ledger in ONE grouped query (no per-location call).
    by_location = (StockMove.objects.filter(tenant=request.tenant, item=obj)
                   .values("location__code", "location__name")
                   .annotate(qty=Sum("quantity"))
                   .order_by("location__code"))
    on_hand = obj.on_hand()
    return render(request, "scm/inventory/item/detail.html", {
        "obj": obj,
        "on_hand": on_hand,
        "total_value": obj.total_value(on_hand=on_hand),
        "by_location": [row for row in by_location if row["qty"]],
        "recent_moves": (StockMove.objects.filter(tenant=request.tenant, item=obj)
                         .select_related("location", "lot_serial")[:15]),
        "reorder_rules": obj.reorder_rules.select_related("location"),
        "lot_serials": obj.lot_serials.all()[:20],
        # 4.7 Demand Planning reads back into the item: the forecasts planned against it, so the
        # item page answers "what do we expect to sell" next to "what do we hold".
        "demand_forecasts": obj.demand_forecasts.select_related("location")[:10],
    })


@login_required
@require_POST
def item_delete(request, pk):
    obj = get_object_or_404(Item, pk=pk, tenant=request.tenant)
    if obj.stock_moves.exists():
        messages.error(request, "This item has stock movements and cannot be deleted — deactivate it instead.")
        return redirect("scm:item_detail", pk=pk)
    # 4.7's DemandForecast.item is PROTECT, so an item with only a PLAN against it — no stock, no
    # transactions — now hits a ProtectedError that crud_delete does not catch (a 500). Refuse it
    # with a message that says where to look, the same way the stock-movement guard does.
    if obj.demand_forecasts.exists():
        messages.error(request, "This item has demand forecasts and cannot be deleted — archive or "
                                "delete them first, or deactivate the item instead.")
        return redirect("scm:item_detail", pk=pk)
    # 4.8 adds three more PROTECT FKs onto Item — BillOfMaterials.item, BOMLine.component and
    # WorkOrderComponent.item — each of which would raise the same uncaught ProtectedError (a 500)
    # that the demand-forecast guard above was added for. Same shape, same reason.
    if obj.boms.exists():
        messages.error(request, "This item is produced by a bill of materials and cannot be "
                                "deleted — delete or obsolete the BOM first, or deactivate the item.")
        return redirect("scm:item_detail", pk=pk)
    if obj.bom_lines.exists():
        messages.error(request, "This item is a component on a bill of materials and cannot be "
                                "deleted — remove it from those BOMs first, or deactivate it.")
        return redirect("scm:item_detail", pk=pk)
    if obj.work_orders.exists() or obj.work_order_components.exists():
        messages.error(request, "This item is used by work orders and cannot be deleted — "
                                "deactivate it instead.")
        return redirect("scm:item_detail", pk=pk)
    return crud_delete(request, model=Item, pk=pk, success_url="scm:item_list")


# =============================================================================== ItemCategory
@login_required
def category_list(request):
    qs = ItemCategory.objects.filter(tenant=request.tenant).select_related("parent").annotate(
        item_count=Count("items", distinct=True)).order_by("name")
    return crud_list(
        request, qs, "scm/inventory/category/list.html",
        search_fields=["name", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def category_create(request):
    if _need_tenant(request):
        return redirect("scm:category_list")
    return crud_create(request, form_class=ItemCategoryForm, template="scm/inventory/category/form.html",
                       success_url="scm:category_list")


@login_required
def category_edit(request, pk):
    return crud_edit(request, model=ItemCategory, pk=pk, form_class=ItemCategoryForm,
                     template="scm/inventory/category/form.html", success_url="scm:category_list")


@login_required
@require_POST
def category_delete(request, pk):
    return crud_delete(request, model=ItemCategory, pk=pk, success_url="scm:category_list")


# =============================================================================== UOM
@login_required
def uom_list(request):
    qs = UOM.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "scm/inventory/uom/list.html",
        search_fields=["code", "name"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def uom_create(request):
    if _need_tenant(request):
        return redirect("scm:uom_list")
    return crud_create(request, form_class=UOMForm, template="scm/inventory/uom/form.html",
                       success_url="scm:uom_list")


@login_required
def uom_edit(request, pk):
    return crud_edit(request, model=UOM, pk=pk, form_class=UOMForm,
                     template="scm/inventory/uom/form.html", success_url="scm:uom_list")


@login_required
@require_POST
def uom_delete(request, pk):
    return crud_delete(request, model=UOM, pk=pk, success_url="scm:uom_list")
