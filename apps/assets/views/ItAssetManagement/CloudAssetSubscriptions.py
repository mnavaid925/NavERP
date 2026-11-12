"""Function-based CRUD, FinOps, and Shadow IT governance views for Cloud Assets (11.18)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscriptionForm,
)
from apps.assets.models.ItAssetManagement._validators import add_months
from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscription,
)
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    CMDB_REL_EDGE_SELECT_RELATED,
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log

_CLOUD_LIST_SELECT_RELATED = (
    "currency",
)

_CLOUD_DETAIL_SELECT_RELATED = _CLOUD_LIST_SELECT_RELATED + (
    "org_unit",
    "vendor_party",
    "business_owner",
    "technical_owner",
    "gl_expense_account",
)


def _filter_cloud_queryset(request, base_qs, select_related=_CLOUD_LIST_SELECT_RELATED):
    """Apply search and dropdown GET filters to a CloudAssetSubscription queryset."""
    qs = base_qs.select_related(*select_related) if select_related else base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(external_account_id__icontains=search_query)
            | Q(cloud_resource_id__icontains=search_query)
            | Q(cloud_region__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in CloudAssetSubscription.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "asset_kind",
        allowed_values={val for val, _ in CloudAssetSubscription.ASSET_KIND_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "provider",
        allowed_values={val for val, _ in CloudAssetSubscription.PROVIDER_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "approval_status",
        allowed_values={val for val, _ in CloudAssetSubscription.APPROVAL_STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "sso_status",
        allowed_values={val for val, _ in CloudAssetSubscription.SSO_STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "org_unit")
    return qs


@login_required
def cloud_asset_subscription_list(request):
    """List cloud assets & SaaS subscriptions with FinOps KPIs, filters, and pagination."""
    base_qs = assets_scope(CloudAssetSubscription.objects.all(), request)
    kpis = base_qs.aggregate(
        total_count=Count("id"),
        monthly_spend_total=Coalesce(
            Sum("monthly_recurring_cost", filter=~Q(status="cancelled")),
            Decimal("0.00"),
        ),
        shadow_flagged_count=Count(
            "id",
            filter=Q(status="shadow_flagged") | Q(approval_status="shadow_it_flagged"),
        ),
        underutilized_count=Count("id", filter=Q(status="underutilized")),
    )
    filtered_qs = _filter_cloud_queryset(request, base_qs)
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "cloud_assets": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_count": kpis["total_count"] or 0,
        "monthly_spend_total": kpis["monthly_spend_total"] or Decimal("0.00"),
        "shadow_flagged_count": kpis["shadow_flagged_count"] or 0,
        "underutilized_count": kpis["underutilized_count"] or 0,
        "status_choices": CloudAssetSubscription.STATUS_CHOICES,
        "asset_kind_choices": CloudAssetSubscription.ASSET_KIND_CHOICES,
        "provider_choices": CloudAssetSubscription.PROVIDER_CHOICES,
        "approval_choices": CloudAssetSubscription.APPROVAL_STATUS_CHOICES,
        "sso_choices": CloudAssetSubscription.SSO_STATUS_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(
        request,
        "assets/itassetmanagement/cloud_asset_subscription/list.html",
        context,
    )


@login_required
def cloud_asset_subscription_export_csv(request):
    """Export filtered cloud assets & SaaS subscriptions as a formula-safe CSV."""
    base_qs = assets_scope(CloudAssetSubscription.objects.all(), request)
    qs = _filter_cloud_queryset(request, base_qs, select_related=())
    headers = [
        "Number",
        "Name",
        "Kind",
        "Provider",
        "Environment",
        "Account ID",
        "Monthly Spend",
        "Annual ACV",
        "Provisioned Seats",
        "Active 30d Seats",
        "Wasted Monthly Spend",
        "SSO Status",
        "Approval Status",
        "Renewal Date",
        "Status",
    ]
    rows = (
        [
            item.number,
            item.name,
            item.get_asset_kind_display(),
            item.get_provider_display(),
            item.get_environment_display(),
            item.external_account_id,
            item.monthly_recurring_cost,
            item.annual_contract_value,
            item.provisioned_seats,
            item.active_seats_30d,
            item.wasted_monthly_spend,
            item.get_sso_status_display(),
            item.get_approval_status_display(),
            item.renewal_date.isoformat() if item.renewal_date else "",
            item.get_status_display(),
        ]
        for item in qs[:10000].iterator(chunk_size=1000)
    )
    return csv_export_response(
        filename="cloud_asset_subscriptions.csv",
        headers=headers,
        rows=rows,
    )


@login_required
def cloud_asset_subscription_create(request):
    """Create a new tenant-scoped cloud asset or SaaS subscription record."""
    if request.method == "POST":
        if request.tenant is None:
            messages.warning(request, "Workspace context is required to create a cloud asset subscription.")
            return redirect("assets:cloud_asset_subscription_list")
        form = CloudAssetSubscriptionForm(request.POST, tenant=request.tenant)
        form.instance.tenant = request.tenant
        if form.is_valid():
            with transaction.atomic():
                cloud_asset = form.save(commit=False)
                cloud_asset.tenant = request.tenant
                if cloud_asset.business_owner_id is None:
                    cloud_asset.business_owner = request.user
                cloud_asset.status = cloud_asset.compute_operational_status()
                cloud_asset.last_finops_sync_at = timezone.now()
                cloud_asset.save()
                write_audit_log(request.user, cloud_asset, "create", tenant=request.tenant)
            messages.success(request, f"Cloud Asset {cloud_asset.number} created.")
            return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    else:
        form = CloudAssetSubscriptionForm(tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/cloud_asset_subscription/form.html",
        {
            "form": form,
            "cloud_asset": None,
            "is_edit": False,
            "title": "New Cloud Asset / SaaS Subscription",
        },
    )


@login_required
def cloud_asset_subscription_detail(request, pk):
    """Display a cloud asset subscription detail page with FinOps telemetry & CMDB edges."""
    cloud_asset = assets_object(
        request,
        CloudAssetSubscription,
        pk,
        select_related=_CLOUD_DETAIL_SELECT_RELATED,
    )
    outbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, source_cloud=cloud_asset)
        .select_related(*CMDB_REL_EDGE_SELECT_RELATED)
        .order_by("-updated_at")[:50]
    )
    inbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, target_cloud=cloud_asset)
        .select_related(*CMDB_REL_EDGE_SELECT_RELATED)
        .order_by("-updated_at")[:50]
    )
    return render(
        request,
        "assets/itassetmanagement/cloud_asset_subscription/detail.html",
        {
            "cloud_asset": cloud_asset,
            "outbound_edges": outbound_edges,
            "inbound_edges": inbound_edges,
        },
    )


@login_required
def cloud_asset_subscription_edit(request, pk):
    """Edit an unlocked cloud asset subscription record."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(
            request,
            f"Cloud Asset {cloud_asset.number} is cancelled and cannot be edited.",
        )
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    if cloud_asset.status == "suspended" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while subscription is suspended.")

    if request.method == "POST":
        form = CloudAssetSubscriptionForm(request.POST, instance=cloud_asset, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                cloud_asset = form.save(commit=False)
                cloud_asset.status = cloud_asset.compute_operational_status()
                cloud_asset.last_finops_sync_at = timezone.now()
                cloud_asset.save()
                write_audit_log(request.user, cloud_asset, "update", tenant=request.tenant)
            messages.success(request, f"Cloud Asset {cloud_asset.number} updated.")
            return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    else:
        form = CloudAssetSubscriptionForm(instance=cloud_asset, tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/cloud_asset_subscription/form.html",
        {
            "form": form,
            "cloud_asset": cloud_asset,
            "is_edit": True,
            "title": f"Edit {cloud_asset.number} — {cloud_asset.name}",
        },
    )


@tenant_admin_required
@require_POST
def cloud_asset_subscription_delete(request, pk):
    """Delete an unlocked cloud asset subscription record (tenant admin only)."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(
            request,
            f"Cloud Asset {cloud_asset.number} is cancelled and cannot be deleted.",
        )
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    number = cloud_asset.number
    with transaction.atomic():
        write_audit_log(request.user, cloud_asset, "delete", tenant=request.tenant)
        cloud_asset.delete()
    messages.success(request, f"Cloud Asset {number} deleted.")
    return redirect("assets:cloud_asset_subscription_list")


@login_required
@require_POST
def cloud_asset_subscription_sanction(request, pk):
    """Mark cloud asset or SaaS tool as IT Sanctioned and recompute operational status."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    if cloud_asset.status == "suspended" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while subscription is suspended.")
    prev_approval = cloud_asset.approval_status
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.approval_status = "sanctioned"
        if cloud_asset.sso_status == "shadow_it_unapproved":
            cloud_asset.sso_status = "sso_optional"
        cloud_asset.status = cloud_asset.compute_operational_status()
        cloud_asset.last_finops_sync_at = timezone.now()
        cloud_asset.save(
            update_fields=[
                "approval_status",
                "sso_status",
                "status",
                "last_finops_sync_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            cloud_asset,
            "sanction",
            changes={
                "approval_status": [prev_approval, "sanctioned"],
                "status": [prev_status, cloud_asset.status],
            },
            tenant=request.tenant,
        )
    messages.success(request, f"Cloud Asset {cloud_asset.number} marked IT Sanctioned.")
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)


