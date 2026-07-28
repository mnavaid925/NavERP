"""SCM 4.3 Inventory Management — Item master views (+ ItemCategory / UOM masters)."""
from django.db.models import ProtectedError

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
        # 4.9 Quality reads back into the item the same way: what has been inspected and what went
        # wrong, next to what we hold and what we expect to sell. Capped — this is a sample panel,
        # not the register.
        "quality_inspections": (obj.quality_inspections
                                .select_related("lot_serial", "inspector", "plan")[:10]),
        "nonconformances": obj.nonconformances.select_related("lot_serial", "owner")[:10],
    })


@login_required
@require_POST
def item_delete(request, pk):
    obj = get_object_or_404(Item, pk=pk, tenant=request.tenant)
    if obj.stock_moves.exists():
        messages.error(request, "This item has stock movements and cannot be deleted — deactivate it instead.")
        return redirect("scm:item_detail", pk=pk)
    # Everything else PROTECT-referencing an Item is caught generically below rather than
    # enumerated. The enumeration this replaces had grown a guard per sub-module (4.7 forecasts,
    # 4.8 BOMs/work orders, 4.9 inspections/NCRs) and STILL missed six: StockAdjustmentLine.item,
    # StockTransferLine.item, PutawayTask.item, PickTaskLine.item, CycleCountTaskLine.item and
    # SalesOrderLine.item. That miss was reachable — an item on a DRAFT stock-adjustment line has
    # no StockMove rows, so it cleared every guard above and 500'd. `lotserial_delete`'s comment
    # predicted exactly this staleness; this is the same shape it uses.
    #
    # Re-verified when 4.10 Returns Management landed: `ReturnLine.item` and `WarrantyClaim.item`
    # are two NEW PROTECT references onto this model. Neither needs a line of code here, because
    # this guard asks the database rather than a list somebody has to remember to extend — which is
    # exactly the property the enumeration above lacked.
    try:
        with transaction.atomic():
            return crud_delete(request, model=Item, pk=pk, success_url="scm:item_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"This item is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "deactivate it instead.")
        return redirect("scm:item_detail", pk=pk)


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
