from django.urls import path

from apps.quality.views.CalibrationAnalysis import CalibrationRecords as views

urlpatterns = [
    path("calibration-record/", views.calibration_record_list, name="calibration_record_list"),
    path("calibration-record/create/", views.calibration_record_create, name="calibration_record_create"),
    path("calibration-record/export/", views.calibration_record_export_csv, name="calibration_record_export_csv"),
    path("calibration-record/<int:pk>/", views.calibration_record_detail, name="calibration_record_detail"),
    path("calibration-record/<int:pk>/edit/", views.calibration_record_edit, name="calibration_record_edit"),
    path("calibration-record/<int:pk>/delete/", views.calibration_record_delete, name="calibration_record_delete"),
]
