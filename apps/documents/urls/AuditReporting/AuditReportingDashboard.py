from django.urls import path

from apps.documents.views.AuditReporting.AuditReportingDashboard import (
    audit_dashboard,
    document_lifecycle_dashboard,
)

urlpatterns = [
    path("audit-dashboard/", audit_dashboard, name="audit_dashboard"),
    path("lifecycle-dashboard/", document_lifecycle_dashboard, name="document_lifecycle_dashboard"),
]
