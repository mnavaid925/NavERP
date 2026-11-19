from django.urls import path

from apps.quality.views.CalibrationAnalysis import CalibrationVendors as views

urlpatterns = [
    path("calibration-vendors/", views.calibration_vendor_directory, name="calibration_vendor_directory"),
]
