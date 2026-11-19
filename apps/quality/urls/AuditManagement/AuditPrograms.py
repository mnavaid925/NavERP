from django.urls import path

from apps.quality.views.AuditManagement.AuditPrograms import (
    audit_program_approve,
    audit_program_create,
    audit_program_delete,
    audit_program_detail,
    audit_program_edit,
    audit_program_export_csv,
    audit_program_list,
)

urlpatterns = [
    path("audits/programs/", audit_program_list, name="audit_program_list"),
    path("audits/programs/create/", audit_program_create, name="audit_program_create"),
    path("audits/programs/export/", audit_program_export_csv, name="audit_program_export_csv"),
    path("audits/programs/<int:pk>/", audit_program_detail, name="audit_program_detail"),
    path("audits/programs/<int:pk>/edit/", audit_program_edit, name="audit_program_edit"),
    path("audits/programs/<int:pk>/delete/", audit_program_delete, name="audit_program_delete"),
    path("audits/programs/<int:pk>/approve/", audit_program_approve, name="audit_program_approve"),
]
