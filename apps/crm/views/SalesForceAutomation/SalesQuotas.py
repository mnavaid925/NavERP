"""CRM 1.2 Sales Force Automation — SalesQuotas views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    SalesQuota,
    Territory,
)
from apps.crm.forms import (
    SalesQuotaForm,
)


# ------------------------------------------------------------ Sales quotas (1.2)
@login_required
def salesquota_list(request):
    return crud_list(
        request,
        SalesQuota.objects.filter(tenant=request.tenant).select_related("owner", "territory"),
        "crm/sales/salesquota/list.html",
        search_fields=["number", "owner__username", "territory__name"],
        filters=[("period_type", "period_type", False), ("territory", "territory_id", True)],
        extra_context={"period_choices": SalesQuota.PERIOD_CHOICES,
                       "territories": Territory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def salesquota_create(request):
    return crud_create(request, form_class=SalesQuotaForm, template="crm/sales/salesquota/form.html",
                       success_url="crm:salesquota_list")


@login_required
def salesquota_detail(request, pk):
    obj = get_object_or_404(SalesQuota.objects.select_related("owner", "territory"), pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/salesquota/detail.html", {"obj": obj})


@login_required
def salesquota_edit(request, pk):
    return crud_edit(request, model=SalesQuota, pk=pk, form_class=SalesQuotaForm,
                     template="crm/sales/salesquota/form.html", success_url="crm:salesquota_list")


@login_required
@require_POST
def salesquota_delete(request, pk):
    return crud_delete(request, model=SalesQuota, pk=pk, success_url="crm:salesquota_list")
