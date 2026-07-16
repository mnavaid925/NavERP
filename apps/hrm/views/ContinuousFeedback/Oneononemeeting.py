"""HRM 3.20 Continuous Feedback — Oneononemeeting views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ContinuousFeedback._helpers import _can_manage_meeting, _can_view_meeting, _visible_meetings_q
from apps.hrm.models import (
    EmployeeProfile,
    OneOnOneMeeting,
)
from apps.hrm.forms import (
    MeetingActionItemForm,
    OneOnOneMeetingForm,
)
from apps.hrm.views.ContinuousFeedback._helpers import _can_manage_meeting, _can_view_meeting, _visible_meetings_q
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ OneOnOneMeeting (3.20 1:1 meetings)
@login_required
def oneononemeeting_list(request):
    profile = _current_employee_profile(request)
    qs = (OneOnOneMeeting.objects.filter(tenant=request.tenant)
          .select_related("manager__party", "employee__party", "related_objective")
          .annotate(num_actions=Count("action_items")))
    vq = _visible_meetings_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        qs.order_by("-scheduled_at"),
        "hrm/performance/oneononemeeting/list.html",
        search_fields=("number", "manager__party__name", "employee__party__name"),
        filters=[("status", "status", False), ("manager", "manager_id", True),
                 ("employee", "employee_id", True)],
        extra_context={
            "status_choices": OneOnOneMeeting.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            # For gating the row manage buttons (edit/delete/complete/cancel) to the manager/admin.
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def oneononemeeting_create(request):
    return crud_create(request, form_class=OneOnOneMeetingForm,
                       template="hrm/performance/oneononemeeting/form.html",
                       success_url="hrm:oneononemeeting_list")


@login_required
def oneononemeeting_detail(request, pk):
    obj = get_object_or_404(
        OneOnOneMeeting.objects.select_related("manager__party", "employee__party", "related_objective"),
        pk=pk, tenant=request.tenant)
    if not _can_view_meeting(request, obj):
        raise PermissionDenied("You do not have access to this 1:1 meeting.")
    can_manage = _can_manage_meeting(request, obj)  # manager or admin
    action_items = list(obj.action_items.select_related("owner__party")
                        .order_by("status", "due_date", "description"))
    profile = _current_employee_profile(request)
    return render(request, "hrm/performance/oneononemeeting/detail.html", {
        "obj": obj,
        "show_private": can_manage,   # manager_private_notes block is gated on this
        "can_manage": can_manage,
        "action_items": action_items,
        "current_profile_id": profile.pk if profile is not None else None,
        "action_form": MeetingActionItemForm(tenant=request.tenant),
    })


@login_required
def oneononemeeting_edit(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    # Manager/admin only — the edit form exposes manager_private_notes, so the employee must never
    # reach it (L20: masking the read view is not enough; keep the field's holder off the bound form
    # for anyone who shouldn't read it). The employee collaborates via action items + the read view.
    if not _can_manage_meeting(request, obj):
        messages.error(request, "Only the meeting's manager or a tenant admin can edit a 1:1.")
        return redirect("hrm:oneononemeeting_detail", pk=obj.pk)
    return crud_edit(request, model=OneOnOneMeeting, pk=pk, form_class=OneOnOneMeetingForm,
                     template="hrm/performance/oneononemeeting/form.html",
                     success_url="hrm:oneononemeeting_list")


@login_required
@require_POST
def oneononemeeting_delete(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        messages.error(request, "Only the meeting's manager or a tenant admin can delete a 1:1.")
        return redirect("hrm:oneononemeeting_detail", pk=obj.pk)
    return crud_delete(request, model=OneOnOneMeeting, pk=pk, success_url="hrm:oneononemeeting_list")


@login_required
@require_POST
def oneononemeeting_complete(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        raise PermissionDenied("Only the meeting's manager or a tenant admin can complete a 1:1.")
    if obj.status == "scheduled":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"1:1 {obj.number} marked completed.")
    else:
        messages.error(request, "Only a scheduled 1:1 can be completed.")
    return redirect("hrm:oneononemeeting_detail", pk=obj.pk)


@login_required
@require_POST
def oneononemeeting_cancel(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        raise PermissionDenied("Only the meeting's manager or a tenant admin can cancel a 1:1.")
    if obj.status == "scheduled":
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"1:1 {obj.number} cancelled.")
    else:
        messages.error(request, "Only a scheduled 1:1 can be cancelled.")
    return redirect("hrm:oneononemeeting_detail", pk=obj.pk)
