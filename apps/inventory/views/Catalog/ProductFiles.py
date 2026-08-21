"""Inventory 5.1 Product & Catalog Management — ProductFile views.

The create/edit forms are multipart (file upload), which ``crud_create``/``crud_edit`` already
handle — both bind ``request.FILES``. Delete removes only the catalog ROW; an uploaded artifact
stays on disk under MEDIA_ROOT until a storage-cleanup pass exists, deliberately: deleting the
row of a mis-filed document should never destroy the artifact itself.
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import ProductFileForm
from apps.inventory.models import ProductFile
from apps.scm.models import Item


@login_required
def productfile_list(request):
    qs = ProductFile.objects.filter(tenant=request.tenant).select_related("item")
    return crud_list(
        request, qs, "inventory/catalog/productfile/list.html",
        search_fields=["item__sku", "item__name", "title", "url"],
        filters=[("item", "item_id", True), ("kind", "kind", False),
                 ("is_primary", "is_primary", False)],
        extra_context={
            "items": Item.objects.filter(tenant=request.tenant).order_by("sku"),
            "kind_choices": ProductFile.KIND_CHOICES,
        },
    )


@login_required
def productfile_create(request):
    return crud_create(
        request, form_class=ProductFileForm,
        template="inventory/catalog/productfile/form.html",
        success_url="inventory:productfile_list",
    )


@login_required
def productfile_detail(request, pk):
    obj = get_object_or_404(
        ProductFile.objects.select_related("item"), pk=pk, tenant=request.tenant)
    return render(request, "inventory/catalog/productfile/detail.html", {
        "obj": obj,
        # Scoped + self-excluded in the view — same reasoning as the price detail's siblings.
        "siblings": (obj.item.catalog_files.filter(tenant=request.tenant)
                     .exclude(pk=obj.pk)),
    })


@login_required
def productfile_edit(request, pk):
    return crud_edit(
        request, model=ProductFile, pk=pk, form_class=ProductFileForm,
        template="inventory/catalog/productfile/form.html",
        success_url="inventory:productfile_list",
    )


@login_required
@require_POST
def productfile_delete(request, pk):
    return crud_delete(request, model=ProductFile, pk=pk,
                       success_url="inventory:productfile_list")
