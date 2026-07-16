"""HRM 3.21 Performance Improvement — Warningletter views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_warning, _can_view_warning, _visible_warnings_q
from apps.hrm.models import (
    EmployeeProfile,
    WarningLetter,
)
from apps.hrm.forms import (
    WarningAcknowledgeForm,
    WarningLetterForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceImprovement._helpers import _can_edit_warning, _can_view_warning, _visible_warnings_q
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ WarningLetter (3.21 progressive discipline)
@login_required
def warningletter_list(request):
    qs = (WarningLetter.objects.filter(tenant=request.tenant)
          .select_related("issued_to__party", "issued_by__party", "related_pip"))
    vq = _visible_warnings_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    return crud_list(
        request, qs.order_by("-incident_date", "number"),
        "hrm/performance/warningletter/list.html",
        search_fields=("number", "issued_to__party__name", "description"),
        filters=[("level", "level", False), ("category", "category", False),
                 ("status", "status", False), ("issued_to", "issued_to_id", True)],
        extra_context={
            "level_choices": WarningLetter.LEVEL_CHOICES,
            "category_choices": WarningLetter.CATEGORY_CHOICES,
            "status_choices": WarningLetter.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def warningletter_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    profile = _current_employee_profile(request)
    if request.method == "POST":
        form = WarningLetterForm(request.POST, tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Warning letter {obj.number} created.")
            return redirect("hrm:warningletter_detail", pk=obj.pk)
    else:
        form = WarningLetterForm(tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/warningletter/form.html", {"form": form, "is_edit": False})


@login_required
def warningletter_detail(request, pk):
    obj = get_object_or_404(
        WarningLetter.objects.select_related(
            "issued_to__party", "issued_by__party", "related_pip", "acknowledged_by__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_warning(request, obj):
        raise PermissionDenied("You do not have access to this warning letter.")
    # Prior-warnings escalation context, scoped to what THIS viewer may see (never the full history).
    # No select_related — the prior-warnings table renders only local fields (number/level/category/date).
    prior = obj.prior_warnings
    vq = _visible_warnings_q(request)
    if vq is not None:
        prior = prior.filter(vq)
    profile = _current_employee_profile(request)
    is_recipient = profile is not None and profile.pk == obj.issued_to_id
    return render(request, "hrm/performance/warningletter/detail.html", {
        "obj": obj,
        "prior_warnings": list(prior[:10]),
        "can_edit": _can_edit_warning(request, obj),
        "is_admin": _is_admin(request.user),
        "is_recipient": is_recipient,
        "can_acknowledge": is_recipient and obj.status == "issued",
        "ack_form": WarningAcknowledgeForm(tenant=request.tenant),
    })


@login_required
def warningletter_edit(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    if not _can_edit_warning(request, obj):
        messages.error(request, "Only the issuer or a tenant admin can edit a warning letter, and only while it is a draft.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    return crud_edit(request, model=WarningLetter, pk=pk, form_class=WarningLetterForm,
                     template="hrm/performance/warningletter/form.html", success_url="hrm:warningletter_list")


@login_required
@require_POST
def warningletter_delete(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user)
            or (obj.status == "draft" and profile is not None and profile.pk == obj.issued_by_id)):
        messages.error(request, "Only a tenant admin (or the issuer, while draft) can delete this warning letter.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    return crud_delete(request, model=WarningLetter, pk=pk, success_url="hrm:warningletter_list")


@tenant_admin_required
@require_POST
def warningletter_issue(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "issued"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "issue"})
        messages.success(request, f"Warning letter {obj.number} issued.")
    else:
        messages.error(request, "Only a draft warning letter can be issued.")
    return redirect("hrm:warningletter_detail", pk=obj.pk)


@login_required
@require_POST
def warningletter_acknowledge(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.issued_to_id)):
        raise PermissionDenied("Only the recipient can acknowledge this warning letter.")
    if obj.status != "issued":
        messages.error(request, "Only an issued warning letter can be acknowledged.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    form = WarningAcknowledgeForm(request.POST, instance=obj, tenant=request.tenant)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["employee_response", "status", "acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Warning letter acknowledged.")
    return redirect("hrm:warningletter_detail", pk=obj.pk)


@login_required
def warningletter_print(request, pk):
    obj = get_object_or_404(
        WarningLetter.objects.select_related("issued_to__party", "issued_by__party", "tenant", "related_pip"),
        pk=pk, tenant=request.tenant)
    if not _can_view_warning(request, obj):
        raise PermissionDenied("You do not have access to this warning letter.")
    return render(request, "hrm/performance/warningletter/print.html", {"obj": obj})
