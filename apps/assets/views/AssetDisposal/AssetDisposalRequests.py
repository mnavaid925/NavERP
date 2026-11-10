from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDisposal.AssetDisposalRequests import (
    AssetDisposalAppraisalForm,
    AssetDisposalRejectForm,
    AssetDisposalRequestForm,
)
from apps.assets.models import AssetCategory
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_disposal_request_list(request):
    qs = assets_scope(
        AssetDisposalRequest.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "category",
            "requested_by",
            "appraised_by",
            "approved_by",
        ).defer("justification_notes", "rejection_reason"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(fixed_asset__asset_number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__tag_code__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    method_filter = request.GET.get("disposal_method", "").strip()
    if method_filter:
        qs = qs.filter(disposal_method=method_filter)

    reason_filter = request.GET.get("retirement_reason", "").strip()
    if reason_filter:
        qs = qs.filter(retirement_reason=reason_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter and category_filter.isdigit():
        qs = qs.filter(category_id=int(category_filter))

    # KPI aggregation
    base_tenant_qs = assets_scope(AssetDisposalRequest.objects.all(), request)
    total_requests = base_tenant_qs.count()
    pending_approval_count = base_tenant_qs.filter(status__in=["submitted", "appraised"]).count()
    in_progress_count = base_tenant_qs.filter(status="in_progress").count()
    completed_count = base_tenant_qs.filter(status="completed").count()
    gain_loss_agg = base_tenant_qs.aggregate(total=Sum("realized_gain_loss"))
    total_gain_loss = gain_loss_agg["total"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "disposal_requests": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetDisposalRequest.STATUS_CHOICES,
        "method_choices": AssetDisposalRequest.DISPOSAL_METHOD_CHOICES,
        "reason_choices": AssetDisposalRequest.RETIREMENT_REASON_CHOICES,
        "category_list": AssetCategory.objects.filter(tenant=request.tenant),
        "total_requests": total_requests,
        "pending_approval_count": pending_approval_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "total_gain_loss": total_gain_loss,
    }
    return render(request, "assets/assetdisposal/asset_disposal_request/list.html", context)


@login_required
def asset_disposal_request_detail(request, pk):
    disposal_request = assets_object(
        request,
        AssetDisposalRequest,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "category",
            "cost_center",
            "requested_by",
            "appraised_by",
            "approved_by",
            "accounting_disposal",
        ],
    )

    resale_listings = disposal_request.resale_listings.select_related("buyer", "broker_auctioneer").order_by("-created_at")
    trade_ins = disposal_request.trade_ins.select_related("vendor", "replacement_fixed_asset").order_by("-created_at")
    scrap_salvages = disposal_request.scrap_salvages.select_related("recycler_partner", "supervisor").order_by("-created_at")

    appraisal_form = AssetDisposalAppraisalForm(tenant=request.tenant)
    reject_form = AssetDisposalRejectForm()

    context = {
        "disposal_request": disposal_request,
        "resale_listings": resale_listings,
        "trade_ins": trade_ins,
        "scrap_salvages": scrap_salvages,
        "appraisal_form": appraisal_form,
        "reject_form": reject_form,
    }
    return render(request, "assets/assetdisposal/asset_disposal_request/detail.html", context)


@login_required
def asset_disposal_request_create(request):
    if request.method == "POST":
        form = AssetDisposalRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.requested_by:
                    instance.requested_by = request.user
                instance.save()
                write_audit_log(request.user, instance, "create", tenant=request.tenant)
            messages.success(request, f"Asset disposal request {instance.number} created successfully.")
            return redirect("assets:asset_disposal_request_detail", pk=instance.pk)
    else:
        initial = {}
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id and fixed_asset_id.isdigit():
            initial["fixed_asset"] = int(fixed_asset_id)
        form = AssetDisposalRequestForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "disposal_request": None,
        "is_edit": False,
    }
    return render(request, "assets/assetdisposal/asset_disposal_request/form.html", context)


@login_required
def asset_disposal_request_edit(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    if instance.status in ["completed", "cancelled"]:
        messages.error(request, f"Disposal request {instance.number} is {instance.get_status_display()} and cannot be edited.")
        return redirect("assets:asset_disposal_request_detail", pk=instance.pk)

    if request.method == "POST":
        form = AssetDisposalRequestForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()
                write_audit_log(request.user, instance, "update", tenant=request.tenant)
            messages.success(request, f"Asset disposal request {instance.number} updated successfully.")
            return redirect("assets:asset_disposal_request_detail", pk=instance.pk)
    else:
        form = AssetDisposalRequestForm(instance=instance, tenant=request.tenant)

    context = {
        "form": form,
        "disposal_request": instance,
        "is_edit": True,
    }
    return render(request, "assets/assetdisposal/asset_disposal_request/form.html", context)


@login_required
@require_POST
def asset_disposal_request_delete(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    if instance.status == "completed":
        messages.error(request, "Completed asset retirement records cannot be deleted.")
        return redirect("assets:asset_disposal_request_detail", pk=instance.pk)

    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
    messages.success(request, f"Asset disposal request {instance.number} deleted successfully.")
    return redirect("assets:asset_disposal_request_list")


@login_required
@require_POST
def asset_disposal_request_submit(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    if instance.status != "draft":
        messages.warning(request, f"Disposal request {instance.number} is already {instance.get_status_display()}.")
        return redirect("assets:asset_disposal_request_detail", pk=instance.pk)

    with transaction.atomic():
        instance.status = "submitted"
        instance.submitted_at = timezone.now()
        instance.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(request, f"Disposal request {instance.number} submitted for appraisal and review.")
    return redirect("assets:asset_disposal_request_detail", pk=instance.pk)


@login_required
@require_POST
def asset_disposal_request_appraise(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    form = AssetDisposalAppraisalForm(request.tenant, request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance.appraised_by = form.cleaned_data["appraised_by"]
            instance.estimated_residual_value = form.cleaned_data["estimated_residual_value"]
            if form.cleaned_data.get("estimated_removal_cost"):
                instance.estimated_removal_cost = form.cleaned_data["estimated_removal_cost"]
            if form.cleaned_data.get("appraisal_notes"):
                instance.justification_notes += f"\n[Appraisal Notes]: {form.cleaned_data['appraisal_notes']}"
            instance.status = "appraised"
            instance.save(update_fields=[
                "appraised_by",
                "estimated_residual_value",
                "estimated_removal_cost",
                "justification_notes",
                "status",
                "updated_at",
            ])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.success(request, f"Appraisal recorded for {instance.number}. Status advanced to Appraised.")
    else:
        messages.error(request, "Failed to record appraisal. Please check input values.")
    return redirect("assets:asset_disposal_request_detail", pk=instance.pk)


@login_required
@require_POST
def asset_disposal_request_approve(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    if instance.status not in ["submitted", "appraised"]:
        messages.warning(request, f"Disposal request {instance.number} cannot be approved from {instance.get_status_display()}.")
        return redirect("assets:asset_disposal_request_detail", pk=instance.pk)

    with transaction.atomic():
        instance.status = "approved"
        instance.approved_by = request.user
        instance.approved_at = timezone.now()
        instance.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(request, f"Disposal request {instance.number} has been officially approved for execution.")
    return redirect("assets:asset_disposal_request_detail", pk=instance.pk)


@login_required
@require_POST
def asset_disposal_request_reject(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    form = AssetDisposalRejectForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance.status = "rejected"
            instance.rejection_reason = form.cleaned_data["rejection_reason"]
            instance.save(update_fields=["status", "rejection_reason", "updated_at"])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.info(request, f"Disposal request {instance.number} has been rejected.")
    else:
        messages.error(request, "Rejection requires a documented justification reason.")
    return redirect("assets:asset_disposal_request_detail", pk=instance.pk)


@login_required
@require_POST
def asset_disposal_request_complete(request, pk):
    instance = assets_object(request, AssetDisposalRequest, pk)
    if instance.status not in ["approved", "in_progress"]:
        messages.warning(request, f"Disposal request {instance.number} cannot be completed from {instance.get_status_display()}.")
        return redirect("assets:asset_disposal_request_detail", pk=instance.pk)

    with transaction.atomic():
        instance.calculate_gain_loss()
        instance.status = "completed"
        instance.completed_at = timezone.now()
        instance.save(update_fields=["status", "completed_at", "realized_gain_loss", "updated_at"])

        # Update FixedAsset status in accounting register
        if instance.fixed_asset:
            fa = instance.fixed_asset
            if hasattr(fa, "status"):
                fa.status = "disposed"
                fa.save(update_fields=["status", "updated_at"] if hasattr(fa, "updated_at") else ["status"])

        # Update scm.Asset status in operational plant equipment
        if instance.operational_asset:
            oa = instance.operational_asset
            if hasattr(oa, "status"):
                oa.status = "disposed"
                oa.save(update_fields=["status", "updated_at"] if hasattr(oa, "updated_at") else ["status"])

        write_audit_log(request.user, instance, "update", tenant=request.tenant)

    messages.success(
        request,
        f"Disposal request {instance.number} completed successfully. "
        f"Fixed Asset status updated to Disposed. Realized Gain/Loss: {instance.realized_gain_loss}."
    )
    return redirect("assets:asset_disposal_request_detail", pk=instance.pk)
