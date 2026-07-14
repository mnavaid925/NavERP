"""CRM 1.2 Sales Force Automation — Territories views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    Territory,
)
from apps.crm.forms import (
    TerritoryForm,
)


# ------------------------------------------------------------ Territories (1.2)
@login_required
def territory_list(request):
    return crud_list(
        request,
        # defer the large description TextField — not rendered on the list.
        Territory.objects.filter(tenant=request.tenant).select_related("parent", "manager").defer("description"),
        "crm/sales/territory/list.html",
        search_fields=["number", "name", "region", "segment"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def territory_create(request):
    return crud_create(request, form_class=TerritoryForm, template="crm/sales/territory/form.html",
                       success_url="crm:territory_list")


@login_required
def territory_detail(request, pk):
    obj = get_object_or_404(Territory.objects.select_related("parent", "manager"), pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/territory/detail.html", {
        "obj": obj,
        "children": Territory.objects.filter(tenant=request.tenant, parent=obj).select_related("manager"),
        "opportunities": Opportunity.objects.filter(
            tenant=request.tenant, territory=obj).select_related("account")[:20],
    })


@login_required
def territory_edit(request, pk):
    return crud_edit(request, model=Territory, pk=pk, form_class=TerritoryForm,
                     template="crm/sales/territory/form.html", success_url="crm:territory_list")


@login_required
@require_POST
def territory_delete(request, pk):
    return crud_delete(request, model=Territory, pk=pk, success_url="crm:territory_list")
