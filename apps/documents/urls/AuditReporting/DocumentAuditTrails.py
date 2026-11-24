from django.urls import path

from apps.documents.views.AuditReporting.DocumentAuditTrails import (
    audit_trail_detail,
    audit_trail_export_csv,
    audit_trail_list,
    audit_trail_verify_chain,
)

urlpatterns = [
    path("audit-trails/", audit_trail_list, name="audit_trail_list"),
    path("audit-trails/verify-chain/", audit_trail_verify_chain, name="audit_trail_verify_chain"),
    path("audit-trails/export-csv/", audit_trail_export_csv, name="audit_trail_export_csv"),
    path("audit-trails/<int:pk>/", audit_trail_detail, name="audit_trail_detail"),
]
