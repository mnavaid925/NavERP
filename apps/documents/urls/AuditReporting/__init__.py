from apps.documents.urls.AuditReporting.AuditReportDefinitions import (
    urlpatterns as audit_report_patterns,
)
from apps.documents.urls.AuditReporting.AuditReportingDashboard import (
    urlpatterns as dashboard_patterns,
)
from apps.documents.urls.AuditReporting.ChainOfCustodyExports import (
    urlpatterns as custody_patterns,
)
from apps.documents.urls.AuditReporting.DocumentAuditTrails import (
    urlpatterns as audit_trail_patterns,
)
from apps.documents.urls.AuditReporting.DocumentSecurityAlerts import (
    urlpatterns as security_alert_patterns,
)

urlpatterns = (
    audit_trail_patterns
    + audit_report_patterns
    + security_alert_patterns
    + custody_patterns
    + dashboard_patterns
)
