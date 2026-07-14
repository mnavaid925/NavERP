"""CRM 1.2 Sales Force Automation — Products views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Product,
)
from apps.crm.forms import (
    ProductForm,
)


# ------------------------------------------------------------ Products (1.2 catalog)
@login_required
def product_list(request):
    return crud_list(
        request,
        Product.objects.filter(tenant=request.tenant).defer("description"),  # description not on the list
        "crm/sales/product/list.html",
        search_fields=["number", "name", "sku"],
        filters=[("product_type", "product_type", False), ("is_active", "is_active", False)],
        extra_context={"type_choices": Product.TYPE_CHOICES},
    )


@login_required
def product_create(request):
    return crud_create(request, form_class=ProductForm, template="crm/sales/product/form.html",
                       success_url="crm:product_list")


@login_required
def product_detail(request, pk):
    obj = get_object_or_404(Product, pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/product/detail.html", {"obj": obj})


@login_required
def product_edit(request, pk):
    return crud_edit(request, model=Product, pk=pk, form_class=ProductForm,
                     template="crm/sales/product/form.html", success_url="crm:product_list")


@login_required
@require_POST
def product_delete(request, pk):
    return crud_delete(request, model=Product, pk=pk, success_url="crm:product_list")
