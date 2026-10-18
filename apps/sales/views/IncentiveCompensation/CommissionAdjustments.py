"""Sales 8.10 — Views for `CommissionAdjustment`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IncentiveCompensation.CommissionAdjustments import CommissionAdjustmentForm
from apps.sales.models.IncentiveCompensation.CommissionAdjustments import (
    ADJUSTMENT_TYPE_CHOICES,
    STATUS_CHOICES,
    CommissionAdjustment,
)


@login_required
def commission_adjustment_list(request):
    qs = (
        CommissionAdjustment.objects.filter(tenant=request.tenant)
        .select_related("statement", "earning", "payee", "approved_by")
        .order_by("-effective_date", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(reason__icontains=q)
            | Q(payee__first_name__icontains=q)
            | Q(payee__last_name__icontains=q)
            | Q(payee__email__icontains=q)
            | Q(number__icontains=q)
        )

    adjustment_type = request.GET.get("adjustment_type", "").strip()
    if adjustment_type:
        qs = qs.filter(adjustment_type=adjustment_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    payee_id = request.GET.get("payee", "").strip()
    if payee_id.isdecimal():
        qs = qs.filter(payee_id=int(payee_id))

    total_adj = qs.aggregate(val=Sum("amount"))["val"] or 0.00
    clawbacks_sum = qs.filter(adjustment_type="cancellation_clawback").aggregate(val=Sum("amount"))["val"] or 0.00
    disputes_count = qs.filter(status="disputed").count()
    approved_count = qs.filter(status__in=["approved", "applied"]).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = {
        "total_adjustments": total_adj,
        "clawbacks_total": clawbacks_sum,
        "disputes_count": disputes_count,
        "approved_count": approved_count,
    }

    payees = User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name")

    context = {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "adjustment_type_choices": ADJUSTMENT_TYPE_CHOICES,
        "status_choices": STATUS_CHOICES,
        "payees": payees,
        "stats": stats,
    }
    return render(request, "sales/incentivecompensation/commissionadjustment/list.html", context)


@login_required
def commission_adjustment_detail(request, pk):
    obj = get_object_or_404(
        CommissionAdjustment.objects.filter(tenant=request.tenant).select_related(
            "statement", "earning", "payee", "requested_by", "approved_by"
        ),
        pk=pk,
    )

    context = {
        "obj": obj,
        "status_display": obj.get_status_display(),
        "adjustment_type_display": obj.get_adjustment_type_display(),
    }
    return render(request, "sales/incentivecompensation/commissionadjustment/detail.html", context)


@login_required
def commission_adjustment_create(request):
    if request.method == "POST":
        form = CommissionAdjustmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.requested_by = request.user
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                {"pk": obj.pk, "number": obj.number, "amount": str(obj.amount)},
                tenant=request.tenant,
            )
            messages.success(request, f"Adjustment {obj.number} created.")
            return redirect("sales:commission_adjustment_detail", pk=obj.pk)
    else:
        initial = {}
        if request.GET.get("earning"):
            initial["earning"] = request.GET.get("earning")
        if request.GET.get("statement"):
            initial["statement"] = request.GET.get("statement")
        form = CommissionAdjustmentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "obj": None,
        "is_edit": False,
        "adjustment_type_choices": ADJUSTMENT_TYPE_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionadjustment/form.html", context)


@login_required
def commission_adjustment_edit(request, pk):
    obj = get_object_or_404(CommissionAdjustment.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status == "applied":
        messages.error(request, "Applied adjustments cannot be edited.")
        return redirect("sales:commission_adjustment_detail", pk=obj.pk)

    if request.method == "POST":
        form = CommissionAdjustmentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                {"pk": obj.pk, "number": obj.number, "amount": str(obj.amount)},
                tenant=request.tenant,
            )
            messages.success(request, f"Adjustment {obj.number} updated.")
            return redirect("sales:commission_adjustment_detail", pk=obj.pk)
    else:
        form = CommissionAdjustmentForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "adjustment_type_choices": ADJUSTMENT_TYPE_CHOICES,
    }
    return render(request, "sales/incentivecompensation/commissionadjustment/form.html", context)


@login_required
@require_POST
def commission_adjustment_resolve_dispute(request, pk):
    obj = get_object_or_404(CommissionAdjustment.objects.filter(tenant=request.tenant), pk=pk)
    decision = request.POST.get("decision")
    notes = request.POST.get("resolution_notes", "").strip()

    if decision == "approve":
        obj.status = "approved"
        obj.approved_by = request.user
    elif decision == "reject":
        obj.status = "rejected"
    else:
        messages.error(request, "Invalid resolution decision.")
        return redirect("sales:commission_adjustment_detail", pk=obj.pk)

    if notes:
        existing = obj.dispute_comments or ""
        obj.dispute_comments = f"{existing}\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {request.user.email}: {notes}".strip()

    obj.save()
    write_audit_log(
        request.user,
        obj,
        "update",
        {"pk": obj.pk, "action": f"dispute_{decision}", "notes": notes},
        tenant=request.tenant,
    )
    messages.success(request, f"Dispute on adjustment {obj.number} updated to {obj.get_status_display()}.")
    return redirect("sales:commission_adjustment_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def commission_adjustment_delete(request, pk):
    obj = get_object_or_404(CommissionAdjustment.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status == "applied":
        messages.error(request, "Cannot delete an adjustment that has been applied to a statement.")
        return redirect("sales:commission_adjustment_detail", pk=obj.pk)

    num = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        {"pk": obj.pk, "number": num},
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Adjustment {num} deleted.")
    return redirect("sales:commission_adjustment_list")
