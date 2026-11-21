from apps.quality.urls.EhsManagement.EhsDashboard import (
    urlpatterns as ehs_dashboard_urls,
)
from apps.quality.urls.EhsManagement.EnvironmentalMonitoringLogs import (
    urlpatterns as environmental_monitoring_logs_urls,
)
from apps.quality.urls.EhsManagement.HazardousMaterials import (
    urlpatterns as hazardous_materials_urls,
)
from apps.quality.urls.EhsManagement.SafetyIncidents import (
    urlpatterns as safety_incidents_urls,
)
from apps.quality.urls.EhsManagement.WasteDisposalManifests import (
    urlpatterns as waste_disposal_manifests_urls,
)

urlpatterns = (
    ehs_dashboard_urls
    + hazardous_materials_urls
    + safety_incidents_urls
    + environmental_monitoring_logs_urls
    + waste_disposal_manifests_urls
)
