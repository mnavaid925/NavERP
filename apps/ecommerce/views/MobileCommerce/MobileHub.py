from django.contrib.auth.decorators import login_required
from django.db.models import Sum
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
    total_devices = devices_qs.count()
    ios_devices = devices_qs.filter(device_platform="ios").count()
    android_devices = devices_qs.filter(device_platform="android").count()
    pwa_devices = devices_qs.filter(device_platform="pwa_web").count()

    campaigns_qs = ecommerce_scope(MobilePushCampaign.objects.all(), request)
    active_campaigns = campaigns_qs.filter(status__in=["scheduled", "sending", "sent"]).count()
    push_aggregates = campaigns_qs.aggregate(
        total_sent=Sum("sent_count"),
        total_opened=Sum("opened_count"),
        total_rev=Sum("converted_revenue"),
    )
    total_push_sent = push_aggregates["total_sent"] or 0
    total_push_opened = push_aggregates["total_opened"] or 0
    total_push_revenue = push_aggregates["total_rev"] or 0

    locations_qs = ecommerce_scope(MobileLocationRule.objects.all(), request)
    active_geofences = locations_qs.filter(is_active=True).count()

    recent_devices = devices_qs.select_related("customer_profile", "party")[:5]
    recent_campaigns = campaigns_qs[:5]
    recent_locations = locations_qs.select_related("fulfillment_center", "linked_promotion")[:5]

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
