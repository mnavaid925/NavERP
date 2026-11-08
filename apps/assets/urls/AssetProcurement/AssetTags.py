from django.urls import path

from apps.assets.views.AssetProcurement.AssetTags import (
    asset_tag_affix,
    asset_tag_create,
    asset_tag_delete,
    asset_tag_detail,
    asset_tag_edit,
    asset_tag_list,
    asset_tag_mark_printed,
    asset_tag_print_label,
    asset_tag_verify,
)

urlpatterns = [
    path("tags/", asset_tag_list, name="asset_tag_list"),
    path("tags/create/", asset_tag_create, name="asset_tag_create"),
    path("tags/<int:pk>/", asset_tag_detail, name="asset_tag_detail"),
    path("tags/<int:pk>/edit/", asset_tag_edit, name="asset_tag_edit"),
    path("tags/<int:pk>/delete/", asset_tag_delete, name="asset_tag_delete"),
    path("tags/<int:pk>/mark-printed/", asset_tag_mark_printed, name="asset_tag_mark_printed"),
    path("tags/<int:pk>/affix/", asset_tag_affix, name="asset_tag_affix"),
    path("tags/<int:pk>/verify/", asset_tag_verify, name="asset_tag_verify"),
    path("tags/<int:pk>/print/", asset_tag_print_label, name="asset_tag_print_label"),
]
