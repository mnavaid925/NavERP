"""HRM 3.15 Statutory Compliance — Statutoryreturn views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    StatutoryReturn,
)
from apps.hrm.forms import (
    StatutoryReturnForm,
)


# ------------------------------------------------- StatutoryReturn (register/challan)
@login_required
def statutoryreturn_list(request):
    # No select_related — the list template renders only scalar fields (scheme/period/totals/status/
    # due_date), never obj.cycle or obj.employee, so joining them would be dead over-fetch.
    qs = StatutoryReturn.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "hrm/statutory/statutoryreturn/list.html",
        search_fields=["number", "registration_number_used", "notes"],
        filters=[("scheme", "scheme", False), ("status", "status", False),
                 ("period_type", "period_type", False)],
        extra_context={
            "scheme_choices": StatutoryReturn.SCHEME_CHOICES,
            "status_choices": StatutoryReturn.STATUS_CHOICES,
            "period_type_choices": StatutoryReturn.PERIOD_TYPE_CHOICES,
        },
    )


@login_required
def statutoryreturn_create(request):
    return crud_create(request, form_class=StatutoryReturnForm,
                       template="hrm/statutory/statutoryreturn/form.html",
                       success_url="hrm:statutoryreturn_list")


@login_required
def statutoryreturn_detail(request, pk):
    return crud_detail(request, model=StatutoryReturn, pk=pk,
                       template="hrm/statutory/statutoryreturn/detail.html",
                       select_related=("cycle", "employee__party"))


@login_required
def statutoryreturn_edit(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be edited.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    return crud_edit(request, model=StatutoryReturn, pk=pk, form_class=StatutoryReturnForm,
                     template="hrm/statutory/statutoryreturn/form.html",
                     success_url="hrm:statutoryreturn_list")


@login_required
@require_POST
def statutoryreturn_delete(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be deleted.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    return crud_delete(request, model=StatutoryReturn, pk=pk, success_url="hrm:statutoryreturn_list")


@tenant_admin_required  # aggregating/filing statutory returns is a privileged finance action
@require_POST
def statutoryreturn_generate(request, pk):
    """(Re)aggregate the return's contribution totals from the period's PayslipLine rows — the key
    domain action (mirrors payrollcycle_generate: create the metadata, then generate from payroll).
    Only a pending return can be re-aggregated; the model's recompute() does the roll-up."""
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be (re)aggregated.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.recompute()
    write_audit_log(request.user, obj, "update", {
        "action": "generate", "headcount": obj.headcount,
        "employee_total": str(obj.employee_contribution_total),
        "employer_total": str(obj.employer_contribution_total)})
    messages.success(request,
        f"Aggregated {obj.get_scheme_display()} return {obj.number}: employee "
        f"{obj.employee_contribution_total}, employer {obj.employer_contribution_total}, "
        f"headcount {obj.headcount}.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def statutoryreturn_mark_filed(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending return can be marked filed.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.status = "filed"
    obj.filed_on = timezone.localdate()
    obj.save(update_fields=["status", "filed_on", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_filed"})
    messages.success(request, f"Return {obj.number} marked filed.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def statutoryreturn_mark_paid(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "filed"):
        messages.error(request, "Only a pending or filed return can be marked paid.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.paid_on = timezone.localdate()
    obj.payment_reference = request.POST.get("payment_reference", "").strip()[:100]
    # Paid after the due date → recorded as Late, not Paid (RazorpayX/saral PayPack convention).
    obj.status = "late" if (obj.due_date and obj.paid_on > obj.due_date) else "paid"
    obj.save(update_fields=["status", "paid_on", "payment_reference", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_paid", "status": obj.status})
    messages.success(request, f"Return {obj.number} marked {obj.get_status_display()}.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
