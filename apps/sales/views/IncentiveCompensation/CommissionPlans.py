"""Sales 8.10 — Views for `CommissionPlan`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IncentiveCompensation.CommissionPlans import CommissionPlanForm
from apps.sales.models.IncentiveCompensation.CommissionPlans import (
    PLAN_TYPE_CHOICES,
    STATUS_CHOICES,
    TIER_MODE_CHOICES,
    CommissionPlan,
)


@login_required
def commission_plan_list(request):
    qs = (
        CommissionPlan.objects.filter(tenant=request.tenant)
        .select_related("currency", "sales_quota", "owner")
        .order_by("-effective_start", "name")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(description__icontains=q)
            | Q(number__icontains=q)
            | Q(target_region__icontains=q)
        )

    plan_type = request.GET.get("plan_type", "").strip()
    if plan_type:
        qs = qs.filter(plan_type=plan_type)

    tier_mode = request.GET.get("tier_mode", "").strip()
    if tier_mode:
        qs = qs.filter(tier_mode=tier_mode)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    total_count = qs.count()
    active_count = qs.filter(status="active").count()
    tiered_count = qs.filter(plan_type__in=["tiered_quota", "hybrid"]).count()
    spif_count = qs.filter(plan_type__in=["spif_only", "hybrid"]).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = {
        "total": total_count,
        "active": active_count,
        "tiered": tiered_count,
        "spif": spif_count,
    }

    context = {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "plan_type_choices": PLAN_TYPE_CHOICES,
        "tier_mode_choices": TIER_MODE_CHOICES,
        "status_choices": STATUS_CHOICES,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/commissionplan/list.html", context)


@login_required
def commission_plan_detail(request, pk):
    obj = get_object_or_404(
        CommissionPlan.objects.filter(tenant=request.tenant).select_related(
            "currency", "sales_quota", "owner"
        ),
        pk=pk,
    )

    recent_earnings = (
        obj.earnings.filter(tenant=request.tenant)
        .select_related("payee", "opportunity")
        .order_by("-earned_date")[:10]
    )

    assigned_reps = (
        obj.statements.filter(tenant=request.tenant)
        .values_list("payee__first_name", "payee__last_name", "payee__email")
        .distinct()[:15]
    )

    context = {
        "obj": obj,
        "plan_type_display": obj.get_plan_type_display(),
        "tier_mode_display": obj.get_tier_mode_display(),
        "status_display": obj.get_status_display(),
        "assigned_reps": assigned_reps,
        "recent_earnings": recent_earnings,
    }
    return render(request, "sales/incentivecompensation/commissionplan/detail.html", context)


@login_required
def commission_plan_create(request):
    if request.method == "POST":
        form = CommissionPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                {"pk": obj.pk, "number": obj.number, "name": obj.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Commission Plan {obj.name} created successfully.")
            return redirect("sales:commission_plan_detail", pk=obj.pk)
    else:
        form = CommissionPlanForm(tenant=request.tenant)

    context = {
        "form": form,
        "obj": None,
        "is_edit": False,
        "plan_type_choices": PLAN_TYPE_CHOICES,
        "tier_mode_choices": TIER_MODE_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionplan/form.html", context)


@login_required
def commission_plan_edit(request, pk):
    obj = get_object_or_404(CommissionPlan.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = CommissionPlanForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                {"pk": obj.pk, "number": obj.number, "name": obj.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Commission Plan {obj.name} updated.")
            return redirect("sales:commission_plan_detail", pk=obj.pk)
    else:
        form = CommissionPlanForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "plan_type_choices": PLAN_TYPE_CHOICES,
        "tier_mode_choices": TIER_MODE_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionplan/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def commission_plan_delete(request, pk):
    obj = get_object_or_404(CommissionPlan.objects.filter(tenant=request.tenant), pk=pk)
    name = obj.name
    write_audit_log(
        request.user,
        obj,
        "delete",
        {"pk": obj.pk, "number": obj.number, "name": name},
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Commission Plan {name} deleted.")
    return redirect("sales:commission_plan_list")
