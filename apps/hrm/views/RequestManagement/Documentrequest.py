"""HRM 3.26 Request Management — Documentrequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit
from apps.hrm.models import (
    DocumentRequest,
)
from apps.hrm.forms import (
    DocumentFulfillForm,
    DocumentRequestForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_detail, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_approve, _hr_request_cancel, _hr_request_delete, _hr_request_edit, _hr_request_reject, _hr_request_submit


# ---- Document Requests ----------------------------------------------------------------------
@login_required
def documentrequest_list(request):
    qs = _ss_scope(request, DocumentRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": DocumentRequest.STATUS_CHOICES,
             "document_type_choices": DocumentRequest.DOCUMENT_TYPE_CHOICES}
    filters = [("status", "status", False), ("document_type", "document_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/documentrequest/list.html",
                     search_fields=("number", "purpose", "addressed_to", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def documentrequest_create(request):
    return _ss_child_create(request, DocumentRequestForm,
                            "hrm/requests/documentrequest/form.html", "hrm:documentrequest_list")


@login_required
def documentrequest_detail(request, pk):
    return _ss_child_detail(request, DocumentRequest, pk, "hrm/requests/documentrequest/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def documentrequest_edit(request, pk):
    return _hr_request_edit(request, DocumentRequest, pk, DocumentRequestForm,
                            "hrm/requests/documentrequest/form.html", "hrm:documentrequest_detail")


@login_required
@require_POST
def documentrequest_delete(request, pk):
    return _hr_request_delete(request, DocumentRequest, pk, "hrm:documentrequest_list")


@login_required
@require_POST
def documentrequest_submit(request, pk):
    return _hr_request_submit(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@login_required
@require_POST
def documentrequest_cancel(request, pk):
    return _hr_request_cancel(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_approve(request, pk):
    return _hr_request_approve(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_reject(request, pk):
    return _hr_request_reject(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_fulfill(request, pk):
    """approved -> fulfilled; optionally attach the signed letter (validated by DocumentFulfillForm)."""
    obj = get_object_or_404(DocumentRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be fulfilled.")
        return redirect("hrm:documentrequest_detail", pk=obj.pk)
    form = DocumentFulfillForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("output_file", ["Invalid upload."])))
        return redirect("hrm:documentrequest_detail", pk=obj.pk)
    obj.status = "fulfilled"
    obj.fulfilled_at = timezone.now()
    update_fields = ["status", "fulfilled_at", "updated_at"]
    uploaded = form.cleaned_data.get("output_file")
    if uploaded:
        obj.output_file = uploaded
        update_fields.append("output_file")
    obj.save(update_fields=update_fields)
    write_audit_log(request.user, obj, "update", {"action": "fulfill"})
    messages.success(request, f"Document request {obj.number} marked fulfilled.")
    return redirect("hrm:documentrequest_detail", pk=obj.pk)
