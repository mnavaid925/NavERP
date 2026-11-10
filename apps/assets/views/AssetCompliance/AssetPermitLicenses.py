from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetCompliance.AssetPermitLicenses import AssetPermitLicenseForm
from apps.assets.models.AssetCompliance.AssetPermitLicenses import AssetPermitLicense
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_permit_license_list(request):
    qs = assets_scope(
        AssetPermitLicense.objects.select_related(
            "asset",
            "issuing_authority",
        ).defer("operating_conditions"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(permit_name__icontains=q)
            | Q(permit_number__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(issuing_authority__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("permit_type", "").strip()
    if type_filter:
        qs = qs.filter(permit_type=type_filter)

    authority_id = request.GET.get("authority", "").strip()
    if authority_id and authority_id.isdigit():
        qs = qs.filter(issuing_authority_id=int(authority_id))

    today = timezone.now().date()
    soon_window = today + timedelta(days=60)

    # Aggregate KPI counts
    base_all = AssetPermitLicense.objects.filter(tenant=request.tenant)
    total_permits = base_all.count()
    active_count = base_all.filter(status="active").count()
    expiring_soon_count = base_all.filter(
        status="active",
        expiration_date__gte=today,
        expiration_date__lte=soon_window,
    ).count()
    expired_count = base_all.filter(
        Q(status="expired") | (Q(status="active") & Q(expiration_date__lt=today))
    ).count()

    authority_list = Party.objects.filter(tenant=request.tenant).order_by("name")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetcompliance/asset_permit_license/list.html",
        {
            "permits": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetPermitLicense.STATUS_CHOICES,
            "type_choices": AssetPermitLicense.PERMIT_TYPE_CHOICES,
            "authority_list": authority_list,
            "total_permits": total_permits,
            "active_count": active_count,
            "expiring_soon_count": expiring_soon_count,
            "expired_count": expired_count,
        },
    )


@login_required
def asset_permit_license_detail(request, pk):
    permit = assets_object(
        request,
        AssetPermitLicense,
        pk,
        select_related=["asset", "issuing_authority"],
    )
    incidents = permit.incidents.select_related("assigned_investigator").order_by("-incident_date")[:10]
    return render(
        request,
        "assets/assetcompliance/asset_permit_license/detail.html",
        {
            "permit": permit,
            "incidents": incidents,
        },
    )


@login_required
def asset_permit_license_create(request):
    if request.method == "POST":
        form = AssetPermitLicenseForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            permit = form.save(commit=False)
            permit.tenant = request.tenant
            permit.save()
            write_audit_log(
                request.user,
                permit,
                "create",
                changes={"details": f"Registered permit/license {permit.number} ({permit.permit_number}) for {permit.asset.code}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Permit/license {permit.number} registered successfully.")
            return redirect("assets:asset_permit_license_detail", pk=permit.pk)
    else:
        initial = {}
        asset_arg = request.GET.get("asset", "").strip()
        if asset_arg and asset_arg.isdigit():
            initial["asset"] = int(asset_arg)
        form = AssetPermitLicenseForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_permit_license/form.html",
        {
            "form": form,
            "permit": None,
            "is_edit": False,
        },
    )


@login_required
def asset_permit_license_edit(request, pk):
    permit = assets_object(request, AssetPermitLicense, pk)
    if request.method == "POST":
        form = AssetPermitLicenseForm(request.POST, instance=permit, tenant=request.tenant)
        if form.is_valid():
            permit = form.save()
            write_audit_log(
                request.user,
                permit,
                "update",
                changes={"details": f"Updated permit/license {permit.number} ({permit.permit_number})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Permit/license {permit.number} updated successfully.")
            return redirect("assets:asset_permit_license_detail", pk=permit.pk)
    else:
        form = AssetPermitLicenseForm(instance=permit, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_permit_license/form.html",
        {
            "form": form,
            "permit": permit,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def asset_permit_license_delete(request, pk):
    permit = assets_object(request, AssetPermitLicense, pk)
    num = permit.number
    pnum = permit.permit_number
    write_audit_log(
        request.user,
        permit,
        "delete",
        changes={"details": f"Deleted permit/license {num} ({pnum})"},
        tenant=request.tenant,
    )
    permit.delete()
    messages.success(request, f"Permit/license {num} ({pnum}) was deleted.")
    return redirect("assets:asset_permit_license_list")


@login_required
@require_POST
def asset_permit_license_renew(request, pk):
    permit = assets_object(request, AssetPermitLicense, pk)
    if permit.status in ["revoked", "suspended"]:
        messages.error(request, f"Permit/license {permit.number} cannot be renewed while {permit.get_status_display().lower()}.")
        return redirect("assets:asset_permit_license_detail", pk=permit.pk)
    permit.status = "pending_renewal"
    permit.save(update_fields=["status", "updated_at"])
    write_audit_log(
        request.user,
        permit,
        "update",
        changes={"details": f"Marked permit/license {permit.number} as pending renewal"},
        tenant=request.tenant,
    )
    messages.success(request, f"Permit {permit.number} marked as Pending Renewal.")
    return redirect("assets:asset_permit_license_detail", pk=permit.pk)
