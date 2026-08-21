"""Inventory 5.1 Product & Catalog Management — ItemPrice views.

Same thin-CRUD shape as the attribute views. The list's margin/markup columns are computed in the
model against each row's item cost, so the queryset ``select_related("item")`` is not cosmetic —
without it every rendered row pays a query to reach ``standard_cost``.
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import ItemPriceForm
from apps.inventory.models import ItemPrice
from apps.scm.models import Item


@login_required
def itemprice_list(request):
    # currency joins in for the list's currency column — without it every rendered row with a
    # currency pays its own query (the detail view already carried it; the list is where the N+1
    # actually bites, one row per page-line).
    qs = ItemPrice.objects.filter(tenant=request.tenant).select_related("item", "currency")
    return crud_list(
        request, qs, "inventory/catalog/itemprice/list.html",
        search_fields=["item__sku", "item__name", "notes"],
        filters=[("item", "item_id", True), ("price_type", "price_type", False),
                 ("is_active", "is_active", False)],
        extra_context={
            "items": Item.objects.filter(tenant=request.tenant).order_by("sku"),
            "type_choices": ItemPrice.PRICE_TYPE_CHOICES,
        },
    )


@login_required
def itemprice_create(request):
    return crud_create(
        request, form_class=ItemPriceForm,
        template="inventory/catalog/itemprice/form.html",
        success_url="inventory:itemprice_list",
    )


@login_required
def itemprice_detail(request, pk):
    obj = get_object_or_404(
        ItemPrice.objects.select_related("item", "currency"), pk=pk, tenant=request.tenant)
    return render(request, "inventory/catalog/itemprice/detail.html", {
        "obj": obj,
        # Scoped + self-excluded here rather than trusted from the reverse relation: the write
        # paths keep item.tenant == row.tenant, but a future raw writer must not be able to
        # render another workspace's rows inline on this page.
        "siblings": (obj.item.catalog_prices.filter(tenant=request.tenant)
                     .exclude(pk=obj.pk)),
    })


@login_required
def itemprice_edit(request, pk):
    return crud_edit(
        request, model=ItemPrice, pk=pk, form_class=ItemPriceForm,
        template="inventory/catalog/itemprice/form.html",
        success_url="inventory:itemprice_list",
    )


@login_required
@require_POST
def itemprice_delete(request, pk):
    return crud_delete(request, model=ItemPrice, pk=pk,
                       success_url="inventory:itemprice_list")
