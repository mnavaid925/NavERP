"""HRM 3.3 Employee Onboarding — Assetallocation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetAllocation,
    EmployeeProfile,
)
from apps.hrm.forms import (
    AssetAllocationForm,
)


# ============================================================ Asset Allocations (3.3)
@login_required
def assetallocation_list(request):
    return crud_list(
        request,
        AssetAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "program", "issued_by"),
        "hrm/onboarding/assetallocation/list.html",
        search_fields=["number", "asset_name", "serial_number", "asset_tag"],
        filters=[("employee", "employee_id", True), ("status", "status", False),
                 ("asset_category", "asset_category", False)],
        extra_context={"status_choices": AssetAllocation.STATUS_CHOICES,
                       "category_choices": AssetAllocation.ASSET_CATEGORY_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def assetallocation_create(request):
    return crud_create(request, form_class=AssetAllocationForm,
                       template="hrm/onboarding/assetallocation/form.html",
                       success_url="hrm:assetallocation_list")


@login_required
def assetallocation_detail(request, pk):
    obj = get_object_or_404(
        AssetAllocation.objects.select_related("employee__party", "program", "issued_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/assetallocation/detail.html", {"obj": obj})


@login_required
def assetallocation_edit(request, pk):
    return crud_edit(request, model=AssetAllocation, pk=pk, form_class=AssetAllocationForm,
                     template="hrm/onboarding/assetallocation/form.html", success_url="hrm:assetallocation_list")


@login_required
@require_POST
def assetallocation_delete(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    # Guard: an issued asset should be returned before its allocation record is removed.
    if obj.status == "issued":
        messages.error(request, "Return this asset before deleting its allocation.")
        return redirect("hrm:assetallocation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Asset allocation deleted.")
    return redirect("hrm:assetallocation_list")


@login_required
@require_POST
def assetallocation_issue(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "issued"
        obj.issued_at = timezone.now()
        obj.issued_by = request.user
        obj.save(update_fields=["status", "issued_at", "issued_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "issue"})
        messages.success(request, f"Asset {obj.number} issued.")
    return redirect("hrm:assetallocation_detail", pk=obj.pk)


@login_required
@require_POST
def assetallocation_return(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    if obj.status == "issued":
        obj.status = "returned"
        obj.returned_at = timezone.now()
        obj.save(update_fields=["status", "returned_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "return"})
        messages.success(request, f"Asset {obj.number} returned.")
    return redirect("hrm:assetallocation_detail", pk=obj.pk)
