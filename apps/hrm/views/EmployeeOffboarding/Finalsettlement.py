"""HRM 3.4 Employee Offboarding — Finalsettlement views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create
from apps.hrm.models import (
    FinalSettlement,
)
from apps.hrm.forms import (
    FinalSettlementForm,
)
from apps.hrm.views.EmployeeOffboarding._helpers import _offboarding_create


# ---------------------------------------------------------- Final Settlements (3.4)
@login_required
def finalsettlement_list(request):
    return crud_list(
        request,
        FinalSettlement.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party"),
        "hrm/offboarding/finalsettlement/list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": FinalSettlement.FNF_STATUS_CHOICES},
    )


@login_required
def finalsettlement_create(request):
    return _offboarding_create(
        request, FinalSettlementForm, "hrm/offboarding/finalsettlement/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def finalsettlement_detail(request, pk):
    obj = get_object_or_404(
        FinalSettlement.objects.select_related("case__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/finalsettlement/detail.html", {"obj": obj})


@login_required
def finalsettlement_edit(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "computed"):
        messages.error(request, "Only a draft or computed settlement can be edited.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    return crud_edit(request, model=FinalSettlement, pk=pk, form_class=FinalSettlementForm,
                     template="hrm/offboarding/finalsettlement/form.html",
                     success_url="hrm:finalsettlement_list")


@login_required
@require_POST
def finalsettlement_delete(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft settlement can be deleted.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Settlement deleted.")
    return redirect("hrm:finalsettlement_list")


@tenant_admin_required  # computing F&F (pulling leave/gratuity) is a privileged HR/finance action
@require_POST
def finalsettlement_compute(request, pk):
    obj = get_object_or_404(
        FinalSettlement.objects.select_related("case__employee__designation",
                                               "case__employee__employment"),
        pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft settlement can be computed.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    employee = obj.case.employee
    days, amount = compute_leave_encashment(employee)
    obj.leave_encashment_days = days
    obj.leave_encashment_amount = amount
    # Gratuity: ≥5 years of service (best-effort from employment.hired_on + designation band).
    employment = employee.employment if employee.employment_id else None
    if (employment and employment.hired_on and employee.designation_id
            and employee.designation and employee.designation.min_salary):
        years = (timezone.localdate() - employment.hired_on).days / 365.25
        if years >= 5:
            obj.gratuity_eligible = True
            basic = employee.designation.min_salary
            obj.gratuity_amount = (basic * Decimal("15") * Decimal(str(round(years, 2)))
                                   / Decimal("26")).quantize(Decimal("0.01"))
    obj.status = "computed"
    obj.save(update_fields=["leave_encashment_days", "leave_encashment_amount",
                            "gratuity_eligible", "gratuity_amount", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "compute"})
    messages.success(request, f"Settlement {obj.number} computed — net payable {obj.net_payable}.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_hr_approve(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    # Require a computed settlement — approving a raw draft would formally rubber-stamp un-computed
    # (often zero) leave-encashment/gratuity figures. Run Compute first (then edit other lines).
    if obj.status == "computed":
        obj.status = "hr_approved"
        obj.hr_approved_by = request.user
        obj.hr_approved_at = timezone.now()
        obj.save(update_fields=["status", "hr_approved_by", "hr_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "hr_approve"})
        messages.success(request, f"Settlement {obj.number} HR-approved.")
    else:
        messages.error(request, "Run Compute first — only a computed settlement can be HR-approved.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_finance_approve(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status == "hr_approved":
        obj.status = "finance_approved"
        obj.finance_approved_by = request.user
        obj.finance_approved_at = timezone.now()
        obj.save(update_fields=["status", "finance_approved_by", "finance_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "finance_approve"})
        messages.success(request, f"Settlement {obj.number} finance-approved.")
    else:
        messages.error(request, "Only an HR-approved settlement can be finance-approved.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_mark_paid(request, pk):
    obj = get_object_or_404(FinalSettlement.objects.select_related("case"), pk=pk, tenant=request.tenant)
    if obj.status in ("hr_approved", "finance_approved"):
        with transaction.atomic():
            obj.status = "paid"
            obj.paid_at = timezone.localdate()
            obj.save(update_fields=["status", "paid_at", "updated_at"])
            # Mark the parent case settled once its F&F is paid (only advances from 'cleared').
            case = obj.case
            if case.status == "cleared":
                case.status = "settled"
                case.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, case, "update",
                                {"action": "settled_via_fnf", "settlement": obj.number})
            write_audit_log(request.user, obj, "update", {"action": "mark_paid"})
        messages.success(request, f"Settlement {obj.number} marked paid.")
    else:
        messages.error(request, "Only an approved settlement can be marked paid.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)
