from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysisForm
from apps.assets.models import AssetCategory
from apps.assets.models.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysis
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_lease_buy_analysis_list(request):
    qs = assets_scope(
        AssetLeaseBuyAnalysis.objects.select_related(
            "category", "evaluated_by", "approved_by"
        ).defer("description", "evaluation_notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(target_asset_name__icontains=q)
            | Q(description__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    recommendation_filter = request.GET.get("recommendation", "").strip()
    if recommendation_filter:
        qs = qs.filter(recommendation=recommendation_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter and category_filter.isdigit():
        qs = qs.filter(category_id=int(category_filter))

    base_tenant_qs = assets_scope(AssetLeaseBuyAnalysis.objects.all(), request)
    kpi_agg = base_tenant_qs.aggregate(
        total_analyses=Count("id"),
        buy_recommended=Count("id", filter=Q(recommendation="buy")),
        lease_recommended=Count("id", filter=Q(recommendation="lease")),
    )
    total_analyses = kpi_agg["total_analyses"] or 0
    buy_recommended_count = kpi_agg["buy_recommended"] or 0
    lease_recommended_count = kpi_agg["lease_recommended"] or 0

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    category_list = AssetCategory.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "analyses": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetLeaseBuyAnalysis.STATUS_CHOICES,
        "recommendation_choices": AssetLeaseBuyAnalysis.RECOMMENDATION_CHOICES,
        "category_list": category_list,
        "total_analyses": total_analyses,
        "buy_recommended_count": buy_recommended_count,
        "lease_recommended_count": lease_recommended_count,
        "q": q,
        "status": status_filter,
        "recommendation": recommendation_filter,
        "category": category_filter,
    }
    return render(request, "assets/assetleaserental/asset_lease_buy_analysis/list.html", context)


@login_required
def asset_lease_buy_analysis_detail(request, pk):
    analysis = assets_object(
        request,
        AssetLeaseBuyAnalysis,
        pk,
        select_related=["category", "evaluated_by", "approved_by"],
    )
    return render(
        request,
        "assets/assetleaserental/asset_lease_buy_analysis/detail.html",
        {"analysis": analysis},
    )


@login_required
def asset_lease_buy_analysis_create(request):
    if request.method == "POST":
        form = AssetLeaseBuyAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.evaluate_financial_models()
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes=f"Created Lease vs Buy Analysis {instance.number} ({instance.title})",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease vs. Buy Analysis {instance.number} created and evaluated.")
                return redirect("assets:asset_lease_buy_analysis_detail", pk=instance.pk)
    else:
        form = AssetLeaseBuyAnalysisForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_buy_analysis/form.html",
        {"form": form, "title": "New Lease vs. Buy Analysis", "is_edit": False},
    )


@login_required
def asset_lease_buy_analysis_edit(request, pk):
    analysis = assets_object(request, AssetLeaseBuyAnalysis, pk)

    if request.method == "POST":
        form = AssetLeaseBuyAnalysisForm(request.POST, instance=analysis, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.evaluate_financial_models()
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes=f"Updated Lease vs Buy Analysis {instance.number}",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease vs. Buy Analysis {instance.number} updated and recalculated.")
                return redirect("assets:asset_lease_buy_analysis_detail", pk=instance.pk)
    else:
        form = AssetLeaseBuyAnalysisForm(instance=analysis, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_buy_analysis/form.html",
        {"form": form, "title": f"Edit Analysis — {analysis.number}", "is_edit": True, "analysis": analysis},
    )


@require_POST
@tenant_admin_required
def asset_lease_buy_analysis_delete(request, pk):
    analysis = assets_object(request, AssetLeaseBuyAnalysis, pk)
    num = analysis.number
    write_audit_log(
        request.user,
        analysis,
        "delete",
        changes=f"Deleted Lease vs Buy Analysis {num}",
        tenant=request.tenant,
    )
    analysis.delete()
    messages.success(request, f"Analysis {num} was deleted.")
    return redirect("assets:asset_lease_buy_analysis_list")


@require_POST
@login_required
def asset_lease_buy_analysis_evaluate(request, pk):
    analysis = assets_object(request, AssetLeaseBuyAnalysis, pk)
    rec = analysis.evaluate_financial_models()
    analysis.save()

    write_audit_log(
        request.user,
        analysis,
        "evaluate",
        changes=f"Recalculated financial metrics for {analysis.number}: Recommendation={analysis.get_recommendation_display()}",
        tenant=request.tenant,
    )

    messages.info(
        request,
        f"Analysis {analysis.number} evaluated: NPV(Buy)=${analysis.npv_purchase_option:,.2f}, "
        f"NPV(Lease)=${analysis.npv_lease_option:,.2f}, NAL=${analysis.net_advantage_to_leasing:,.2f} -> "
        f"Recommendation: {analysis.get_recommendation_display()}.",
    )
    return redirect("assets:asset_lease_buy_analysis_detail", pk=analysis.pk)
