from django.urls import path

from apps.quality.views.CalibrationAnalysis import MeasurementSystemAnalyses as views

urlpatterns = [
    path("msa/", views.measurement_system_analysis_list, name="measurement_system_analysis_list"),
    path("msa/create/", views.measurement_system_analysis_create, name="measurement_system_analysis_create"),
    path("msa/export/", views.measurement_system_analysis_export_csv, name="measurement_system_analysis_export_csv"),
    path("msa/<int:pk>/", views.measurement_system_analysis_detail, name="measurement_system_analysis_detail"),
    path("msa/<int:pk>/edit/", views.measurement_system_analysis_edit, name="measurement_system_analysis_edit"),
    path("msa/<int:pk>/delete/", views.measurement_system_analysis_delete, name="measurement_system_analysis_delete"),
]
