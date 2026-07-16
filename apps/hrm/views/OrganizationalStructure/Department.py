"""HRM 3.2 Organizational Structure — Department views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    DepartmentProfile,
    Designation,
    EmployeeProfile,
)
from apps.hrm.forms import (
    DepartmentProfileForm,
)


# ============================================================ Departments (3.2 — OrgUnit companion)
@login_required
def department_list(request):
    return crud_list(
        request,
        DepartmentProfile.objects.filter(tenant=request.tenant)
        .select_related("org_unit", "org_unit__parent", "head__party", "cost_center")
        .annotate(employee_count=Count(
            "org_unit__employments",
            filter=Q(org_unit__employments__status="active"))).order_by("org_unit__name"),
        "hrm/organization/department/list.html",
        search_fields=["org_unit__name", "code", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def department_create(request):
    return crud_create(request, form_class=DepartmentProfileForm,
                       template="hrm/organization/department/form.html",
                       success_url="hrm:department_list")


@login_required
def department_detail(request, pk):
    obj = get_object_or_404(
        DepartmentProfile.objects.select_related(
            "org_unit", "org_unit__parent", "head__party", "cost_center"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/department/detail.html", {
        "obj": obj,
        "designations": Designation.objects.filter(tenant=request.tenant, department=obj.org_unit)
        .select_related("job_grade")[:50],
        # Only currently-employed staff count as "in" the department (matches the delete guard).
        "employees": EmployeeProfile.objects.filter(
            tenant=request.tenant, employment__org_unit=obj.org_unit, employment__status="active")
        .select_related("party", "designation")[:50],
    })


@login_required
def department_edit(request, pk):
    return crud_edit(request, model=DepartmentProfile, pk=pk, form_class=DepartmentProfileForm,
                     template="hrm/organization/department/form.html",
                     success_url="hrm:department_list")


@login_required
@require_POST
def department_delete(request, pk):
    obj = get_object_or_404(DepartmentProfile, pk=pk, tenant=request.tenant)
    # Guard: don't strip a department's HR profile while staff are still posted to the OrgUnit.
    if Employment.objects.filter(tenant=request.tenant, org_unit=obj.org_unit, status="active").exists():
        messages.error(request, "Cannot delete a department profile while employees are assigned. "
                                "Deactivate it instead.")
        return redirect("hrm:department_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()  # removes only the HRM companion; the core.OrgUnit node is untouched.
    messages.success(request, "Department profile deleted.")
    return redirect("hrm:department_list")
