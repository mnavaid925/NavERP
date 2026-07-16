"""HRM 3.4 Employee Offboarding — Separationcase views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create
from apps.hrm.models import (
    ClearanceItem,
    EmployeeProfile,
    SeparationCase,
)
from apps.hrm.forms import (
    SeparationCaseForm,
)
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


# ---------------------------------------------------------- Separation Cases (3.4)
@login_required
def separationcase_list(request):
    return crud_list(
        request,
        SeparationCase.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "approver"),
        "hrm/offboarding/separationcase/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("separation_type", "separation_type", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": SeparationCase.STATUS_CHOICES,
                       "separation_type_choices": SeparationCase.SEPARATION_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def separationcase_create(request):
    return _offboarding_create(
        request, SeparationCaseForm, "hrm/offboarding/separationcase/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.pk))


@login_required
def separationcase_detail(request, pk):
    obj = get_object_or_404(
        SeparationCase.objects.select_related(
            "employee__party", "employee__employment", "employee__employment__org_unit",
            "employee__designation", "approver"),
        pk=pk, tenant=request.tenant)
    clearance_items = list(obj.clearance_items
                           .select_related("assigned_to", "cleared_by", "asset_allocation"))
    clearance_total = len(clearance_items)
    clearance_done = sum(1 for c in clearance_items
                         if c.status in ClearanceItem.RESOLVED_STATUSES)
    clearance_progress = int(round(clearance_done / clearance_total * 100)) if clearance_total else 0
    # all-mandatory-cleared computed from the already-fetched list (avoids the property's extra query)
    all_mandatory_cleared = not any(
        c.is_mandatory and c.status not in ClearanceItem.RESOLVED_STATUSES for c in clearance_items)
    return render(request, "hrm/offboarding/separationcase/detail.html", {
        "obj": obj,
        "clearance_items": clearance_items,
        "clearance_total": clearance_total,
        "clearance_done": clearance_done,
        "clearance_progress": clearance_progress,
        "all_mandatory_cleared": all_mandatory_cleared,
        "exit_interview": obj.exit_interviews.select_related("interviewer").first(),
        "settlement": obj.final_settlements.first(),
    })


@login_required
def separationcase_edit(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "pending_approval"):
        messages.error(request, "Only a draft or pending separation case can be edited.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    return crud_edit(request, model=SeparationCase, pk=pk, form_class=SeparationCaseForm,
                     template="hrm/offboarding/separationcase/form.html",
                     success_url="hrm:separationcase_list")


@login_required
@require_POST
def separationcase_delete(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    # Only a draft case is deletable — a submitted one is withdrawn (keeps the audit trail).
    if obj.status != "draft":
        messages.error(request, "Only a draft separation case can be deleted. Withdraw it instead.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Separation case deleted.")
    return redirect("hrm:separationcase_list")


@login_required
@require_POST
def separationcase_submit(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending_approval"
        if obj.submitted_at is None:
            obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Separation case {obj.number} submitted for approval.")
    else:
        messages.error(request, "Only a draft case can be submitted.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required  # approving a separation is a privileged HR/admin action
@require_POST
def separationcase_approve(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "pending_approval":
        with transaction.atomic():
            obj.status = "in_clearance"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
            created = generate_clearance_checklist(obj)  # auto-build the department checklist
            write_audit_log(request.user, obj, "update",
                            {"action": "approve", "clearance_items": created})
        messages.success(request, f"Separation case {obj.number} approved — "
                         f"{created} clearance item(s) created.")
    else:
        messages.error(request, "Only a case pending approval can be approved.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_reject(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "pending_approval":
        obj.status = "rejected"
        obj.rejection_reason = request.POST.get("reason", "").strip()[:2000]
        obj.save(update_fields=["status", "rejection_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Separation case {obj.number} rejected.")
    else:
        messages.error(request, "Only a case pending approval can be rejected.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@login_required
@require_POST
def separationcase_withdraw(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending_approval"):
        obj.status = "withdrawn"
        obj.withdrawal_reason = request.POST.get("reason", "").strip()[:2000]
        obj.save(update_fields=["status", "withdrawal_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "withdraw"})
        messages.success(request, f"Separation case {obj.number} withdrawn.")
    else:
        messages.error(request, "Only a draft or pending case can be withdrawn.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_mark_cleared(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status != "in_clearance":
        messages.error(request, "Only a case in clearance can be marked cleared.")
    elif not obj.all_mandatory_cleared:
        messages.error(request, "All mandatory clearance items must be cleared or marked N/A first.")
    else:
        obj.status = "cleared"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_cleared"})
        messages.success(request, f"Separation case {obj.number} fully cleared.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_complete(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status in ("cleared", "settled"):
        obj.status = "completed"
        if obj.actual_last_working_day is None:
            posted = _parse_iso_date(request.POST.get("actual_last_working_day", "").strip())
            obj.actual_last_working_day = (posted or obj.expected_last_working_day
                                           or timezone.localdate())
        obj.save(update_fields=["status", "actual_last_working_day", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Separation case {obj.number} completed.")
    else:
        messages.error(request, "A case must be cleared (and settled) before completion.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)
