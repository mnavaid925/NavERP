from apps.quality.urls.AuditManagement.AuditActionTracker import (
    urlpatterns as action_tracker_urls,
)
from apps.quality.urls.AuditManagement.AuditFindings import (
    urlpatterns as findings_urls,
)
from apps.quality.urls.AuditManagement.AuditPrograms import (
    urlpatterns as programs_urls,
)
from apps.quality.urls.AuditManagement.AuditWarRoom import (
    urlpatterns as war_room_urls,
)
from apps.quality.urls.AuditManagement.QualityAudits import (
    urlpatterns as audits_urls,
)
from apps.quality.urls.AuditManagement.RegulatoryInspectionHosts import (
    urlpatterns as inspections_urls,
)

urlpatterns = (
    programs_urls
    + audits_urls
    + findings_urls
    + inspections_urls
    + action_tracker_urls
    + war_room_urls
)
