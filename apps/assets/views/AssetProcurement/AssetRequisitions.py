from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetProcurement.AssetRequisitions import AssetRequisitionForm
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def asset_requisition_list(request):
    """List capital asset requisitions with multi-factor filtering, search, and pagination."""
    queryset = assets_scope(AssetRequisition.objects.all(), request).select_related(
        "currency", "proposed_vendor", "target_org_unit", "target_location", "submitted_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(budget_code__icontains=q)
            | Q(proposed_manufacturer__icontains=q)
            | Q(proposed_model__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        queryset = queryset.filter(status=status)

    priority = request.GET.get("priority", "").strip()
    if priority:
        queryset = queryset.filter(priority=priority)

    category = request.GET.get("category", "").strip()
    if category:
        queryset = queryset.filter(asset_category=category)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "requisitions": page_obj,
        "page_obj": page_obj,
        "status_choices": AssetRequisition.STATUS_CHOICES,
        "priority_choices": AssetRequisition.PRIORITY_CHOICES,
        "category_choices": AssetRequisition.CATEGORY_CHOICES,
    }
    return render(request, "assets/asset_procurement/asset_requisition/list.html", context)


@login_required
def asset_requisition_detail(request, pk):
    """Display comprehensive details of an asset requisition."""
    requisition = assets_object(
        request,
        AssetRequisition,
        pk,
        select_related=(
            "currency",
            "proposed_vendor",
            "target_org_unit",
            "target_location",
            "submitted_by",
            "approved_by",
            "purchase_order",
        ),
    )
    return render(
        request,
        "assets/asset_procurement/asset_requisition/detail.html",
        {"requisition": requisition},
    )


@login_required
def asset_requisition_create(request):
    """Create a new capital asset requisition."""
    if request.method == "POST":
        form = AssetRequisitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            req = form.save(commit=False)
            req.tenant = request.tenant
            req.save()
            write_audit_log(
                request.user,
                req,
                "create",
                changes={"details": f"Created asset requisition {req.number} ({req.title})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Requisition {req.number} created successfully.")
            return redirect("assets:asset_requisition_detail", pk=req.pk)
    else:
        form = AssetRequisitionForm(tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_requisition/form.html",
        {"form": form, "requisition": None, "is_edit": False},
    )


@login_required
def asset_requisition_edit(request, pk):
    """Update an existing asset requisition."""
    requisition = assets_object(request, AssetRequisition, pk)
    if requisition.status in ("approved", "ordered", "received"):
        messages.error(request, f"Requisition {requisition.number} cannot be edited in status '{requisition.get_status_display()}'.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    if request.method == "POST":
        form = AssetRequisitionForm(request.POST, instance=requisition, tenant=request.tenant)
        if form.is_valid():
            req = form.save()
            write_audit_log(
                request.user,
                req,
                "update",
                changes={"details": f"Updated asset requisition {req.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Requisition {req.number} updated successfully.")
            return redirect("assets:asset_requisition_detail", pk=req.pk)
    else:
        form = AssetRequisitionForm(instance=requisition, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_requisition/form.html",
        {"form": form, "requisition": requisition, "is_edit": True},
    )


@login_required
@require_POST
def asset_requisition_delete(request, pk):
    """Delete an asset requisition."""
    requisition = assets_object(request, AssetRequisition, pk)
    if requisition.status not in ("draft", "rejected"):
        messages.error(request, f"Requisition {requisition.number} cannot be deleted in status '{requisition.get_status_display()}'. Only draft or rejected requisitions can be deleted.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)
    number = requisition.number
    write_audit_log(
        request.user,
        requisition,
        "delete",
        changes={"details": f"Deleted asset requisition {number}"},
        tenant=request.tenant,
    )
    requisition.delete()
    messages.success(request, f"Asset Requisition {number} was deleted.")
    return redirect("assets:asset_requisition_list")


@login_required
@require_POST
def asset_requisition_submit(request, pk):
    """Submit a draft/rejected asset requisition for management approval."""
    requisition = assets_object(request, AssetRequisition, pk)
    if not requisition.can_submit():
        messages.error(request, f"Requisition {requisition.number} cannot be submitted in state '{requisition.get_status_display()}'.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    with transaction.atomic():
        requisition.status = "pending_approval"
        requisition.submitted_by = request.user
        requisition.submitted_at = timezone.now()
        requisition.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])

        write_audit_log(
            request.user,
            requisition,
            "update",
            changes={"action": "submit", "details": f"Submitted asset requisition {requisition.number} for approval"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Requisition {requisition.number} submitted for approval.")
    return redirect("assets:asset_requisition_detail", pk=requisition.pk)


@login_required
@require_POST
def asset_requisition_approve(request, pk):
    """Approve a pending asset requisition."""
    requisition = assets_object(request, AssetRequisition, pk)
    if not requisition.can_approve():
        messages.error(request, f"Requisition {requisition.number} cannot be approved in state '{requisition.get_status_display()}'.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    if requisition.submitted_by_id and requisition.submitted_by_id == request.user.pk:
        messages.error(request, "Segregation of Duties violation: You cannot approve a requisition you submitted.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    with transaction.atomic():
        requisition.status = "approved"
        requisition.approved_by = request.user
        requisition.approved_at = timezone.now()
        requisition.rejection_reason = ""
        requisition.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason", "updated_at"])

        write_audit_log(
            request.user,
            requisition,
            "update",
            changes={"action": "approve", "details": f"Approved asset requisition {requisition.number}"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Requisition {requisition.number} approved.")
    return redirect("assets:asset_requisition_detail", pk=requisition.pk)


@login_required
@require_POST
def asset_requisition_reject(request, pk):
    """Reject a pending asset requisition with a reason."""
    requisition = assets_object(request, AssetRequisition, pk)
    if not requisition.can_reject():
        messages.error(request, f"Requisition {requisition.number} cannot be rejected in state '{requisition.get_status_display()}'.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    reason = request.POST.get("rejection_reason", "").strip()
    if not reason:
        messages.error(request, "A reason is required to reject an asset requisition.")
        return redirect("assets:asset_requisition_detail", pk=requisition.pk)

    with transaction.atomic():
        requisition.status = "rejected"
        requisition.approved_by = request.user
        requisition.approved_at = timezone.now()
        requisition.rejection_reason = reason
        requisition.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason", "updated_at"])

        write_audit_log(
            request.user,
            requisition,
            "update",
            changes={"action": "reject", "details": f"Rejected asset requisition {requisition.number}: {reason}"},
            tenant=request.tenant,
        )
    messages.warning(request, f"Asset Requisition {requisition.number} has been rejected.")
    return redirect("assets:asset_requisition_detail", pk=requisition.pk)
