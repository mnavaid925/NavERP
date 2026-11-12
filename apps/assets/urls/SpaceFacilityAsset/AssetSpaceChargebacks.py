"""URL patterns for Tenant & Occupancy Coordination / Space Chargebacks (11.17)."""

from django.urls import path

from apps.assets.views.SpaceFacilityAsset import AssetSpaceChargebacks as views

urlpatterns = [
    path(
        "space-chargebacks/",
        views.asset_space_chargeback_list,
        name="asset_space_chargeback_list",
    ),
    path(
        "space-chargebacks/create/",
        views.asset_space_chargeback_create,
        name="asset_space_chargeback_create",
    ),
    path(
        "space-chargebacks/export-csv/",
        views.asset_space_chargeback_export_csv,
        name="asset_space_chargeback_export_csv",
    ),
    path(
        "space-chargebacks/<int:pk>/",
        views.asset_space_chargeback_detail,
        name="asset_space_chargeback_detail",
    ),
    path(
        "space-chargebacks/<int:pk>/edit/",
        views.asset_space_chargeback_edit,
        name="asset_space_chargeback_edit",
    ),
    path(
        "space-chargebacks/<int:pk>/delete/",
        views.asset_space_chargeback_delete,
        name="asset_space_chargeback_delete",
    ),
    path(
        "space-chargebacks/<int:pk>/submit-approval/",
        views.asset_space_chargeback_submit_approval,
        name="asset_space_chargeback_submit_approval",
    ),
    path(
        "space-chargebacks/<int:pk>/approve/",
        views.asset_space_chargeback_approve,
        name="asset_space_chargeback_approve",
    ),
    path(
        "space-chargebacks/<int:pk>/post-gl/",
        views.asset_space_chargeback_post_gl,
        name="asset_space_chargeback_post_gl",
    ),
    path(
        "space-chargebacks/<int:pk>/dispute/",
        views.asset_space_chargeback_dispute,
        name="asset_space_chargeback_dispute",
    ),
    path(
        "space-chargebacks/<int:pk>/close/",
        views.asset_space_chargeback_close,
        name="asset_space_chargeback_close",
    ),
]
