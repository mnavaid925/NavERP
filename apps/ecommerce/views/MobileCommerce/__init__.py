from apps.ecommerce.views.MobileCommerce.MobileAppConfigs import (
    mobileappconfig_create,
    mobileappconfig_delete,
    mobileappconfig_detail,
    mobileappconfig_edit,
    mobileappconfig_list,
    pwa_manifest_json,
)
from apps.ecommerce.views.MobileCommerce.MobileDeviceRegistrations import (
    mobiledeviceregistration_create,
    mobiledeviceregistration_delete,
    mobiledeviceregistration_detail,
    mobiledeviceregistration_edit,
    mobiledeviceregistration_list,
    mobiledeviceregistration_ping,
)
from apps.ecommerce.views.MobileCommerce.MobileHub import mobile_hub
from apps.ecommerce.views.MobileCommerce.MobileLocationRules import (
    mobilelocationrule_create,
    mobilelocationrule_delete,
    mobilelocationrule_detail,
    mobilelocationrule_edit,
    mobilelocationrule_list,
    mobilelocationrule_simulate,
)
from apps.ecommerce.views.MobileCommerce.MobilePushCampaigns import (
    mobilepushcampaign_create,
    mobilepushcampaign_delete,
    mobilepushcampaign_detail,
    mobilepushcampaign_edit,
    mobilepushcampaign_list,
    mobilepushcampaign_test_send,
)

__all__ = [
    "mobileappconfig_list",
    "mobileappconfig_detail",
    "mobileappconfig_create",
    "mobileappconfig_edit",
    "mobileappconfig_delete",
    "pwa_manifest_json",
    "mobiledeviceregistration_list",
    "mobiledeviceregistration_detail",
    "mobiledeviceregistration_create",
    "mobiledeviceregistration_edit",
    "mobiledeviceregistration_delete",
    "mobiledeviceregistration_ping",
    "mobilepushcampaign_list",
    "mobilepushcampaign_detail",
    "mobilepushcampaign_create",
    "mobilepushcampaign_edit",
    "mobilepushcampaign_delete",
    "mobilepushcampaign_test_send",
    "mobilelocationrule_list",
    "mobilelocationrule_detail",
    "mobilelocationrule_create",
    "mobilelocationrule_edit",
    "mobilelocationrule_delete",
    "mobilelocationrule_simulate",
    "mobile_hub",
]
