"""HRM 3.2 Organizational Structure — Costcenter views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CostCenterProfile,
    DepartmentProfile,
)
from apps.hrm.forms import (
    CostCenterProfileForm,
)


# ============================================================ Cost Centers (3.2 — OrgUnit companion)
@login_required
def costcenter_list(request):
    return crud_list(
        request,
        CostCenterProfile.objects.filter(tenant=request.tenant)
        .select_related("org_unit", "org_unit__parent", "owner__party").order_by("org_unit__name"),
        "hrm/organization/costcenter/list.html",
        search_fields=["org_unit__name", "code", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def costcenter_create(request):
    return crud_create(request, form_class=CostCenterProfileForm,
                       template="hrm/organization/costcenter/form.html",
                       success_url="hrm:costcenter_list")


@login_required
def costcenter_detail(request, pk):
    obj = get_object_or_404(
        CostCenterProfile.objects.select_related("org_unit", "org_unit__parent", "owner__party"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/costcenter/detail.html", {
        "obj": obj,
        "mapped_departments": DepartmentProfile.objects.filter(
            tenant=request.tenant, cost_center=obj.org_unit)
        .select_related("org_unit", "head__party")[:50],
    })


@login_required
def costcenter_edit(request, pk):
    return crud_edit(request, model=CostCenterProfile, pk=pk, form_class=CostCenterProfileForm,
                     template="hrm/organization/costcenter/form.html",
                     success_url="hrm:costcenter_list")


@login_required
@require_POST
def costcenter_delete(request, pk):
    obj = get_object_or_404(CostCenterProfile, pk=pk, tenant=request.tenant)
    if DepartmentProfile.objects.filter(tenant=request.tenant, cost_center=obj.org_unit).exists():
        messages.error(request, "Cannot delete a cost center mapped to departments. "
                                "Unmap them or deactivate it instead.")
        return redirect("hrm:costcenter_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Cost center profile deleted.")
    return redirect("hrm:costcenter_list")
