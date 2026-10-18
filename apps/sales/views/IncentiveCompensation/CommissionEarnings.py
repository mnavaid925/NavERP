"""Sales 8.10 — Views for `CommissionEarning`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IncentiveCompensation.CommissionEarnings import CommissionEarningForm
from apps.sales.models.IncentiveCompensation.CommissionEarnings import (
    CREDIT_TYPE_CHOICES,
    STATUS_CHOICES,
    CommissionEarning,
)
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan


@login_required
def commission_earning_list(request):
    qs = (
        CommissionEarning.objects.filter(tenant=request.tenant)
        .select_related("plan", "payee", "opportunity", "sales_order", "deal_currency", "statement")
        .order_by("-earned_date", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(payee__first_name__icontains=q)
            | Q(payee__last_name__icontains=q)
            | Q(payee__email__icontains=q)
            | Q(opportunity__name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    credit_type = request.GET.get("credit_type", "").strip()
    if credit_type:
        qs = qs.filter(credit_type=credit_type)

    payee_id = request.GET.get("payee", "").strip()
    if payee_id.isdecimal():
        qs = qs.filter(payee_id=int(payee_id))

    plan_id = request.GET.get("plan", "").strip()
    if plan_id.isdecimal():
        qs = qs.filter(plan_id=int(plan_id))

    total_gross = qs.aggregate(val=Sum("gross_commission"))["val"] or 0.00
    total_spif = qs.aggregate(val=Sum("spif_amount"))["val"] or 0.00
    calculated_count = qs.filter(status="calculated").count()
    paid_count = qs.filter(status="paid").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = {
        "total_gross": total_gross,
        "total_spif": total_spif,
        "calculated_count": calculated_count,
        "paid_count": paid_count,
    }

    payees = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name")
    plans = CommissionPlan.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": STATUS_CHOICES,
        "credit_type_choices": CREDIT_TYPE_CHOICES,
        "payees": payees,
        "plans": plans,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/commissionearning/list.html", context)


@login_required
def commission_earning_detail(request, pk):
    obj = get_object_or_404(
        CommissionEarning.objects.filter(tenant=request.tenant).select_related(
            "plan", "payee", "opportunity", "sales_order", "deal_currency", "statement", "clawback_parent"
        ),
        pk=pk,
    )

    deal_split_info = None
    if obj.opportunity:
        splits = obj.opportunity.splits.select_related("user").all() if hasattr(obj.opportunity, "splits") else []
        deal_split_info = list(splits)

    context = {
        "obj": obj,
        "status_display": obj.get_status_display(),
        "credit_type_display": obj.get_credit_type_display(),
        "deal_split_info": deal_split_info,
    }
    return render(request, "sales/incentivecompensation/commissionearning/detail.html", context)


@login_required
def commission_earning_create(request):
    if request.method == "POST":
        form = CommissionEarningForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                {"pk": obj.pk, "number": obj.number, "gross": str(obj.gross_commission)},
                tenant=request.tenant,
            )
            messages.success(request, f"Commission earning {obj.number} recorded.")
            return redirect("sales:commission_earning_detail", pk=obj.pk)
    else:
        initial = {}
        if request.GET.get("plan"):
            initial["plan"] = request.GET.get("plan")
        form = CommissionEarningForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "obj": None,
        "is_edit": False,
        "credit_type_choices": CREDIT_TYPE_CHOICES,
        "status_choices": STATUS_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionearning/form.html", context)


@login_required
def commission_earning_edit(request, pk):
    obj = get_object_or_404(CommissionEarning.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status in ("approved", "paid", "clawed_back") or (
        obj.statement and obj.statement.status in ("locked", "exported", "paid")
    ):
        messages.error(
            request,
            f"Commission earning {obj.number} cannot be edited in '{obj.get_status_display()}' status or when attached to a locked statement.",
        )
        return redirect("sales:commission_earning_detail", pk=obj.pk)

    if request.method == "POST":
        form = CommissionEarningForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                {"pk": obj.pk, "number": obj.number, "gross": str(obj.gross_commission)},
                tenant=request.tenant,
            )
            messages.success(request, f"Commission earning {obj.number} updated.")
            return redirect("sales:commission_earning_detail", pk=obj.pk)
    else:
        form = CommissionEarningForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "credit_type_choices": CREDIT_TYPE_CHOICES,
        "status_choices": STATUS_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionearning/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def commission_earning_delete(request, pk):
    obj = get_object_or_404(CommissionEarning.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status in ("approved", "paid", "clawed_back") or (
        obj.statement and obj.statement.status in ("locked", "exported", "paid")
    ):
        messages.error(
            request,
            f"Commission earning {obj.number} cannot be deleted in '{obj.get_status_display()}' status or when attached to a locked statement.",
        )
        return redirect("sales:commission_earning_detail", pk=obj.pk)

    num = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        {"pk": obj.pk, "number": num},
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Commission earning {num} deleted.")
    return redirect("sales:commission_earning_list")
