"""HRM 3.26 Request Management — Suggestions views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_reject, _hr_request_submit
from apps.hrm.models import (
    Suggestion,
)
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_reject, _hr_request_submit


@login_required
@require_POST
def suggestion_delete(request, pk):
    return _hr_request_delete(request, Suggestion, pk, "hrm:suggestion_list")


@login_required
@require_POST
def suggestion_submit(request, pk):
    return _hr_request_submit(request, Suggestion, pk, "hrm:suggestion_detail")


@login_required
@require_POST
def suggestion_cancel(request, pk):
    return _hr_request_cancel(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_approve(request, pk):
    return _hr_request_approve(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_reject(request, pk):
    return _hr_request_reject(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_implement(request, pk):
    """approved -> implemented; stamps implemented_at + an optional implementation_note."""
    obj = get_object_or_404(Suggestion, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an accepted suggestion can be marked implemented.")
        return redirect("hrm:suggestion_detail", pk=obj.pk)
    obj.status = "implemented"
    obj.implemented_at = timezone.now()
    obj.implementation_note = (request.POST.get("implementation_note") or "").strip()[:2000]
    obj.save(update_fields=["status", "implemented_at", "implementation_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "implement"})
    messages.success(request, f"Suggestion {obj.number} marked implemented.")
    return redirect("hrm:suggestion_detail", pk=obj.pk)
