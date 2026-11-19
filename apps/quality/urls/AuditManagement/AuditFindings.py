from django.urls import path

from apps.quality.views.AuditManagement.AuditFindings import (
    audit_finding_create,
    audit_finding_create_capa,
    audit_finding_delete,
    audit_finding_detail,
    audit_finding_edit,
    audit_finding_export_csv,
    audit_finding_list,
    audit_finding_submit_response,
    audit_finding_verify_close,
)

urlpatterns = [
    path("audits/findings/", audit_finding_list, name="audit_finding_list"),
    path("audits/findings/create/", audit_finding_create, name="audit_finding_create"),
    path("audits/findings/export/", audit_finding_export_csv, name="audit_finding_export_csv"),
    path("audits/findings/<int:pk>/", audit_finding_detail, name="audit_finding_detail"),
    path("audits/findings/<int:pk>/edit/", audit_finding_edit, name="audit_finding_edit"),
    path("audits/findings/<int:pk>/delete/", audit_finding_delete, name="audit_finding_delete"),
    path("audits/findings/<int:pk>/respond/", audit_finding_submit_response, name="audit_finding_submit_response"),
    path("audits/findings/<int:pk>/verify/", audit_finding_verify_close, name="audit_finding_verify_close"),
    path("audits/findings/<int:pk>/create-capa/", audit_finding_create_capa, name="audit_finding_create_capa"),
]
