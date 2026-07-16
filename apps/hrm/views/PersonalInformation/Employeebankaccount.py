"""HRM 3.25 Personal Information — Employeebankaccount views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope
from apps.hrm.models import (
    EmployeeBankAccount,
)
from apps.hrm.forms import (
    EmployeeBankAccountForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_delete, _ss_child_detail, _ss_child_edit, _ss_employees, _ss_scope


# ---------------------------------------------------------------- Bank Accounts (admin-gated writes)
@login_required
def employeebankaccount_list(request):
    qs = _ss_scope(request, EmployeeBankAccount.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "verification_status_choices": EmployeeBankAccount.VERIFICATION_STATUS_CHOICES,
             "account_type_choices": EmployeeBankAccount.ACCOUNT_TYPE_CHOICES,
             "status_choices": EmployeeBankAccount.STATUS_CHOICES}
    filters = [("verification_status", "verification_status", False),
               ("account_type", "account_type", False),
               ("status", "status", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/employeebankaccount/list.html",
                     search_fields=("bank_name", "account_holder_name", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def employeebankaccount_detail(request, pk):
    return _ss_child_detail(request, EmployeeBankAccount, pk,
                            "hrm/selfservice/employeebankaccount/detail.html", select_related=("employee__party",))


@tenant_admin_required
def employeebankaccount_create(request):
    return _ss_child_create(request, EmployeeBankAccountForm,
                            "hrm/selfservice/employeebankaccount/form.html", "hrm:employeebankaccount_list")


@tenant_admin_required
def employeebankaccount_edit(request, pk):
    return _ss_child_edit(request, EmployeeBankAccount, pk, EmployeeBankAccountForm,
                          "hrm/selfservice/employeebankaccount/form.html", "hrm:employeebankaccount_detail")


@tenant_admin_required
@require_POST
def employeebankaccount_delete(request, pk):
    return _ss_child_delete(request, EmployeeBankAccount, pk, "hrm:employeebankaccount_list")


@tenant_admin_required
@require_POST
def employeebankaccount_verify(request, pk):
    obj = get_object_or_404(EmployeeBankAccount, pk=pk, tenant=request.tenant)
    if obj.verification_status == "pending":
        obj.verification_status = "verified"
        obj.save(update_fields=["verification_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "verify"})
        messages.success(request, "Bank account verified.")
    else:
        messages.error(request, "Only a pending account can be verified.")
    return redirect("hrm:employeebankaccount_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def employeebankaccount_reject(request, pk):
    obj = get_object_or_404(EmployeeBankAccount, pk=pk, tenant=request.tenant)
    if obj.verification_status in ("pending", "verified"):
        obj.verification_status = "rejected"
        obj.save(update_fields=["verification_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Bank account rejected.")
    else:
        messages.error(request, "This account is already rejected.")
    return redirect("hrm:employeebankaccount_detail", pk=obj.pk)
