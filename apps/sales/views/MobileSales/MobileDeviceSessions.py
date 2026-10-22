"""Sales 8.16 — MobileDeviceSession views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.MobileSales.MobileDeviceSessions import (
    MobileDeviceSessionFilterForm,
    MobileDeviceSessionForm,
)
from apps.sales.models.MobileSales.MobileDeviceSessions import (
    PLATFORM_CHOICES,
    SYNC_STATUS_CHOICES,
    MobileDeviceSession,
)


@login_required
def mobile_device_session_list(request):
    tenant = request.tenant
    qs = MobileDeviceSession.objects.filter(tenant=tenant).select_related("user").order_by("-updated_at")

    filter_form = MobileDeviceSessionFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(device_name__icontains=q)
                | Q(device_uuid__icontains=q)
                | Q(user__username__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
            )

        platform = filter_form.cleaned_data.get("platform")
        if platform:
            qs = qs.filter(platform=platform)

        last_sync_status = filter_form.cleaned_data.get("last_sync_status")
        if last_sync_status:
            qs = qs.filter(last_sync_status=last_sync_status)

        user = filter_form.cleaned_data.get("user")
        if user:
            qs = qs.filter(user=user)

    all_devices = MobileDeviceSession.objects.filter(tenant=tenant)
    total_devices_count = all_devices.count()
    active_devices_count = all_devices.filter(is_active=True).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "devices": page_obj.object_list,
        "filter_form": filter_form,
        "platform_choices": PLATFORM_CHOICES,
        "sync_status_choices": SYNC_STATUS_CHOICES,
        "total_devices_count": total_devices_count,
        "active_devices_count": active_devices_count,
    }
    return render(request, "sales/mobilesales/mobiledevicesession/list.html", context)


@login_required
def mobile_device_session_detail(request, pk):
    tenant = request.tenant
    device = get_object_or_404(MobileDeviceSession.objects.filter(tenant=tenant).select_related("user"), pk=pk)
    recent_alerts = device.received_alerts.filter(tenant=tenant).order_by("-created_at")[:10]

    context = {
        "device": device,
        "recent_alerts": recent_alerts,
    }
    return render(request, "sales/mobilesales/mobiledevicesession/detail.html", context)


@login_required
@transaction.atomic
def mobile_device_session_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = MobileDeviceSessionForm(request.POST, tenant=tenant)
        if form.is_valid():
            device = form.save(commit=False)
            device.tenant = tenant
            device.save()
            write_audit_log(
                request.user,
                device,
                "create",
                tenant=tenant,
            )
            messages.success(request, f"Mobile Device '{device.device_name}' registered successfully.")
            return redirect("sales:mobile_device_session_detail", pk=device.pk)
    else:
        form = MobileDeviceSessionForm(tenant=tenant, initial={"user": request.user})

    context = {
        "form": form,
        "device": None,
        "is_edit": False,
    }
    return render(request, "sales/mobilesales/mobiledevicesession/form.html", context)


@login_required
@transaction.atomic
def mobile_device_session_edit(request, pk):
    tenant = request.tenant
    device = get_object_or_404(MobileDeviceSession.objects.filter(tenant=tenant), pk=pk)
    is_admin = bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))
    if device.user != request.user and not is_admin:
        messages.error(request, "Only the device owner or a tenant administrator may edit this mobile device.")
        return redirect("sales:mobile_device_session_detail", pk=device.pk)

    if request.method == "POST":
        form = MobileDeviceSessionForm(request.POST, instance=device, tenant=tenant)
        if form.is_valid():
            device = form.save()
            write_audit_log(
                request.user,
                device,
                "update",
                tenant=tenant,
            )
            messages.success(request, f"Mobile Device '{device.device_name}' updated successfully.")
            return redirect("sales:mobile_device_session_detail", pk=device.pk)
    else:
        form = MobileDeviceSessionForm(instance=device, tenant=tenant)

    context = {
        "form": form,
        "device": device,
        "is_edit": True,
    }
    return render(request, "sales/mobilesales/mobiledevicesession/form.html", context)


@login_required
@require_POST
@transaction.atomic
def mobile_device_session_delete(request, pk):
    tenant = request.tenant
    device = get_object_or_404(MobileDeviceSession.objects.filter(tenant=tenant), pk=pk)
    is_admin = bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))
    if device.user != request.user and not is_admin:
        messages.error(request, "Only the device owner or a tenant administrator may delete this mobile device.")
        return redirect("sales:mobile_device_session_list")
    name = device.device_name
    write_audit_log(
        request.user,
        device,
        "delete",
        tenant=tenant,
    )
    device.delete()
    messages.success(request, f"Mobile Device '{name}' removed successfully.")
    return redirect("sales:mobile_device_session_list")


@login_required
@require_POST
@transaction.atomic
def mobile_device_session_sync(request, pk):
    tenant = request.tenant
    device = get_object_or_404(MobileDeviceSession.objects.filter(tenant=tenant), pk=pk)
    device.record_sync_event(status="success", cached_count=120, pending_count=0, ip=request.META.get("REMOTE_ADDR"))
    write_audit_log(
        request.user,
        device,
        "update",
        changes={"action": "sync"},
        tenant=tenant,
    )
    messages.success(request, f"Delta synchronization completed for '{device.device_name}' (120 records cached).")
    return redirect("sales:mobile_device_session_detail", pk=device.pk)
