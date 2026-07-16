"""HRM 3.39 Compliance & Legal — Grievance views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Grievance,
)
from apps.hrm.forms import (
    GrievanceForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_delete, _hr_request_edit


# ---- Grievances (CONFIDENTIAL: own-vs-admin; is_anonymous masks the complainant) ---------------
@login_required
def grievance_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, Grievance.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "assigned_investigator__party")
                   .defer("description", "resolution"))  # only `subject` is rendered in the list
    extra = {"is_admin": is_admin, "status_choices": Grievance.STATUS_CHOICES,
             "category_choices": Grievance.CATEGORY_CHOICES,
             "severity_choices": Grievance.SEVERITY_CHOICES}
    filters = [("status", "status", False), ("category", "category", False),
               ("severity", "severity", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/compliance/grievance/list.html",
                     search_fields=["number", "subject", "description"],
                     filters=filters, extra_context=extra)


@login_required
def grievance_create(request):
    """File a grievance. A non-admin files for THEMSELVES; an admin may file on behalf of ?employee=<id>."""
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
        messages.error(request, "Select an employee to file this grievance for.")
        return redirect("hrm:grievance_list")
    if request.method == "POST":
        form = GrievanceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.employee = target
            obj.status = "open"
            obj.filed_on = timezone.localdate()
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Grievance {obj.number} filed.")
            return redirect("hrm:grievance_detail", pk=obj.pk)
    else:
        form = GrievanceForm(tenant=request.tenant)
    return render(request, "hrm/compliance/grievance/form.html", {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None})


@login_required
def grievance_detail(request, pk):
    obj = get_object_or_404(
        Grievance.objects.select_related("employee__party", "assigned_investigator__party",
                                         "related_policy", "related_warning"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This grievance belongs to another employee.")
    is_admin = _is_admin(request.user)
    profile = _current_employee_profile(request)
    return render(request, "hrm/compliance/grievance/detail.html", {
        "obj": obj, "is_admin": is_admin,
        "is_own": profile is not None and obj.employee_id == profile.pk,
        # is_anonymous hides the complainant from everyone except HR admins (who must investigate).
        "show_complainant": is_admin or not obj.is_anonymous,
        "investigators": _ss_employees(request) if is_admin else None})


@login_required
def grievance_edit(request, pk):
    return _hr_request_edit(request, Grievance, pk, GrievanceForm,
                            "hrm/compliance/grievance/form.html", "hrm:grievance_detail")


@login_required
@require_POST
def grievance_delete(request, pk):
    return _hr_request_delete(request, Grievance, pk, "hrm:grievance_list")


@tenant_admin_required
@require_POST
def grievance_assign(request, pk):
    """Assign an investigator and move the grievance to 'investigating' (admin only)."""
    obj = get_object_or_404(Grievance, pk=pk, tenant=request.tenant)
    if obj.status in ("resolved", "closed", "withdrawn"):
        messages.error(request, "A closed grievance can't be reassigned.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    raw = (request.POST.get("investigator") or "").strip()
    investigator = None
    if raw.isdigit():
        investigator = EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(raw)).first()
    if investigator is None:
        messages.error(request, "Select a valid investigator.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    obj.assigned_investigator = investigator
    obj.status = "investigating"
    obj.save(update_fields=["assigned_investigator", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "assign"})
    messages.success(request, f"Grievance {obj.number} assigned for investigation.")
    return redirect("hrm:grievance_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def grievance_resolve(request, pk):
    obj = get_object_or_404(Grievance, pk=pk, tenant=request.tenant)
    if obj.status not in ("open", "investigating"):
        messages.error(request, "Only an open or under-investigation grievance can be resolved.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    resolution = (request.POST.get("resolution") or "").strip()
    if not resolution:
        messages.error(request, "A resolution note is required.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    obj.status = "resolved"
    obj.resolution = resolution[:5000]
    obj.resolved_at = timezone.now()
    obj.save(update_fields=["status", "resolution", "resolved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "resolve"})
    messages.success(request, f"Grievance {obj.number} resolved.")
    return redirect("hrm:grievance_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def grievance_close(request, pk):
    obj = get_object_or_404(Grievance, pk=pk, tenant=request.tenant)
    if obj.status == "closed":
        messages.error(request, "This grievance is already closed.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"Grievance {obj.number} closed.")
    return redirect("hrm:grievance_detail", pk=obj.pk)


@login_required
@require_POST
def grievance_withdraw(request, pk):
    """The complainant withdraws their own still-open grievance."""
    obj = get_object_or_404(Grievance, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (profile is not None and obj.employee_id == profile.pk):
        messages.error(request, "You can only withdraw your own grievance.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    if obj.status not in ("open", "investigating"):
        messages.error(request, "Only an open grievance can be withdrawn.")
        return redirect("hrm:grievance_detail", pk=obj.pk)
    obj.status = "withdrawn"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "withdraw"})
    messages.success(request, f"Grievance {obj.number} withdrawn.")
    return redirect("hrm:grievance_detail", pk=obj.pk)
