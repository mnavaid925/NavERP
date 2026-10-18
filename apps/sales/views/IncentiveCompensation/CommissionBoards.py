"""Sales 8.10 — Derived Read-Only Incentive Compensation Boards.

Projections over CommissionPlan, CommissionEarning, CommissionStatement,
and CommissionAdjustment mapping directly to the 5 NavERP.md 8.10 feature bullets:
1. sales_commission_plan_hub (Bullet 1: Plan Design)
2. sales_commission_earnings_dashboard (Bullet 2: Real-Time Earnings Tracking & What-If Calculator)
3. sales_commission_adjustment_workbench (Bullet 3: Clawbacks & Adjustments)
4. sales_global_compensation_matrix (Bullet 4: Multi-Currency & Global Plans)
5. sales_commission_payout_processing (Bullet 5: Payout Processing & Integration)
"""
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import User
from apps.accounting.models import Currency, ExchangeRate, PayrollRun
from apps.sales.models.IncentiveCompensation.CommissionAdjustments import CommissionAdjustment
from apps.sales.models.IncentiveCompensation.CommissionEarnings import CommissionEarning
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan
from apps.sales.models.IncentiveCompensation.CommissionStatements import CommissionStatement


@login_required
def sales_commission_plan_hub(request):
    plans = (
        CommissionPlan.objects.filter(tenant=request.tenant)
        .select_related("currency", "sales_quota", "owner")
        .order_by("-effective_start", "name")
    )

    active_plans = plans.filter(status="active")
    active_plans_count = active_plans.count()
    avg_base_rate = active_plans.aggregate(avg=Avg("base_rate_pct"))["avg"] or 0.00
    reps_enrolled = (
        CommissionStatement.objects.filter(tenant=request.tenant)
        .values("payee")
        .distinct()
        .count()
    )

    stats = {
        "active_plans_count": active_plans_count,
        "avg_base_rate": round(avg_base_rate, 2),
        "reps_enrolled": reps_enrolled,
    }

    active_spifs = []
    tier_accelerator_benchmarks = []
    for p in active_plans:
        if p.spif_config:
            for spif in p.spif_config:
                active_spifs.append({
                    "plan_name": p.name,
                    "plan_pk": p.pk,
                    "currency": p.currency.code,
                    "campaign": spif.get("name", "Campaign"),
                    "bonus": spif.get("bonus_amount", 0),
                    "criteria": spif.get("criteria", "Standard"),
                })
        if p.tiers_config:
            tier_accelerator_benchmarks.append({
                "plan_name": p.name,
                "plan_pk": p.pk,
                "tier_mode": p.get_tier_mode_display(),
                "tiers": p.tiers_config,
            })

    context = {
        "plans": plans,
        "active_spifs": active_spifs,
        "tier_accelerator_benchmarks": tier_accelerator_benchmarks,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/boards/plan_hub.html", context)


@login_required
def sales_commission_earnings_dashboard(request):
    earnings = (
        CommissionEarning.objects.filter(tenant=request.tenant)
        .select_related("plan", "payee", "opportunity", "deal_currency")
        .order_by("-earned_date", "-created_at")
    )

    recent_earnings = earnings[:12]

    # Aggregate by payee
    payee_summary = []
    reps = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name")
    for rep in reps:
        rep_earnings = earnings.filter(payee=rep)
        if rep_earnings.exists():
            totals = rep_earnings.aggregate(
                vol=Sum("credited_volume"),
                gross=Sum("gross_commission"),
                spif=Sum("spif_amount"),
                avg_attainment=Avg("attainment_pct_at_close"),
            )
            payee_summary.append({
                "payee": rep,
                "volume": totals["vol"] or Decimal("0.00"),
                "gross": totals["gross"] or Decimal("0.00"),
                "spif": totals["spif"] or Decimal("0.00"),
                "attainment": round(totals["avg_attainment"] or Decimal("0.00"), 1),
            })

    # Overall attainment gauge metrics
    avg_team_attainment = (
        earnings.aggregate(avg=Avg("attainment_pct_at_close"))["avg"] or Decimal("0.00")
    )
    total_gross_earned = earnings.aggregate(gross=Sum("gross_commission"))["gross"] or Decimal("0.00")
    total_spif_earned = earnings.aggregate(spif=Sum("spif_amount"))["spif"] or Decimal("0.00")

    attainment_gauge = {
        "avg_team_attainment": round(avg_team_attainment, 1),
        "total_gross_earned": total_gross_earned,
        "total_spif_earned": total_spif_earned,
    }

    plans = CommissionPlan.objects.filter(tenant=request.tenant, status="active").order_by("name")

    context = {
        "payee_summary": payee_summary,
        "recent_earnings": recent_earnings,
        "attainment_gauge": attainment_gauge,
        "plans": plans,
    }
    return render(request, "sales/incentivecompensation/boards/earnings_dashboard.html", context)


@login_required
def sales_commission_adjustment_workbench(request):
    adjustments = (
        CommissionAdjustment.objects.filter(tenant=request.tenant)
        .select_related("statement", "earning", "payee", "requested_by")
        .order_by("-effective_date")
    )

    pending_clawbacks = adjustments.filter(
        adjustment_type="cancellation_clawback", status__in=["draft", "disputed"]
    )
    active_disputes = adjustments.filter(status="disputed")
    draw_reconciliation_queue = adjustments.filter(
        adjustment_type="draw_true_up", status__in=["draft", "approved"]
    )

    pending_clawback_amount = (
        pending_clawbacks.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    )

    stats = {
        "pending_clawback_amount": abs(pending_clawback_amount),
        "open_disputes_count": active_disputes.count(),
        "total_queue_items": adjustments.filter(status__in=["draft", "disputed"]).count(),
    }

    context = {
        "pending_clawbacks": pending_clawbacks,
        "active_disputes": active_disputes,
        "draw_reconciliation_queue": draw_reconciliation_queue,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/boards/adjustment_workbench.html", context)


@login_required
def sales_global_compensation_matrix(request):
    plans = (
        CommissionPlan.objects.filter(tenant=request.tenant)
        .select_related("currency")
        .order_by("target_region", "name")
    )

    regional_plans = {}
    for p in plans:
        reg = p.target_region.strip() if p.target_region else "Global"
        regional_plans.setdefault(reg, []).append(p)

    currencies = Currency.objects.filter(is_active=True).order_by("code")
    recent_exchange_rates = (
        ExchangeRate.objects.filter(tenant=request.tenant)
        .select_related("currency")
        .order_by("-rate_date")[:10]
    )

    tax_withholding_summary = (
        plans.values("target_region")
        .annotate(avg_tax=Avg("tax_withholding_pct"), plan_count=Count("id"))
        .order_by("target_region")
    )

    context = {
        "regional_plans": regional_plans,
        "currencies": currencies,
        "recent_exchange_rates": recent_exchange_rates,
        "tax_withholding_summary": tax_withholding_summary,
    }
    return render(request, "sales/incentivecompensation/boards/global_matrix.html", context)


@login_required
def sales_commission_payout_processing(request):
    statements = (
        CommissionStatement.objects.filter(tenant=request.tenant)
        .select_related("payee", "plan", "approved_by", "payroll_run")
        .order_by("-period_end")
    )

    ready_statements = statements.filter(status__in=["approved", "locked"])
    pending_approvals = statements.filter(status="under_review")
    payroll_runs = PayrollRun.objects.filter(tenant=request.tenant).order_by("-pay_date")[:5]

    total_payout_due = ready_statements.aggregate(s=Sum("net_payout"))["s"] or Decimal("0.00")
    statements_ready = ready_statements.count()
    payroll_integrated = statements.filter(payroll_run__isnull=False).count()

    stats = {
        "total_payout_due": total_payout_due,
        "statements_ready": statements_ready,
        "payroll_integrated": payroll_integrated,
    }

    context = {
        "ready_statements": ready_statements,
        "pending_approvals": pending_approvals,
        "payroll_runs": payroll_runs,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/boards/payout_processing.html", context)


@login_required
def sales_commission_what_if_calc(request):
    deal_amount = Decimal(str(request.GET.get("deal_amount") or 0))
    split_pct = Decimal(str(request.GET.get("split_pct") or 100))
    current_attainment = Decimal(str(request.GET.get("current_attainment") or 0))
    plan_id = request.GET.get("plan_id")

    if not plan_id or not plan_id.isdecimal():
        return JsonResponse({"error": "Valid plan required"}, status=400)

    plan = get_object_or_404(CommissionPlan.objects.filter(tenant=request.tenant), pk=int(plan_id))

    attributed_vol = round(deal_amount * split_pct / Decimal("100"), 2)

    # Estimate tier rate
    applied_rate = plan.base_rate_pct
    tier_name = "Base Rate"
    if plan.tiers_config and plan.plan_type in ("tiered_quota", "hybrid"):
        for t in plan.tiers_config:
            min_p = Decimal(str(t.get("min_pct", 0)))
            max_p = Decimal(str(t.get("max_pct", 9999)))
            if min_p <= current_attainment < max_p or (current_attainment >= max_p and t == plan.tiers_config[-1]):
                applied_rate = Decimal(str(t.get("rate_pct", plan.base_rate_pct)))
                tier_name = f"Tier ({min_p}% - {max_p}%)"

    base_comm = round(attributed_vol * applied_rate / Decimal("100"), 2)
    spif_bonus = Decimal("0.00")
    if plan.spif_config:
        spif_bonus = Decimal(str(plan.spif_config[0].get("bonus_amount", 0)))

    projected_gross = round(base_comm + spif_bonus, 2)

    return JsonResponse({
        "ok": True,
        "attributed_volume": float(attributed_vol),
        "applied_rate_pct": float(applied_rate),
        "tier_bracket_name": tier_name,
        "base_commission": float(base_comm),
        "spif_bonus": float(spif_bonus),
        "projected_gross": float(projected_gross),
        "currency": plan.currency.code,
    })
