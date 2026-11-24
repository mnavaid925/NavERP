from django.urls import path

from apps.documents.views.AuditReporting.ChainOfCustodyExports import (
    auditor_portal_verify,
    auditor_portal_view,
    custody_export_certificate,
    custody_export_create,
    custody_export_detail,
    custody_export_list,
    custody_export_revoke,
)

urlpatterns = [
    path("custody-exports/", custody_export_list, name="custody_export_list"),
    path("custody-exports/create/", custody_export_create, name="custody_export_create"),
    path("custody-exports/<int:pk>/", custody_export_detail, name="custody_export_detail"),
    path("custody-exports/<int:pk>/certificate/", custody_export_certificate, name="custody_export_certificate"),
    path("custody-exports/<int:pk>/revoke/", custody_export_revoke, name="custody_export_revoke"),
    path("auditor-portal/<str:token>/", auditor_portal_view, name="auditor_portal_view"),
    path("auditor-portal/<str:token>/verify/", auditor_portal_verify, name="auditor_portal_verify"),
]
