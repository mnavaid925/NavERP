from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MobileCommerce.MobilePushCampaigns import MobilePushCampaignForm
from apps.ecommerce.models.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistration
from apps.ecommerce.models.MobileCommerce.MobilePushCampaigns import MobilePushCampaign
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def mobilepushcampaign_list(request):
    qs = ecommerce_scope(
        MobilePushCampaign.objects.all().select_related("target_product", "target_category", "target_coupon"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(campaign_name__icontains=q)
            | Q(notification_title__icontains=q)
            | Q(number__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_type = request.GET.get("type", "").strip()
    if selected_type:
        qs = qs.filter(campaign_type=selected_type)

    selected_platform = request.GET.get("platform", "").strip()
    if selected_platform:
        qs = qs.filter(target_platform=selected_platform)

    base_all = ecommerce_scope(MobilePushCampaign.objects.all(), request)
    total_count = base_all.count()
    sent_count = base_all.filter(status="sent").count()
    draft_count = base_all.filter(status="draft").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "campaigns": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": MobilePushCampaign.STATUS_CHOICES,
        "type_choices": MobilePushCampaign.CAMPAIGN_TYPE_CHOICES,
        "platform_choices": MobilePushCampaign.TARGET_PLATFORM_CHOICES,
        "selected_status": selected_status,
        "selected_type": selected_type,
        "selected_platform": selected_platform,
        "total_count": total_count,
        "sent_count": sent_count,
        "draft_count": draft_count,
        "q": q,
    }
    return render(request, "ecommerce/mobile/mobile_push_campaign/list.html", context)


@login_required
def mobilepushcampaign_detail(request, pk):
    campaign = ecommerce_object(
        request,
        MobilePushCampaign,
        pk,
        select_related=("target_product", "target_category", "target_coupon", "created_by"),
    )
    context = {
        "campaign": campaign,
        "object": campaign,
        "open_rate_pct": campaign.calculate_open_rate_pct(),
        "ctr_pct": campaign.calculate_ctr_pct(),
    }
    return render(request, "ecommerce/mobile/mobile_push_campaign/detail.html", context)


@login_required
@tenant_admin_required
def mobilepushcampaign_create(request):
    if request.method == "POST":
        form = MobilePushCampaignForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.tenant = request.tenant
            if request.user.is_authenticated:
                campaign.created_by = request.user
            campaign.save()
            write_audit_log(
                request=request,
                action="CREATE",
                instance=campaign,
                message=f"Created MobilePushCampaign {campaign.number} ({campaign.campaign_name})",
            )
            messages.success(request, f"Push Campaign '{campaign.campaign_name}' created successfully.")
            return redirect("ecommerce:mobilepushcampaign_detail", pk=campaign.pk)
    else:
        form = MobilePushCampaignForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/mobile/mobile_push_campaign/form.html", context)


@login_required
@tenant_admin_required
def mobilepushcampaign_edit(request, pk):
    campaign = ecommerce_object(request, MobilePushCampaign, pk)
    if request.method == "POST":
        form = MobilePushCampaignForm(request.POST, instance=campaign, tenant=request.tenant)
        if form.is_valid():
            campaign = form.save()
            write_audit_log(
                request=request,
                action="UPDATE",
                instance=campaign,
                message=f"Updated MobilePushCampaign {campaign.number}",
            )
            messages.success(request, f"Push Campaign '{campaign.campaign_name}' updated successfully.")
            return redirect("ecommerce:mobilepushcampaign_detail", pk=campaign.pk)
    else:
        form = MobilePushCampaignForm(instance=campaign, tenant=request.tenant)

    context = {
        "form": form,
        "campaign": campaign,
        "object": campaign,
        "is_edit": True,
    }
    return render(request, "ecommerce/mobile/mobile_push_campaign/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def mobilepushcampaign_delete(request, pk):
    campaign = ecommerce_object(request, MobilePushCampaign, pk)
    number = campaign.number
    name = campaign.campaign_name
    write_audit_log(
        request=request,
        action="DELETE",
        instance=campaign,
        message=f"Deleted MobilePushCampaign {number} ({name})",
    )
    campaign.delete()
    messages.success(request, f"Campaign '{name}' ({number}) deleted.")
    return redirect("ecommerce:mobilepushcampaign_list")


@login_required
@tenant_admin_required
@require_POST
def mobilepushcampaign_test_send(request, pk):
    """Simulate push notification dispatch to all eligible registered devices."""
    campaign = ecommerce_object(request, MobilePushCampaign, pk)
    device_qs = ecommerce_scope(MobileDeviceRegistration.objects.filter(is_active=True, push_enabled=True), request)
    if campaign.target_platform == "ios_only":
        device_qs = device_qs.filter(device_platform="ios")
    elif campaign.target_platform == "android_only":
        device_qs = device_qs.filter(device_platform="android")
    elif campaign.target_platform == "pwa_only":
        device_qs = device_qs.filter(device_platform="pwa_web")

    count = max(1, device_qs.count())
    campaign.dispatch_simulation(device_count=count)
    write_audit_log(
        request=request,
        action="SEND",
        instance=campaign,
        message=f"Dispatched push campaign {campaign.number} to {count} devices",
    )
    messages.success(request, f"Campaign '{campaign.campaign_name}' dispatched to {count} registered devices.")
    return redirect("ecommerce:mobilepushcampaign_detail", pk=campaign.pk)
