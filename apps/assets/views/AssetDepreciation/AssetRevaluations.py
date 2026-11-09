from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDepreciation.AssetRevaluations import AssetRevaluationForm
from apps.assets.models.AssetDepreciation.AssetRevaluations import AssetRevaluation
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def revaluation_list(request):
    qs = AssetRevaluation.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "appraiser"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(appraiser_name_fallback__icontains=q)
            | Q(reason_and_methodology__icontains=q)
        )

    selected_event_type = request.GET.get("event_type", "").strip()
    if selected_event_type:
        qs = qs.filter(event_type=selected_event_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    all_tenant_events = AssetRevaluation.objects.filter(tenant=request.tenant)
    agg = all_tenant_events.aggregate(
        total_events=Count("id"),
        approved_count=Count("id", filter=Q(status="approved")),
        impairment_count=Count("id", filter=Q(event_type="impairment")),
        surplus_count=Count("id", filter=Q(event_type="revaluation_up")),
        total_adj=Sum("revaluation_adjustment"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "revaluations": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "event_type_choices": AssetRevaluation.EVENT_TYPE_CHOICES,
        "status_choices": AssetRevaluation.STATUS_CHOICES,
        "total_adjustment_value": agg["total_adj"] or Decimal("0.00"),
        "total_events": agg["total_events"] or 0,
        "approved_count": agg["approved_count"] or 0,
        "impairment_count": agg["impairment_count"] or 0,
        "surplus_count": agg["surplus_count"] or 0,
        "q": q,
        "search_query": q,
        "selected_event_type": selected_event_type,
        "selected_status": selected_status,
    }
    return render(request, "assets/asset_depreciation/revaluation/list.html", context)


@login_required
def revaluation_detail(request, pk):
    revaluation = assets_object(
        request,
        AssetRevaluation,
        pk=pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "appraiser",
            "impairment_loss_account",
            "revaluation_surplus_account",
            "journal_entry",
            "approved_by",
        ],
    )
    context = {
        "revaluation": revaluation,
        "object": revaluation,
    }
    return render(request, "assets/asset_depreciation/revaluation/detail.html", context)


@login_required
def revaluation_create(request):
    if request.method == "POST":
        form = AssetRevaluationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            revaluation = form.save(commit=False)
            revaluation.tenant = request.tenant
            revaluation.save()
            revaluation.calculate_adjustment()
            revaluation.save()
            write_audit_log(request.user, revaluation, "create", tenant=request.tenant)
            messages.success(
                request, f"Asset revaluation {revaluation.number} created successfully."
            )
            return redirect("assets:revaluation_detail", pk=revaluation.pk)
    else:
        form = AssetRevaluationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "revaluation": None,
        "object": None,
    }
    return render(request, "assets/asset_depreciation/revaluation/form.html", context)


@login_required
def revaluation_edit(request, pk):
    revaluation = assets_object(request, AssetRevaluation, pk=pk)
    if revaluation.status == "approved":
        messages.error(request, "Approved revaluations cannot be edited.")
        return redirect("assets:revaluation_detail", pk=revaluation.pk)

    if request.method == "POST":
        form = AssetRevaluationForm(
            request.POST, instance=revaluation, tenant=request.tenant
        )
        if form.is_valid():
            revaluation = form.save(commit=False)
            revaluation.save()
            revaluation.calculate_adjustment()
            revaluation.save()
            write_audit_log(request.user, revaluation, "update", tenant=request.tenant)
            messages.success(
                request, f"Asset revaluation {revaluation.number} updated successfully."
            )
            return redirect("assets:revaluation_detail", pk=revaluation.pk)
    else:
        form = AssetRevaluationForm(instance=revaluation, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "revaluation": revaluation,
        "object": revaluation,
    }
    return render(request, "assets/asset_depreciation/revaluation/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def revaluation_delete(request, pk):
    revaluation = assets_object(request, AssetRevaluation, pk=pk)
    if revaluation.status == "approved":
        messages.error(request, "Cannot delete an approved revaluation record.")
        return redirect("assets:revaluation_detail", pk=revaluation.pk)

    num = revaluation.number
    revaluation.delete()
    write_audit_log(request.user, revaluation, "delete", tenant=request.tenant)
    messages.success(request, f"Revaluation record {num} deleted.")
    return redirect("assets:revaluation_list")


@login_required
@require_POST
@tenant_admin_required
def revaluation_approve(request, pk):
    revaluation = assets_object(request, AssetRevaluation, pk=pk)
    try:
        je = revaluation.execute_revaluation(user=request.user)
        write_audit_log(request.user, revaluation, "approve", tenant=request.tenant)
        msg = f"Revaluation {revaluation.number} approved and applied to fixed asset subledger."
        if je:
            msg += f" Journal Entry {je.number} created."
        messages.success(request, msg)
    except ValidationError as exc:
        messages.error(request, str(exc.message if hasattr(exc, "message") else exc))

    return redirect("assets:revaluation_detail", pk=revaluation.pk)
