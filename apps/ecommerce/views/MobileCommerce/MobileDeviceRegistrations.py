from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistrationForm
from apps.ecommerce.models.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistration
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def mobiledeviceregistration_list(request):
    qs = ecommerce_scope(
        MobileDeviceRegistration.objects.all().select_related("customer_profile", "party"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(device_uuid__icontains=q)
            | Q(device_model__icontains=q)
            | Q(number__icontains=q)
            | Q(customer_profile__number__icontains=q)
            | Q(party__name__icontains=q)
        )

    selected_platform = request.GET.get("platform", "").strip()
    if selected_platform:
        qs = qs.filter(device_platform=selected_platform)

    selected_provider = request.GET.get("provider", "").strip()
    if selected_provider:
        qs = qs.filter(push_provider=selected_provider)

    selected_status = request.GET.get("is_active", "").strip()
    if selected_status in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif selected_status in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    base_all = ecommerce_scope(MobileDeviceRegistration.objects.all(), request)
    total_count = base_all.count()
    ios_count = base_all.filter(device_platform="ios").count()
    android_count = base_all.filter(device_platform="android").count()
    pwa_count = base_all.filter(device_platform="pwa_web").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "devices": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "platform_choices": MobileDeviceRegistration.PLATFORM_CHOICES,
        "provider_choices": MobileDeviceRegistration.PUSH_PROVIDER_CHOICES,
        "selected_platform": selected_platform,
        "selected_provider": selected_provider,
        "selected_status": selected_status,
        "total_count": total_count,
        "ios_count": ios_count,
        "android_count": android_count,
        "pwa_count": pwa_count,
        "q": q,
    }
    return render(request, "ecommerce/mobile/mobile_device_registration/list.html", context)


@login_required
def mobiledeviceregistration_detail(request, pk):
    device = ecommerce_object(
        request,
        MobileDeviceRegistration,
        pk,
        select_related=("customer_profile", "party"),
    )
    context = {
        "device": device,
        "object": device,
    }
    return render(request, "ecommerce/mobile/mobile_device_registration/detail.html", context)


@login_required
@tenant_admin_required
def mobiledeviceregistration_create(request):
    if request.method == "POST":
        form = MobileDeviceRegistrationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            device = form.save(commit=False)
            device.tenant = request.tenant
            device.last_active_at = timezone.now()
            device.save()
            write_audit_log(
                user=request.user,
                obj=device,
                action="CREATE",
                changes={"uuid": device.device_uuid},
                tenant=request.tenant,
            )
            messages.success(request, f"Device {device.number} registered successfully.")
            return redirect("ecommerce:mobiledeviceregistration_detail", pk=device.pk)
    else:
        form = MobileDeviceRegistrationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/mobile/mobile_device_registration/form.html", context)


@login_required
@tenant_admin_required
def mobiledeviceregistration_edit(request, pk):
    device = ecommerce_object(request, MobileDeviceRegistration, pk)
    if request.method == "POST":
        form = MobileDeviceRegistrationForm(request.POST, instance=device, tenant=request.tenant)
        if form.is_valid():
            device = form.save()
            write_audit_log(
                user=request.user,
                obj=device,
                action="UPDATE",
                changes={"uuid": device.device_uuid},
                tenant=request.tenant,
            )
            messages.success(request, f"Device {device.number} updated successfully.")
            return redirect("ecommerce:mobiledeviceregistration_detail", pk=device.pk)
    else:
        form = MobileDeviceRegistrationForm(instance=device, tenant=request.tenant)

    context = {
        "form": form,
        "device": device,
        "object": device,
        "is_edit": True,
    }
    return render(request, "ecommerce/mobile/mobile_device_registration/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def mobiledeviceregistration_delete(request, pk):
    device = ecommerce_object(request, MobileDeviceRegistration, pk)
    number = device.number
    uuid_str = device.device_uuid
    write_audit_log(
        user=request.user,
        obj=device,
        action="DELETE",
        changes={"number": number, "uuid": uuid_str},
        tenant=request.tenant,
    )
    device.delete()
    messages.success(request, f"Device {number} ({uuid_str[:8]}...) deleted.")
    return redirect("ecommerce:mobiledeviceregistration_list")


@login_required
@tenant_admin_required
@require_POST
def mobiledeviceregistration_ping(request, pk):
    """Simulate a telemetry ping / keep-alive heartbeat from a registered mobile device."""
    device = ecommerce_object(request, MobileDeviceRegistration, pk)
    lat = request.POST.get("lat")
    lng = request.POST.get("lng")
    try:
        lat_dec = float(lat) if lat else None
        lng_dec = float(lng) if lng else None
    except ValueError:
        lat_dec = None
        lng_dec = None

    device.record_activity(lat=lat_dec, lng=lng_dec)
    messages.success(request, f"Simulated telemetry ping recorded for device {device.number}.")
    return redirect("ecommerce:mobiledeviceregistration_detail", pk=device.pk)