@login_required
@require_POST
def cloud_asset_subscription_flag_shadow(request, pk):
    """Flag subscription as unapproved Shadow IT for security & FinOps review."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    if cloud_asset.status == "suspended" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while subscription is suspended.")
    prev_approval = cloud_asset.approval_status
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.approval_status = "shadow_it_flagged"
        cloud_asset.status = "shadow_flagged"
        cloud_asset.save(update_fields=["approval_status", "status", "updated_at"])
        write_audit_log(
            request.user,
            cloud_asset,
            "shadow",
            changes={
                "approval_status": [prev_approval, "shadow_it_flagged"],
                "status": [prev_status, "shadow_flagged"],
            },
            tenant=request.tenant,
        )
    messages.warning(request, f"Cloud Asset {cloud_asset.number} flagged as Shadow IT.")
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)


@login_required
@require_POST
def cloud_asset_subscription_sync_finops(request, pk):
    """Refresh FinOps utilization status and sync timestamp."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    if cloud_asset.status == "suspended" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while subscription is suspended.")
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.status = cloud_asset.compute_operational_status()
        cloud_asset.last_finops_sync_at = timezone.now()
        cloud_asset.save(update_fields=["status", "last_finops_sync_at", "updated_at"])
        write_audit_log(
            request.user,
            cloud_asset,
            "finops",
            changes={"status": [prev_status, cloud_asset.status]},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"FinOps telemetry synced for {cloud_asset.number}: {cloud_asset.get_status_display()}.",
    )
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)


