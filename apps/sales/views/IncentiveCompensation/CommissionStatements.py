"""Sales 8.10 — Views for `CommissionStatement`."""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IncentiveCompensation.CommissionStatements import CommissionStatementForm
from apps.sales.models.IncentiveCompensation.CommissionEarnings import CommissionEarning
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan
from apps.sales.models.IncentiveCompensation.CommissionStatements import (
    STATEMENT_STATUS_CHOICES,
    CommissionStatement,
)


@login_required
def commission_statement_list(request):
    qs = (
        CommissionStatement.objects.filter(tenant=request.tenant)
        .select_related("payee", "plan", "approved_by", "payroll_run")
        .order_by("-period_end", "payee__email")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(statement_number__icontains=q)
            | Q(payee__first_name__icontains=q)
            | Q(payee__last_name__icontains=q)
            | Q(payee__email__icontains=q)
            | Q(number__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    payee_id = request.GET.get("payee", "").strip()
    if payee_id.isdecimal():
        qs = qs.filter(payee_id=int(payee_id))

    total_net = qs.aggregate(val=Sum("net_payout"))["val"] or 0.00
    locked_count = qs.filter(status__in=["locked", "exported", "paid"]).count()
    pending_approval = qs.filter(status="under_review").count()
    draws_rec = qs.aggregate(val=Sum("draw_recovered"))["val"] or 0.00

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = {
        "total_net_payout": total_net,
        "locked_count": locked_count,
        "pending_approval": pending_approval,
        "total_draws_recovered": draws_rec,
    }

    payees = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name")

    context = {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": STATEMENT_STATUS_CHOICES,
        "payees": payees,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/commissionstatement/list.html", context)


@login_required
def commission_statement_detail(request, pk):
    obj = get_object_or_404(
        CommissionStatement.objects.filter(tenant=request.tenant).select_related(
            "payee", "plan", "approved_by", "payroll_run"
        ),
        pk=pk,
    )

    earnings_list = (
        obj.earnings.filter(tenant=request.tenant)
        .select_related("opportunity", "deal_currency")
        .order_by("-earned_date")
    )

    adjustments_list = (
        obj.adjustments.filter(tenant=request.tenant)
        .select_related("approved_by")
        .order_by("-effective_date")
    )

    can_approve = obj.status in ("draft", "under_review")
    can_lock = obj.status == "approved"

    context = {
        "obj": obj,
        "status_display": obj.get_status_display(),
        "earnings_list": earnings_list,
        "adjustments_list": adjustments_list,
        "can_approve": can_approve,
        "can_lock": can_lock,
    }
    return render(request, "sales/incentivecompensation/commissionstatement/detail.html", context)


@login_required
def commission_statement_create(request):
    if request.method == "POST":
        form = CommissionStatementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(
                request.user,
                "sales.CommissionStatement",
                "create",
                {"pk": obj.pk, "number": obj.number, "statement_number": obj.statement_number},
                tenant=request.tenant,
            )
            messages.success(request, f"Commission statement {obj.statement_number} created.")
            return redirect("sales:commission_statement_detail", pk=obj.pk)
    else:
        form = CommissionStatementForm(tenant=request.tenant)

    context = {
        "form": form,
        "obj": None,
        "is_edit": False,
        "status_choices": STATEMENT_STATUS_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionstatement/form.html", context)


@login_required
def commission_statement_edit(request, pk):
    obj = get_object_or_404(CommissionStatement.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status in ("locked", "exported", "paid"):
        messages.error(request, "Locked or exported statements cannot be edited directly.")
        return redirect("sales:commission_statement_detail", pk=obj.pk)

    if request.method == "POST":
        form = CommissionStatementForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                "sales.CommissionStatement",
                "update",
                {"pk": obj.pk, "statement_number": obj.statement_number},
                tenant=request.tenant,
            )
            messages.success(request, f"Statement {obj.statement_number} updated.")
            return redirect("sales:commission_statement_detail", pk=obj.pk)
    else:
        form = CommissionStatementForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "status_choices": STATEMENT_STATUS_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionstatement/form.html", context)


@login_required
@require_POST
def commission_statement_approve(request, pk):
    obj = get_object_or_404(CommissionStatement.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save()
    write_audit_log(
        request.user,
        "sales.CommissionStatement",
        "update",
        {"pk": obj.pk, "action": "approve"},
        tenant=request.tenant,
    )
    messages.success(request, f"Statement {obj.statement_number} approved.")
    return redirect("sales:commission_statement_detail", pk=obj.pk)


@login_required
@require_POST
def commission_statement_lock(request, pk):
    obj = get_object_or_404(CommissionStatement.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "locked"
    obj.locked_at = timezone.now()
    obj.save()
    write_audit_log(
        request.user,
        "sales.CommissionStatement",
        "update",
        {"pk": obj.pk, "action": "lock"},
        tenant=request.tenant,
    )
    messages.success(request, f"Statement {obj.statement_number} finalized and locked.")
    return redirect("sales:commission_statement_detail", pk=obj.pk)


@login_required
@require_POST
def commission_statement_generate_batch(request):
    period_start = request.POST.get("period_start")
    period_end = request.POST.get("period_end")
    plan_id = request.POST.get("plan_id")

    if not period_start or not period_end or not plan_id:
        messages.error(request, "Please specify period start, period end, and compensation plan.")
        return redirect("sales:commission_statement_list")

    plan = get_object_or_404(CommissionPlan.objects.filter(tenant=request.tenant), pk=plan_id)
    reps = User.objects.filter(tenant=request.tenant, is_active=True)

    created_count = 0
    with transaction.atomic():
        for rep in reps:
            # Check if statement already exists for this payee & period
            if CommissionStatement.objects.filter(
                tenant=request.tenant, payee=rep, period_start=period_start, period_end=period_end
            ).exists():
                continue

            # Query unattached earnings in period
            unattached = CommissionEarning.objects.filter(
                tenant=request.tenant,
                payee=rep,
                earned_date__gte=period_start,
                earned_date__lte=period_end,
                statement__isnull=True,
            )

            vol = unattached.aggregate(s=Sum("credited_volume"))["s"] or Decimal("0.00")
            base = unattached.aggregate(s=Sum("base_commission_amount"))["s"] or Decimal("0.00")
            spif = unattached.aggregate(s=Sum("spif_amount"))["s"] or Decimal("0.00")
            gross = unattached.aggregate(s=Sum("gross_commission"))["s"] or Decimal("0.00")

            code = f"STMT-{period_end[:7]}-{rep.id}"
            stmt = CommissionStatement.objects.create(
                tenant=request.tenant,
                statement_number=code,
                payee=rep,
                plan=plan,
                period_start=period_start,
                period_end=period_end,
                status="draft",
                total_credited_volume=vol,
                total_base_commission=base,
                total_spif_amount=spif,
                gross_earnings=gross,
                draw_advance_paid=plan.draw_amount,
                draw_recovered=min(gross, plan.draw_amount) if plan.is_draw_recoverable else Decimal("0.00"),
                net_payout=gross,
            )
            unattached.update(statement=stmt)
            created_count += 1

    messages.success(request, f"Batch generated {created_count} statement(s) for {period_start} to {period_end}.")
    return redirect("sales:commission_statement_list")


@login_required
@require_POST
@tenant_admin_required
def commission_statement_delete(request, pk):
    obj = get_object_or_404(CommissionStatement.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status in ("locked", "exported", "paid"):
        messages.error(request, "Cannot delete a locked statement.")
        return redirect("sales:commission_statement_detail", pk=obj.pk)

    stmt_num = obj.statement_number
    write_audit_log(
        request.user,
        "sales.CommissionStatement",
        "delete",
        {"pk": obj.pk, "statement_number": stmt_num},
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Statement {stmt_num} deleted.")
    return redirect("sales:commission_statement_list")
