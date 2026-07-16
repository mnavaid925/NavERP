"""HRM 3.9 Attendance Management — Shiftassignment views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Shift,
    ShiftAssignment,
)
from apps.hrm.forms import (
    ShiftAssignmentForm,
)


# ============================================================ Shift Assignments (3.9)
@login_required
def shiftassignment_list(request):
    return crud_list(
        request,
        ShiftAssignment.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "shift"),
        "hrm/attendance/shiftassignment/list.html",
        search_fields=["employee__party__name", "shift__name"],
        filters=[("shift", "shift_id", True), ("employee", "employee_id", True)],
        extra_context={"shifts": Shift.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def shiftassignment_create(request):
    return crud_create(request, form_class=ShiftAssignmentForm,
                       template="hrm/attendance/shiftassignment/form.html", success_url="hrm:shiftassignment_list")


@login_required
def shiftassignment_detail(request, pk):
    obj = get_object_or_404(
        ShiftAssignment.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shiftassignment/detail.html", {"obj": obj})


@login_required
def shiftassignment_edit(request, pk):
    return crud_edit(request, model=ShiftAssignment, pk=pk, form_class=ShiftAssignmentForm,
                     template="hrm/attendance/shiftassignment/form.html", success_url="hrm:shiftassignment_list")


@login_required
@require_POST
def shiftassignment_delete(request, pk):
    return crud_delete(request, model=ShiftAssignment, pk=pk, success_url="hrm:shiftassignment_list")
