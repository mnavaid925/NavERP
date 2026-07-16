"""HRM 3.1 Employee Management — Form views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.forms import (
    EmployeeProfileForm,
)


@login_required
def employee_create(request):
    return crud_create(request, form_class=EmployeeProfileForm, template="hrm/employee/form.html",
                       success_url="hrm:employee_list")


@login_required
def employee_edit(request, pk):
    return crud_edit(request, model=EmployeeProfile, pk=pk, form_class=EmployeeProfileForm,
                     template="hrm/employee/form.html", success_url="hrm:employee_list")


@login_required
@require_POST
def employee_delete(request, pk):
    obj = get_object_or_404(
        EmployeeProfile.objects.select_related("employment"), pk=pk, tenant=request.tenant)
    # Guard: don't delete an actively-employed person — terminate the Employment first.
    if obj.employment_id and obj.employment.status == "active":
        messages.error(request, "Cannot delete an active employee — set their employment to "
                                "terminated/on-leave first.")
        return redirect("hrm:employee_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Employee deleted.")
    return redirect("hrm:employee_list")
