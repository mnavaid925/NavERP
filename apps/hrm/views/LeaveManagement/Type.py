"""HRM 3.10 Leave Management — Type views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
)
from apps.hrm.forms import (
    LeaveTypeForm,
)


# ============================================================ Leave Types (3.10)
@login_required
def leavetype_list(request):
    return crud_list(
        request,
        LeaveType.objects.filter(tenant=request.tenant),
        "hrm/leave/type/list.html",
        search_fields=["name", "code"],
        filters=[("is_active", "is_active", False), ("is_paid", "is_paid", False),
                 ("accrual_rule", "accrual_rule", False)],
        extra_context={"accrual_choices": LeaveType.ACCRUAL_CHOICES},
    )


@login_required
def leavetype_create(request):
    return crud_create(request, form_class=LeaveTypeForm, template="hrm/leave/type/form.html",
                       success_url="hrm:leavetype_list")


@login_required
def leavetype_detail(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    return render(request, "hrm/leave/type/detail.html", {
        "obj": obj,
        "year": year,
        "allocation_count": LeaveAllocation.objects.filter(
            tenant=request.tenant, leave_type=obj, year=year).count(),
        "request_count": LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).count(),
    })


@login_required
def leavetype_edit(request, pk):
    return crud_edit(request, model=LeaveType, pk=pk, form_class=LeaveTypeForm,
                     template="hrm/leave/type/form.html", success_url="hrm:leavetype_list")


@login_required
@require_POST
def leavetype_delete(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    # Guard: a leave type still referenced by allocations or requests cannot be removed.
    if (LeaveAllocation.objects.filter(tenant=request.tenant, leave_type=obj).exists()
            or LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).exists()):
        messages.error(request, "Cannot delete a leave type that has allocations or requests. "
                                "Deactivate it instead.")
        return redirect("hrm:leavetype_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Leave type deleted.")
    return redirect("hrm:leavetype_list")
