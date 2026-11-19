from django.urls import path

from apps.quality.views.CalibrationAnalysis import OutOfToleranceInvestigations as views

urlpatterns = [
    path("oot-investigation/", views.out_of_tolerance_investigation_list, name="out_of_tolerance_investigation_list"),
    path("oot-investigation/create/", views.out_of_tolerance_investigation_create, name="out_of_tolerance_investigation_create"),
    path("oot-investigation/export/", views.out_of_tolerance_investigation_export_csv, name="out_of_tolerance_investigation_export_csv"),
    path("oot-investigation/<int:pk>/", views.out_of_tolerance_investigation_detail, name="out_of_tolerance_investigation_detail"),
    path("oot-investigation/<int:pk>/edit/", views.out_of_tolerance_investigation_edit, name="out_of_tolerance_investigation_edit"),
    path("oot-investigation/<int:pk>/delete/", views.out_of_tolerance_investigation_delete, name="out_of_tolerance_investigation_delete"),
]
