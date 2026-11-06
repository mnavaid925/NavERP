from django.urls import path

from apps.bi.views.OperationalReporting import ReportDrillPaths as views

urlpatterns = [
    path("report-drill-paths/", views.report_drill_path_list, name="report_drill_path_list"),
    path("report-drill-paths/create/", views.report_drill_path_create, name="report_drill_path_create"),
    path("report-drill-paths/<int:pk>/", views.report_drill_path_detail, name="report_drill_path_detail"),
    path("report-drill-paths/<int:pk>/edit/", views.report_drill_path_edit, name="report_drill_path_edit"),
    path("report-drill-paths/<int:pk>/delete/", views.report_drill_path_delete, name="report_drill_path_delete"),
]
