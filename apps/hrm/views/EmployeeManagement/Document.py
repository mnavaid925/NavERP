"""HRM 3.1 Employee Management — Document views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeManagement._helpers import _employee_child_create, _is_hr_admin
from apps.hrm.models import (
    EmployeeDocument,
    EmployeeProfile,
)
from apps.hrm.forms import (
    EmployeeDocumentForm,
)
from apps.hrm.views.EmployeeManagement._helpers import _employee_child_create, _is_hr_admin


# ---------------------------------------------------------- Employee Documents (3.1)
@login_required
def employee_document_list(request):
    qs = EmployeeDocument.objects.filter(tenant=request.tenant).select_related("employee__party")
    # Confidential documents are visible only to tenant admins.
    if not _is_hr_admin(request.user):
        qs = qs.exclude(is_confidential=True)
    return crud_list(
        request,
        qs,
        "hrm/employee/document/list.html",
        search_fields=["number", "title", "document_number", "employee__party__name"],
        filters=[("document_type", "document_type", False),
                 ("verification_status", "verification_status", False),
                 ("employee", "employee_id", True)],
        extra_context={"document_type_choices": EmployeeDocument.DOCUMENT_TYPE_CHOICES,
                       "verification_status_choices": EmployeeDocument.VERIFICATION_STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def employee_document_create(request):
    return _employee_child_create(request, EmployeeDocumentForm, "hrm/employee/document/form.html")


@login_required
def employee_document_detail(request, pk):
    obj = get_object_or_404(
        EmployeeDocument.objects.select_related("employee__party", "verified_by"),
        pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    return render(request, "hrm/employee/document/detail.html", {"obj": obj})


@login_required
def employee_document_edit(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    # A verified document is locked — reject it first to re-open for editing.
    if obj.verification_status == "verified":
        messages.error(request, "A verified document cannot be edited. Reject it first.")
        return redirect("hrm:employee_document_detail", pk=obj.pk)
    return crud_edit(request, model=EmployeeDocument, pk=pk, form_class=EmployeeDocumentForm,
                     template="hrm/employee/document/form.html", success_url="hrm:employee_document_list")


@login_required
@require_POST
def employee_document_delete(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    if obj.verification_status == "verified":
        messages.error(request, "A verified document cannot be deleted. Reject it first.")
        return redirect("hrm:employee_document_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Document deleted.")
    return redirect("hrm:employee_document_list")


@tenant_admin_required  # verifying a personnel document is a privileged HR action
@require_POST
def employee_document_mark_verified(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.verification_status == "pending":
        obj.verification_status = "verified"
        obj.verified_by = request.user
        obj.verified_at = timezone.now()
        obj.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_verified"})
        messages.success(request, f"Document {obj.number} verified.")
    else:
        messages.error(request, "Only a pending document can be verified.")
    return redirect("hrm:employee_document_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def employee_document_reject(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.verification_status in ("pending", "verified"):
        obj.verification_status = "rejected"
        obj.verified_by = None
        obj.verified_at = None
        obj.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Document {obj.number} rejected.")
    else:
        messages.error(request, "This document is already rejected.")
    return redirect("hrm:employee_document_detail", pk=obj.pk)
