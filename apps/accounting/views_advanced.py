"""Views for the advanced accounting sub-modules 2.6–2.15.

Plain CRUD reuses ``apps.core.crud``; the workflow actions (depreciation run, disposal, cost
allocation, payroll, job-cost, intercompany) each post a BALANCED ``JournalEntry`` via the local
``_post_journal_entry`` helper (Σdebit==Σcredit enforced before the entry is created) and are
``@tenant_admin_required`` + POST-only. The 2.12 financial statements are pure report views over
posted ``JournalLine`` aggregates. Reuses ``_first_account``/``_open_period``/``_need_tenant`` from
``views.py``.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

from .models import ZERO, GLAccount, JournalEntry, JournalLine
from .models_advanced import (
    AssetDisposal,
    Budget,
    BudgetLine,
    CostAllocation,
    FixedAsset,
    IntegrationConfig,
    IntercompanyTransaction,
    InternalControl,
    JobCostEntry,
    PayrollRun,
    Project,
    ScheduledReport,
    TaxCode,
    TaxReturn,
)
from .forms_advanced import (
    AssetDisposalForm,
    BudgetForm,
    BudgetLineForm,
    CostAllocationForm,
    FixedAssetForm,
    IntegrationConfigForm,
    IntercompanyTransactionForm,
    InternalControlForm,
    JobCostEntryForm,
    PayrollRunForm,
    ProjectForm,
    ScheduledReportForm,
    TaxCodeForm,
    TaxReturnForm,
)
from .views import _first_account, _open_period


# --------------------------------------------------------------------------- posting helper
def _post_journal_entry(tenant, user, description, legs, *, reference="", entry_type="manual", date=None):
    """Create a posted, balanced JournalEntry. ``legs`` = [(gl_account, debit, credit, party, org_unit)].
    Returns the JE, or None when legs are empty / don't balance (caller handles the skip)."""
    legs = [l for l in legs if (l[1] or ZERO) or (l[2] or ZERO)]
    if not legs:
        return None
    debit = sum((l[1] or ZERO for l in legs), ZERO)
    credit = sum((l[2] or ZERO for l in legs), ZERO)
    if debit != credit or debit <= ZERO:
        return None
    je = JournalEntry.objects.create(
        tenant=tenant, entry_type=entry_type, status="posted", fiscal_period=_open_period(tenant),
        entry_date=date or timezone.localdate(), description=description[:255], reference=reference[:100],
        created_by=user, approved_by=user, posted_at=timezone.now(),
    )
    for gl, d, c, party, org in legs:
        JournalLine.objects.create(entry=je, gl_account=gl, debit=d or ZERO, credit=c or ZERO,
                                   description=description[:255], party=party, org_unit=org)
    return je


# ============================================================== 2.6 Fixed Assets
@login_required
def fixed_asset_list(request):
    return crud_list(
        request, FixedAsset.objects.filter(tenant=request.tenant).select_related("location"),
        "accounting/assets/fixed_asset/list.html",
        search_fields=["number", "name", "category"],
        filters=[("status", "status", False), ("method", "method", False)],
        extra_context={"status_choices": FixedAsset.STATUS_CHOICES, "method_choices": FixedAsset.METHOD_CHOICES},
    )


@login_required
def fixed_asset_create(request):
    return crud_create(request, form_class=FixedAssetForm, template="accounting/assets/fixed_asset/form.html",
                       success_url="accounting:fixed_asset_list")


@login_required
def fixed_asset_detail(request, pk):
    obj = get_object_or_404(
        FixedAsset.objects.select_related("custodian", "location", "asset_account",
                                          "accumulated_account", "expense_account"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/assets/fixed_asset/detail.html", {
        "obj": obj,
        "book_value": obj.book_value(),
        "next_depreciation": obj.period_depreciation(),
        "disposals": obj.disposals.all()[:5],
    })


@login_required
def fixed_asset_edit(request, pk):
    return crud_edit(request, model=FixedAsset, pk=pk, form_class=FixedAssetForm,
                     template="accounting/assets/fixed_asset/form.html", success_url="accounting:fixed_asset_list")


