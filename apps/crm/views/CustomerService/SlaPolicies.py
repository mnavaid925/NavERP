"""CRM 1.4 Customer Service & Support — SlaPolicies views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    SlaPolicy,
)
from apps.crm.forms import (
    SlaPolicyForm,
)


# ------------------------------------------------------------ SLA policies (1.4)
@login_required
def slapolicy_list(request):
    return crud_list(
        request, SlaPolicy.objects.filter(tenant=request.tenant).defer("description"),
        "crm/service/slapolicy/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@tenant_admin_required  # SLA policy is tenant-wide config (is_default drives every case's SLA)
def slapolicy_create(request):
    return crud_create(request, form_class=SlaPolicyForm, template="crm/service/slapolicy/form.html",
                       success_url="crm:slapolicy_list")


@login_required
def slapolicy_detail(request, pk):
    obj = get_object_or_404(SlaPolicy, pk=pk, tenant=request.tenant)
    return render(request, "crm/service/slapolicy/detail.html", {"obj": obj})


@tenant_admin_required
def slapolicy_edit(request, pk):
    return crud_edit(request, model=SlaPolicy, pk=pk, form_class=SlaPolicyForm,
                     template="crm/service/slapolicy/form.html", success_url="crm:slapolicy_list")


@tenant_admin_required
@require_POST
def slapolicy_delete(request, pk):
    return crud_delete(request, model=SlaPolicy, pk=pk, success_url="crm:slapolicy_list")
