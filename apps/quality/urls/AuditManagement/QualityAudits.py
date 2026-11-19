from django.urls import path

from apps.quality.views.AuditManagement.QualityAudits import (
    quality_audit_close,
    quality_audit_create,
    quality_audit_delete,
    quality_audit_detail,
    quality_audit_edit,
    quality_audit_export_csv,
    quality_audit_list,
    quality_audit_publish_report,
)

urlpatterns = [
    path("audits/records/", quality_audit_list, name="quality_audit_list"),
    path("audits/records/create/", quality_audit_create, name="quality_audit_create"),
    path("audits/records/export/", quality_audit_export_csv, name="quality_audit_export_csv"),
    path("audits/records/<int:pk>/", quality_audit_detail, name="quality_audit_detail"),
    path("audits/records/<int:pk>/edit/", quality_audit_edit, name="quality_audit_edit"),
    path("audits/records/<int:pk>/delete/", quality_audit_delete, name="quality_audit_delete"),
    path("audits/records/<int:pk>/publish/", quality_audit_publish_report, name="quality_audit_publish_report"),
    path("audits/records/<int:pk>/close/", quality_audit_close, name="quality_audit_close"),
]
