"""HRM 3.37 Compensation & Benefits — Employeebenefitenrollment views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CompensationBenefits._helpers import _enrollment_decide
from apps.hrm.models import (
    BenefitPlan,
    EmployeeBenefitEnrollment,
    EmployeeProfile,
)
from apps.hrm.forms import (
    EmployeeBenefitEnrollmentForm,
)
from apps.hrm.views.CompensationBenefits._helpers import _enrollment_decide
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_detail, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_delete, _hr_request_edit


# ---- Employee benefit enrollments (own-vs-admin self-service) ---------------------------------
@login_required
def employeebenefitenrollment_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, EmployeeBenefitEnrollment.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "plan"))
    extra = {"status_choices": EmployeeBenefitEnrollment.STATUS_CHOICES, "is_admin": is_admin,
             "plans": BenefitPlan.objects.filter(tenant=request.tenant, is_active=True)
             .order_by("plan_type", "name")}
    filters = [("status", "status", False), ("plan", "plan_id", True)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/compensation/employeebenefitenrollment/list.html",
                     search_fields=["number", "plan__name", "employee__party__name"],
                     filters=filters, extra_context=extra)


@login_required
def employeebenefitenrollment_create(request):
    """Elect a benefit. A non-admin elects for THEMSELVES; an admin may target ?employee=<id>/employee_pk.
    Contributions default from the plan when left blank."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    target = own
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            target = EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    if target is None:
        messages.error(request, "Select an employee to enroll.")
        return redirect("hrm:employeebenefitenrollment_list")
    if request.method == "POST":
        form = EmployeeBenefitEnrollmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.employee = target
            obj.status = "pending"
            # Contributions are DERIVED from the plan server-side (not user-editable — employer money).
            if obj.plan_id:
                obj.employee_contribution = obj.plan.employee_cost_monthly
                obj.employer_contribution = obj.plan.employer_cost_monthly
            try:
                obj.save()
            except IntegrityError:
                messages.error(request, "An enrollment for this plan and effective date already exists.")
                return redirect("hrm:employeebenefitenrollment_list")
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Enrollment {obj.number} submitted.")
            return redirect("hrm:employeebenefitenrollment_detail", pk=obj.pk)
    else:
        form = EmployeeBenefitEnrollmentForm(tenant=request.tenant)
    return render(request, "hrm/compensation/employeebenefitenrollment/form.html", {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None})


@login_required
def employeebenefitenrollment_detail(request, pk):
    return _ss_child_detail(request, EmployeeBenefitEnrollment, pk,
                            "hrm/compensation/employeebenefitenrollment/detail.html",
                            select_related=("employee__party", "plan__currency", "decided_by"))


@login_required
def employeebenefitenrollment_edit(request, pk):
    return _hr_request_edit(request, EmployeeBenefitEnrollment, pk, EmployeeBenefitEnrollmentForm,
                            "hrm/compensation/employeebenefitenrollment/form.html",
                            "hrm:employeebenefitenrollment_detail")


@login_required
@require_POST
def employeebenefitenrollment_delete(request, pk):
    return _hr_request_delete(request, EmployeeBenefitEnrollment, pk, "hrm:employeebenefitenrollment_list")


@tenant_admin_required
@require_POST
def employeebenefitenrollment_enroll(request, pk):
    return _enrollment_decide(request, pk, "enrolled", ("pending",), "enrolled")


@tenant_admin_required
@require_POST
def employeebenefitenrollment_waive(request, pk):
    return _enrollment_decide(request, pk, "waived", ("pending", "enrolled"), "waived")


@tenant_admin_required
@require_POST
def employeebenefitenrollment_terminate(request, pk):
    return _enrollment_decide(request, pk, "terminated", ("enrolled",), "terminated")
