"""Projects 7.15 Financial & Billing Management — Computed Financial Dashboards & Reports.

Computed on read directly from the verified spine entities (Project, CostControlAccount,
ProjectExpense, ResourceTimeEntry, ProjectRevenueSchedule, Invoice, ProjectPaymentRecord).
Holds NO duplicate snapshot tables, adhering strictly to L31 and 7.4 rulings.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.accounting.models import Invoice
from apps.core.crud import as_db_int
from apps.projects.models.CostManagement.CostControlAccounts import CostControlAccount
from apps.projects.models.CostManagement.ProjectExpenses import ProjectExpense
from apps.projects.models.FinancialBillingManagement.BillingRuns import ProjectBillingRun
from apps.projects.models.FinancialBillingManagement.PaymentRecords import ProjectPaymentRecord
from apps.projects.models.FinancialBillingManagement.RevenueSchedules import ProjectRevenueSchedule
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ResourceManagement.ResourceTimeEntries import ResourceTimeEntry
from apps.projects.views._common import login_required


@login_required
def financial_pnl(request):
    """Project Profit & Loss statement computed in real-time."""
    projects_qs = Project.objects.filter(tenant=request.tenant).order_by("name")
    project_id = as_db_int(request.GET.get("project"))

    target_projects = projects_qs
    if project_id:
        target_projects = target_projects.filter(pk=project_id)

    pnl_rows = []
    tot_contract = Decimal("0.00")
    tot_revenue = Decimal("0.00")
    tot_labor = Decimal("0.00")
    tot_expense = Decimal("0.00")
    tot_cost = Decimal("0.00")
    tot_margin = Decimal("0.00")

    rev_stats = (
        ProjectRevenueSchedule.objects.filter(
            tenant=request.tenant,
            project__in=target_projects,
        )
        .values("project_id")
        .annotate(
            contract_val=Sum("contract_amount"),
            recognized_rev=Sum("recognized_amount", filter=Q(status__in=["approved", "recognized", "locked"])),
        )
    )
    rev_by_prj = {r["project_id"]: r for r in rev_stats}

    hours_stats = (
        ResourceTimeEntry.objects.filter(
            tenant=request.tenant,
            project__in=target_projects,
            status__in=["approved", "submitted"],
        )
        .values("project_id")
        .annotate(hours=Sum("hours"))
    )
    hours_by_prj = {h["project_id"]: (h["hours"] or Decimal("0.00")) for h in hours_stats}

    expense_stats = (
        ProjectExpense.objects.filter(
            tenant=request.tenant,
            project__in=target_projects,
            entry_type__in=["actual", "commitment"],
        )
        .values("project_id")
        .annotate(expense=Sum("amount"))
    )
    expense_by_prj = {e["project_id"]: (e["expense"] or Decimal("0.00")) for e in expense_stats}

    for prj in target_projects:
        rev_data = rev_by_prj.get(prj.pk, {})
        rev = rev_data.get("recognized_rev") or Decimal("0.00")
        contract_val = rev_data.get("contract_val") or Decimal("0.00")

        hours = hours_by_prj.get(prj.pk, Decimal("0.00"))
        labor_cost = (hours * Decimal("75.00")).quantize(Decimal("0.01"))

        expense_cost = expense_by_prj.get(prj.pk, Decimal("0.00"))

        total_cost = labor_cost + expense_cost
        gross_margin = rev - total_cost
        margin_pct = (gross_margin / rev * Decimal("100.0")).quantize(Decimal("0.1")) if rev > Decimal("0.00") else Decimal("0.0")

        pnl_rows.append({
            "project": prj,
            "contract_value": contract_val,
            "recognized_revenue": rev,
            "labor_hours": hours,
            "labor_cost": labor_cost,
            "expense_cost": expense_cost,
            "total_cost": total_cost,
            "gross_margin": gross_margin,
            "margin_pct": margin_pct,
        })

        tot_contract += contract_val
        tot_revenue += rev
        tot_labor += labor_cost
        tot_expense += expense_cost
        tot_cost += total_cost
        tot_margin += gross_margin

    avg_margin_pct = (tot_margin / tot_revenue * Decimal("100.0")).quantize(Decimal("0.1")) if tot_revenue > Decimal("0.00") else Decimal("0.0")

    totals = {
        "contract_value": tot_contract,
        "recognized_revenue": tot_revenue,
        "labor_cost": tot_labor,
        "expense_cost": tot_expense,
        "total_cost": tot_cost,
        "gross_margin": tot_margin,
        "margin_pct": avg_margin_pct,
    }

    return render(
        request,
        "projects/financialbilling/pnl.html",
        {
            "pnl_rows": pnl_rows,
            "totals": totals,
            "projects": projects_qs,
            "project_filter": project_id,
        },
    )


@login_required
def financial_variance(request):
    """Triple-constraint variance & EVM metrics join over 7.4 CostControlAccount."""
    projects_qs = Project.objects.filter(tenant=request.tenant).order_by("name")
    project_id = as_db_int(request.GET.get("project"))

    ccas_qs = (
        CostControlAccount.objects.filter(tenant=request.tenant)
        .select_related("project")
        .order_by("project__name", "code")
    )
    if project_id:
        ccas_qs = ccas_qs.filter(project_id=project_id)

    variance_rows = []
    tot_bac = Decimal("0.00")
    tot_pv = Decimal("0.00")
    tot_ev = Decimal("0.00")
    tot_ac = Decimal("0.00")
    tot_cv = Decimal("0.00")
    tot_sv = Decimal("0.00")
    tot_eac = Decimal("0.00")

    for cca in ccas_qs:
        bac = cca.bac
        pv = cca.pv
        ev = cca.ev
        ac = cca.ac
        cv = cca.cv
        sv = cca.sv
        cpi = cca.cpi
        spi = cca.spi
        eac = cca.eac
        health = cca.health

        variance_rows.append({
            "cca": cca,
            "project": cca.project,
            "code": cca.code,
            "name": cca.name,
            "bac": bac,
            "pv": pv,
            "ev": ev,
            "ac": ac,
            "cv": cv,
            "sv": sv,
            "cpi": cpi,
            "spi": spi,
            "eac": eac,
            "health": health,
        })

        tot_bac += bac
        tot_pv += pv
        tot_ev += ev
        tot_ac += ac
        tot_cv += cv
        tot_sv += sv
        tot_eac += eac

    overall_cpi = (tot_ev / tot_ac).quantize(Decimal("0.01")) if tot_ac > Decimal("0.00") else Decimal("1.00")
    overall_spi = (tot_ev / tot_pv).quantize(Decimal("0.01")) if tot_pv > Decimal("0.00") else Decimal("1.00")

    totals = {
        "bac": tot_bac,
        "pv": tot_pv,
        "ev": tot_ev,
        "ac": tot_ac,
        "cv": tot_cv,
        "sv": tot_sv,
        "cpi": overall_cpi,
        "spi": overall_spi,
        "eac": tot_eac,
    }

    return render(
        request,
        "projects/financialbilling/variance.html",
        {
            "variance_rows": variance_rows,
            "totals": totals,
            "projects": projects_qs,
            "project_filter": project_id,
        },
    )


@login_required
def ar_aging(request):
    """Accounts Receivable aging buckets (Current, 1-30, 31-60, 61-90, 90+ days)."""
    projects_qs = Project.objects.filter(tenant=request.tenant).order_by("name")
    project_id = as_db_int(request.GET.get("project"))

    records_qs = (
        ProjectPaymentRecord.objects.filter(tenant=request.tenant)
        .select_related("project", "client", "accounting_invoice")
        .exclude(stage__in=["settled", "written_off"])
    )
    if project_id:
        records_qs = records_qs.filter(project_id=project_id)

    today = timezone.localdate()
    aging_buckets = []
    tot_current = Decimal("0.00")
    tot_1_30 = Decimal("0.00")
    tot_31_60 = Decimal("0.00")
    tot_61_90 = Decimal("0.00")
    tot_over_90 = Decimal("0.00")
    tot_balance = Decimal("0.00")

    for rec in records_qs:
        inv = rec.accounting_invoice
        due_date = inv.due_date or inv.issue_date or today
        days_overdue = (today - due_date).days if today > due_date else 0
        bal = inv.balance_due() if callable(getattr(inv, "balance_due", None)) else (inv.balance_due or Decimal("0.00"))

        b_current = Decimal("0.00")
        b_1_30 = Decimal("0.00")
        b_31_60 = Decimal("0.00")
        b_61_90 = Decimal("0.00")
        b_over_90 = Decimal("0.00")

        if days_overdue <= 0:
            b_current = bal
            tot_current += bal
        elif days_overdue <= 30:
            b_1_30 = bal
            tot_1_30 += bal
        elif days_overdue <= 60:
            b_31_60 = bal
            tot_31_60 += bal
        elif days_overdue <= 90:
            b_61_90 = bal
            tot_61_90 += bal
        else:
            b_over_90 = bal
            tot_over_90 += bal

        tot_balance += bal

        aging_buckets.append({
            "record": rec,
            "project": rec.project,
            "client": rec.client,
            "invoice": inv,
            "due_date": due_date,
            "days_overdue": days_overdue,
            "balance": bal,
            "current": b_current,
            "b_1_30": b_1_30,
            "b_31_60": b_31_60,
            "b_61_90": b_61_90,
            "b_over_90": b_over_90,
            "stage": rec.stage,
            "stage_display": rec.get_stage_display(),
        })

    bucket_totals = {
        "current": tot_current,
        "b_1_30": tot_1_30,
        "b_31_60": tot_31_60,
        "b_61_90": tot_61_90,
        "b_over_90": tot_over_90,
        "total_balance": tot_balance,
    }

    return render(
        request,
        "projects/financialbilling/aging.html",
        {
            "aging_buckets": aging_buckets,
            "bucket_totals": bucket_totals,
            "projects": projects_qs,
            "project_filter": project_id,
        },
    )


@login_required
def cash_flow_forecast(request):
    """Forward-looking 30/60/90-day cash inflows vs outflows forecast."""
    projects_qs = Project.objects.filter(tenant=request.tenant).order_by("name")
    project_id = as_db_int(request.GET.get("project"))

    today = timezone.localdate()
    p30 = today + timedelta(days=30)
    p60 = today + timedelta(days=60)
    p90 = today + timedelta(days=90)

    # Inflows: Outstanding uncollected invoices by due date/promise date
    inflows_qs = (
        Invoice.objects.filter(tenant=request.tenant, status__in=["sent", "partial"])
        .select_related("party")
    )
    if project_id:
        inflows_qs = inflows_qs.filter(project_billing_runs__project_id=project_id)

    in_30 = Decimal("0.00")
    in_60 = Decimal("0.00")
    in_90 = Decimal("0.00")

    for inv in inflows_qs:
        dt = inv.due_date or today
        bal = inv.balance_due() if callable(getattr(inv, "balance_due", None)) else (inv.balance_due or Decimal("0.00"))
        if dt <= p30:
            in_30 += bal
        elif dt <= p60:
            in_60 += bal
        elif dt <= p90:
            in_90 += bal

    # Outflows: Committed project expenses / supplier POs
    outflows_qs = ProjectExpense.objects.filter(tenant=request.tenant, entry_type="commitment")
    if project_id:
        outflows_qs = outflows_qs.filter(project_id=project_id)

    out_30 = Decimal("0.00")
    out_60 = Decimal("0.00")
    out_90 = Decimal("0.00")

    for exp in outflows_qs:
        dt = exp.entry_date
        amt = exp.amount
        if dt <= p30:
            out_30 += amt
        elif dt <= p60:
            out_60 += amt
        elif dt <= p90:
            out_90 += amt

    net_30 = in_30 - out_30
    net_60 = in_60 - out_60
    net_90 = in_90 - out_90

    inflows = {"p30": in_30, "p60": in_60, "p90": in_90, "total": in_30 + in_60 + in_90}
    outflows = {"p30": out_30, "p60": out_60, "p90": out_90, "total": out_30 + out_60 + out_90}
    net_cash_periods = {
        "p30": net_30,
        "p60": net_60,
        "p90": net_90,
        "total": net_30 + net_60 + net_90,
    }

    return render(
        request,
        "projects/financialbilling/cashflow.html",
        {
            "inflows": inflows,
            "outflows": outflows,
            "net_cash_periods": net_cash_periods,
            "projects": projects_qs,
            "project_filter": project_id,
        },
    )
