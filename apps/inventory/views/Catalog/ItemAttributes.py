"""Inventory 5.1 Product & Catalog Management — ItemAttribute views.

Thin CRUD over the core helpers: the tenant scoping, the int-FK filter guard (L11), pagination and
the audit trail all live in ``apps.core.crud``; this module declares only its own search fields,
filter spec and templates.
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import ItemAttributeForm
from apps.inventory.models import ItemAttribute
from apps.scm.models import Item


@login_required
def itemattribute_list(request):
    qs = ItemAttribute.objects.filter(tenant=request.tenant).select_related("item")
    return crud_list(
        request, qs, "inventory/catalog/itemattribute/list.html",
        search_fields=["item__sku", "item__name", "name", "value"],
        filters=[("item", "item_id", True)],
        extra_context={
            "items": Item.objects.filter(tenant=request.tenant).order_by("sku"),
        },
    )


@login_required
def itemattribute_create(request):
    return crud_create(
        request, form_class=ItemAttributeForm,
        template="inventory/catalog/itemattribute/form.html",
        success_url="inventory:itemattribute_list",
    )


@login_required
def itemattribute_detail(request, pk):
    obj = get_object_or_404(
        ItemAttribute.objects.select_related("item"), pk=pk, tenant=request.tenant)
    return render(request, "inventory/catalog/itemattribute/detail.html", {
        "obj": obj,
        # Scoped + self-excluded in the view — same reasoning as the price detail's siblings.
        "siblings": (obj.item.catalog_attributes.filter(tenant=request.tenant)
                     .exclude(pk=obj.pk).order_by("sequence", "name")),
    })


@login_required
def itemattribute_edit(request, pk):
    return crud_edit(
        request, model=ItemAttribute, pk=pk, form_class=ItemAttributeForm,
        template="inventory/catalog/itemattribute/form.html",
        success_url="inventory:itemattribute_list",
    )


@login_required
@require_POST
def itemattribute_delete(request, pk):
    return crud_delete(request, model=ItemAttribute, pk=pk,
                       success_url="inventory:itemattribute_list")
