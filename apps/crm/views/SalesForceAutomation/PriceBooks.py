"""CRM 1.2 Sales Force Automation — PriceBooks views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    PriceBook,
)
from apps.crm.forms import (
    PriceBookForm,
)


# ------------------------------------------------------------ Price books (1.2)
@login_required
def pricebook_list(request):
    return crud_list(
        request,
        PriceBook.objects.filter(tenant=request.tenant).defer("description"),  # description not on the list
        "crm/sales/pricebook/list.html",
        search_fields=["number", "name", "region", "tier"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def pricebook_create(request):
    return crud_create(request, form_class=PriceBookForm, template="crm/sales/pricebook/form.html",
                       success_url="crm:pricebook_list")


@login_required
def pricebook_detail(request, pk):
    obj = get_object_or_404(PriceBook, pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/pricebook/detail.html", {"obj": obj})


@login_required
def pricebook_edit(request, pk):
    return crud_edit(request, model=PriceBook, pk=pk, form_class=PriceBookForm,
                     template="crm/sales/pricebook/form.html", success_url="crm:pricebook_list")


@login_required
@require_POST
def pricebook_delete(request, pk):
    return crud_delete(request, model=PriceBook, pk=pk, success_url="crm:pricebook_list")
