"""CRM 1.12 Inventory & Vendor Management — ProductStock views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    ProductStock,
)
from apps.crm.forms import (
    ProductStockForm,
)


# ------------------------------------------------------------ 1.12 Product stock
@login_required
def productstock_list(request):
    return crud_list(
        request,
        ProductStock.objects.filter(tenant=request.tenant),
        "crm/vendor/productstock/list.html",
        search_fields=["number", "name", "sku"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def productstock_create(request):
    return crud_create(request, form_class=ProductStockForm, template="crm/vendor/productstock/form.html",
                       success_url="crm:productstock_list")


@login_required
def productstock_detail(request, pk):
    obj = get_object_or_404(ProductStock, pk=pk, tenant=request.tenant)
    return render(request, "crm/vendor/productstock/detail.html", {"obj": obj})


@login_required
def productstock_edit(request, pk):
    return crud_edit(request, model=ProductStock, pk=pk, form_class=ProductStockForm,
                     template="crm/vendor/productstock/form.html", success_url="crm:productstock_list")


@login_required
@require_POST
def productstock_delete(request, pk):
    return crud_delete(request, model=ProductStock, pk=pk, success_url="crm:productstock_list")
