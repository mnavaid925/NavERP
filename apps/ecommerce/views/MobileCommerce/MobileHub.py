from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.ecommerce.models.MobileCommerce.MobileAppConfigs import MobileAppConfig
from apps.ecommerce.models.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistration
from apps.ecommerce.models.MobileCommerce.MobileLocationRules import MobileLocationRule
from apps.ecommerce.models.MobileCommerce.MobilePushCampaigns import MobilePushCampaign
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def mobile_hub(request):
    """Central command cockpit for Mobile Commerce operations."""
    app_config = ecommerce_scope(
        MobileAppConfig.objects.filter(is_active=True), request
    ).first()

    devices_qs = ecommerce_scope(MobileDeviceRegistration.objects.all(), request)
    devices_agg = devices_qs.aggregate(
        total=Count("id"),
        ios=Count("id", filter=Q(device_platform="ios")),
        android=Count("id", filter=Q(device_platform="android")),
        pwa=Count("id", filter=Q(device_platform="pwa_web")),
    )
    total_devices = devices_agg["total"] or 0
    ios_devices = devices_agg["ios"] or 0
    android_devices = devices_agg["android"] or 0
    pwa_devices = devices_agg["pwa"] or 0

    campaigns_qs = ecommerce_scope(MobilePushCampaign.objects.all(), request)
    campaigns_agg = campaigns_qs.aggregate(
        active=Count("id", filter=Q(status__in=["scheduled", "sending", "sent"])),
        total_sent=Sum("sent_count"),
        total_opened=Sum("opened_count"),
        total_rev=Sum("converted_revenue"),
    )
    active_campaigns = campaigns_agg["active"] or 0
    total_push_sent = campaigns_agg["total_sent"] or 0
    total_push_opened = campaigns_agg["total_opened"] or 0
    total_push_revenue = campaigns_agg["total_rev"] or 0

    locations_qs = ecommerce_scope(MobileLocationRule.objects.all(), request)
    active_geofences = locations_qs.filter(is_active=True).count()

    recent_devices = devices_qs.select_related("customer_profile", "party")[:5]
    recent_campaigns = campaigns_qs[:5]
    recent_locations = locations_qs[:5]

    context = {
        "app_config": app_config,
        "total_devices": total_devices,
        "ios_devices": ios_devices,
        "android_devices": android_devices,
        "pwa_devices": pwa_devices,
        "active_campaigns": active_campaigns,
        "total_push_sent": total_push_sent,
        "total_push_opened": total_push_opened,
        "total_push_revenue": total_push_revenue,
        "active_geofences": active_geofences,
        "pwa_enabled": app_config.enable_pwa if app_config else False,
        "apple_pay_enabled": app_config.enable_apple_pay if app_config else False,
        "google_pay_enabled": app_config.enable_google_pay if app_config else False,
        "recent_devices": recent_devices,
        "recent_campaigns": recent_campaigns,
        "recent_locations": recent_locations,
    }
    return render(request, "ecommerce/mobile/mobile_hub.html", context)
