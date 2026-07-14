"""Accounting 2.8 Payroll Integration — PayrollRuns views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _post_journal_entry
from apps.accounting.models import (
    PayrollRun,
    ZERO,
)
from apps.accounting.forms import (
    PayrollRunForm,
)


# ============================================================= 2.8 Payroll
@login_required
def payroll_run_list(request):
    return crud_list(
        request, PayrollRun.objects.filter(tenant=request.tenant),
        "accounting/payroll/run/list.html",
        search_fields=["number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": PayrollRun.STATUS_CHOICES},
    )


@login_required
def payroll_run_create(request):
    return crud_create(request, form_class=PayrollRunForm, template="accounting/payroll/run/form.html",
                       success_url="accounting:payroll_run_list")


@login_required
def payroll_run_detail(request, pk):
    obj = get_object_or_404(PayrollRun.objects.select_related("journal_entry"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/payroll/run/detail.html", {"obj": obj})


@login_required
def payroll_run_edit(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk, tenant=request.tenant)
    if run.is_locked:
        messages.error(request, "A posted payroll run cannot be edited.")
        return redirect("accounting:payroll_run_detail", pk=pk)
    return crud_edit(request, model=PayrollRun, pk=pk, form_class=PayrollRunForm,
                     template="accounting/payroll/run/form.html", success_url="accounting:payroll_run_list")


@login_required
@require_POST
def payroll_run_delete(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk, tenant=request.tenant)
    if run.is_locked:
        messages.error(request, "A posted payroll run cannot be deleted.")
        return redirect("accounting:payroll_run_detail", pk=pk)
    return crud_delete(request, model=PayrollRun, pk=pk, success_url="accounting:payroll_run_list")


@tenant_admin_required
@require_POST
def payroll_run_post(request, pk):
    run = get_object_or_404(PayrollRun, pk=pk, tenant=request.tenant)
    if run.is_locked:
        messages.error(request, "This payroll run is already posted.")
        return redirect("accounting:payroll_run_detail", pk=pk)
    wages_exp = _first_account(request.tenant, "expense", "6100") or _first_account(request.tenant, "expense")
    cash = _first_account(request.tenant, "asset", "1000") or _first_account(request.tenant, "asset")
    tax_payable = _first_account(request.tenant, "liability", "2200") or _first_account(request.tenant, "liability")
    ded_payable = _first_account(request.tenant, "liability", "2100") or tax_payable
    if not (wages_exp and cash and tax_payable):
        messages.error(request, "Configure wage-expense, cash and tax-payable accounts before posting payroll.")
        return redirect("accounting:payroll_run_detail", pk=pk)
    legs = [
        (wages_exp, run.total_expense(), ZERO, None, None),
        (cash, ZERO, run.net_pay or ZERO, None, None),
        (tax_payable, ZERO, (run.employee_tax or ZERO) + (run.employer_tax or ZERO), None, None),
        (ded_payable, ZERO, (run.deductions or ZERO) + (run.benefits or ZERO), None, None),
    ]
    with transaction.atomic():
        je = _post_journal_entry(request.tenant, request.user,
                                 f"Payroll {run.number} ({run.period_start} – {run.period_end})", legs,
                                 reference=run.number, entry_type="manual")
        if je is None:
            messages.error(request, "Payroll did not balance (check the amounts) — nothing was posted.")
            return redirect("accounting:payroll_run_detail", pk=pk)
        run.journal_entry = je
        run.status = "posted"
        run.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, run, "update", {"action": "post"})
    messages.success(request, f"Payroll {run.number} posted.")
    return redirect("accounting:payroll_run_detail", pk=pk)
