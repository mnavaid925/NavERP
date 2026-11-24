from django.urls import path

from apps.documents.views.AuditReporting.DocumentSecurityAlerts import (
    security_alert_detail,
    security_alert_list,
    security_alert_scan,
    security_alert_triage,
)

urlpatterns = [
    path("security-alerts/", security_alert_list, name="security_alert_list"),
    path("security-alerts/scan/", security_alert_scan, name="security_alert_scan"),
    path("security-alerts/<int:pk>/", security_alert_detail, name="security_alert_detail"),
    path("security-alerts/<int:pk>/triage/", security_alert_triage, name="security_alert_triage"),
]
