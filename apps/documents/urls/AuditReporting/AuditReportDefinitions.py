from django.urls import path

from apps.documents.views.AuditReporting.AuditReportDefinitions import (
    audit_report_create,
    audit_report_delete,
    audit_report_detail,
    audit_report_edit,
    audit_report_list,
    audit_report_run,
)

urlpatterns = [
    path("audit-reports/", audit_report_list, name="audit_report_list"),
    path("audit-reports/create/", audit_report_create, name="audit_report_create"),
    path("audit-reports/<int:pk>/", audit_report_detail, name="audit_report_detail"),
    path("audit-reports/<int:pk>/edit/", audit_report_edit, name="audit_report_edit"),
    path("audit-reports/<int:pk>/delete/", audit_report_delete, name="audit_report_delete"),
    path("audit-reports/<int:pk>/run/", audit_report_run, name="audit_report_run"),
]
