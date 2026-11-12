"""URL patterns for Cloud Assets & SaaS Subscriptions (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement.CloudAssetSubscriptions import (
    cloud_asset_subscription_create,
    cloud_asset_subscription_decommission,
    cloud_asset_subscription_delete,
    cloud_asset_subscription_detail,
    cloud_asset_subscription_edit,
    cloud_asset_subscription_export_csv,
    cloud_asset_subscription_flag_shadow,
    cloud_asset_subscription_list,
    cloud_asset_subscription_renew,
    cloud_asset_subscription_sanction,
    cloud_asset_subscription_suspend,
    cloud_asset_subscription_sync_finops,
)

urlpatterns = [
    path("cloud-assets/", cloud_asset_subscription_list, name="cloud_asset_subscription_list"),
    path("cloud-assets/create/", cloud_asset_subscription_create, name="cloud_asset_subscription_create"),
    path("cloud-assets/export-csv/", cloud_asset_subscription_export_csv, name="cloud_asset_subscription_export_csv"),
    path("cloud-assets/<int:pk>/", cloud_asset_subscription_detail, name="cloud_asset_subscription_detail"),
    path("cloud-assets/<int:pk>/edit/", cloud_asset_subscription_edit, name="cloud_asset_subscription_edit"),
    path("cloud-assets/<int:pk>/delete/", cloud_asset_subscription_delete, name="cloud_asset_subscription_delete"),
    path("cloud-assets/<int:pk>/sanction/", cloud_asset_subscription_sanction, name="cloud_asset_subscription_sanction"),
    path("cloud-assets/<int:pk>/flag-shadow/", cloud_asset_subscription_flag_shadow, name="cloud_asset_subscription_flag_shadow"),
    path("cloud-assets/<int:pk>/sync-finops/", cloud_asset_subscription_sync_finops, name="cloud_asset_subscription_sync_finops"),
    path("cloud-assets/<int:pk>/renew/", cloud_asset_subscription_renew, name="cloud_asset_subscription_renew"),
    path("cloud-assets/<int:pk>/suspend/", cloud_asset_subscription_suspend, name="cloud_asset_subscription_suspend"),
    path("cloud-assets/<int:pk>/decommission/", cloud_asset_subscription_decommission, name="cloud_asset_subscription_decommission"),
]
