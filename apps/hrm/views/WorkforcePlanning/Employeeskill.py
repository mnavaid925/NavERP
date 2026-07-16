"""HRM 3.40 Workforce Planning — Employeeskill views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    EmployeeSkill,
)
from apps.hrm.forms import (
    EmployeeSkillForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope


# ---- Employee skills inventory (own-vs-admin self-service) --------------------------------------
@login_required
def employeeskill_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, EmployeeSkill.objects.filter(tenant=request.tenant)
                   .select_related("employee__party").defer("notes"))
    extra = {"is_admin": is_admin,
             "skill_category_choices": EmployeeSkill.SKILL_CATEGORY_CHOICES,
             "proficiency_choices": EmployeeSkill.PROFICIENCY_CHOICES}
    filters = [("skill_category", "skill_category", False),
               ("proficiency_level", "proficiency_level", False),
               ("is_critical_skill", "is_critical_skill", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/workforce/employeeskill/list.html",
                     search_fields=["skill_name", "certification_name", "employee__party__name"],
                     filters=filters, extra_context=extra)


@login_required
def employeeskill_create(request):
    """Add a skill. A non-admin adds to THEIR OWN profile; an admin may target ?employee=<id>."""
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
        messages.error(request, "Select an employee to add this skill to.")
        return redirect("hrm:employeeskill_list")
    if request.method == "POST":
        # Seed the unsaved instance with tenant+employee so the form's unique_together guard can run.
        instance = EmployeeSkill(tenant=request.tenant, employee=target)
        form = EmployeeSkillForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            try:
                # Savepoint: a duplicate skill must roll back only this insert, never poison the request
                # transaction (the 3.38 lesson).
                with transaction.atomic():
                    obj = form.save()
            except IntegrityError:
                messages.error(request, "That skill is already on the employee's profile.")
                return redirect("hrm:employeeskill_list")
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Skill added.")
            return redirect("hrm:employeeskill_list")
    else:
        form = EmployeeSkillForm(tenant=request.tenant)
    return render(request, "hrm/workforce/employeeskill/form.html", {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None})


@login_required
def employeeskill_detail(request, pk):
    return _ss_child_detail(request, EmployeeSkill, pk, "hrm/workforce/employeeskill/detail.html",
                            select_related=("employee__party",))


@login_required
def employeeskill_edit(request, pk):
    return _ss_child_edit(request, EmployeeSkill, pk, EmployeeSkillForm,
                          "hrm/workforce/employeeskill/form.html", "hrm:employeeskill_detail")


@login_required
@require_POST
def employeeskill_delete(request, pk):
    return _ss_child_delete(request, EmployeeSkill, pk, "hrm:employeeskill_list")
