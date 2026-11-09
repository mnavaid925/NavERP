from django.urls import path

from apps.assets.views.AssetReliability import AssetCalibrationRecords as views

urlpatterns = [
    path("reliability/calibrations/", views.asset_calibration_record_list, name="asset_calibration_record_list"),
    path("reliability/calibrations/create/", views.asset_calibration_record_create, name="asset_calibration_record_create"),
    path("reliability/calibrations/<int:pk>/", views.asset_calibration_record_detail, name="asset_calibration_record_detail"),
    path("reliability/calibrations/<int:pk>/edit/", views.asset_calibration_record_edit, name="asset_calibration_record_edit"),
    path("reliability/calibrations/<int:pk>/delete/", views.asset_calibration_record_delete, name="asset_calibration_record_delete"),
    path("reliability/calibrations/<int:pk>/quarantine/", views.asset_calibration_record_quarantine, name="asset_calibration_record_quarantine"),
]
