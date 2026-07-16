"""HRM 3.26 Request Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_child_delete, _ss_child_edit


def _is_own_hr_request(request, obj):
    """3.26 self-approval guard: the acting user is the request's SUBMITTER (the `employee`), so
    they must NOT also be the approver/rejecter — a different admin must review it. `employee` IS
    the submitter on all three request models, so there's no separate requested_by leg to check."""
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


# ---- Shared workflow helpers (used by all three 3.26 request models) ------------------------
def _hr_request_submit(request, model, pk, detail_url):
    """draft -> pending, gated to the owning employee or an admin (stricter than the older
    leaverequest_submit, which has no ownership gate — 3.26 follows the 3.25 _can_manage_own_child
    convention)."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only submit your own requests.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Request {obj.number} submitted for approval.")
    else:
        messages.error(request, "Only a draft request can be submitted.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_cancel(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only cancel your own requests.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status in obj.OPEN_STATUSES:
        obj.status = "cancelled"
        obj.decision_note = (request.POST.get("decision_note") or "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Request {obj.number} cancelled.")
    else:
        messages.error(request, "Only a draft or pending request can be cancelled.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_approve(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't approve your own request — another admin must review it.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"Request {obj.number} approved.")
    else:
        messages.error(request, "Only a pending request can be approved.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_reject(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't reject your own request — another admin must review it.")
        return redirect(detail_url, pk=obj.pk)
    note = (request.POST.get("decision_note") or "").strip()
    if not note:
        messages.error(request, "A reason is required to reject a request.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.decision_note = note[:2000]
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "decision_note", "approver", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Request {obj.number} rejected.")
    else:
        messages.error(request, "Only a pending request can be rejected.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_edit(request, model, pk, form_class, template, detail_url):
    """Edit only while OPEN (draft/pending) — a decided request is locked — then delegate to the
    shared ownership-gated _ss_child_edit. Ownership is checked BEFORE the status branch so a
    non-owner can't read another employee's request state off the differing flash message."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own records.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status not in obj.OPEN_STATUSES:
        messages.error(request, "A decided request can no longer be edited.")
        return redirect(detail_url, pk=obj.pk)
    return _ss_child_edit(request, model, pk, form_class, template, detail_url)


def _hr_request_delete(request, model, pk, list_url):
    """Delete only a still-open request (a decided/closed row is preserved for the audit trail).
    Ownership is checked BEFORE the status branch so a non-owner can't read another employee's
    request state off the differing flash message."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own records.")
        return redirect(list_url)
    if obj.status not in obj.OPEN_STATUSES:
        messages.error(request, "A decided request can no longer be deleted.")
        return redirect(list_url)
    return _ss_child_delete(request, model, pk, list_url)
