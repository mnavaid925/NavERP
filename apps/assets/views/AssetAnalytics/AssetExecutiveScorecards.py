from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, ProtectedError, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetAnalytics.AssetExecutiveScorecards import (
    AssetExecutiveScorecardForm,
)
from apps.assets.models.AssetAnalytics.AssetExecutiveScorecards import (
    AssetExecutiveScorecard,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetAnalytics._helpers import (
    PAGE_SIZE,
    ZERO,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


def _filter_akpi_queryset(request):
    qs = assets_scope(
        AssetExecutiveScorecard.objects.select_related(
            "org_unit",
            "asset_category",
            "currency",
            "prepared_by",
            "approved_by",
        ).defer("executive_summary"),
        request,
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(org_unit__name__icontains=q)
            | Q(asset_category__name__icontains=q)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={k for k, _ in AssetExecutiveScorecard.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "period_type",
        allowed_values={k for k, _ in AssetExecutiveScorecard.PERIOD_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "rag_status",
        allowed_values={k for k, _ in AssetExecutiveScorecard.RAG_STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "org_unit")
    qs = apply_fk_filter(qs, request, "asset_category")
    return qs


@login_required
def asset_executive_scorecard_list(request):
    qs = _filter_akpi_queryset(request)

    metrics = AssetExecutiveScorecard.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        green_cnt=Count("id", filter=Q(rag_status="green")),
        board_cnt=Count("id", filter=Q(status="board_approved")),
        avg_roi=Avg("asset_roi_pct"),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    categories = AssetCategory.objects.filter(tenant=request.tenant).order_by("name")

    return render(
        request,
        "assets/assetanalytics/asset_executive_scorecard/list.html",
        {
            "scorecards": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetExecutiveScorecard.STATUS_CHOICES,
            "period_choices": AssetExecutiveScorecard.PERIOD_TYPE_CHOICES,
            "rag_choices": AssetExecutiveScorecard.RAG_STATUS_CHOICES,
            "org_units": org_units,
            "categories": categories,
            "total_scorecards": metrics["total"] or 0,
            "green_count": metrics["green_cnt"] or 0,
            "board_approved_count": metrics["board_cnt"] or 0,
            "avg_roi_pct": (metrics["avg_roi"] or ZERO).quantize(Decimal("0.01")),
        },
    )


@login_required
def asset_executive_scorecard_detail(request, pk):
    scorecard = assets_object(
        request,
        AssetExecutiveScorecard,
        pk,
        select_related=[
            "org_unit",
            "asset_category",
            "currency",
            "prepared_by",
            "approved_by",
        ],
    )
    return render(
        request,
        "assets/assetanalytics/asset_executive_scorecard/detail.html",
        {"scorecard": scorecard},
    )


@login_required
@tenant_admin_required
def asset_executive_scorecard_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating an executive scorecard.")
        return redirect("assets:portfolio_dashboard")
    if request.method == "POST":
        form = AssetExecutiveScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                scorecard = form.save(commit=False)
                scorecard.tenant = request.tenant
                if not scorecard.prepared_by_id:
                    scorecard.prepared_by = request.user
                scorecard.save()
                write_audit_log(request.user, scorecard, "create", tenant=request.tenant)
            messages.success(request, f"Executive scorecard '{scorecard.number}' created successfully.")
            return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    else:
        form = AssetExecutiveScorecardForm(tenant=request.tenant, initial={"prepared_by": request.user})

    return render(
        request,
        "assets/assetanalytics/asset_executive_scorecard/form.html",
        {"form": form, "scorecard": None, "is_edit": False},
    )


@login_required
@tenant_admin_required
def asset_executive_scorecard_edit(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.is_locked:
        messages.error(
            request,
            f"Scorecard '{scorecard.number}' is '{scorecard.get_status_display()}' and locked from editing.",
        )
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)

    if request.method == "POST":
        form = AssetExecutiveScorecardForm(request.POST, instance=scorecard, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                scorecard = form.save()
                write_audit_log(request.user, scorecard, "update", tenant=request.tenant)
            messages.success(request, f"Executive scorecard '{scorecard.number}' updated successfully.")
            return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    else:
        form = AssetExecutiveScorecardForm(instance=scorecard, tenant=request.tenant)

    return render(
        request,
        "assets/assetanalytics/asset_executive_scorecard/form.html",
        {"form": form, "scorecard": scorecard, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def asset_executive_scorecard_delete(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.is_locked:
        messages.error(
            request,
            f"Scorecard '{scorecard.number}' is locked ({scorecard.get_status_display()}) and cannot be deleted.",
        )
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, scorecard, "delete", tenant=request.tenant)
            scorecard.delete()
        messages.success(request, "Executive scorecard deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete executive scorecard because dependent records exist.")
    return redirect("assets:asset_executive_scorecard_list")


@login_required
@tenant_admin_required
@require_POST
def asset_executive_scorecard_compute(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.is_locked:
        messages.error(
            request,
            f"Scorecard '{scorecard.number}' is '{scorecard.get_status_display()}' and locked from recalculation.",
        )
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    try:
        with transaction.atomic():
            scorecard.compute_from_live_portfolio(save=True)
            write_audit_log(request.user, scorecard, "compute", tenant=request.tenant)
        messages.success(
            request,
            f"Computed live portfolio KPIs and RAG status ({scorecard.get_rag_status_display()}) for '{scorecard.number}'.",
        )
    except ValidationError as exc:
        messages.error(request, str(exc.message if hasattr(exc, "message") else exc))
    return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_executive_scorecard_publish(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.status != "draft":
        messages.error(request, f"Only Draft scorecards can be published (current status: '{scorecard.get_status_display()}').")
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    with transaction.atomic():
        scorecard.status = "published"
        scorecard.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, scorecard, "publish", tenant=request.tenant)
    messages.success(request, f"Scorecard '{scorecard.number}' published and snapshot locked.")
    return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_executive_scorecard_approve(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.status != "published":
        messages.error(request, f"Scorecard '{scorecard.number}' must be Published before Board Approval.")
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    if scorecard.prepared_by_id and scorecard.prepared_by_id == request.user.pk:
        messages.error(
            request,
            "Segregation of duties: the preparer cannot board-approve their own executive scorecard.",
        )
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    with transaction.atomic():
        scorecard.status = "board_approved"
        scorecard.approved_by = request.user
        scorecard.save(update_fields=["status", "approved_by", "updated_at"])
        write_audit_log(request.user, scorecard, "approve", tenant=request.tenant)
    messages.success(request, f"Scorecard '{scorecard.number}' marked as Board Approved.")
    return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_executive_scorecard_archive(request, pk):
    scorecard = assets_object(request, AssetExecutiveScorecard, pk)
    if scorecard.status == "archived":
        messages.info(request, f"Scorecard '{scorecard.number}' is already archived.")
        return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)
    with transaction.atomic():
        scorecard.status = "archived"
        scorecard.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, scorecard, "archive", tenant=request.tenant)
    messages.success(request, f"Scorecard '{scorecard.number}' archived.")
    return redirect("assets:asset_executive_scorecard_detail", pk=scorecard.pk)


@login_required
def asset_executive_scorecard_export_csv(request):
    qs = _filter_akpi_queryset(request)
    headers = [
        "Number",
        "Title",
        "Period Type",
        "Period Start",
        "Period End",
        "RAG Status",
        "Status",
        "Active Assets",
        "Gross Replacement Value",
        "Net Book Value",
        "Asset ROI %",
        "Maint Cost / RAV %",
        "Planned Maint %",
        "Portfolio FCI %",
        "Compliance Pass Rate %",
        "Open Incidents",
        "Risk Exposure",
        "Unfunded Backlog",
    ]
    rows = (
        [
            k.number,
            k.title,
            k.get_period_type_display(),
            k.period_start.isoformat() if k.period_start else "",
            k.period_end.isoformat() if k.period_end else "",
            k.get_rag_status_display(),
            k.get_status_display(),
            k.total_asset_count,
            f"{k.gross_replacement_value:.2f}",
            f"{k.total_net_book_value:.2f}",
            f"{k.asset_roi_pct:.2f}",
            f"{k.maintenance_cost_to_rav_pct:.2f}",
            f"{k.planned_maintenance_ratio_pct:.2f}",
            f"{k.portfolio_fci_pct:.2f}",
            f"{k.compliance_audit_pass_rate_pct:.2f}",
            k.open_compliance_incidents,
            f"{k.total_risk_exposure_amount:.2f}",
            f"{k.unfunded_replacement_backlog:.2f}",
        ]
        for k in qs[:10000].iterator(chunk_size=500)
    )
    return csv_export_response(filename="akpi-scorecards.csv", headers=headers, rows=rows)
