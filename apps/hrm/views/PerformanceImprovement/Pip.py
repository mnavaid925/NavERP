"""HRM 3.21 Performance Improvement — Pip views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_pip, _can_view_pip, _visible_pips_q
from apps.hrm.models import (
    EmployeeProfile,
    PerformanceImprovementPlan,
)
from apps.hrm.forms import (
    PIPCheckInForm,
    PIPCloseForm,
    PerformanceImprovementPlanForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_pip, _can_view_pip, _visible_pips_q
from apps.hrm.views.PerformanceReview._helpers import _is_admin
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


# ------------------------------------------------------------ PerformanceImprovementPlan (3.21 PIPs)
@login_required
def pip_list(request):
    qs = (PerformanceImprovementPlan.objects.filter(tenant=request.tenant)
          .select_related("subject__party", "manager__party")
          .annotate(num_checkins=Count("checkins")))
    vq = _visible_pips_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    return crud_list(
        request,
        qs.order_by("-start_date", "number"),
        "hrm/performance/pip/list.html",
        search_fields=("number", "subject__party__name", "manager__party__name"),
        filters=[("status", "status", False), ("outcome", "outcome", False),
                 ("subject", "subject_id", True), ("manager", "manager_id", True)],
        extra_context={
            "status_choices": PerformanceImprovementPlan.STATUS_CHOICES,
            "outcome_choices": PerformanceImprovementPlan.OUTCOME_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def pip_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    profile = _current_employee_profile(request)
    if request.method == "POST":
        form = PerformanceImprovementPlanForm(request.POST, tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"PIP {obj.number} created.")
            return redirect("hrm:pip_detail", pk=obj.pk)
    else:
        form = PerformanceImprovementPlanForm(tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/pip/form.html", {"form": form, "is_edit": False})


@login_required
def pip_detail(request, pk):
    obj = get_object_or_404(
        PerformanceImprovementPlan.objects.select_related(
            "subject__party", "manager__party", "triggering_review",
            "acknowledged_by__party", "hr_approved_by__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_pip(request, obj):
        raise PermissionDenied("You do not have access to this performance improvement plan.")
    checkins = list(obj.checkins.order_by("checkin_date"))
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    is_subject = profile is not None and profile.pk == obj.subject_id
    is_manager = profile is not None and profile.pk == obj.manager_id
    pip_open = obj.status != "closed"
    return render(request, "hrm/performance/pip/detail.html", {
        "obj": obj,
        "checkins": checkins,
        "can_edit": _can_edit_pip(request, obj),
        "is_admin": is_admin,
        "is_subject": is_subject,
        "is_manager": is_manager,
        # subject/manager/admin may LOG a check-in (open plan); only manager/admin may edit/delete one.
        "can_add_checkin": pip_open and _can_view_pip(request, obj),
        "can_manage_checkin": pip_open and (is_admin or is_manager),
        "checkin_form": PIPCheckInForm(tenant=request.tenant),
    })


@login_required
def pip_edit(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if not _can_edit_pip(request, obj):
        messages.error(request, "Only the manager or a tenant admin can edit a PIP, and only while it is a draft.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    return crud_edit(request, model=PerformanceImprovementPlan, pk=pk, form_class=PerformanceImprovementPlanForm,
                     template="hrm/performance/pip/form.html", success_url="hrm:pip_list")


@login_required
@require_POST
def pip_delete(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user)
            or (obj.status == "draft" and profile is not None and profile.pk == obj.manager_id)):
        messages.error(request, "Only a tenant admin (or the manager, while draft) can delete this PIP.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    return crud_delete(request, model=PerformanceImprovementPlan, pk=pk, success_url="hrm:pip_list")


@login_required
@require_POST
def pip_submit(request, pk):
    """The manager submits a draft PIP for HR approval (draft -> pending_hr_approval)."""
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.manager_id)):
        raise PermissionDenied("Only the manager (or a tenant admin) can submit this PIP.")
    if obj.status == "draft":
        obj.status = "pending_hr_approval"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"PIP {obj.number} submitted for HR approval.")
    else:
        messages.error(request, "Only a draft PIP can be submitted.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def pip_hr_approve(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending_hr_approval"):
        obj.status = "active"
        obj.hr_approved_at = timezone.now()
        obj.hr_approved_by = _current_employee_profile(request)
        obj.save(update_fields=["status", "hr_approved_at", "hr_approved_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "hr_approve"})
        messages.success(request, f"PIP {obj.number} approved and activated.")
    else:
        messages.error(request, "Only a draft or pending PIP can be approved.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@login_required
@require_POST
def pip_acknowledge(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.subject_id)):
        raise PermissionDenied("Only the plan's subject can acknowledge it.")
    if obj.status == "active" and obj.acknowledged_at is None:
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Plan acknowledged.")
    else:
        messages.error(request, "Only an active, not-yet-acknowledged plan can be acknowledged.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@tenant_admin_required
def pip_close(request, pk):
    obj = get_object_or_404(
        PerformanceImprovementPlan.objects.select_related("subject__party"), pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Only an active plan can be closed.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    if request.method == "POST":
        obj.status = "closed"  # set before validation so the model's outcome-iff-closed clean() passes
        form = PIPCloseForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.outcome_date:
                obj.outcome_date = timezone.localdate()
            obj.save()
            write_audit_log(request.user, obj, "update", {"action": "close", "outcome": obj.outcome})
            messages.success(request, f"PIP {obj.number} closed ({obj.get_outcome_display()}).")
            return redirect("hrm:pip_detail", pk=obj.pk)
    else:
        form = PIPCloseForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/performance/pip/close.html", {"form": form, "obj": obj})


@tenant_admin_required
@require_POST
def pip_extend(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Only an active plan can be extended.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    raw = (request.POST.get("extended_end_date") or "").strip()
    try:
        parsed = _date.fromisoformat(raw) if raw else None
    except ValueError:
        parsed = None
    if parsed is None or parsed <= (obj.extended_end_date or obj.end_date):
        messages.error(request, "Enter a new end date later than the plan's current end date.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    obj.extended_end_date = parsed
    obj.save(update_fields=["extended_end_date", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "extend", "to": str(parsed)})
    messages.success(request, f"PIP {obj.number} extended to {parsed}.")
    return redirect("hrm:pip_detail", pk=obj.pk)
