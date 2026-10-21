"""Sales 8.14 — Views for `JointAccountPlan`."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.PartnerChannel.JointAccountPlans import JointAccountPlanForm
from apps.sales.models.PartnerChannel.JointAccountPlans import (
    CO_SELL_MOTION_CHOICES,
    PLAN_STATUS_CHOICES,
    JointAccountPlan,
)


@login_required
def joint_account_plan_list(request):
    qs = (
        JointAccountPlan.objects.filter(tenant=request.tenant)
        .select_related("partner", "client_account", "currency", "vendor_lead", "collateral_document")
        .order_by("-period_end", "-target_revenue")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(plan_name__icontains=q)
            | Q(number__icontains=q)
            | Q(partner__name__icontains=q)
            | Q(client_account__name__icontains=q)
            | Q(partner_lead_name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    co_sell_motion = request.GET.get("co_sell_motion", "").strip()
    if co_sell_motion:
        qs = qs.filter(co_sell_motion=co_sell_motion)

    partner_id = request.GET.get("partner", "").strip()
    if partner_id and partner_id.isdigit():
        qs = qs.filter(partner_id=int(partner_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        achieved_count=Count("id", filter=Q(status="achieved")),
        total_target=Sum("target_revenue"),
        total_actual=Sum("actual_revenue"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    partners = (
        Party.objects.filter(tenant=request.tenant, roles__role="partner")
        .distinct()
        .order_by("name")
    )
    if not partners.exists():
        partners = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "joint_plans": page_obj.object_list,
        "status_choices": PLAN_STATUS_CHOICES,
        "motion_choices": CO_SELL_MOTION_CHOICES,
        "partners": partners,
        "stats": stats,
        "q": q,
        "selected_status": status,
        "selected_motion": co_sell_motion,
        "selected_partner": partner_id,
    }
    return render(request, "sales/partnerchannel/jointaccountplan/list.html", context)


@login_required
def joint_account_plan_detail(request, pk):
    joint_plan = get_object_or_404(
        JointAccountPlan.objects.filter(tenant=request.tenant).select_related(
            "partner", "client_account", "currency", "vendor_lead", "collateral_document"
        ),
        pk=pk,
    )

    context = {
        "joint_plan": joint_plan,
    }
    return render(request, "sales/partnerchannel/jointaccountplan/detail.html", context)


@login_required
def joint_account_plan_create(request):
    if request.method == "POST":
        form = JointAccountPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(
                user=request.user,
                obj=obj,
                action="create",
                changes=f"Created joint account plan {obj.number} — {obj.plan_name}",
                tenant=request.tenant,
            )
            messages.success(request, f"Joint account plan {obj.number} created successfully.")
            return redirect("sales:joint_account_plan_detail", pk=obj.pk)
    else:
        form = JointAccountPlanForm(tenant=request.tenant)

    return render(request, "sales/partnerchannel/jointaccountplan/form.html", {"form": form, "is_edit": False})


@login_required
def joint_account_plan_edit(request, pk):
    obj = get_object_or_404(JointAccountPlan.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = JointAccountPlanForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(
                user=request.user,
                obj=obj,
                action="update",
                changes=f"Updated joint account plan {obj.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Joint account plan {obj.number} updated successfully.")
            return redirect("sales:joint_account_plan_detail", pk=obj.pk)
    else:
        form = JointAccountPlanForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/partnerchannel/jointaccountplan/form.html",
        {"form": form, "joint_plan": obj, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def joint_account_plan_delete(request, pk):
    obj = get_object_or_404(JointAccountPlan.objects.filter(tenant=request.tenant), pk=pk)
    number = obj.number
    write_audit_log(
        user=request.user,
        obj=obj,
        action="delete",
        changes=f"Deleted joint account plan {number}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Joint account plan {number} deleted successfully.")
    return redirect("sales:joint_account_plan_list")
