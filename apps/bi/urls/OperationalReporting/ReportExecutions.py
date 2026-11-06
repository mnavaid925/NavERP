from django.urls import path

from apps.bi.views.OperationalReporting import ReportExecutions as views

urlpatterns = [
    path("report-executions/", views.report_execution_list, name="report_execution_list"),
    path("report-executions/run/<int:report_pk>/", views.report_execution_run, name="report_execution_run"),
    path("report-executions/<int:pk>/", views.report_execution_detail, name="report_execution_detail"),
    path("report-executions/<int:pk>/delete/", views.report_execution_delete, name="report_execution_delete"),
    path("report-executions/<int:pk>/export/<str:export_format>/", views.report_execution_export, name="report_execution_export"),
]
