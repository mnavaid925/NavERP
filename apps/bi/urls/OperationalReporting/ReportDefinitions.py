from django.urls import path

from apps.bi.views.OperationalReporting import ReportDefinitions as views

urlpatterns = [
    path("reports/", views.report_definition_list, name="report_definition_list"),
    path("reports/create/", views.report_definition_create, name="report_definition_create"),
    path("reports/<int:pk>/", views.report_definition_detail, name="report_definition_detail"),
    path("reports/<int:pk>/edit/", views.report_definition_edit, name="report_definition_edit"),
    path("reports/<int:pk>/delete/", views.report_definition_delete, name="report_definition_delete"),
    path("reports/<int:pk>/clone/", views.report_definition_clone, name="report_definition_clone"),
    path("reports/<int:pk>/view/", views.report_definition_viewer, name="report_definition_viewer"),
    path("reports/<int:pk>/print/", views.report_definition_print, name="report_definition_print"),
]
