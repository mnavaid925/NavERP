"""HRM 3.2 Organizational Structure — Designation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    JobGrade,
)
from apps.hrm.forms import (
    DesignationForm,
)


# ============================================================ Designations (3.2)
@login_required
def designation_list(request):
    return crud_list(
        request,
        Designation.objects.filter(tenant=request.tenant).select_related("department", "job_grade")
        .annotate(employee_count=Count("employees")).order_by("name"),
        "hrm/organization/designation/list.html",
        search_fields=["name", "grade", "job_grade__name", "department__name"],
        filters=[("is_active", "is_active", False), ("department", "department_id", True),
                 ("job_grade", "job_grade_id", True)],
        extra_context={
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
            "job_grades": JobGrade.objects.filter(tenant=request.tenant, is_active=True).order_by("level_order", "name"),
        },
    )


@login_required
def designation_create(request):
    return crud_create(request, form_class=DesignationForm,
                       template="hrm/organization/designation/form.html",
                       success_url="hrm:designation_list")


@login_required
def designation_detail(request, pk):
    obj = get_object_or_404(
        Designation.objects.select_related("department", "job_grade")
        .annotate(employee_count=Count("employees")), pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/designation/detail.html", {
        "obj": obj,
        "employees": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj)
        .select_related("party")[:50],
        "employee_count": obj.employee_count,
    })


@login_required
def designation_edit(request, pk):
    return crud_edit(request, model=Designation, pk=pk, form_class=DesignationForm,
                     template="hrm/organization/designation/form.html",
                     success_url="hrm:designation_list")


@login_required
@require_POST
def designation_delete(request, pk):
    obj = get_object_or_404(Designation, pk=pk, tenant=request.tenant)
    # Guard: deleting a designation in use would silently de-designate employees (SET_NULL).
    if EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj).exists():
        messages.error(request, "Cannot delete a designation assigned to employees. "
                                "Deactivate it instead.")
        return redirect("hrm:designation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Designation deleted.")
    return redirect("hrm:designation_list")
