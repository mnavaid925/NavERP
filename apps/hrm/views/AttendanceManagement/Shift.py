"""HRM 3.9 Attendance Management — Shift views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Shift,
    ShiftAssignment,
)
from apps.hrm.forms import (
    ShiftForm,
)


# ============================================================ Shifts (3.9)
@login_required
def shift_list(request):
    return crud_list(
        request,
        Shift.objects.filter(tenant=request.tenant)
        .annotate(assignment_count=Count("assignments")).order_by("name"),
        "hrm/attendance/shift/list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def shift_create(request):
    return crud_create(request, form_class=ShiftForm, template="hrm/attendance/shift/form.html",
                       success_url="hrm:shift_list")


@login_required
def shift_detail(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shift/detail.html", {
        "obj": obj,
        "assignments": ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj)
        .select_related("employee__party").order_by("-effective_from")[:50],
    })


@login_required
def shift_edit(request, pk):
    return crud_edit(request, model=Shift, pk=pk, form_class=ShiftForm,
                     template="hrm/attendance/shift/form.html", success_url="hrm:shift_list")


@login_required
@require_POST
def shift_delete(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    if ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj).exists():
        messages.error(request, "Cannot delete a shift that has assignments. Deactivate it instead.")
        return redirect("hrm:shift_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Shift deleted.")
    return redirect("hrm:shift_list")
