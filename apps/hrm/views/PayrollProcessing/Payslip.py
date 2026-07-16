"""HRM 3.14 Payroll Processing — Payslip views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayrollCycle,
    Payslip,
)
from apps.hrm.forms import (
    PayslipForm,
)


# ------------------------------------------------------------ Payslips (3.14)
@login_required
def payslip_list(request):
    qs = Payslip.objects.filter(tenant=request.tenant).select_related("employee__party", "cycle")
    on_hold = request.GET.get("on_hold", "").strip()
    if on_hold in ("True", "False"):
        qs = qs.filter(on_hold=(on_hold == "True"))
    return crud_list(
        request, qs, "hrm/payroll/payslip/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("cycle", "cycle_id", True)],
        extra_context={"cycles": PayrollCycle.objects.filter(tenant=request.tenant)},
    )


@login_required
def payslip_detail(request, pk):
    obj = get_object_or_404(
        Payslip.objects.select_related("employee__party", "cycle", "salary_structure"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/payroll/payslip/detail.html", {"obj": obj, "lines": obj.lines.all()})


@login_required
def payslip_edit(request, pk):
    # select_related the structure+template too so the recompute() after save() doesn't re-fetch them.
    obj = get_object_or_404(
        Payslip.objects.select_related("cycle", "salary_structure__template"), pk=pk, tenant=request.tenant)
    # Payslip inputs are editable only while the cycle is a draft; recompute after every change.
    if obj.cycle.status != "draft":
        messages.error(request, "A payslip can only be edited while its cycle is a draft.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    if request.method == "POST":
        form = PayslipForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            obj.recompute()
            write_audit_log(request.user, obj, "update", {"action": "edit"})
            messages.success(request, "Payslip updated.")
            return redirect("hrm:payslip_detail", pk=obj.pk)
    else:
        form = PayslipForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/payroll/payslip/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # holding an employee's pay is a privileged action
@require_POST
def payslip_hold(request, pk):
    obj = get_object_or_404(Payslip.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if obj.cycle.is_locked:
        messages.error(request, "A locked cycle's payslips cannot be held.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    obj.on_hold = True
    obj.hold_reason = request.POST.get("hold_reason", "").strip()[:2000]
    obj.save(update_fields=["on_hold", "hold_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    messages.success(request, "Payslip put on hold.")
    return redirect("hrm:payslip_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def payslip_release(request, pk):
    obj = get_object_or_404(Payslip.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if obj.cycle.is_locked:
        messages.error(request, "A locked cycle's payslips cannot be modified.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    obj.on_hold = False
    obj.released_at = timezone.now()
    obj.save(update_fields=["on_hold", "released_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "release"})
    messages.success(request, "Payslip hold released.")
    return redirect("hrm:payslip_detail", pk=obj.pk)
