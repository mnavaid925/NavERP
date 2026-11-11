from django.urls import path

from apps.assets.views.MobileAssetManagement import MobileAssetInspections as views

urlpatterns = [
    path("mobile/inspections/", views.mobile_asset_inspection_list, name="mobile_asset_inspection_list"),
    path("mobile/inspections/create/", views.mobile_asset_inspection_create, name="mobile_asset_inspection_create"),
    path("mobile/inspections/<int:pk>/", views.mobile_asset_inspection_detail, name="mobile_asset_inspection_detail"),
    path("mobile/inspections/<int:pk>/edit/", views.mobile_asset_inspection_edit, name="mobile_asset_inspection_edit"),
    path("mobile/inspections/<int:pk>/delete/", views.mobile_asset_inspection_delete, name="mobile_asset_inspection_delete"),
]
