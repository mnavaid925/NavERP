"""HRM 3.13 Salary Structure — Employeesalarystructure views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    EmployeeSalaryStructure,
    SalaryStructureTemplate,
)
from apps.hrm.forms import (
    EmployeeSalaryStructureForm,
)


# ============================================================ Employee Salary Structures (3.13)
@login_required
def employeesalarystructure_list(request):
    return crud_list(
        request,
        EmployeeSalaryStructure.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "template"),
        "hrm/salary/employeesalarystructure/list.html",
        search_fields=["employee__party__name", "number"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("template", "template_id", True)],
        extra_context={
            "status_choices": EmployeeSalaryStructure.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "templates": SalaryStructureTemplate.objects.filter(tenant=request.tenant).order_by("name"),
        },
    )


@login_required
def employeesalarystructure_create(request):
    return crud_create(request, form_class=EmployeeSalaryStructureForm,
                       template="hrm/salary/employeesalarystructure/form.html",
                       success_url="hrm:employeesalarystructure_list")


@login_required
def employeesalarystructure_detail(request, pk):
    obj = get_object_or_404(
        EmployeeSalaryStructure.objects.select_related("employee__party", "template"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/salary/employeesalarystructure/detail.html", {"obj": obj})


@login_required
def employeesalarystructure_edit(request, pk):
    obj = get_object_or_404(EmployeeSalaryStructure, pk=pk, tenant=request.tenant)
    # A superseded (historical) assignment is read-only — compensation history must not be silently
    # rewritten via a direct POST (a payroll run may depend on it). Only the active one is editable.
    if obj.status == "superseded":
        messages.error(request, "A superseded salary assignment is read-only history and cannot be edited.")
        return redirect("hrm:employeesalarystructure_detail", pk=obj.pk)
    return crud_edit(request, model=EmployeeSalaryStructure, pk=pk, form_class=EmployeeSalaryStructureForm,
                     template="hrm/salary/employeesalarystructure/form.html",
                     success_url="hrm:employeesalarystructure_list")


@login_required
@require_POST
def employeesalarystructure_delete(request, pk):
    obj = get_object_or_404(EmployeeSalaryStructure, pk=pk, tenant=request.tenant)
    if obj.status == "superseded":
        messages.error(request, "A superseded salary assignment is read-only history and cannot be deleted.")
        return redirect("hrm:employeesalarystructure_detail", pk=obj.pk)
    return crud_delete(request, model=EmployeeSalaryStructure, pk=pk,
                       success_url="hrm:employeesalarystructure_list")
