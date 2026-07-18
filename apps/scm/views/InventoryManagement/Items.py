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
    })


@login_required
@require_POST
def item_delete(request, pk):
    obj = get_object_or_404(Item, pk=pk, tenant=request.tenant)
    if obj.stock_moves.exists():
        messages.error(request, "This item has stock movements and cannot be deleted — deactivate it instead.")
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
