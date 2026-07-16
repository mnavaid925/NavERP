"""HRM 3.26 Request Management — Assetrequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit
from apps.hrm.models import (
    AssetAllocation,
    AssetRequest,
)
from apps.hrm.forms import (
    AssetRequestForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_detail, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit


# ---- Asset Requests -------------------------------------------------------------------------
@login_required
def assetrequest_list(request):
    qs = _ss_scope(request, AssetRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": AssetRequest.STATUS_CHOICES,
             "asset_category_choices": AssetAllocation.ASSET_CATEGORY_CHOICES,
             "priority_choices": AssetRequest.PRIORITY_CHOICES}
    filters = [("status", "status", False), ("asset_category", "asset_category", False),
               ("priority", "priority", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/assetrequest/list.html",
                     search_fields=("number", "asset_name", "justification", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def assetrequest_create(request):
    return _ss_child_create(request, AssetRequestForm,
                            "hrm/requests/assetrequest/form.html", "hrm:assetrequest_list")


@login_required
def assetrequest_detail(request, pk):
    return _ss_child_detail(request, AssetRequest, pk, "hrm/requests/assetrequest/detail.html",
                            select_related=("employee__party", "approver", "allocation"))


@login_required
def assetrequest_edit(request, pk):
    return _hr_request_edit(request, AssetRequest, pk, AssetRequestForm,
                            "hrm/requests/assetrequest/form.html", "hrm:assetrequest_detail")


@login_required
@require_POST
def assetrequest_delete(request, pk):
    return _hr_request_delete(request, AssetRequest, pk, "hrm:assetrequest_list")


@login_required
@require_POST
def assetrequest_submit(request, pk):
    return _hr_request_submit(request, AssetRequest, pk, "hrm:assetrequest_detail")


@login_required
@require_POST
def assetrequest_cancel(request, pk):
    return _hr_request_cancel(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_approve(request, pk):
    return _hr_request_approve(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_reject(request, pk):
    return _hr_request_reject(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_fulfill(request, pk):
    """approved -> fulfilled; create + link an AssetAllocation (program=None) inside one atomic txn
    so the request and its issued allocation are written together (never a half-fulfilled request)."""
    obj = get_object_or_404(AssetRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be fulfilled.")
        return redirect("hrm:assetrequest_detail", pk=obj.pk)
    with transaction.atomic():
        allocation = AssetAllocation.objects.create(
            tenant=request.tenant, program=None, employee=obj.employee,
            asset_name=obj.asset_name, asset_category=obj.asset_category,
            status="issued", issued_at=timezone.now(), issued_by=request.user,
            serial_number=(request.POST.get("serial_number") or "").strip()[:100],
            asset_tag=(request.POST.get("asset_tag") or "").strip()[:100])
        obj.allocation = allocation
        obj.status = "fulfilled"
        obj.save(update_fields=["allocation", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "fulfill", "allocation": allocation.number})
    messages.success(request, f"Asset request {obj.number} fulfilled — issued {allocation.number}.")
    return redirect("hrm:assetrequest_detail", pk=obj.pk)
