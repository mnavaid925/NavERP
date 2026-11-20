from django.urls import path

from apps.quality.views.CustomerComplaints import RegulatoryReports as views

urlpatterns = [
    path("regulatory-reports/", views.regulatory_report_list, name="regulatory_report_list"),
    path("regulatory-reports/create/", views.regulatory_report_create, name="regulatory_report_create"),
    path("regulatory-reports/export/csv/", views.regulatory_report_export_csv, name="regulatory_report_export_csv"),
    path("regulatory-reports/<int:pk>/", views.regulatory_report_detail, name="regulatory_report_detail"),
    path("regulatory-reports/<int:pk>/edit/", views.regulatory_report_edit, name="regulatory_report_edit"),
    path("regulatory-reports/<int:pk>/delete/", views.regulatory_report_delete, name="regulatory_report_delete"),
    path("regulatory-reports/<int:pk>/submit/", views.regulatory_report_submit, name="regulatory_report_submit"),
    path("regulatory-reports/<int:pk>/acknowledge/", views.regulatory_report_acknowledge, name="regulatory_report_acknowledge"),
]
