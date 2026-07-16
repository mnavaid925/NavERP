"""HRM 3.10 Leave Management — Allocation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    LeaveAllocation,
    LeaveEncashment,
    LeaveRequest,
    LeaveType,
)
from apps.hrm.forms import (
    LeaveAllocationForm,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _DEC, _used_days_subquery


# ============================================================ Leave Allocations (3.10)
@login_required
def leaveallocation_list(request):
    used_subq = _used_days_subquery()
    return crud_list(
        request,
        LeaveAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type")
        .annotate(used_days_db=used_subq)
        .annotate(balance_db=ExpressionWrapper(
            F("allocated_days") - F("used_days_db") - F("encashed_days"), output_field=_DEC)),
        "hrm/leave/allocation/list.html",
        search_fields=["number", "employee__party__name", "leave_type__name"],
        filters=[("status", "status", False), ("year", "year", True),
                 ("employee", "employee_id", True), ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveAllocation.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant).order_by("name"),
                       "current_year": timezone.localdate().year},
    )


@login_required
def leaveallocation_create(request):
    return crud_create(request, form_class=LeaveAllocationForm,
                       template="hrm/leave/allocation/form.html", success_url="hrm:leaveallocation_list")


@login_required
def leaveallocation_detail(request, pk):
    obj = get_object_or_404(
        LeaveAllocation.objects.select_related("employee__party", "leave_type"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/leave/allocation/detail.html", {
        "obj": obj,
        "requests": LeaveRequest.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            start_date__year=obj.year).order_by("-start_date")[:20],
        "encashments": LeaveEncashment.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            year=obj.year).order_by("-created_at")[:20],
    })


@login_required
def leaveallocation_edit(request, pk):
    return crud_edit(request, model=LeaveAllocation, pk=pk, form_class=LeaveAllocationForm,
                     template="hrm/leave/allocation/form.html", success_url="hrm:leaveallocation_list")


@login_required
@require_POST
def leaveallocation_delete(request, pk):
    return crud_delete(request, model=LeaveAllocation, pk=pk, success_url="hrm:leaveallocation_list")
