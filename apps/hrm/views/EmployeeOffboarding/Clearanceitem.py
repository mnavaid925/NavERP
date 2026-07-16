"""HRM 3.4 Employee Offboarding — Clearanceitem views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create
from apps.hrm.models import (
    ClearanceItem,
    SeparationCase,
)
from apps.hrm.forms import (
    ClearanceItemForm,
)
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create


# ---------------------------------------------------------- Clearance Items (3.4)
@login_required
def clearanceitem_list(request):
    return crud_list(
        request,
        ClearanceItem.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party", "assigned_to", "cleared_by"),
        "hrm/offboarding/clearanceitem/list.html",
        search_fields=["description", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("department", "department", False),
                 ("case", "case_id", True)],
        extra_context={"status_choices": ClearanceItem.CLEARANCE_STATUS_CHOICES,
                       "dept_choices": ClearanceItem.CLEARANCE_DEPT_CHOICES,
                       "cases": SeparationCase.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-created_at")},
    )


@login_required
def clearanceitem_create(request):
    return _offboarding_create(
        request, ClearanceItemForm, "hrm/offboarding/clearanceitem/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def clearanceitem_detail(request, pk):
    obj = get_object_or_404(
        ClearanceItem.objects.select_related(
            "case__employee__party", "assigned_to", "cleared_by", "asset_allocation"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/clearanceitem/detail.html", {"obj": obj})


@login_required
def clearanceitem_edit(request, pk):
    obj = get_object_or_404(ClearanceItem, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "Only a pending clearance item can be edited.")
        return redirect("hrm:clearanceitem_detail", pk=obj.pk)
    return crud_edit(request, model=ClearanceItem, pk=pk, form_class=ClearanceItemForm,
                     template="hrm/offboarding/clearanceitem/form.html",
                     success_url="hrm:clearanceitem_list")


@login_required
@require_POST
def clearanceitem_delete(request, pk):
    obj = get_object_or_404(ClearanceItem, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending clearance item can be deleted.")
        return redirect("hrm:clearanceitem_detail", pk=obj.pk)
    case_id = obj.case_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Clearance item deleted.")
    return redirect("hrm:separationcase_detail", pk=case_id)


@tenant_admin_required  # resolving a clearance line gates the case — privileged HR action (no
@require_POST           # per-department role yet, so admin-only mirrors clearanceitem_reject)
def clearanceitem_mark_cleared(request, pk):
    obj = get_object_or_404(
        ClearanceItem.objects.select_related("case", "asset_allocation"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        with transaction.atomic():
            obj.status = "cleared"
            obj.cleared_by = request.user
            obj.cleared_at = timezone.now()
            obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
            # Returning the linked asset is part of clearing its line — keep the two in one txn.
            # Only return an asset that actually belongs to this case's employee (guard against a
            # mis-linked allocation from another employee being silently marked returned).
            returned = None
            if (obj.asset_allocation_id and obj.asset_allocation.status == "issued"
                    and obj.asset_allocation.employee_id == obj.case.employee_id):
                obj.asset_allocation.status = "returned"
                obj.asset_allocation.returned_at = timezone.now()
                obj.asset_allocation.save(update_fields=["status", "returned_at", "updated_at"])
                returned = obj.asset_allocation.number
        write_audit_log(request.user, obj, "update",
                        {"action": "mark_cleared", "asset_returned": returned})
        messages.success(request, "Clearance item cleared."
                         + (f" Asset {returned} returned." if returned else ""))
    else:
        messages.error(request, "This clearance item cannot be cleared in its current state.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)


@tenant_admin_required  # marking a clearance line N/A also gates the case — privileged HR action
@require_POST
def clearanceitem_mark_na(request, pk):
    obj = get_object_or_404(ClearanceItem.objects.select_related("case"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        obj.status = "not_applicable"
        obj.cleared_by = request.user
        obj.cleared_at = timezone.now()
        obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_na"})
        messages.success(request, "Clearance item marked not applicable.")
    else:
        messages.error(request, "This clearance item cannot be changed in its current state.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)


@tenant_admin_required  # rejecting a clearance line is a privileged action (blocks the gate)
@require_POST
def clearanceitem_reject(request, pk):
    obj = get_object_or_404(ClearanceItem.objects.select_related("case"), pk=pk, tenant=request.tenant)
    # Only an open line can be rejected (failed clearance) — a resolved one stays resolved.
    if obj.status in ("pending", "in_progress"):
        obj.status = "rejected"
        obj.cleared_by = None
        obj.cleared_at = None
        obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Clearance item rejected.")
    else:
        messages.error(request, "Only a pending or in-progress clearance item can be rejected.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)