@login_required
@require_POST
def fixed_asset_delete(request, pk):
    # Lock the row and re-check the guard + delete in one transaction so a concurrent depreciation
    # run can't slip a row in between the check and the delete (code-review #3).
    with transaction.atomic():
        asset = get_object_or_404(FixedAsset.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if asset.accumulated_depreciation or asset.disposals.exists():
            messages.error(request, "Cannot delete an asset that has been depreciated or disposed.")
            return redirect("accounting:fixed_asset_detail", pk=pk)
        write_audit_log(request.user, asset, "delete")
        asset.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:fixed_asset_list")


@tenant_admin_required
@require_POST
def fixed_asset_depreciate(request, pk):
    asset = get_object_or_404(FixedAsset, pk=pk, tenant=request.tenant)
    if asset.status != "active":
        messages.error(request, "Only an in-service asset can be depreciated.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    amount = asset.period_depreciation()
    if amount <= ZERO:
        messages.info(request, "This asset is already fully depreciated.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    expense = asset.expense_account or _first_account(request.tenant, "expense", "6")
    accum = asset.accumulated_account or _first_account(request.tenant, "asset", "1500") \
        or _first_account(request.tenant, "asset")
    if not (expense and accum):
        messages.error(request, "Configure a depreciation expense account and an accumulated-depreciation account first.")
        return redirect("accounting:fixed_asset_detail", pk=pk)
    with transaction.atomic():
        je = _post_journal_entry(
            request.tenant, request.user, f"Depreciation — {asset.number} {asset.name}",
            [(expense, amount, ZERO, None, asset.location), (accum, ZERO, amount, None, asset.location)],
            reference=asset.number)
        asset.accumulated_depreciation = (asset.accumulated_depreciation or ZERO) + amount
        asset.last_depreciation_date = timezone.localdate()
        asset.save(update_fields=["accumulated_depreciation", "last_depreciation_date", "updated_at"])
    write_audit_log(request.user, asset, "update", {"action": "depreciate", "amount": str(amount),
                                                    "journal_entry": je.number if je else None})
    messages.success(request, f"Posted {amount} depreciation for {asset.number}.")
    return redirect("accounting:fixed_asset_detail", pk=pk)


# --------------------------------------------------------------- Asset disposals
@login_required
def asset_disposal_list(request):
    return crud_list(
        request, AssetDisposal.objects.filter(tenant=request.tenant).select_related("asset"),
        "accounting/assets/asset_disposal/list.html",
        search_fields=["number", "asset__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": AssetDisposal.STATUS_CHOICES},
    )


@login_required
def asset_disposal_create(request):
    return crud_create(request, form_class=AssetDisposalForm, template="accounting/assets/asset_disposal/form.html",
                       success_url="accounting:asset_disposal_list")


@login_required
def asset_disposal_detail(request, pk):
    obj = get_object_or_404(AssetDisposal.objects.select_related("asset", "journal_entry"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/assets/asset_disposal/detail.html", {
        "obj": obj, "computed_gain_loss": obj.computed_gain_loss() if obj.status == "draft" else obj.gain_loss,
    })


@login_required
def asset_disposal_edit(request, pk):
    disposal = get_object_or_404(AssetDisposal, pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "A posted disposal cannot be edited.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    return crud_edit(request, model=AssetDisposal, pk=pk, form_class=AssetDisposalForm,
                     template="accounting/assets/asset_disposal/form.html", success_url="accounting:asset_disposal_list")


@login_required
@require_POST
def asset_disposal_delete(request, pk):
    disposal = get_object_or_404(AssetDisposal, pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "A posted disposal cannot be deleted.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    return crud_delete(request, model=AssetDisposal, pk=pk, success_url="accounting:asset_disposal_list")


@tenant_admin_required
@require_POST
def asset_disposal_post(request, pk):
    disposal = get_object_or_404(AssetDisposal.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    if disposal.is_locked:
        messages.error(request, "This disposal is already posted.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    asset = disposal.asset
    cost_acct = asset.asset_account or _first_account(request.tenant, "asset", "1600") \
        or _first_account(request.tenant, "asset")
    accum_acct = asset.accumulated_account or _first_account(request.tenant, "asset", "1690") \
        or _first_account(request.tenant, "asset")
    cash_acct = _first_account(request.tenant, "asset", "1000") or _first_account(request.tenant, "asset")
    gain_acct = _first_account(request.tenant, "income")
    loss_acct = _first_account(request.tenant, "expense")
    if not (cost_acct and cash_acct and gain_acct and loss_acct):
        messages.error(request, "Configure asset, cash, income and expense accounts before disposing.")
        return redirect("accounting:asset_disposal_detail", pk=pk)
    gain_loss = disposal.computed_gain_loss()
    legs = [
        (cash_acct, disposal.proceeds or ZERO, ZERO, None, asset.location),
        (accum_acct, asset.accumulated_depreciation or ZERO, ZERO, None, asset.location),
        (cost_acct, ZERO, asset.acquisition_cost or ZERO, None, asset.location),
    ]
    if gain_loss > ZERO:
        legs.append((gain_acct, ZERO, gain_loss, None, asset.location))
    elif gain_loss < ZERO:
        legs.append((loss_acct, -gain_loss, ZERO, None, asset.location))
    with transaction.atomic():
        je = _post_journal_entry(request.tenant, request.user,
                                 f"Disposal of {asset.number} {asset.name}", legs, reference=disposal.number)
        if je is None:
            messages.error(request, "Disposal entry did not balance — nothing was posted.")
            return redirect("accounting:asset_disposal_detail", pk=pk)
        disposal.gain_loss = gain_loss
        disposal.journal_entry = je
        disposal.status = "posted"
        disposal.save(update_fields=["gain_loss", "journal_entry", "status", "updated_at"])
        asset.status = "disposed"
        asset.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, disposal, "update", {"action": "post_disposal",
                                                       "gain_loss": str(gain_loss)})
    messages.success(request, f"Disposal {disposal.number} posted ({'gain' if gain_loss >= 0 else 'loss'} {abs(gain_loss)}).")
    return redirect("accounting:asset_disposal_detail", pk=pk)


# ====================================================== 2.7 Cost Allocation
@login_required
def cost_allocation_list(request):
    return crud_list(
        request, CostAllocation.objects.filter(tenant=request.tenant)
        .select_related("source_account", "target_account", "target_org_unit"),
        "accounting/costing/cost_allocation/list.html",
        search_fields=["number", "description"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": CostAllocation.STATUS_CHOICES},
    )


@login_required
def cost_allocation_create(request):
    return crud_create(request, form_class=CostAllocationForm, template="accounting/costing/cost_allocation/form.html",
                       success_url="accounting:cost_allocation_list")


@login_required
def cost_allocation_detail(request, pk):
    obj = get_object_or_404(
        CostAllocation.objects.select_related("source_account", "target_account", "target_org_unit", "journal_entry"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/costing/cost_allocation/detail.html", {"obj": obj})


@login_required
def cost_allocation_edit(request, pk):
    alloc = get_object_or_404(CostAllocation, pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "A posted allocation cannot be edited.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    return crud_edit(request, model=CostAllocation, pk=pk, form_class=CostAllocationForm,
                     template="accounting/costing/cost_allocation/form.html", success_url="accounting:cost_allocation_list")


@login_required
@require_POST
def cost_allocation_delete(request, pk):
    alloc = get_object_or_404(CostAllocation, pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "A posted allocation cannot be deleted.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    return crud_delete(request, model=CostAllocation, pk=pk, success_url="accounting:cost_allocation_list")


@tenant_admin_required
@require_POST
def cost_allocation_post(request, pk):
    alloc = get_object_or_404(CostAllocation.objects.select_related("source_account", "target_account", "target_org_unit"),
                              pk=pk, tenant=request.tenant)
    if alloc.is_locked:
        messages.error(request, "This allocation is already posted.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    if (alloc.amount or ZERO) <= ZERO:
        messages.error(request, "Allocation amount must be greater than zero.")
        return redirect("accounting:cost_allocation_detail", pk=pk)
    with transaction.atomic():
        je = _post_journal_entry(
            request.tenant, request.user, f"Cost allocation {alloc.number} — {alloc.description}",
            [(alloc.target_account, alloc.amount, ZERO, None, alloc.target_org_unit),
             (alloc.source_account, ZERO, alloc.amount, None, None)], reference=alloc.number)
        if je is None:
            messages.error(request, "Allocation entry did not balance — nothing was posted.")
            return redirect("accounting:cost_allocation_detail", pk=pk)
        alloc.journal_entry = je
        alloc.status = "posted"
        alloc.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, alloc, "update", {"action": "post"})
    messages.success(request, f"Allocation {alloc.number} posted.")
    return redirect("accounting:cost_allocation_detail", pk=pk)


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


# ===================================================== 2.9 Project / Job Costing
@login_required
def project_list(request):
    return crud_list(
        request, Project.objects.filter(tenant=request.tenant).select_related("client", "org_unit"),
        "accounting/projects/project/list.html",
        search_fields=["number", "name"],
        filters=[("status", "status", False), ("billing_method", "billing_method", False)],
        extra_context={"status_choices": Project.STATUS_CHOICES, "billing_choices": Project.BILLING_CHOICES},
    )


@login_required
def project_create(request):
    return crud_create(request, form_class=ProjectForm, template="accounting/projects/project/form.html",
                       success_url="accounting:project_list")


@login_required
def project_detail(request, pk):
    obj = get_object_or_404(Project.objects.select_related("client", "org_unit"), pk=pk, tenant=request.tenant)
    # One grouped aggregate for the cost/revenue actuals (was 5 separate .aggregate() calls — perf C2).
    sums = {r["kind"]: r["total"] or ZERO
            for r in obj.cost_entries.filter(status="posted").values("kind").annotate(total=Sum("amount"))}
    actual_cost, actual_revenue = sums.get("cost", ZERO), sums.get("revenue", ZERO)
    return render(request, "accounting/projects/project/detail.html", {
        "obj": obj,
        "cost_entries": obj.cost_entries.all()[:20],
        "actual_cost": actual_cost, "actual_revenue": actual_revenue,
        "variance": (obj.budget_amount or ZERO) - actual_cost,
        "margin": actual_revenue - actual_cost,
    })


@login_required
def project_edit(request, pk):
    return crud_edit(request, model=Project, pk=pk, form_class=ProjectForm,
                     template="accounting/projects/project/form.html", success_url="accounting:project_list")


@login_required
@require_POST
def project_delete(request, pk):
    return crud_delete(request, model=Project, pk=pk, success_url="accounting:project_list")


# --------------------------------------------------------------- Job cost entries
@login_required
def job_cost_entry_list(request):
    return crud_list(
        request, JobCostEntry.objects.filter(tenant=request.tenant).select_related("project", "gl_account"),
        "accounting/projects/job_cost_entry/list.html",
        search_fields=["number", "description", "project__name"],
        filters=[("status", "status", False), ("kind", "kind", False), ("project", "project_id", True)],
        extra_context={"status_choices": JobCostEntry.STATUS_CHOICES, "kind_choices": JobCostEntry.KIND_CHOICES,
                       "projects": Project.objects.filter(tenant=request.tenant)},
    )


@login_required
def job_cost_entry_create(request):
    return crud_create(request, form_class=JobCostEntryForm, template="accounting/projects/job_cost_entry/form.html",
                       success_url="accounting:job_cost_entry_list")


@login_required
def job_cost_entry_detail(request, pk):
    obj = get_object_or_404(JobCostEntry.objects.select_related("project", "gl_account", "journal_entry"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/projects/job_cost_entry/detail.html", {"obj": obj})


@login_required
def job_cost_entry_edit(request, pk):
    entry = get_object_or_404(JobCostEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted cost entry cannot be edited.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    return crud_edit(request, model=JobCostEntry, pk=pk, form_class=JobCostEntryForm,
                     template="accounting/projects/job_cost_entry/form.html", success_url="accounting:job_cost_entry_list")


@login_required
@require_POST
def job_cost_entry_delete(request, pk):
    entry = get_object_or_404(JobCostEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted cost entry cannot be deleted.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    return crud_delete(request, model=JobCostEntry, pk=pk, success_url="accounting:job_cost_entry_list")


@tenant_admin_required
@require_POST
def job_cost_entry_post(request, pk):
    entry = get_object_or_404(JobCostEntry.objects.select_related("project", "gl_account"),
                              pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "This cost entry is already posted.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    cash = _first_account(request.tenant, "asset", "1000") or _first_account(request.tenant, "asset")
    if not (entry.gl_account and cash) or (entry.amount or ZERO) <= ZERO:
        messages.error(request, "A GL account, a cash account and a positive amount are required to post.")
        return redirect("accounting:job_cost_entry_detail", pk=pk)
    org = entry.project.org_unit if entry.project_id else None
    if entry.kind == "cost":  # Dr expense / Cr cash
        legs = [(entry.gl_account, entry.amount, ZERO, None, org), (cash, ZERO, entry.amount, None, org)]
    else:  # revenue: Dr cash / Cr income
        legs = [(cash, entry.amount, ZERO, None, org), (entry.gl_account, ZERO, entry.amount, None, org)]
    with transaction.atomic():
        je = _post_journal_entry(request.tenant, request.user,
                                 f"{entry.get_kind_display()} — {entry.project.name} ({entry.number})", legs,
                                 reference=entry.number)
        if je is None:
            messages.error(request, "Cost entry did not balance — nothing was posted.")
            return redirect("accounting:job_cost_entry_detail", pk=pk)
        entry.journal_entry = je
        entry.status = "posted"
        entry.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, entry, "update", {"action": "post"})
    messages.success(request, f"Cost entry {entry.number} posted.")
    return redirect("accounting:job_cost_entry_detail", pk=pk)


# ============================================== 2.10 Multi-Entity / Intercompany
@login_required
def intercompany_list(request):
    return crud_list(
        request, IntercompanyTransaction.objects.filter(tenant=request.tenant)
        .select_related("from_org_unit", "to_org_unit"),
        "accounting/intercompany/list.html",
        search_fields=["number", "description"],
        filters=[("status", "status", False), ("eliminated", "eliminated", False)],
        extra_context={"status_choices": IntercompanyTransaction.STATUS_CHOICES},
    )


@login_required
def intercompany_create(request):
    return crud_create(request, form_class=IntercompanyTransactionForm, template="accounting/intercompany/form.html",
                       success_url="accounting:intercompany_list")


@login_required
def intercompany_detail(request, pk):
    obj = get_object_or_404(
        IntercompanyTransaction.objects.select_related("from_org_unit", "to_org_unit", "due_from_account",
                                                       "due_to_account", "journal_entry"),
        pk=pk, tenant=request.tenant)
    return render(request, "accounting/intercompany/detail.html", {"obj": obj})


@login_required
def intercompany_edit(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "A posted intercompany transaction cannot be edited.")
        return redirect("accounting:intercompany_detail", pk=pk)
    return crud_edit(request, model=IntercompanyTransaction, pk=pk, form_class=IntercompanyTransactionForm,
                     template="accounting/intercompany/form.html", success_url="accounting:intercompany_list")


@login_required
@require_POST
def intercompany_delete(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "A posted intercompany transaction cannot be deleted.")
        return redirect("accounting:intercompany_detail", pk=pk)
    return crud_delete(request, model=IntercompanyTransaction, pk=pk, success_url="accounting:intercompany_list")


@tenant_admin_required
@require_POST
def intercompany_post(request, pk):
    ict = get_object_or_404(
        IntercompanyTransaction.objects.select_related("from_org_unit", "to_org_unit", "due_from_account",
                                                       "due_to_account"),
        pk=pk, tenant=request.tenant)
    if ict.is_locked:
        messages.error(request, "This intercompany transaction is already posted.")
        return redirect("accounting:intercompany_detail", pk=pk)
    due_from = ict.due_from_account or _first_account(request.tenant, "asset", "1100") \
        or _first_account(request.tenant, "asset")
    due_to = ict.due_to_account or _first_account(request.tenant, "liability", "2000") \
        or _first_account(request.tenant, "liability")
    if not (due_from and due_to) or (ict.amount or ZERO) <= ZERO:
        messages.error(request, "Due-from and due-to accounts and a positive amount are required to post.")
        return redirect("accounting:intercompany_detail", pk=pk)
    with transaction.atomic():
        # due-from (receivable) sits on the lender's books (from_org_unit); due-to (payable) on the
        # borrower's books (to_org_unit).
        je = _post_journal_entry(
            request.tenant, request.user, f"Intercompany {ict.number} — {ict.description}",
            [(due_from, ict.amount, ZERO, None, ict.from_org_unit),
             (due_to, ZERO, ict.amount, None, ict.to_org_unit)], reference=ict.number)
        if je is None:
            messages.error(request, "Intercompany transaction did not balance — nothing was posted.")
            return redirect("accounting:intercompany_detail", pk=pk)
        ict.journal_entry = je
        ict.status = "posted"
        ict.save(update_fields=["journal_entry", "status", "updated_at"])
    write_audit_log(request.user, ict, "update", {"action": "post"})
    messages.success(request, f"Intercompany transaction {ict.number} posted.")
    return redirect("accounting:intercompany_detail", pk=pk)


@tenant_admin_required
@require_POST
def intercompany_toggle_eliminated(request, pk):
    ict = get_object_or_404(IntercompanyTransaction, pk=pk, tenant=request.tenant)
    ict.eliminated = not ict.eliminated
    ict.save(update_fields=["eliminated", "updated_at"])
    write_audit_log(request.user, ict, "update", {"action": "toggle_eliminated", "eliminated": ict.eliminated})
    messages.success(request, f"Marked {'eliminated' if ict.eliminated else 'not eliminated'} for consolidation.")
    return redirect("accounting:intercompany_detail", pk=pk)


# ============================================================================ 2.11 Tax
@login_required
def tax_code_list(request):
    return crud_list(
        request, TaxCode.objects.filter(tenant=request.tenant),
        "accounting/tax/code/list.html",
        search_fields=["name", "jurisdiction"],
        filters=[("tax_type", "tax_type", False), ("is_active", "is_active", False)],
        extra_context={"tax_type_choices": TaxCode.TAX_TYPE_CHOICES},
    )


@login_required
def tax_code_create(request):
    return crud_create(request, form_class=TaxCodeForm, template="accounting/tax/code/form.html",
                       success_url="accounting:tax_code_list")


@login_required
def tax_code_detail(request, pk):
    obj = get_object_or_404(TaxCode.objects.select_related("payable_account"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/tax/code/detail.html", {"obj": obj, "returns": obj.returns.all()[:5]})


@login_required
def tax_code_edit(request, pk):
    return crud_edit(request, model=TaxCode, pk=pk, form_class=TaxCodeForm,
                     template="accounting/tax/code/form.html", success_url="accounting:tax_code_list")


@login_required
@require_POST
def tax_code_delete(request, pk):
    return crud_delete(request, model=TaxCode, pk=pk, success_url="accounting:tax_code_list")


@login_required
def tax_return_list(request):
    return crud_list(
        request, TaxReturn.objects.filter(tenant=request.tenant).select_related("tax_code"),
        "accounting/tax/return/list.html",
        search_fields=["number", "tax_code__name"],
        filters=[("status", "status", False), ("tax_code", "tax_code_id", True)],
        extra_context={"status_choices": TaxReturn.STATUS_CHOICES,
                       "tax_codes": TaxCode.objects.filter(tenant=request.tenant)},
    )


@login_required
def tax_return_create(request):
    return crud_create(request, form_class=TaxReturnForm, template="accounting/tax/return/form.html",
                       success_url="accounting:tax_return_list")


@login_required
def tax_return_detail(request, pk):
    obj = get_object_or_404(TaxReturn.objects.select_related("tax_code"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/tax/return/detail.html", {"obj": obj})


@tenant_admin_required
def tax_return_edit(request, pk):
    return crud_edit(request, model=TaxReturn, pk=pk, form_class=TaxReturnForm,
                     template="accounting/tax/return/form.html", success_url="accounting:tax_return_list")


@tenant_admin_required
@require_POST
def tax_return_delete(request, pk):
    return crud_delete(request, model=TaxReturn, pk=pk, success_url="accounting:tax_return_list")


# ===================================================== 2.12 Reporting & Compliance
def _account_balances(tenant):
    """Return per-account balances grouped from a single posted-line aggregate (no per-account query)."""
    rows = (JournalLine.objects.filter(entry__tenant=tenant, entry__status="posted")
            .values("gl_account__code", "gl_account__name", "gl_account__account_type",
                    "gl_account__normal_balance")
            .annotate(d=Sum("debit"), c=Sum("credit")).order_by("gl_account__code"))
    out = []
    for r in rows:
        debit, credit = r["d"] or ZERO, r["c"] or ZERO
        signed = (debit - credit) if r["gl_account__normal_balance"] == "debit" else (credit - debit)
        out.append({"code": r["gl_account__code"], "name": r["gl_account__name"],
                    "type": r["gl_account__account_type"], "balance": signed})
    return out


@login_required
def balance_sheet(request):
    assets = liabilities = equity = []
    total_assets = total_liabilities = total_equity = net_income = ZERO
    if request.tenant is not None:
        rows = _account_balances(request.tenant)
        assets = [r for r in rows if r["type"] == "asset"]
        liabilities = [r for r in rows if r["type"] == "liability"]
        equity = [r for r in rows if r["type"] == "equity"]
        income = sum((r["balance"] for r in rows if r["type"] == "income"), ZERO)
        expense = sum((r["balance"] for r in rows if r["type"] == "expense"), ZERO)
        net_income = income - expense
        total_assets = sum((r["balance"] for r in assets), ZERO)
        total_liabilities = sum((r["balance"] for r in liabilities), ZERO)
        total_equity = sum((r["balance"] for r in equity), ZERO)
    return render(request, "accounting/reports/balance_sheet.html", {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": total_assets, "total_liabilities": total_liabilities,
        "total_equity": total_equity, "net_income": net_income,
        "total_liab_equity": total_liabilities + total_equity + net_income,
        "balanced": total_assets == (total_liabilities + total_equity + net_income),
    })


@login_required
def profit_and_loss(request):
    income = expense = []
    total_income = total_expense = ZERO
    if request.tenant is not None:
        rows = _account_balances(request.tenant)
        income = [r for r in rows if r["type"] == "income"]
        expense = [r for r in rows if r["type"] == "expense"]
        total_income = sum((r["balance"] for r in income), ZERO)
        total_expense = sum((r["balance"] for r in expense), ZERO)
    return render(request, "accounting/reports/profit_and_loss.html", {
        "income": income, "expense": expense, "total_income": total_income,
        "total_expense": total_expense, "net_income": total_income - total_expense,
    })


# --------------------------------------------------------------- Scheduled reports
@login_required
def scheduled_report_list(request):
    return crud_list(
        request, ScheduledReport.objects.filter(tenant=request.tenant),
        "accounting/reports/scheduled_report/list.html",
        search_fields=["name"],
        filters=[("report_type", "report_type", False), ("frequency", "frequency", False),
                 ("is_active", "is_active", False)],
        extra_context={"report_choices": ScheduledReport.REPORT_CHOICES,
                       "frequency_choices": ScheduledReport.FREQUENCY_CHOICES},
    )


@login_required
def scheduled_report_create(request):
    return crud_create(request, form_class=ScheduledReportForm, template="accounting/reports/scheduled_report/form.html",
                       success_url="accounting:scheduled_report_list")


@login_required
def scheduled_report_detail(request, pk):
    obj = get_object_or_404(ScheduledReport, pk=pk, tenant=request.tenant)
    return render(request, "accounting/reports/scheduled_report/detail.html", {"obj": obj})


@login_required
def scheduled_report_edit(request, pk):
    return crud_edit(request, model=ScheduledReport, pk=pk, form_class=ScheduledReportForm,
                     template="accounting/reports/scheduled_report/form.html", success_url="accounting:scheduled_report_list")


@login_required
@require_POST
def scheduled_report_delete(request, pk):
    return crud_delete(request, model=ScheduledReport, pk=pk, success_url="accounting:scheduled_report_list")


# =============================================================== 2.13 Budgeting & Planning
@login_required
def budget_list(request):
    return crud_list(
        request, Budget.objects.filter(tenant=request.tenant).select_related("fiscal_period"),
        "accounting/budget/list.html",
        search_fields=["number", "name"],
        filters=[("status", "status", False), ("version", "version", False)],
        extra_context={"status_choices": Budget.STATUS_CHOICES, "version_choices": Budget.VERSION_CHOICES},
    )


@login_required
def budget_create(request):
    return crud_create(request, form_class=BudgetForm, template="accounting/budget/form.html",
                       success_url="accounting:budget_list")


@login_required
def budget_detail(request, pk):
    obj = get_object_or_404(Budget.objects.select_related("fiscal_period"), pk=pk, tenant=request.tenant)
    # Lines are fully fetched, so sum them in Python instead of a second aggregate query (perf I4).
    lines = list(obj.lines.select_related("gl_account", "org_unit"))
    total = sum((ln.amount or ZERO for ln in lines), ZERO)
    return render(request, "accounting/budget/detail.html", {"obj": obj, "lines": lines, "total": total})


@login_required
def budget_edit(request, pk):
    return crud_edit(request, model=Budget, pk=pk, form_class=BudgetForm,
                     template="accounting/budget/form.html", success_url="accounting:budget_list")


@login_required
@require_POST
def budget_delete(request, pk):
    return crud_delete(request, model=Budget, pk=pk, success_url="accounting:budget_list")


# --------------------------------------------------------------- Budget lines
@login_required
def budget_line_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before adding budget lines.")
        return redirect("accounting:budget_list")
    initial = {}
    bp = request.GET.get("budget", "")
    if bp.isdigit():
        initial["budget"] = bp
    if request.method == "POST":
        form = BudgetLineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Budget line added.")
            return redirect("accounting:budget_detail", pk=obj.budget_id)
    else:
        form = BudgetLineForm(tenant=request.tenant, initial=initial)
    return render(request, "accounting/budget/line/form.html", {"form": form, "is_edit": False})


@login_required
def budget_line_edit(request, pk):
    line = get_object_or_404(BudgetLine, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = BudgetLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Budget line updated.")
            return redirect("accounting:budget_detail", pk=obj.budget_id)
    else:
        form = BudgetLineForm(instance=line, tenant=request.tenant)
    return render(request, "accounting/budget/line/form.html", {"form": form, "obj": line, "is_edit": True})


@login_required
@require_POST
def budget_line_delete(request, pk):
    line = get_object_or_404(BudgetLine, pk=pk, tenant=request.tenant)
    budget_pk = line.budget_id
    line.delete()
    write_audit_log(request.user, line, "delete")
    messages.success(request, "Budget line removed.")
    return redirect("accounting:budget_detail", pk=budget_pk)


@login_required
def budget_variance(request):
    """Budget vs. posted actuals for a chosen budget (?budget=pk, default = latest)."""
    if request.tenant is None:
        return render(request, "accounting/budget/variance.html",
                      {"budgets": [], "selected": None, "rows": [], "total_budget": ZERO,
                       "total_actual": ZERO, "total_variance": ZERO})
    # Evaluate the budget list once (was re-queried for the dropdown + pk lookup + fallback — perf I5).
    budgets = list(Budget.objects.filter(tenant=request.tenant).select_related("fiscal_period"))
    bp = request.GET.get("budget", "")
    selected = next((b for b in budgets if str(b.pk) == bp), None) if bp.isdigit() else None
    if selected is None and budgets:
        selected = budgets[0]
    rows, total_budget, total_actual = [], ZERO, ZERO
    if selected is not None:
        balances = {r["code"]: r["balance"] for r in _account_balances(request.tenant)}
        for line in selected.lines.select_related("gl_account", "org_unit"):
            actual = balances.get(line.gl_account.code, ZERO)
            rows.append({"line": line, "actual": actual, "variance": (line.amount or ZERO) - actual})
            total_budget += line.amount or ZERO
            total_actual += actual
    return render(request, "accounting/budget/variance.html", {
        "budgets": budgets, "selected": selected, "rows": rows,
        "total_budget": total_budget, "total_actual": total_actual,
        "total_variance": total_budget - total_actual,
    })


# ================================================================= 2.14 Audit & Controls
@login_required
def internal_control_list(request):
    return crud_list(
        request, InternalControl.objects.filter(tenant=request.tenant),
        "accounting/audit/internal_control/list.html",
        search_fields=["code", "name"],
        filters=[("control_type", "control_type", False), ("risk_level", "risk_level", False),
                 ("status", "status", False), ("last_result", "last_result", False)],
        extra_context={"control_type_choices": InternalControl.CONTROL_TYPE_CHOICES,
                       "risk_choices": InternalControl.RISK_CHOICES,
                       "status_choices": InternalControl.STATUS_CHOICES,
                       "result_choices": InternalControl.RESULT_CHOICES},
    )


@login_required
def internal_control_create(request):
    return crud_create(request, form_class=InternalControlForm, template="accounting/audit/internal_control/form.html",
                       success_url="accounting:internal_control_list")


@login_required
def internal_control_detail(request, pk):
    obj = get_object_or_404(InternalControl.objects.select_related("owner"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/audit/internal_control/detail.html", {"obj": obj})


@login_required
def internal_control_edit(request, pk):
    return crud_edit(request, model=InternalControl, pk=pk, form_class=InternalControlForm,
                     template="accounting/audit/internal_control/form.html", success_url="accounting:internal_control_list")


@login_required
@require_POST
def internal_control_delete(request, pk):
    return crud_delete(request, model=InternalControl, pk=pk, success_url="accounting:internal_control_list")


# ================================================================= 2.15 Integration & API
@login_required
def integration_list(request):
    return crud_list(
        request, IntegrationConfig.objects.filter(tenant=request.tenant),
        "accounting/integration/list.html",
        search_fields=["name", "provider"],
        filters=[("category", "category", False), ("status", "status", False),
                 ("is_active", "is_active", False)],
        extra_context={"category_choices": IntegrationConfig.CATEGORY_CHOICES,
                       "status_choices": IntegrationConfig.STATUS_CHOICES},
    )


@login_required
def integration_create(request):
    return crud_create(request, form_class=IntegrationConfigForm, template="accounting/integration/form.html",
                       success_url="accounting:integration_list")


@login_required
def integration_detail(request, pk):
    obj = get_object_or_404(IntegrationConfig, pk=pk, tenant=request.tenant)
    # One-time reveal of a freshly rotated key (L25 — pop-once session key, never flashed).
    reveal = request.session.pop("_integration_key_reveal", None)
    plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == obj.pk else None
    return render(request, "accounting/integration/detail.html", {"obj": obj, "plaintext_once": plaintext_once})


@tenant_admin_required
def integration_edit(request, pk):
    return crud_edit(request, model=IntegrationConfig, pk=pk, form_class=IntegrationConfigForm,
                     template="accounting/integration/form.html", success_url="accounting:integration_list")


@tenant_admin_required
@require_POST
def integration_delete(request, pk):
    return crud_delete(request, model=IntegrationConfig, pk=pk, success_url="accounting:integration_list")


@tenant_admin_required
@require_POST
def integration_rotate_key(request, pk):
    obj = get_object_or_404(IntegrationConfig, pk=pk, tenant=request.tenant)
    secret = IntegrationConfig.generate_secret()
    with transaction.atomic():
        obj.set_secret(secret)
        obj.status = "connected"
        obj.save(update_fields=["api_key_prefix", "api_key_hash", "status", "updated_at"])
    # Reveal exactly once on the redirect target — never via messages (would persist in the session, L25).
    request.session["_integration_key_reveal"] = {"pk": obj.pk, "secret": secret}
    write_audit_log(request.user, obj, "update", {"action": "rotate_key"})
    messages.success(request, "API key rotated — copy it now; it won't be shown again.")
    return redirect("accounting:integration_detail", pk=pk)