@login_required
@require_POST
def cloud_asset_subscription_renew(request, pk):
    """Extend cloud subscription renewal date by 12 months."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    if cloud_asset.status == "suspended" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while subscription is suspended.")
    today = timezone.now().date()
    base_date = max(cloud_asset.renewal_date, today) if cloud_asset.renewal_date else today
    prev_renewal = cloud_asset.renewal_date.isoformat() if cloud_asset.renewal_date else None
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.renewal_date = add_months(base_date, 12)
        cloud_asset.status = cloud_asset.compute_operational_status(today=today)
        cloud_asset.last_finops_sync_at = timezone.now()
        cloud_asset.save(
            update_fields=[
                "renewal_date",
                "status",
                "last_finops_sync_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            cloud_asset,
            "renew",
            changes={
                "renewal_date": [prev_renewal, cloud_asset.renewal_date.isoformat()],
                "status": [prev_status, cloud_asset.status],
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Renewed {cloud_asset.number} through {cloud_asset.renewal_date.isoformat()}.",
    )
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)


@tenant_admin_required
@require_POST
def cloud_asset_subscription_suspend(request, pk):
    """Suspend an active cloud asset or SaaS subscription."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.status = "suspended"
        cloud_asset.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            cloud_asset,
            "suspend",
            changes={"status": [prev_status, "suspended"]},
            tenant=request.tenant,
        )
    messages.warning(request, f"Cloud Asset {cloud_asset.number} suspended.")
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)


@tenant_admin_required
@require_POST
def cloud_asset_subscription_decommission(request, pk):
    """Permanently decommission & cancel a cloud asset subscription."""
    cloud_asset = assets_object(request, CloudAssetSubscription, pk)
    if cloud_asset.is_locked:
        messages.warning(request, f"Cloud Asset {cloud_asset.number} is already cancelled.")
        return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
    prev_approval = cloud_asset.approval_status
    prev_status = cloud_asset.status
    with transaction.atomic():
        cloud_asset.approval_status = "decommissioned"
        cloud_asset.status = "cancelled"
        cloud_asset.decommissioned_at = timezone.now()
        cloud_asset.save(
            update_fields=[
                "approval_status",
                "status",
                "decommissioned_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            cloud_asset,
            "decomm",
            changes={
                "approval_status": [prev_approval, "decommissioned"],
                "status": [prev_status, "cancelled"],
            },
            tenant=request.tenant,
        )
    messages.success(request, f"Cloud Asset {cloud_asset.number} decommissioned and cancelled.")
    return redirect("assets:cloud_asset_subscription_detail", pk=cloud_asset.pk)
