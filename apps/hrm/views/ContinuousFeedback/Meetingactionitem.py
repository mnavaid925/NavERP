"""HRM 3.20 Continuous Feedback — Meetingactionitem views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ContinuousFeedback._helpers import _can_manage_action_item, _can_view_meeting
from apps.hrm.models import (
    MeetingActionItem,
    OneOnOneMeeting,
)
from apps.hrm.forms import (
    MeetingActionItemForm,
)
from apps.hrm.views.ContinuousFeedback._helpers import _can_manage_action_item, _can_view_meeting


# ------------------------------------------------------------ MeetingActionItem (3.20 nested child)
@login_required
def meetingactionitem_create(request, meeting_pk):
    meeting = get_object_or_404(OneOnOneMeeting, pk=meeting_pk, tenant=request.tenant)
    if not _can_view_meeting(request, meeting):  # either party or admin may add an action item
        raise PermissionDenied("You do not have access to this 1:1 meeting.")
    if request.method == "POST":
        form = MeetingActionItemForm(
            request.POST, instance=MeetingActionItem(tenant=request.tenant, meeting=meeting),
            tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    item = form.save()
                write_audit_log(request.user, item, "create")
                messages.success(request, "Action item added.")
            except IntegrityError:
                messages.error(request, "Could not add that action item.")
            return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)
    else:
        form = MeetingActionItemForm(
            instance=MeetingActionItem(tenant=request.tenant, meeting=meeting), tenant=request.tenant)
    return render(request, "hrm/performance/meetingactionitem/form.html", {
        "form": form, "is_edit": False, "meeting": meeting})


@login_required
def meetingactionitem_detail(request, pk):
    item = get_object_or_404(
        MeetingActionItem.objects.select_related(
            "meeting__manager__party", "meeting__employee__party", "owner__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_meeting(request, item.meeting):
        raise PermissionDenied("You do not have access to this action item.")
    return render(request, "hrm/performance/meetingactionitem/detail.html", {
        "obj": item, "meeting": item.meeting,
        # Gate the Edit/Delete affordances to who can actually mutate it (owner/manager/admin).
        "can_manage": _can_manage_action_item(request, item),
    })


@login_required
def meetingactionitem_edit(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    if not _can_manage_action_item(request, item):
        raise PermissionDenied("Only the item's owner, the meeting's manager, or an admin can edit this action item.")
    if request.method == "POST":
        form = MeetingActionItemForm(request.POST, instance=item, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, item, "update")
            messages.success(request, "Action item updated.")
            return redirect("hrm:oneononemeeting_detail", pk=item.meeting_id)
    else:
        form = MeetingActionItemForm(instance=item, tenant=request.tenant)
    return render(request, "hrm/performance/meetingactionitem/form.html", {
        "form": form, "is_edit": True, "obj": item, "meeting": item.meeting})


@login_required
@require_POST
def meetingactionitem_delete(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    meeting = item.meeting
    if not _can_manage_action_item(request, item):
        messages.error(request, "Only the item's owner, the meeting's manager, or an admin can delete this action item.")
        return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Action item deleted.")
    return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)


@login_required
@require_POST
def meetingactionitem_toggle(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    meeting = item.meeting
    # The item's owner, the meeting's manager, or an admin may flip its state.
    if not _can_manage_action_item(request, item):
        raise PermissionDenied("Only the owner, the meeting's manager, or an admin can update this action item.")
    if item.status == "open":
        item.status, item.completed_at = "done", timezone.now()
    else:
        item.status, item.completed_at = "open", None
    item.save(update_fields=["status", "completed_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "toggle", "to": item.status})
    messages.success(request, f"Action item marked {item.get_status_display().lower()}.")
    return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)
