"""HRM 3.26 Request Management — Idcardrequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit
from apps.hrm.models import (
    IdCardRequest,
)
from apps.hrm.forms import (
    IdCardRequestForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_detail, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit


# ---- ID Card Requests -----------------------------------------------------------------------
@login_required
def idcardrequest_list(request):
    qs = _ss_scope(request, IdCardRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": IdCardRequest.STATUS_CHOICES,
             "request_type_choices": IdCardRequest.REQUEST_TYPE_CHOICES,
             "reason_type_choices": IdCardRequest.REASON_TYPE_CHOICES}
    filters = [("status", "status", False), ("request_type", "request_type", False),
               ("reason_type", "reason_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/idcardrequest/list.html",
                     search_fields=("number", "reason", "delivery_location", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def idcardrequest_create(request):
    return _ss_child_create(request, IdCardRequestForm,
                            "hrm/requests/idcardrequest/form.html", "hrm:idcardrequest_list")


@login_required
def idcardrequest_detail(request, pk):
    return _ss_child_detail(request, IdCardRequest, pk, "hrm/requests/idcardrequest/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def idcardrequest_edit(request, pk):
    return _hr_request_edit(request, IdCardRequest, pk, IdCardRequestForm,
                            "hrm/requests/idcardrequest/form.html", "hrm:idcardrequest_detail")


@login_required
@require_POST
def idcardrequest_delete(request, pk):
    return _hr_request_delete(request, IdCardRequest, pk, "hrm:idcardrequest_list")


@login_required
@require_POST
def idcardrequest_submit(request, pk):
    return _hr_request_submit(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@login_required
@require_POST
def idcardrequest_cancel(request, pk):
    return _hr_request_cancel(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_approve(request, pk):
    return _hr_request_approve(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_reject(request, pk):
    return _hr_request_reject(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_issue(request, pk):
    """approved -> issued; requires a non-blank card_number (stamped with issued_at)."""
    obj = get_object_or_404(IdCardRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be issued.")
        return redirect("hrm:idcardrequest_detail", pk=obj.pk)
    card_number = (request.POST.get("card_number") or "").strip()
    if not card_number:
        messages.error(request, "A card number is required to issue the ID card.")
        return redirect("hrm:idcardrequest_detail", pk=obj.pk)
    obj.status = "issued"
    obj.card_number = card_number[:100]
    obj.issued_at = timezone.now()
    obj.save(update_fields=["status", "card_number", "issued_at", "updated_at"])
    # Don't copy the badge/card number into the audit metadata — it's already stored on the row and
    # is the kind of physical-access identifier the codebase redacts elsewhere (_SENSITIVE_AUDIT_FIELDS).
    write_audit_log(request.user, obj, "update", {"action": "issue"})
    messages.success(request, f"ID card request {obj.number} issued (card {obj.card_number}).")
    return redirect("hrm:idcardrequest_detail", pk=obj.pk)
