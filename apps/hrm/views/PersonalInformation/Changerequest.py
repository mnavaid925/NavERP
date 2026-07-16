"""HRM 3.25 Personal Information — Changerequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _CHANGE_FORMS, _assemble_change_request, _can_manage_own_child, _is_own_change_request, _mask_diff_value, _resolve_cr_employee, _ss_employees, _ss_scope
from apps.hrm.models import (
    EmployeeInfoChangeRequest,
)
from apps.hrm.forms import (
    ProfileFieldChangeForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _CHANGE_FORMS, _assemble_change_request, _can_manage_own_child, _is_own_change_request, _mask_diff_value, _resolve_cr_employee, _ss_employees, _ss_scope


@login_required
def changerequest_list(request):
    # The list renders only obj.employee.party.name (admin col) + local fields — requested_by/
    # reviewed_by are shown on the detail page, not here.
    qs = _ss_scope(request, EmployeeInfoChangeRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": EmployeeInfoChangeRequest.STATUS_CHOICES,
             "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES}
    filters = [("status", "status", False), ("request_type", "request_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/changerequest/list.html",
                     search_fields=("number", "employee__party__name", "reason"),
                     filters=filters, extra_context=extra)


@login_required
def changerequest_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    employee = _resolve_cr_employee(request, is_admin, own)
    if employee is None:
        messages.error(request, "No employee record to raise a change request against.")
        return redirect("hrm:changerequest_list")

    req_type = (request.POST.get("request_type") or request.GET.get("type") or "profile_field").strip()
    if req_type not in _CHANGE_FORMS:
        req_type = "profile_field"

    def build(data=None):
        if req_type == "profile_field":
            initial = None
            if data is None:
                fld = request.GET.get("field", "").strip()
                if fld in EmployeeInfoChangeRequest.SENSITIVE_PROFILE_FIELDS:
                    initial = {"field_name": fld}
            return ProfileFieldChangeForm(data, initial=initial)
        return _CHANGE_FORMS[req_type](data, employee=employee, tenant=request.tenant)

    if request.method == "POST":
        form = build(request.POST)
        if form.is_valid():
            cr = _assemble_change_request(request, employee, req_type, form)
            try:
                cr.clean()  # anti-tamper safety net (own-record only); number is set in save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                cr.save()
                write_audit_log(request.user, cr, "create")
                messages.success(request, f"Change request {cr.number} submitted for review.")
                return redirect("hrm:changerequest_detail", pk=cr.pk)
    else:
        form = build()
    return render(request, "hrm/selfservice/changerequest/form.html", {
        "form": form, "is_edit": False, "request_type": req_type, "employee": employee,
        "is_admin": is_admin,
        "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES,
        "employees": _ss_employees(request) if is_admin else None,
    })


@login_required
def changerequest_detail(request, pk):
    obj = get_object_or_404(
        EmployeeInfoChangeRequest.objects.select_related(
            "employee__party", "requested_by", "reviewed_by", "content_type"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This change request belongs to another employee.")
    diffs = [{"field": k.replace("_", " ").title(),
              "old": _mask_diff_value(k, (v or {}).get("old")),
              "new": _mask_diff_value(k, (v or {}).get("new"))}
             for k, v in (obj.field_changes or {}).items()]
    return render(request, "hrm/selfservice/changerequest/detail.html", {
        "obj": obj, "diffs": diffs, "is_admin": _is_admin(request.user),
        "can_manage": _can_manage_own_child(request, obj),
        # Maker-checker: an admin who is the maker/subject may NOT review their own request, so the
        # Approve/Reject controls are hidden for them (the view would bounce them anyway).
        "is_own": _is_own_change_request(request, obj),
    })


@login_required
def changerequest_edit(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own requests.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be edited.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    req_type, employee = obj.request_type, obj.employee

    # Pre-fill the sub-form from the stored proposal (the "new" values).
    if req_type == "profile_field":
        (fname, change), = (obj.field_changes or {"": {}}).items()
        initial = {"field_name": fname, "new_value": (change or {}).get("new"), "reason": obj.reason}
    else:
        initial = {k: (v or {}).get("new") for k, v in (obj.field_changes or {}).items()}
        initial["reason"] = obj.reason
        if obj.object_id:
            initial["existing_account" if req_type == "bank" else "existing_member"] = obj.object_id

    def build(data=None):
        if req_type == "profile_field":
            return ProfileFieldChangeForm(data, initial=None if data else initial)
        return _CHANGE_FORMS[req_type](data, initial=None if data else initial,
                                       employee=employee, tenant=request.tenant)

    if request.method == "POST":
        form = build(request.POST)
        if form.is_valid():
            rebuilt = _assemble_change_request(request, employee, req_type, form)
            try:
                rebuilt.clean()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                obj.field_changes = rebuilt.field_changes
                obj.content_type = rebuilt.content_type
                obj.object_id = rebuilt.object_id
                obj.reason = rebuilt.reason
                obj.save(update_fields=["field_changes", "content_type", "object_id", "reason", "updated_at"])
                write_audit_log(request.user, obj, "update")
                messages.success(request, "Change request updated.")
                return redirect("hrm:changerequest_detail", pk=obj.pk)
    else:
        form = build()
    return render(request, "hrm/selfservice/changerequest/form.html", {
        "form": form, "is_edit": True, "obj": obj, "request_type": req_type, "employee": employee,
        "is_admin": _is_admin(request.user),
        "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES, "employees": None,
    })


@login_required
@require_POST
def changerequest_delete(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own requests.")
        return redirect("hrm:changerequest_list")
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be deleted.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Change request deleted.")
    return redirect("hrm:changerequest_list")


@login_required
@require_POST
def changerequest_cancel(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only cancel your own requests.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be cancelled.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, "Change request cancelled.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def changerequest_approve(request, pk):
    # select_related so apply() doesn't re-fetch self.employee / .party for the legal_name write.
    obj = get_object_or_404(
        EmployeeInfoChangeRequest.objects.select_related("employee__party", "content_type"),
        pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be approved.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if _is_own_change_request(request, obj):
        messages.error(request, "You can't review your own change request — another admin must approve or reject it.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    try:
        obj.apply(request.user)
    except ValidationError as exc:
        messages.error(request, f"Could not apply this change: {'; '.join(exc.messages)}")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Change request {obj.number} approved and applied.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def changerequest_reject(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be rejected.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if _is_own_change_request(request, obj):
        messages.error(request, "You can't review your own change request — another admin must approve or reject it.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    note = (request.POST.get("decision_note") or "").strip()
    if not note:
        messages.error(request, "A reason is required to reject a change request.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.decision_note = note
    obj.reviewed_by = request.user
    obj.reviewed_at = timezone.now()
    obj.save(update_fields=["status", "decision_note", "reviewed_by", "reviewed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Change request {obj.number} rejected.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)
