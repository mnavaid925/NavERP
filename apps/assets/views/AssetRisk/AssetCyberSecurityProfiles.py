from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetRisk.AssetCyberSecurityProfiles import AssetCyberSecurityProfileForm
from apps.assets.models.AssetRisk.AssetCyberSecurityProfiles import AssetCyberSecurityProfile
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_cybersecurity_profile_list(request):
    qs = assets_scope(
        AssetCyberSecurityProfile.objects.select_related(
            "asset",
        ).defer("compensating_controls", "known_vulnerabilities_cve"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__asset_code__icontains=q)
            | Q(ip_address__icontains=q)
            | Q(mac_address__icontains=q)
            | Q(firmware_version__icontains=q)
        )

    device_filter = request.GET.get("device_type", "").strip()
    if device_filter:
        qs = qs.filter(device_type=device_filter)

    zone_filter = request.GET.get("network_zone", "").strip()
    if zone_filter:
        qs = qs.filter(network_zone=zone_filter)

    posture_filter = request.GET.get("security_posture_status", "").strip()
    if posture_filter:
        qs = qs.filter(security_posture_status=posture_filter)

    firmware_filter = request.GET.get("firmware_update_status", "").strip()
    if firmware_filter:
        qs = qs.filter(firmware_update_status=firmware_filter)

    # Aggregate KPI metrics over tenant-scoped records
    metrics = AssetCyberSecurityProfile.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        secure=Count("id", filter=Q(security_posture_status="secure")),
        vulnerable=Count("id", filter=Q(security_posture_status__in=["vulnerable", "compromised"])),
        critical_patches=Count("id", filter=Q(firmware_update_status="critical_patch_pending")),
    )
    total_profiles = metrics["total"] or 0
    secure_count = metrics["secure"] or 0
    vulnerable_count = metrics["vulnerable"] or 0
    critical_patches_count = metrics["critical_patches"] or 0

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetrisk/asset_cybersecurity/list.html",
        {
            "profiles": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "device_choices": AssetCyberSecurityProfile.DEVICE_TYPE_CHOICES,
            "zone_choices": AssetCyberSecurityProfile.NETWORK_ZONE_CHOICES,
            "posture_choices": AssetCyberSecurityProfile.POSTURE_STATUS_CHOICES,
            "firmware_choices": AssetCyberSecurityProfile.FIRMWARE_STATUS_CHOICES,
            "total_profiles": total_profiles,
            "secure_count": secure_count,
            "vulnerable_count": vulnerable_count,
            "critical_patches_count": critical_patches_count,
        },
    )


@login_required
def asset_cybersecurity_profile_detail(request, pk):
    profile = assets_object(
        request,
        AssetCyberSecurityProfile,
        pk,
        select_related=["asset"],
    )

    return render(
        request,
        "assets/assetrisk/asset_cybersecurity/detail.html",
        {
            "profile": profile,
        },
    )


@login_required
@tenant_admin_required
def asset_cybersecurity_profile_create(request):
    if request.method == "POST":
        form = AssetCyberSecurityProfileForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                profile = form.save(commit=False)
                profile.tenant = request.tenant
                profile.save()
                write_audit_log(request.user, profile, "create", tenant=request.tenant)
            messages.success(request, f"Cybersecurity profile '{profile.number}' created successfully.")
            return redirect("assets:asset_cybersecurity_profile_detail", pk=profile.pk)
    else:
        form = AssetCyberSecurityProfileForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_cybersecurity/form.html",
        {
            "form": form,
            "profile": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def asset_cybersecurity_profile_edit(request, pk):
    profile = assets_object(request, AssetCyberSecurityProfile, pk)
    if request.method == "POST":
        form = AssetCyberSecurityProfileForm(request.POST, instance=profile, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                profile = form.save()
                write_audit_log(request.user, profile, "update", tenant=request.tenant)
            messages.success(request, f"Cybersecurity profile '{profile.number}' updated successfully.")
            return redirect("assets:asset_cybersecurity_profile_detail", pk=profile.pk)
    else:
        form = AssetCyberSecurityProfileForm(instance=profile, tenant=request.tenant)

    return render(
        request,
        "assets/assetrisk/asset_cybersecurity/form.html",
        {
            "form": form,
            "profile": profile,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_cybersecurity_profile_delete(request, pk):
    profile = assets_object(request, AssetCyberSecurityProfile, pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, profile, "delete", tenant=request.tenant)
            profile.delete()
        messages.success(request, "Cybersecurity profile deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete profile: dependent records exist.")
    return redirect("assets:asset_cybersecurity_profile_list")


@login_required
@require_POST
def asset_cybersecurity_profile_scan(request, pk):
    profile = assets_object(request, AssetCyberSecurityProfile, pk)
    with transaction.atomic():
        profile.last_vulnerability_scan_date = timezone.now().date()
        profile.save(update_fields=["last_vulnerability_scan_date", "updated_at"])
        write_audit_log(request.user, profile, "scan", changes={"scanned_at": str(timezone.now().date())}, tenant=request.tenant)
    messages.success(request, f"Vulnerability scan recorded for '{profile.number}'.")
    return redirect("assets:asset_cybersecurity_profile_detail", pk=profile.pk)
