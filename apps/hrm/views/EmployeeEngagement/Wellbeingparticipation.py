"""HRM 3.41 Employee Engagement & Wellbeing — Wellbeingparticipation views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    WellbeingParticipation,
    WellbeingProgram,
)
from apps.hrm.forms import (
    WellbeingParticipationForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_employees
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _changed


# ---- Wellbeing participation (inline child of a program) ----------------------------------------
@login_required
def wellbeingparticipation_add(request, program_pk):
    """RSVP / log a participation. A non-admin adds for THEMSELVES; an admin may target ?employee=<id>."""
    program = get_object_or_404(WellbeingProgram, pk=program_pk, tenant=request.tenant)
    if program.status != "active":
        messages.error(request, "You can only join an active program.")
        return redirect("hrm:wellbeingprogram_detail", pk=program.pk)
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    target = own
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            target = EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    if target is None:
        messages.error(request, "Select an employee to register.")
        return redirect("hrm:wellbeingprogram_detail", pk=program.pk)

    if request.method == "POST":
        form = WellbeingParticipationForm(request.POST, can_admin=is_admin, tenant=request.tenant)
        # unique_together(tenant, program, employee) — all three are view-resolved, so guard by an explicit
        # query (Django can't validate_unique it), then keep the savepoint as a concurrent-race backstop.
        if WellbeingParticipation.objects.filter(tenant=request.tenant, program=program,
                                                 employee=target).exists():
            form.add_error(None, "That employee is already registered for this program.")
        elif form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.program = program
            obj.employee = target
            try:
                with transaction.atomic():
                    obj.save()
            except IntegrityError:
                messages.error(request, "That employee is already registered for this program.")
                return redirect("hrm:wellbeingprogram_detail", pk=program.pk)
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Registered for the program.")
            return redirect("hrm:wellbeingprogram_detail", pk=program.pk)
    else:
        form = WellbeingParticipationForm(can_admin=is_admin, tenant=request.tenant)
    return render(request, "hrm/engagement/wellbeingparticipation/form.html",
                  {"form": form, "program": program, "is_edit": False, "is_admin": is_admin,
                   "target_employee": target, "employees": _ss_employees(request) if is_admin else None})


@login_required
def wellbeingparticipation_edit(request, program_pk, pk):
    # select_related program (for the is_confidential check) AND employee__party (str(obj) -> the audit
    # log dereferences employee.party.name; without it that's 2 extra queries per edit).
    obj = get_object_or_404(
        WellbeingParticipation.objects.select_related("program", "employee__party"),
        pk=pk, program_id=program_pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only manage your own participation.")
        return redirect("hrm:wellbeingprogram_detail", pk=program_pk)
    is_admin = _is_admin(request.user)
    if request.method == "POST":
        form = WellbeingParticipationForm(request.POST, instance=obj, can_admin=is_admin,
                                          tenant=request.tenant)
        if form.is_valid():
            form.save()
            # Don't record the field diff (status/notes) for a confidential program — the audit trail is
            # admin-readable, and that would leak what the aggregate-only rule protects.
            changes = None if obj.program.is_confidential else _changed(form)
            write_audit_log(request.user, obj, "update", changes=changes)
            messages.success(request, "Participation updated.")
            return redirect("hrm:wellbeingprogram_detail", pk=program_pk)
    else:
        form = WellbeingParticipationForm(instance=obj, can_admin=is_admin, tenant=request.tenant)
    return render(request, "hrm/engagement/wellbeingparticipation/form.html",
                  {"form": form, "program": obj.program, "obj": obj, "is_edit": True, "is_admin": is_admin})


@login_required
@require_POST
def wellbeingparticipation_delete(request, program_pk, pk):
    obj = get_object_or_404(WellbeingParticipation.objects.select_related("program"),
                            pk=pk, program_id=program_pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only manage your own participation.")
        return redirect("hrm:wellbeingprogram_detail", pk=program_pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Participation removed.")
    return redirect("hrm:wellbeingprogram_detail", pk=program_pk)
