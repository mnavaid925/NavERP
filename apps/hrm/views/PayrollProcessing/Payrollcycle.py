"""HRM 3.14 Payroll Processing — Payrollcycle views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeSalaryStructure,
    PayrollCycle,
    Payslip,
    PayslipLine,
)
from apps.hrm.forms import (
    PayrollCycleForm,
)


# ============================================================ Payroll Cycles (3.14)
@login_required
def payrollcycle_list(request):
    return crud_list(
        request,
        PayrollCycle.objects.filter(tenant=request.tenant),
        "hrm/payroll/payrollcycle/list.html",
        search_fields=["number", "notes"],
        filters=[("status", "status", False), ("cycle_type", "cycle_type", False)],
        extra_context={
            "status_choices": PayrollCycle.STATUS_CHOICES,
            "cycle_type_choices": PayrollCycle.CYCLE_TYPE_CHOICES,
        },
    )


@login_required
def payrollcycle_create(request):
    return crud_create(request, form_class=PayrollCycleForm,
                       template="hrm/payroll/payrollcycle/form.html", success_url="hrm:payrollcycle_list")


@login_required
def payrollcycle_detail(request, pk):
    obj = get_object_or_404(
        PayrollCycle.objects.select_related("accounting_payroll_run", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant)
    payslips = obj.payslips.select_related("employee__party").order_by("employee__party__name")
    return render(request, "hrm/payroll/payrollcycle/detail.html", {
        "obj": obj,
        "payslips": payslips,
        # one aggregate query for the three totals shown on the summary panel
        "totals": obj.payslips.aggregate(g=Sum("gross_pay"), d=Sum("total_deductions"), n=Sum("net_pay")),
    })


@login_required
def payrollcycle_edit(request, pk):
    obj = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    # Only a draft cycle's header is editable; once submitted/approved/locked it's read-only.
    if obj.status != "draft":
        messages.error(request, "Only a draft payroll cycle can be edited.")
        return redirect("hrm:payrollcycle_detail", pk=obj.pk)
    return crud_edit(request, model=PayrollCycle, pk=pk, form_class=PayrollCycleForm,
                     template="hrm/payroll/payrollcycle/form.html", success_url="hrm:payrollcycle_list")


@login_required
@require_POST
def payrollcycle_delete(request, pk):
    obj = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "A locked payroll cycle cannot be deleted.")
        return redirect("hrm:payrollcycle_detail", pk=obj.pk)
    return crud_delete(request, model=PayrollCycle, pk=pk, success_url="hrm:payrollcycle_list")


@login_required
@require_POST
def payrollcycle_generate(request, pk):
    """(Re)generate payslips for every employee with an active salary structure — draft cycles only."""
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status != "draft":
        messages.error(request, "Payslips can only be (re)generated while the cycle is a draft.")
        return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
    days_in = ((cycle.period_end - cycle.period_start).days + 1
               if cycle.period_end and cycle.period_start else 30)
    with transaction.atomic():
        # Preserve HR manual inputs (arrears/bonus/hold/days/lop) across a re-generate, keyed by employee.
        preserved = {p.employee_id: p for p in cycle.payslips.all()}
        cycle.payslips.all().delete()  # safe re-run while draft (cascades the lines)
        structures = (EmployeeSalaryStructure.objects
                      .filter(tenant=request.tenant, status="active", effective_from__lte=cycle.period_end)
                      .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=cycle.period_start))
                      .select_related("employee__party", "template"))
        count = 0
        for structure in structures:
            prev = preserved.get(structure.employee_id)
            payslip = Payslip.objects.create(
                tenant=request.tenant, cycle=cycle, employee=structure.employee,
                salary_structure=structure, days_in_period=days_in,
                days_worked=min(prev.days_worked, days_in) if prev else days_in,
                lop_days=prev.lop_days if prev else Decimal("0"),
                arrears_amount=prev.arrears_amount if prev else Decimal("0"),
                bonus_amount=prev.bonus_amount if prev else Decimal("0"),
                on_hold=prev.on_hold if prev else False,
                hold_reason=prev.hold_reason if prev else "")
            payslip.recompute()
            count += 1
    write_audit_log(request.user, cycle, "update", {"action": "generate", "headcount": count})
    messages.success(request, f"Generated {count} payslip(s) for {cycle.number}.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@login_required
@require_POST
def payrollcycle_submit(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "draft":
        if not cycle.payslips.exists():
            messages.error(request, "Generate payslips before submitting the cycle.")
            return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
        # Off-cycle / bonus runs skip the approval step and go straight to approved (Gusto convention);
        # locking is always a separate explicit action, never implicit.
        cycle.status = "approved" if cycle.cycle_type != "regular" else "pending_approval"
        cycle.submitted_by = request.user
        cycle.submitted_at = timezone.now()
        cycle.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "submit", "to": cycle.status})
        messages.success(request, f"Cycle {cycle.number} submitted ({cycle.get_status_display()}).")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required  # approving payroll is a privileged finance/admin action
@require_POST
def payrollcycle_approve(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "pending_approval":
        cycle.status = "approved"
        cycle.approved_by = request.user
        cycle.approved_at = timezone.now()
        cycle.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "approve"})
        messages.success(request, f"Cycle {cycle.number} approved.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required
@require_POST
def payrollcycle_reject(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "pending_approval":
        cycle.status = "rejected"
        cycle.approved_by = request.user
        cycle.rejection_reason = request.POST.get("rejection_reason", "").strip()[:2000]
        cycle.save(update_fields=["status", "approved_by", "rejection_reason", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "reject"})
        messages.success(request, f"Cycle {cycle.number} rejected.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required
@require_POST
def payrollcycle_lock(request, pk):
    """Lock an approved cycle and hand the rolled-up totals to accounting: create an
    ``accounting.PayrollRun`` (draft) for the GL. HRM NEVER builds a JournalEntry (L29) — accounting's
    own ``payroll_run_post`` posts the balanced entry from that row."""
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status != "approved":
        messages.error(request, "Only an approved cycle can be locked.")
        return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
    # Lazy import keeps accounting a runtime (not module-load) dependency.
    from apps.accounting.models import PayrollRun as AccountingPayrollRun
    lines = PayslipLine.objects.filter(payslip__cycle=cycle)

    def _sum(qs):
        return qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    gross = cycle.payslips.aggregate(s=Sum("gross_pay"))["s"] or Decimal("0")
    statutory = lines.filter(component_type="statutory_deduction")
    # Mirror recompute()'s bucketing exactly — only employer-side is excluded from net; employee/both/
    # blank all reduce net — so the accounting run's derived net_pay reconciles with Σ payslip.net_pay.
    employee_tax = _sum(statutory.exclude(contribution_side="employer"))
    employer_tax = _sum(statutory.filter(contribution_side="employer"))
    deductions = _sum(lines.filter(component_type="voluntary_deduction").exclude(contribution_side="employer"))
    with transaction.atomic():
        run = AccountingPayrollRun.objects.create(
            tenant=request.tenant, period_start=cycle.period_start, period_end=cycle.period_end,
            pay_date=cycle.pay_date, headcount=cycle.payslips.count(),
            gross_wages=gross, employee_tax=employee_tax, employer_tax=employer_tax,
            benefits=Decimal("0"), deductions=deductions)
        cycle.accounting_payroll_run = run
        cycle.status = "locked"
        cycle.save(update_fields=["accounting_payroll_run", "status", "updated_at"])
    write_audit_log(request.user, cycle, "update",
                    {"action": "lock", "accounting_payroll_run": run.number})
    messages.success(request, f"Cycle {cycle.number} locked — created accounting run {run.number}. "
                              f"Post it from Accounting → Payroll to generate the GL entry.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
