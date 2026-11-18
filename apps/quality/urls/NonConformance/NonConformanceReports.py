from django.urls import path

from apps.quality.views.NonConformance import NonConformanceReports as views

urlpatterns = [
    path("ncrs/", views.non_conformance_report_list, name="non_conformance_report_list"),
    path("ncrs/create/", views.non_conformance_report_create, name="non_conformance_report_create"),
    path("ncrs/export/csv/", views.non_conformance_report_export_csv, name="non_conformance_report_export_csv"),
    path("ncrs/<int:pk>/", views.non_conformance_report_detail, name="non_conformance_report_detail"),
    path("ncrs/<int:pk>/edit/", views.non_conformance_report_edit, name="non_conformance_report_edit"),
    path("ncrs/<int:pk>/delete/", views.non_conformance_report_delete, name="non_conformance_report_delete"),
]
