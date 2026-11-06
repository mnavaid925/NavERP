from django.urls import path

from apps.bi.views.OperationalReporting import ReportParameters as views

urlpatterns = [
    path("report-parameters/", views.report_parameter_list, name="report_parameter_list"),
    path("report-parameters/create/", views.report_parameter_create, name="report_parameter_create"),
    path("report-parameters/<int:pk>/", views.report_parameter_detail, name="report_parameter_detail"),
    path("report-parameters/<int:pk>/edit/", views.report_parameter_edit, name="report_parameter_edit"),
    path("report-parameters/<int:pk>/delete/", views.report_parameter_delete, name="report_parameter_delete"),
]
