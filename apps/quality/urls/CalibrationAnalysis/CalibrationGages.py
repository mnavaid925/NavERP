from django.urls import path

from apps.quality.views.CalibrationAnalysis import CalibrationGages as views

urlpatterns = [
    path("gage/", views.calibration_gage_list, name="calibration_gage_list"),
    path("gage/create/", views.calibration_gage_create, name="calibration_gage_create"),
    path("gage/export/", views.calibration_gage_export_csv, name="calibration_gage_export_csv"),
    path("gage/<int:pk>/", views.calibration_gage_detail, name="calibration_gage_detail"),
    path("gage/<int:pk>/edit/", views.calibration_gage_edit, name="calibration_gage_edit"),
    path("gage/<int:pk>/delete/", views.calibration_gage_delete, name="calibration_gage_delete"),
]
